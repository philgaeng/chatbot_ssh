"""GRM-116 — resolution actions: a catalog owned by organizations, each workflow's list from it.

Pins the rules `services/resolution_catalog.py` exists to enforce (model: DESIGN §3.1.1, owner's
decisions Q-10) and what RESOLVE records:

1. **nothing is global** — every action belongs to an organization; an action owned by a ministry is
   shared, one owned below it is local and must count as a shared action of the same ministry;
2. an action is usable by a workflow of its organization or below — never across a ministry, never by
   a workflow with no organization;
3. a sensitive workflow lists nothing, and a SEAH case records neither an action nor a label;
4. at most 8 actions; a published non-sensitive workflow at least one, and publishing is refused
   without one;
5. lists are copied, never inherited;

plus the migration's organization assignment and the label snapshot on both resolution events.

Rows are flushed, never committed — every test rolls back. API tests route `commit` to `flush` so the
router's own commits roll back too.
"""
from __future__ import annotations

import importlib.util
import pathlib
import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import select

from ticketing.api.schemas.ticket import TicketActionRequest
from ticketing.constants.resolution import (
    GENERAL_ACTION_CODES,
    MAX_RESOLUTION_ACTIONS,
    ROAD_WORKS_ACTION_CODES,
)
from ticketing.engine.ticket_actions import ActionError, resolve
from ticketing.models.base import SessionLocal
from ticketing.models.organization import Organization
from ticketing.models.project import Project
from ticketing.models.project_workflow import ProjectWorkflow
from ticketing.models.resolution_action import ResolutionAction
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_file import TicketFile
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.resolution_catalog import (
    ResolutionCatalogError,
    available_to_workflow,
    copy_workflow_actions,
    create_action,
    event_action_label,
    options_for_ticket,
    selected_codes,
    set_workflow_actions,
)
from tests.ticketing.conftest import (
    LOC_P1_JHA_BIR,
    ORG_DOR,
    PROJECT_KL_ROAD,
    WORKFLOW_SEAH_KEY,
    WORKFLOW_STANDARD_KEY,
)

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


def _org(db, name: str, parent: str | None = None) -> str:
    oid = f"RA_{name}_{_tag()}"
    db.add(Organization(organization_id=oid, name=f"GRM-116 {name}", parent_organization_id=parent))
    db.flush()
    return oid


def _shared(db, ministry: str) -> ResolutionAction:
    return create_action(
        db, code=f"TEST_{_tag()}", label="Shared test action", default_wording="Shared wording.",
        owner_organization_id=ministry,
    )


def _local(db, owner: str, counts_as: str) -> ResolutionAction:
    return create_action(
        db, code=f"TEST_{_tag()}", label="Local test action", default_wording="Local wording.",
        owner_organization_id=owner, counts_as_code=counts_as,
    )


def _workflow(db, owner: str | None, *, sensitive=False, status="draft", template=False) -> WorkflowDefinition:
    wf = WorkflowDefinition(
        workflow_id=str(uuid.uuid4()),
        workflow_key=f"RA_TEST_{_tag()}",
        display_name="GRM-116 test workflow",
        workflow_type="seah" if sensitive else "standard",
        owner_organization_id=owner,
        status=status,
        is_template=template,
    )
    db.add(wf)
    db.flush()
    return wf


@pytest.fixture
def tree(db):
    """Two ministries: MOI ⊃ JHAPA ⊃ BIRTAMOD, MOI ⊃ ILAM — and CUSTOMS beside it."""
    moi = _org(db, "MOI")
    jhapa = _org(db, "JHAPA", moi)
    birtamod = _org(db, "BIRTAMOD", jhapa)
    ilam = _org(db, "ILAM", moi)
    customs = _org(db, "CUSTOMS")
    return {"moi": moi, "jhapa": jhapa, "birtamod": birtamod, "ilam": ilam, "customs": customs}


# ── 1. every action belongs to an organization ──────────────────────────────────────────────────

