"""GRM-122 — an admin says which organization a workflow belongs to.

Resolution actions belong to organizations, so a workflow can offer an action only if the workflow
belongs to one (DESIGN §3.1.1). This pins how that organization is chosen and changed:

- a platform admin must choose it on create; an org_admin's defaults to its own and must be in reach;
- a move needs reach on both organizations, is refused while the list holds an action the new
  organization could not use (naming each), and is written to the admin audit log;
- the template picker is ancestor-aware: a PD-ADB workflow may start from DOR's template;
- *Save as template* keeps the workflow's organization;
- the organization picker lists only organizations the caller manages.

Everything is flushed, never committed: the router's commits are routed to `flush`.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ticketing.api.dependencies import CurrentUser
from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.base import SessionLocal
from ticketing.models.organization import Organization
from ticketing.models.workflow import WorkflowDefinition
from ticketing.services.admin_access import AdminScopeRow
from ticketing.services.resolution_catalog import create_action, set_workflow_actions
from tests.ticketing.conftest import ORG_DOR

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _tag() -> str:
    return uuid.uuid4().hex[:6].upper()


def _org(db, name: str, parent: str | None) -> str:
    oid = f"WO_{name}_{_tag()}"
    db.add(Organization(organization_id=oid, name=f"GRM-122 {name}", parent_organization_id=parent))
    db.flush()
    return oid


@pytest.fixture
def tree(db):
    """DOR ⊃ PD-ADB, DOR ⊃ ILAM (a sibling office), and another ministry beside DOR."""
    return {
        "pd_adb": _org(db, "PDADB", ORG_DOR),
        "ilam": _org(db, "ILAM", ORG_DOR),
        "other": _org(db, "MINISTRY", None),
    }


def _workflow(db, owner: str | None, *, template=False, sensitive=False, codes=()) -> WorkflowDefinition:
    wf = WorkflowDefinition(
        workflow_id=str(uuid.uuid4()), workflow_key=f"WO_TEST_{_tag()}", display_name="GRM-122 test",
        workflow_type="seah" if sensitive else "standard", owner_organization_id=owner,
        status="draft", is_template=template,
    )
    db.add(wf)
    db.flush()
    if codes:
        set_workflow_actions(db, wf, list(codes))
    return wf


def _super() -> CurrentUser:
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _org_admin(org: str) -> CurrentUser:
    return CurrentUser(user_id=f"admin-{org}@grm.local", role_keys=[], admin_scopes=[AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()), user_id=f"admin-{org}@grm.local", role_key="org_admin",
        country_code="NP", project_id=None, organization_id=org, package_id=None, workflow_track="standard",
    )])


@pytest.fixture
def as_user(db, monkeypatch):
    from ticketing.api.dependencies import get_authenticated_user
    from ticketing.api.dependencies import get_db as api_get_db
    from ticketing.api.main import app
    from ticketing.models.base import get_db as base_get_db

    monkeypatch.setattr(db, "commit", db.flush)

    def _db():
        yield db

    # Both session hooks: routers import get_db from either module (see test_resolution_catalog).
    app.dependency_overrides[api_get_db] = _db
    app.dependency_overrides[base_get_db] = _db

    def _as(user: CurrentUser) -> TestClient:
        app.dependency_overrides[get_authenticated_user] = lambda: user
        return TestClient(app)

    yield _as
    app.dependency_overrides.clear()


def _move(client, wf, org):
    return client.patch(f"/api/v1/workflows/{wf.workflow_id}/organization", json={"organization_id": org})


# ── moving ──────────────────────────────────────────────────────────────────────────────────────

def test_moving_down_keeps_the_ministrys_actions_and_is_audited(db, tree, as_user):
    wf = _workflow(db, ORG_DOR, codes=["CLASSIFIED", "ACCEPTED_OTHER"])
    res = _move(as_user(_org_admin(ORG_DOR)), wf, tree["pd_adb"])
    assert res.status_code == 200, res.text
    assert res.json()["owner_organization_id"] == tree["pd_adb"]
    assert res.json()["owner_name"] == "GRM-122 PDADB"
    audit = db.execute(
        select(AdminAuditLog).where(AdminAuditLog.action == "workflow_organization_changed")
        .order_by(AdminAuditLog.created_at.desc())
    ).scalars().first()
    assert audit.payload == {"workflow_id": wf.workflow_id, "from_organization_id": ORG_DOR,
                             "to_organization_id": tree["pd_adb"]}


def test_moving_sideways_is_refused_while_a_local_action_is_on_the_list(db, tree, as_user):
    local = create_action(db, code=f"TEST_{_tag()}", label="Culvert cleared", default_wording="x",
                          owner_organization_id=tree["pd_adb"], counts_as_code="CLASSIFIED")
    wf = _workflow(db, tree["pd_adb"], codes=[local.code, "CLASSIFIED"])
    res = _move(as_user(_org_admin(ORG_DOR)), wf, tree["ilam"])
    assert res.status_code == 422, res.text
    assert "Remove 'Culvert cleared' first — it belongs to GRM-122 PDADB." in res.text
    assert "Grievance classified" not in res.text  # DOR's shared action is usable by Ilam
    assert db.get(WorkflowDefinition, wf.workflow_id).owner_organization_id == tree["pd_adb"]


def test_moving_to_another_ministry_is_refused_with_any_action_on_the_list(db, tree, as_user):
    wf = _workflow(db, ORG_DOR, codes=["CLASSIFIED"])
    res = _move(as_user(_super()), wf, tree["other"])
    assert res.status_code == 422, res.text
    assert "Grievance classified" in res.text


def test_a_move_needs_reach_on_both_organizations(db, tree, as_user):
    wf = _workflow(db, ORG_DOR, codes=["CLASSIFIED"])
    assert _move(as_user(_org_admin(tree["pd_adb"])), wf, tree["pd_adb"]).status_code == 403
    assert _move(as_user(_org_admin(ORG_DOR)), wf, tree["other"]).status_code == 403


def test_a_sensitive_workflow_moves_only_with_the_sensitive_configuration_capability(db, tree, as_user):
    wf = _workflow(db, ORG_DOR, sensitive=True)
    assert _move(as_user(_org_admin(ORG_DOR)), wf, tree["pd_adb"]).status_code == 403


# ── creating ────────────────────────────────────────────────────────────────────────────────────

def test_a_platform_admin_must_choose_the_organization(db, as_user):
    res = as_user(_super()).post("/api/v1/workflows", json={"display_name": "GRM-122 no org"})
    assert res.status_code == 422, res.text
    assert "Choose the organization" in res.text


def test_an_org_admins_workflow_defaults_to_its_organization_and_stays_in_reach(db, tree, as_user):
    client = as_user(_org_admin(tree["pd_adb"]))
    res = client.post("/api/v1/workflows", json={"display_name": "GRM-122 default"})
    assert res.status_code == 201, res.text
    assert res.json()["owner_organization_id"] == tree["pd_adb"]
    outside = client.post("/api/v1/workflows", json={"display_name": "GRM-122 outside",
                                                     "owner_organization_id": tree["ilam"]})
    assert outside.status_code == 403, outside.text


def test_the_template_picker_offers_templates_of_the_organization_and_above(db, tree, as_user):
    mine = _workflow(db, tree["pd_adb"], template=True)
    dors = _workflow(db, ORG_DOR, template=True)
    siblings = _workflow(db, tree["ilam"], template=True)
    foreign = _workflow(db, tree["other"], template=True)
    res = as_user(_org_admin(tree["pd_adb"])).get(
        "/api/v1/workflows", params={"is_template": "true", "for_organization_id": tree["pd_adb"]}
    )
    assert res.status_code == 200, res.text
    ids = {w["workflow_id"] for w in res.json()["items"]}
    assert {mine.workflow_id, dors.workflow_id} <= ids
    assert siblings.workflow_id not in ids and foreign.workflow_id not in ids


def test_the_template_picker_refuses_an_organization_outside_reach(db, tree, as_user):
    res = as_user(_org_admin(tree["pd_adb"])).get(
        "/api/v1/workflows", params={"is_template": "true", "for_organization_id": tree["ilam"]}
    )
    assert res.status_code == 403, res.text


def test_save_as_template_keeps_the_workflows_organization(db, tree, as_user):
    wf = _workflow(db, tree["pd_adb"], codes=["CLASSIFIED"])
    res = as_user(_super()).post(f"/api/v1/workflows/{wf.workflow_id}/save-as-template", json={})
    assert res.status_code == 201, res.text
    assert res.json()["owner_organization_id"] == tree["pd_adb"]


def test_the_workflow_detail_names_the_projects_using_it(db, as_user):
    std = db.execute(select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == "KL_ROAD_STANDARD")).scalar_one()
    res = as_user(_super()).get(f"/api/v1/workflows/{std.workflow_id}")
    assert res.status_code == 200, res.text
    assert res.json()["used_by_projects"], "KL Road binds the standard workflow"
    assert res.json()["owner_name"]


# ── the organization picker ─────────────────────────────────────────────────────────────────────

def test_the_picker_lists_only_organizations_the_caller_manages(db, tree, as_user):
    res = as_user(_org_admin(tree["pd_adb"])).get("/api/v1/organizations", params={"manageable": "true", "active_only": "false"})
    assert res.status_code == 200, res.text
    ids = {o["organization_id"] for o in res.json()}
    assert tree["pd_adb"] in ids
    assert ORG_DOR not in ids and tree["ilam"] not in ids and tree["other"] not in ids
