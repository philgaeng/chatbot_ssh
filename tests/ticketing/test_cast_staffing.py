"""Per-package cast staffing + synthetic per-step-tier keys (DESIGN-cast-model §3.3, §3.5, §3.6).

Integration (live seeded DB): the tier-toggle step editor mints synthetic keys backed by
plumbing role rows; staffing a (step, tier) slot per package writes officer_scopes through the
sanctioned writer and auto-assign resolves per package; the self-escalation guard holds.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from ticketing.api.dependencies import CurrentUser

pytestmark = pytest.mark.integration

# Seeded fixtures reused (see conftest): DOR is linked to KL_ROAD.
_ORG = "DOR"
_LOC = "P1_JHA"


def _super():
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


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


# ── synthetic-key minting via the tier-toggle step editor ────────────────────

def test_step_toggles_mint_synthetic_keys():
    from ticketing.models.base import SessionLocal
    from ticketing.models.user import Role
    from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

    app, client, db = _client(_super())
    created_wf = None
    try:
        wf = client.post("/api/v1/workflows", json={
            "display_name": "Cast Mint " + uuid.uuid4().hex[:6], "workflow_type": "standard"}).json()
        created_wf = wf["workflow_id"]
        step = client.post(f"/api/v1/workflows/{created_wf}/steps", json={
            "display_name": "Level 1 — Site review",
            "supervisor_enabled": True,
            "participants_enabled": True,
            "observers_enabled": False,
        })
        assert step.status_code == 201, step.text
        body = step.json()
        # Actor always minted; supervisor/participant minted; observer off.
        assert body["assigned_role_key"].startswith("wf:")
        assert body["supervisor_role"].startswith("wf:")
        assert len(body["informed_roles"]) == 1 and body["informed_roles"][0].startswith("wf:")
        assert body["observer_roles"] == []
        # backing plumbing role rows exist, scoped to the workflow track
        s = SessionLocal()
        try:
            role = s.execute(
                sa.select(Role).where(Role.role_key == body["assigned_role_key"])
            ).scalar_one()
            assert role.workflow_scope == "Standard"
            assert role.role_origin == "system"
            assert role.permissions == []
        finally:
            s.close()
    finally:
        app.dependency_overrides.clear()
        db.close()
        if created_wf:
            _cleanup_workflow(created_wf)


def _cleanup_workflow(workflow_id):
    from ticketing.models.base import SessionLocal
    from ticketing.models.user import Role, UserRole
    from ticketing.models.officer_scope import OfficerScope
    from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

    s = SessionLocal()
    try:
        wf = s.get(WorkflowDefinition, workflow_id)
        wf_key = wf.workflow_key if wf else None
        s.execute(sa.delete(WorkflowStep).where(WorkflowStep.workflow_id == workflow_id))
        if wf:
            s.delete(wf)
        if wf_key:
            like = f"wf:{wf_key}:%"
            role_ids = [
                r.role_id for r in s.execute(sa.select(Role).where(Role.role_key.like(like))).scalars().all()
            ]
            if role_ids:
                s.execute(sa.delete(UserRole).where(UserRole.role_id.in_(role_ids)))
                s.execute(sa.delete(Role).where(Role.role_id.in_(role_ids)))
            s.execute(sa.delete(OfficerScope).where(OfficerScope.role_key.like(like)))
        s.commit()
    finally:
        s.close()


# ── per-package staffing + auto-assign + self-escalation ─────────────────────

@pytest.fixture
def cast_env():
    """A throwaway standard workflow with one tier-toggle step (Actor+Supervisor) + two
    packages under KL_ROAD. Full cleanup of scopes/user_roles/roles/steps/packages/workflow."""
    from ticketing.models.base import SessionLocal
    from ticketing.models.package import ProjectPackage
    from ticketing.models.project import Project
    from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
    from ticketing.services.cast_staffing import set_step_tier_keys

    s = SessionLocal()
    proj = s.execute(sa.select(Project).where(Project.short_code == "KL_ROAD")).scalar_one()
    wf_key = f"CAST_{uuid.uuid4().hex[:6].upper()}"
    wf = WorkflowDefinition(workflow_key=wf_key, display_name="Cast Test", workflow_type="standard",
                            status="published")
    s.add(wf); s.flush()
    step = WorkflowStep(workflow_id=wf.workflow_id, step_order=1, step_key="L1",
                        display_name="Level 1", assigned_role_key="", informed_roles=[], observer_roles=[])
    set_step_tier_keys(s, wf, step, supervisor=True, participants=False, observers=False)
    s.add(step)
    pa = ProjectPackage(project_id=proj.project_id, package_code="CA", name="Contractor A")
    pb = ProjectPackage(project_id=proj.project_id, package_code="CB", name="Contractor B")
    s.add_all([pa, pb]); s.commit()

    env = {
        "workflow_id": wf.workflow_id, "workflow_key": wf_key, "step_id": step.step_id,
        "actor_key": step.assigned_role_key, "supervisor_key": step.supervisor_role,
        "project_id": proj.project_id, "project_code": proj.short_code,
        "package_a": pa.package_id, "package_b": pb.package_id,
        "officer_a": f"cast-a-{uuid.uuid4().hex[:6]}@grm.local",
        "officer_b": f"cast-b-{uuid.uuid4().hex[:6]}@grm.local",
    }
    s.close()
    yield env

    # cleanup
    from ticketing.models.user import Role, UserRole
    from ticketing.models.officer_scope import OfficerScope
    s = SessionLocal()
    try:
        for em in (env["officer_a"], env["officer_b"]):
            s.execute(sa.delete(OfficerScope).where(OfficerScope.user_id == em))
            s.execute(sa.delete(UserRole).where(UserRole.user_id == em))
        for pid in (env["package_a"], env["package_b"]):
            obj = s.get(ProjectPackage, pid)
            if obj:
                s.delete(obj)
        s.execute(sa.delete(WorkflowStep).where(WorkflowStep.workflow_id == env["workflow_id"]))
        wf = s.get(WorkflowDefinition, env["workflow_id"])
        if wf:
            s.delete(wf)
        like = f"wf:{env['workflow_key']}:%"
        role_ids = [r.role_id for r in s.execute(sa.select(Role).where(Role.role_key.like(like))).scalars().all()]
        if role_ids:
            s.execute(sa.delete(UserRole).where(UserRole.role_id.in_(role_ids)))
            s.execute(sa.delete(Role).where(Role.role_id.in_(role_ids)))
        s.commit()
    finally:
        s.close()


def _staff(client, env, *, tier, user, package):
    return client.post(f"/api/v1/projects/{env['project_id']}/cast", json={
        "workflow_id": env["workflow_id"], "step_id": env["step_id"], "tier": tier,
        "user_id": user, "organization_id": _ORG, "location_code": _LOC, "package_id": package,
    })


def test_per_package_staffing_and_autoassign(cast_env):
    from ticketing.models.base import SessionLocal
    from ticketing.engine.workflow_engine import auto_assign_for_workflow_step

    app, client, db = _client(_super())
    try:
        # two contractors, same Actor tier, different packages
        ra = _staff(client, cast_env, tier="actor", user=cast_env["officer_a"], package=cast_env["package_a"])
        rb = _staff(client, cast_env, tier="actor", user=cast_env["officer_b"], package=cast_env["package_b"])
        assert ra.status_code == 201, ra.text
        assert rb.status_code == 201, rb.text

        # auto-assign resolves per package on the synthetic actor key
        s = SessionLocal()
        try:
            got_a = auto_assign_for_workflow_step(
                cast_env["actor_key"], _ORG, _LOC, cast_env["project_code"], s,
                ticket_package_id=cast_env["package_a"])
            got_b = auto_assign_for_workflow_step(
                cast_env["actor_key"], _ORG, _LOC, cast_env["project_code"], s,
                ticket_package_id=cast_env["package_b"])
            assert got_a == cast_env["officer_a"]
            assert got_b == cast_env["officer_b"]
        finally:
            s.close()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_self_escalation_guard(cast_env):
    app, client, db = _client(_super())
    try:
        assert _staff(client, cast_env, tier="actor", user=cast_env["officer_a"],
                      package=cast_env["package_a"]).status_code == 201
        # same person as Supervisor of the same step+package → rejected
        clash = _staff(client, cast_env, tier="supervisor", user=cast_env["officer_a"],
                       package=cast_env["package_a"])
        assert clash.status_code == 422, clash.text
        assert "self-escalation" in clash.text.lower()
        # a different officer as Supervisor is fine
        assert _staff(client, cast_env, tier="supervisor", user=cast_env["officer_b"],
                      package=cast_env["package_a"]).status_code == 201
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_read_cast(cast_env):
    app, client, db = _client(_super())
    try:
        _staff(client, cast_env, tier="actor", user=cast_env["officer_a"], package=cast_env["package_a"])
        listed = client.get(
            f"/api/v1/projects/{cast_env['project_id']}/cast",
            params={"workflow_id": cast_env["workflow_id"], "package_id": cast_env["package_a"]},
        ).json()
        assert any(r["user_id"] == cast_env["officer_a"] and r["tier"] == "actor" for r in listed)
    finally:
        app.dependency_overrides.clear()
        db.close()