def test_an_action_with_no_organization_is_refused(db):
    with pytest.raises(ResolutionCatalogError, match="must belong to an organization"):
        create_action(db, code=f"TEST_{_tag()}", label="x", default_wording="x", owner_organization_id=None)


def test_a_ministrys_action_is_shared_and_counts_as_nothing(db, tree):
    other = _shared(db, tree["moi"])
    with pytest.raises(ResolutionCatalogError, match="national action"):
        create_action(db, code=f"TEST_{_tag()}", label="x", default_wording="x",
                      owner_organization_id=tree["moi"], counts_as_code=other.code)


def test_a_local_action_must_count_as_a_shared_action_of_its_own_ministry(db, tree):
    moi_shared = _shared(db, tree["moi"])
    customs_shared = _shared(db, tree["customs"])
    jhapa_local = _local(db, tree["jhapa"], moi_shared.code)
    assert jhapa_local.counts_as_code == moi_shared.code

    for counts_as, why in [(None, "must say"), (customs_shared.code, "not a national action"),
                           (jhapa_local.code, "not a national action")]:
        with pytest.raises(ResolutionCatalogError, match=why):
            create_action(db, code=f"TEST_{_tag()}", label="x", default_wording="x",
                          owner_organization_id=tree["birtamod"], counts_as_code=counts_as)


# ── 2. usable by a workflow of its organization or below ────────────────────────────────────────

def test_an_action_is_usable_at_its_organization_and_below(db, tree):
    action = _local(db, tree["jhapa"], _shared(db, tree["moi"]).code)
    assert available_to_workflow(db, action, _workflow(db, tree["jhapa"]))
    assert available_to_workflow(db, action, _workflow(db, tree["birtamod"]))
    assert not available_to_workflow(db, action, _workflow(db, tree["ilam"]))
    assert not available_to_workflow(db, action, _workflow(db, tree["moi"]))


def test_a_ministrys_shared_action_never_reaches_another_ministry(db, tree):
    action = _shared(db, tree["moi"])
    assert available_to_workflow(db, action, _workflow(db, tree["birtamod"]))
    assert not available_to_workflow(db, action, _workflow(db, tree["customs"]))


def test_a_workflow_with_no_organization_can_use_nothing(db, tree):
    wf = _workflow(db, None)
    assert not available_to_workflow(db, _shared(db, tree["moi"]), wf)
    with pytest.raises(ResolutionCatalogError, match="not part of"):
        set_workflow_actions(db, wf, ["CLASSIFIED"])


# ── 3 + 4. what a list may hold ─────────────────────────────────────────────────────────────────

def test_a_sensitive_workflow_lists_nothing(db):
    wf = _workflow(db, ORG_DOR, sensitive=True)
    with pytest.raises(ResolutionCatalogError, match="sensitive"):
        set_workflow_actions(db, wf, ["ACCEPTED_OTHER"])
    set_workflow_actions(db, wf, [])
    assert selected_codes(db, wf.workflow_id) == []


def test_at_most_eight_actions(db, tree):
    wf = _workflow(db, tree["moi"])
    codes = [_shared(db, tree["moi"]).code for _ in range(MAX_RESOLUTION_ACTIONS + 1)]
    set_workflow_actions(db, wf, codes[:MAX_RESOLUTION_ACTIONS])
    with pytest.raises(ResolutionCatalogError, match=f"at most {MAX_RESOLUTION_ACTIONS}"):
        set_workflow_actions(db, wf, codes)
    assert len(selected_codes(db, wf.workflow_id)) == MAX_RESOLUTION_ACTIONS


def test_only_a_published_workflow_must_list_something(db):
    with pytest.raises(ResolutionCatalogError, match="at least one"):
        set_workflow_actions(db, _workflow(db, ORG_DOR, status="published"), [])
    set_workflow_actions(db, _workflow(db, ORG_DOR, status="draft"), [])
    set_workflow_actions(db, _workflow(db, ORG_DOR, status="published", template=True), [])


