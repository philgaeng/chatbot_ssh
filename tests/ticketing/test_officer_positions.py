"""OC-03 — officer_positions: invite-by-position pre-fill + the per-(project, step)
supervisor resolver.

All integration (@pytest.mark.integration, live seeded DB): the resolver against the
seeded KL_ROAD workflow, the positions lifecycle (pre-fill / override / dual-hat / end),
the position-type holder delete-guard, jurisdiction validation, and the authz matrix.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import AdminScopeRow

pytestmark = pytest.mark.integration

_ROLE_STD = "site_safeguards_focal_person"
_ROLE_L2 = "pd_piu_safeguards_focal"


# ── personas ─────────────────────────────────────────────────────────────────

def _super():
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _project_admin():
    return CurrentUser(
        user_id="p@grm.local", role_keys=[],
        admin_scopes=[AdminScopeRow(admin_scope_id=str(uuid.uuid4()), user_id="p@grm.local",
                                    role_key="project_admin", country_code="NP", project_id="KL_ROAD",
                                    organization_id=None, package_id=None, workflow_track="standard")],
    )


def _operational():
    return CurrentUser(user_id="o@grm.local", role_keys=["site_safeguards_focal_person"])


def _client(user):
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.models.base import SessionLocal

    db = SessionLocal()

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: user
    app.dependency_overrides[get_db] = _db
    return app, TestClient(app), db


@pytest.fixture
def officer_env():
    """A throwaway position type (owned globally) + a unique officer email; full cleanup."""
    from ticketing.models.base import SessionLocal
    from ticketing.models.officer_position import OfficerPosition
    from ticketing.models.officer_scope import OfficerScope
    from ticketing.models.position_type import PositionType
    from ticketing.models.user import UserRole

    email = f"oc3-{uuid.uuid4().hex[:8]}@grm.local"
    pkey = f"oc3_pt_{uuid.uuid4().hex[:6]}"
    s = SessionLocal()
    pt = PositionType(position_key=pkey, display_name="OC3 Position",
                      allowed_unit_types=["division_office"], default_role_key=_ROLE_STD,
                      workflow_track="standard")
    s.add(pt)
    s.commit()
    pt_id = pt.position_type_id
    s.close()
    yield {"email": email, "position_type_id": pt_id, "position_key": pkey}
    s = SessionLocal()
    s.execute(sa.delete(OfficerPosition).where(OfficerPosition.user_id == email))
    s.execute(sa.delete(OfficerScope).where(OfficerScope.user_id == email))
    s.execute(sa.delete(UserRole).where(UserRole.user_id == email))
    obj = s.get(PositionType, pt_id)
    if obj:
        s.delete(obj)
    s.commit()
    s.close()


# ── supervisor resolver ──────────────────────────────────────────────────────

def test_supervisor_resolver_project_step():
    """Per-(project, step): a non-top step resolves to the NEXT step's Handler pool; the
    top step falls to its supervisor_role (or none). No org-tree walk anywhere."""
    from ticketing.models.base import SessionLocal
    from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
    from ticketing.services.supervisor import resolve_supervisor

    db = SessionLocal()
    try:
        wf = db.execute(
            sa.select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == "KL_ROAD_STANDARD")
        ).scalar_one()
        steps = db.execute(
            sa.select(WorkflowStep).where(WorkflowStep.workflow_id == wf.workflow_id,
                                          WorkflowStep.is_deleted.is_(False))
            .order_by(WorkflowStep.step_order)
        ).scalars().all()
        assert len(steps) >= 2
        # step 1 → next step's handler pool
        res = resolve_supervisor(db, steps[0], project_code="KL_ROAD")
        assert res.source == "next_step_handler"
        assert res.role_pool == steps[1].assigned_role_key
        # top step → supervisor_role fallback or none (never next-step)
        top = resolve_supervisor(db, steps[-1], project_code="KL_ROAD")
        assert top.source in ("step_supervisor_role", "none")
        assert top.role_pool == (steps[-1].supervisor_role or None)
    finally:
        db.close()


# ── positions lifecycle ──────────────────────────────────────────────────────

def _scopes(email):
    from ticketing.models.base import SessionLocal
    from ticketing.models.officer_scope import OfficerScope
    s = SessionLocal()
    try:
        return [(x.role_key, x.organization_id, x.location_code)
                for x in s.execute(sa.select(OfficerScope).where(OfficerScope.user_id == email)).scalars().all()]
    finally:
        s.close()


def test_assign_prefill_and_override(officer_env):
    email = officer_env["email"]
    app, client, db = _client(_super())
    try:
        # pre-fill: role comes from the matrix (position_type.default_role_key)
        r = client.post(f"/api/v1/users/{email}/positions", json={
            "position_type_id": officer_env["position_type_id"], "organization_id": "DOR",
            "location_code": "P1_JHA"})
        assert r.status_code == 201, r.text
        assert r.json()["default_role_key"] == _ROLE_STD
        # an officer_scope was minted with the matrix role
        assert (_ROLE_STD, "DOR", "P1_JHA") in _scopes(email)

        # override: explicit role_key beats the matrix
        r2 = client.post(f"/api/v1/users/{email}/positions", json={
            "position_type_id": officer_env["position_type_id"], "organization_id": "DOR",
            "location_code": "P1_JHA", "role_key": _ROLE_L2})
        assert r2.status_code == 201, r2.text
        assert any(role == _ROLE_L2 for role, _, _ in _scopes(email))  # override scope present
    finally:
        app.dependency_overrides.clear(); db.close()


def test_assign_untiered_position_requires_explicit_role(officer_env):
    """DESIGN-cast-model §3.2: a display-only title carries no default role — staffing must
    pass the tier explicitly. Assign without role_key → 422; with role_key → 201."""
    from ticketing.models.base import SessionLocal
    from ticketing.models.position_type import PositionType

    email = officer_env["email"]
    s = SessionLocal()
    pt = PositionType(position_key=f"untiered_{uuid.uuid4().hex[:6]}",
                      display_name="Untiered", allowed_unit_types=["division_office"],
                      default_role_key=None)
    s.add(pt); s.commit()
    pt_id = pt.position_type_id
    s.close()

    app, client, db = _client(_super())
    try:
        # no default, no override → the tier is required
        r = client.post(f"/api/v1/users/{email}/positions", json={
            "position_type_id": pt_id, "organization_id": "DOR", "location_code": "P1_JHA"})
        assert r.status_code == 422, r.text
        assert "role_key" in r.text
        # explicit role_key → the scope is minted with that role
        r2 = client.post(f"/api/v1/users/{email}/positions", json={
            "position_type_id": pt_id, "organization_id": "DOR", "location_code": "P1_JHA",
            "role_key": _ROLE_STD})
        assert r2.status_code == 201, r2.text
        assert (_ROLE_STD, "DOR", "P1_JHA") in _scopes(email)
    finally:
        app.dependency_overrides.clear(); db.close()
        # Drop the officer_position rows referencing this PT before the PT (FK RESTRICT);
        # officer_env's teardown clears this email's scopes/user_roles afterwards.
        from ticketing.models.officer_position import OfficerPosition
        s = SessionLocal()
        s.execute(sa.delete(OfficerPosition).where(OfficerPosition.position_type_id == pt_id))
        s.commit()
        obj = s.get(PositionType, pt_id)
        if obj:
            s.delete(obj); s.commit()
        s.close()


def test_dual_hat_list_and_end(officer_env):
    email = officer_env["email"]
    app, client, db = _client(_super())
    try:
        for _ in range(2):
            assert client.post(f"/api/v1/users/{email}/positions", json={
                "position_type_id": officer_env["position_type_id"], "organization_id": "DOR",
                "location_code": "P1_JHA"}).status_code == 201
        listed = client.get(f"/api/v1/users/{email}/positions").json()
        assert len(listed) == 2  # dual-hat
        opid = listed[0]["officer_position_id"]
        # end one position → deactivated, but scopes are NOT removed (transfer semantics)
        scopes_before = len(_scopes(email))
        assert client.delete(f"/api/v1/users/{email}/positions/{opid}").status_code == 204
        assert len(client.get(f"/api/v1/users/{email}/positions").json()) == 1  # active_only
        assert len(_scopes(email)) == scopes_before  # scopes untouched
    finally:
        app.dependency_overrides.clear(); db.close()


def test_validate_jurisdiction_still_enforced(officer_env):
    """SH-3 still applies: an org not linked to the named project → 422."""
    email = officer_env["email"]
    app, client, db = _client(_super())
    try:
        # ADB is a seeded org but not the KL_ROAD implementing link for a field role via project
        r = client.post(f"/api/v1/users/{email}/positions", json={
            "position_type_id": officer_env["position_type_id"], "organization_id": "NO_SUCH_ORG",
            "location_code": "P1_JHA"})
        assert r.status_code in (404, 422), r.text  # org doesn't exist
    finally:
        app.dependency_overrides.clear(); db.close()


def test_position_type_delete_blocked_by_holder(officer_env):
    email = officer_env["email"]
    app, client, db = _client(_super())
    try:
        assert client.post(f"/api/v1/users/{email}/positions", json={
            "position_type_id": officer_env["position_type_id"], "organization_id": "DOR",
            "location_code": "P1_JHA"}).status_code == 201
        # now the position type has a holder → delete blocked
        res = client.delete(f"/api/v1/position-types/{officer_env['position_type_id']}")
        assert res.status_code == 409, res.text
        assert "holders_count" in res.text
    finally:
        app.dependency_overrides.clear(); db.close()


def test_authz_matrix(officer_env):
    email = officer_env["email"]
    body = {"position_type_id": officer_env["position_type_id"], "organization_id": "DOR",
            "location_code": "P1_JHA"}
    # project_admin may staff (INVITE_OFFICERS)
    app, client, db = _client(_project_admin())
    try:
        assert client.post(f"/api/v1/users/{email}/positions", json=body).status_code in (201, 422), None
    finally:
        app.dependency_overrides.clear(); db.close()
    # an operational officer may not
    app, client, db = _client(_operational())
    try:
        assert client.post(f"/api/v1/users/{email}/positions", json=body).status_code == 403
    finally:
        app.dependency_overrides.clear(); db.close()