@pytest.mark.parametrize("bad", ["unknown", "inactive", "other_ministry", "twice"])
def test_a_list_is_refused_whole(db, tree, bad):
    wf = _workflow(db, tree["jhapa"])
    ok = _shared(db, tree["moi"]).code
    set_workflow_actions(db, wf, [ok])
    inactive = _shared(db, tree["moi"])
    inactive.is_active = False
    db.flush()
    codes = {
        "unknown": [ok, "NOT_A_CODE"],
        "inactive": [ok, inactive.code],
        "other_ministry": [ok, _shared(db, tree["customs"]).code],
        "twice": [ok, ok],
    }[bad]
    with pytest.raises(ResolutionCatalogError):
        set_workflow_actions(db, wf, codes)
    assert selected_codes(db, wf.workflow_id) == [ok]  # nothing half-written


def test_a_list_keeps_its_order(db):
    wf = _workflow(db, ORG_DOR)
    order = ["ROAD_NO_HAZARD_FOUND", "CLASSIFIED", "ROAD_REPAIRED"]
    set_workflow_actions(db, wf, order)
    assert selected_codes(db, wf.workflow_id) == order


# ── 5. copied, never inherited ──────────────────────────────────────────────────────────────────

def test_a_copy_is_its_own_list(db):
    source = _workflow(db, ORG_DOR)
    set_workflow_actions(db, source, ["CLASSIFIED", "ACCEPTED_OTHER"])
    copy = _workflow(db, ORG_DOR)
    copy_workflow_actions(db, source.workflow_id, copy)
    set_workflow_actions(db, source, ["ROAD_REPAIRED"])
    assert selected_codes(db, copy.workflow_id) == ["CLASSIFIED", "ACCEPTED_OTHER"]


def test_a_copy_into_an_organization_that_cannot_use_an_action_is_refused(db, tree):
    source = _workflow(db, tree["jhapa"])
    local = _local(db, tree["jhapa"], _shared(db, tree["moi"]).code)
    set_workflow_actions(db, source, [local.code])
    sibling = _workflow(db, tree["ilam"])
    with pytest.raises(ResolutionCatalogError):
        copy_workflow_actions(db, source.workflow_id, sibling)
    assert selected_codes(db, sibling.workflow_id) == []


# ── the router: new workflows start empty, templates are owned, publish is gated ────────────────

def _client(db, monkeypatch, user):
    from ticketing.api.dependencies import get_authenticated_user
    from ticketing.api.dependencies import get_db as api_get_db
    from ticketing.api.main import app
    from ticketing.models.base import get_db as base_get_db

    monkeypatch.setattr(db, "commit", db.flush)  # the router's commits roll back with the test

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: user
    # ⚠ Both: routers import `get_db` from either module, and an override of one leaves the other
    # handing out a real session that commits. Measured the hard way — this file's first version
    # overrode only one and wrote five workflows to the dev database.
    app.dependency_overrides[api_get_db] = _db
    app.dependency_overrides[base_get_db] = _db
    return app, TestClient(app)


def _super():
    from ticketing.api.dependencies import CurrentUser
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _dor_admin():
    from ticketing.api.dependencies import CurrentUser
    from ticketing.services.admin_access import AdminScopeRow
    return CurrentUser(user_id="o@grm.local", role_keys=[], admin_scopes=[AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()), user_id="o@grm.local", role_key="org_admin",
        country_code="NP", project_id=None, organization_id=ORG_DOR, package_id=None,
        workflow_track="standard",
    )])


def test_a_new_workflow_starts_empty_and_cannot_be_published(db, monkeypatch):
    app, client = _client(db, monkeypatch, _super())
    try:
        for body in ({"display_name": "GRM-116 scratch"},
                     {"display_name": "GRM-116 built-in", "clone_from_id": "__builtin_default_grm"}):
            res = client.post("/api/v1/workflows", json=body)
            assert res.status_code == 201, res.text
            wf_id = res.json()["workflow_id"]
            assert selected_codes(db, wf_id) == []
            pub = client.post(f"/api/v1/workflows/{wf_id}/publish")
            assert pub.status_code == 422, pub.text
            assert "resolution action" in pub.text
    finally:
        app.dependency_overrides.clear()


def test_a_sensitive_workflow_publishes_with_no_action(db, monkeypatch):
    app, client = _client(db, monkeypatch, _super())
    try:
        res = client.post("/api/v1/workflows", json={"display_name": "GRM-116 sensitive", "workflow_type": "seah"})
        assert res.status_code == 201, res.text
        pub = client.post(f"/api/v1/workflows/{res.json()['workflow_id']}/publish")
        assert pub.status_code == 200, pub.text
    finally:
        app.dependency_overrides.clear()


def test_an_org_admins_clone_copies_the_list_and_its_template_is_owned(db, monkeypatch):
    source = _seeded(db, WORKFLOW_STANDARD_KEY)
    app, client = _client(db, monkeypatch, _dor_admin())
    try:
        clone = client.post("/api/v1/workflows", json={"display_name": "GRM-116 clone", "clone_from_id": source.workflow_id})
        assert clone.status_code == 201, clone.text
        assert selected_codes(db, clone.json()["workflow_id"]) == list(GENERAL_ACTION_CODES)

        tpl = client.post("/api/v1/workflows", json={"display_name": "GRM-116 template", "is_template": True})
        assert tpl.status_code == 201, tpl.text
        assert db.get(WorkflowDefinition, tpl.json()["workflow_id"]).owner_organization_id == ORG_DOR
    finally:
        app.dependency_overrides.clear()


def test_a_platform_admins_clone_has_no_organization_so_its_list_is_refused(db, monkeypatch):
    # Until GRM-122 lets a platform admin choose the organization: an ownerless copy can use nothing,
    # and the copy is refused rather than silently emptied.
    source = _seeded(db, WORKFLOW_STANDARD_KEY)
    app, client = _client(db, monkeypatch, _super())
    try:
        res = client.post("/api/v1/workflows", json={"display_name": "GRM-116 clone", "clone_from_id": source.workflow_id})
        assert res.status_code == 422, res.text
    finally:
        app.dependency_overrides.clear()


# ── the migration: organizations for ownerless workflows ────────────────────────────────────────

def _assign(db) -> None:
    """Run the migration's step 1 against only this test's workflows: any other ownerless workflow on
    the database is given an owner inside the test transaction first (rolled back after)."""
    db.execute(
        sa.text("UPDATE ticketing.workflow_definitions SET owner_organization_id = :o "
                "WHERE owner_organization_id IS NULL AND workflow_key NOT LIKE 'RA_TEST_%'"),
        {"o": ORG_DOR},
    )
    _migration().assign_workflow_organizations(db.connection())


def _migration():
    path = pathlib.Path(__file__).resolve().parents[2] / "ticketing/migrations/versions/b3d5f7h9_resolution_actions.py"
    spec = importlib.util.spec_from_file_location("b3d5f7h9", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project(db, agency: str) -> Project:
    p = Project(project_id=str(uuid.uuid4()), country_code="NP", short_code=f"T{_tag()}"[:8],
                name="GRM-116 migration test", implementing_agency_org_id=agency)
    db.add(p)
    db.flush()
    return p


def _bind(db, workflow: WorkflowDefinition, project: Project) -> None:
    db.add(ProjectWorkflow(project_workflow_id=str(uuid.uuid4()), project_id=project.project_id,
                           workflow_id=workflow.workflow_id, display_label="test", is_default=False))
    db.flush()


def test_the_migration_gives_a_workflow_its_projects_ministry(db, tree):
    wf = _workflow(db, None)
    _bind(db, wf, _project(db, tree["birtamod"]))
    _assign(db)
    db.expire_all()
    assert db.get(WorkflowDefinition, wf.workflow_id).owner_organization_id == tree["moi"]


def test_the_migration_stops_on_a_workflow_used_by_two_ministries(db, tree):
    wf = _workflow(db, None)
    _bind(db, wf, _project(db, tree["jhapa"]))
    _bind(db, wf, _project(db, tree["customs"]))
    with pytest.raises(RuntimeError, match=wf.workflow_key):
        _assign(db)


def test_the_migration_stops_on_an_unused_workflow_when_several_ministries_implement(db, tree):
    _project(db, tree["customs"])  # DOR already implements KL_ROAD, so there are now several
    wf = _workflow(db, None)
    with pytest.raises(RuntimeError, match=wf.workflow_key):
        _assign(db)


def test_the_migration_leaves_an_owned_workflow_alone(db, tree):
    wf = _workflow(db, tree["ilam"])
    _bind(db, wf, _project(db, tree["customs"]))
    _assign(db)
    db.expire_all()
    assert db.get(WorkflowDefinition, wf.workflow_id).owner_organization_id == tree["ilam"]


# ── the backfill, read off the seeded workflows ─────────────────────────────────────────────────

def _seeded(db, key: str) -> WorkflowDefinition:
    return db.execute(select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == key)).scalar_one()


def test_the_seeded_workflows_belong_to_dor(db):
    assert _seeded(db, WORKFLOW_STANDARD_KEY).owner_organization_id == ORG_DOR
    assert _seeded(db, WORKFLOW_SEAH_KEY).owner_organization_id == ORG_DOR


def test_the_seeded_standard_workflow_offers_the_general_five(db):
    assert selected_codes(db, _seeded(db, WORKFLOW_STANDARD_KEY).workflow_id) == list(GENERAL_ACTION_CODES)


def test_the_seeded_seah_workflow_offers_nothing(db):
    assert selected_codes(db, _seeded(db, WORKFLOW_SEAH_KEY).workflow_id) == []


def test_every_starter_action_is_a_shared_action_of_dor(db):
    rows = db.execute(
        select(ResolutionAction).where(ResolutionAction.code.in_(GENERAL_ACTION_CODES + ROAD_WORKS_ACTION_CODES))
    ).scalars().all()
    assert len(rows) == 10
    assert all(r.owner_organization_id == ORG_DOR and r.counts_as_code is None and r.is_active for r in rows)


# ── RESOLVE ─────────────────────────────────────────────────────────────────────────────────────

class _Actor:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.role_keys = ["site_safeguards_focal_person"]

    @property
    def is_admin(self) -> bool:
        return False

    def matches_assignee(self, assignee_id):
        return assignee_id == self.user_id


def _ticket(db, workflow_key: str) -> Ticket:
    wf = _seeded(db, workflow_key)
    step = db.execute(
        select(WorkflowStep).where(WorkflowStep.workflow_id == wf.workflow_id).order_by(WorkflowStep.step_order).limit(1)
    ).scalar_one()
    t = Ticket(
        ticket_id=str(uuid.uuid4()),
        grievance_id=f"ra-{uuid.uuid4().hex[:12]}",
        organization_id=ORG_DOR,
        location_code=LOC_P1_JHA_BIR,
        project_code=PROJECT_KL_ROAD,
        current_workflow_id=wf.workflow_id,
        current_step_id=step.step_id,
        assigned_to_user_id="ra-officer@grm.local",
        status_code="IN_PROGRESS",
        is_seah=workflow_key == WORKFLOW_SEAH_KEY,
        is_deleted=False,
        sla_breached=False,
        priority="NORMAL",
    )
    db.add(t)
    db.flush()
    db.add(TicketFile(
        file_id=str(uuid.uuid4()), ticket_id=t.ticket_id, file_name="site.jpg",
        file_path=f"uploads/ticketing/{t.ticket_id}/site.jpg", file_type="image", file_size=1,
        uploaded_by_user_id=t.assigned_to_user_id,
    ))
    db.flush()
    return t


def _resolve(db, ticket, category: str | None):
    payload = TicketActionRequest(
        action_type="RESOLVE", resolution_category=category,
        note="The site was inspected and the matter closed as recorded.",
    )
    return resolve(db, ticket, _Actor(ticket.assigned_to_user_id), payload)


def _record(db, ticket) -> TicketEvent:
    db.flush()  # SessionLocal has autoflush off
    return db.execute(
        select(TicketEvent).where(TicketEvent.ticket_id == ticket.ticket_id, TicketEvent.event_type == "NOTE_ADDED")
    ).scalars().one()


def test_resolve_snapshots_the_chosen_label_on_both_events(db, monkeypatch):
    monkeypatch.setattr("ticketing.engine.ticket_actions.update_grievance_status", lambda *a, **k: None)
    ticket = _ticket(db, WORKFLOW_STANDARD_KEY)
    outcome = _resolve(db, ticket, "ACCEPTED_OTHER")

    label = "Grievance accepted — other remedy"
    assert outcome.event.payload["resolution_category"] == "ACCEPTED_OTHER"
    assert outcome.event.payload["resolution_category_label"] == label
    assert outcome.event.note == f"Case resolved — {label}"
    record = _record(db, ticket)
    assert record.payload["resolution_category_label"] == label
    assert record.note.startswith(f"Resolution — {label}\n")


def test_resolve_refuses_an_action_the_cases_workflow_does_not_offer(db):
    ticket = _ticket(db, WORKFLOW_STANDARD_KEY)
    with pytest.raises(ActionError) as exc:
        _resolve(db, ticket, "ROAD_REPAIRED")
    assert "not offered" in exc.value.detail


def test_resolve_on_a_standard_case_requires_an_action(db):
    ticket = _ticket(db, WORKFLOW_STANDARD_KEY)
    with pytest.raises(ActionError) as exc:
        _resolve(db, ticket, None)
    assert "required" in exc.value.detail


def test_a_seah_case_resolves_with_text_alone_and_records_no_action(db, monkeypatch):
    monkeypatch.setattr("ticketing.engine.ticket_actions.update_grievance_status", lambda *a, **k: None)
    ticket = _ticket(db, WORKFLOW_SEAH_KEY)
    outcome = _resolve(db, ticket, None)

    assert outcome.ticket.status_code == "RESOLVED"
    assert outcome.event.note == "Case resolved"
    for event in (outcome.event, _record(db, ticket)):
        assert "resolution_category" not in event.payload
        assert "resolution_category_label" not in event.payload
    assert _record(db, ticket).note.startswith("Resolution\n")


def test_a_seah_case_refuses_any_action(db):
    ticket = _ticket(db, WORKFLOW_SEAH_KEY)
    with pytest.raises(ActionError) as exc:
        _resolve(db, ticket, "ACCEPTED_OTHER")
    assert "does not record a resolution action" in exc.value.detail


def test_ticket_detail_options_follow_the_cases_workflow(db):
    standard = _ticket(db, WORKFLOW_STANDARD_KEY)
    seah = _ticket(db, WORKFLOW_SEAH_KEY)
    assert [o["code"] for o in options_for_ticket(db, standard)] == list(GENERAL_ACTION_CODES)
    assert options_for_ticket(db, seah) == []


# ── labels read back ────────────────────────────────────────────────────────────────────────────

def test_the_snapshot_wins_over_the_catalog_label(db):
    payload = {"resolution_category": "ACCEPTED_OTHER", "resolution_category_label": "What the officer saw"}
    assert event_action_label(db, payload) == "What the officer saw"


def test_an_event_from_before_snapshots_reads_the_catalog(db):
    assert event_action_label(db, {"resolution_category": "DEMAND_REJECTED"}) == "Complainant demand rejected"
    assert event_action_label(db, {}) == ""


# ── organization delete ─────────────────────────────────────────────────────────────────────────

def test_an_organization_that_owns_an_action_cannot_be_deleted(db, monkeypatch):
    oid = _org(db, "OWNER")
    _shared(db, oid)
    _workflow(db, oid)
    app, client = _client(db, monkeypatch, _super())
    try:
        impact = client.get(f"/api/v1/organizations/{oid}/delete-impact")
        assert impact.status_code == 200, impact.text
        assert impact.json()["resolution_action_count"] == 1
        assert impact.json()["workflow_count"] == 1
        assert impact.json()["deletable"] is False
        res = client.delete(f"/api/v1/organizations/{oid}")
        assert res.status_code == 409, res.text
        assert "resolution action" in res.text
    finally:
        app.dependency_overrides.clear()
