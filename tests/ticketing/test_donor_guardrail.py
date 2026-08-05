"""doc 13 / DECISION 2026-07-10 §3 + OC-04 §5.6 — project participants + donor guardrail.

Acceptance (DECISION §9):
* implementing_agency rejects a non-gov/local-gov org.
* The organization stamped on a ticket is descriptive: the project's first-named organization,
  legacy field as fallback. Reporting is membership — see test_org_reach.py.
* Go-live BLOCKS on donor-present-but-not-informed-at-last-step; passes once informed.
* Donor auto-populates the last-step "Kept informed" cast; admin can trim to ≥1.
* Go-live BLOCKS on any unstaffed standard workflow level (C5).
* SEAH-leak: a donor is cast on a standard ticket's final-step informed cast, but
  receives NOTHING on a SEAH ticket (payload suppressed).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from ticketing.engine.escalation import _apply_step_tier_roles
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services import project_go_live as go_live_svc
from ticketing.services.donor_guardrail import (
    apply_donor_informed_defaults,
    donor_informed_ok,
    donor_informed_role_keys,
    implementing_agency_org_id,
    last_standard_step,
    project_donor_org_ids,
    validate_implementing_agency,
)
from ticketing.services.project_routing import routing_org_id_for_loaded_project

pytestmark = pytest.mark.integration

ORG_DOR = "DOR"
ORG_ADB = "ADB"
DONOR_ROLE = "donor_national"


# ── implementing agency validation (DECISION §2, §9) ──────────────────────────

def test_validate_implementing_agency_accepts_government(db):
    # DOR is category 'government' in the seed — must be accepted.
    validate_implementing_agency(db, ORG_DOR)  # no raise


def test_validate_implementing_agency_rejects_donor(db):
    # ADB is category 'donor' — a funder can never be the accountable agency.
    with pytest.raises(ValueError, match="government or local-government"):
        validate_implementing_agency(db, ORG_ADB)


def test_validate_implementing_agency_allows_none(db):
    validate_implementing_agency(db, None)  # defaulted elsewhere → allowed


def test_validate_implementing_agency_rejects_unknown(db):
    with pytest.raises(ValueError, match="does not exist"):
        validate_implementing_agency(db, f"nope-{uuid.uuid4().hex[:6]}")


# ── routing reads implementing_agency_org_id (DECISION §2, §9) ─────────────────

def test_stamp_prefers_a_named_organization_over_the_legacy_field(db, kl_road_project):
    """`tickets.organization_id` takes the project's first-named organization; the legacy field
    is only a fallback.

    The stamp stopped *meaning* anything on 2026-08-04 (DECISION-organization-membership) —
    reporting is membership, so no single organization owns a grievance. It still needs a
    stable value because the column is NOT NULL, and "first organization the type lists" is
    that value.
    """
    assert routing_org_id_for_loaded_project(db, kl_road_project) == ORG_DOR

    original = kl_road_project.implementing_agency_org_id
    try:
        kl_road_project.implementing_agency_org_id = ORG_ADB
        db.flush()
        # DOR is still named on the project, so the stamp does not follow the legacy field.
        assert routing_org_id_for_loaded_project(db, kl_road_project) == ORG_DOR
    finally:
        kl_road_project.implementing_agency_org_id = original
        db.flush()


def test_implementing_agency_helper_falls_back_to_org_role(db, kl_road_project):
    """When the field is NULL, the helper falls back to the org_role link (expand phase)."""
    original = kl_road_project.implementing_agency_org_id
    try:
        kl_road_project.implementing_agency_org_id = None
        db.flush()
        # KL Road still has ProjectOrganization(org_role='implementing_agency') = DOR.
        assert implementing_agency_org_id(db, kl_road_project) == ORG_DOR
    finally:
        kl_road_project.implementing_agency_org_id = original
        db.flush()


# ── donor guardrail predicate; go-live A5 is GONE (DECISION-author-defined-slots §4, §7) ──

def test_kl_road_has_donor_and_is_informed(db, kl_road_project):
    assert ORG_ADB in project_donor_org_ids(db, kl_road_project.project_id)
    # Seed + auto-populate keep a donor tier in the final standard step's informed cast.
    assert donor_informed_ok(db, kl_road_project) is True


def test_a5_is_gone_and_the_predicate_still_works(db, kl_road_project):
    """The donor guardrail stopped being a hardcoded go-live check on 2026-08-04.

    A5 asked one question the platform had wired in: *is a donor kept informed at the last
    level?* The type model asks it in the author's own words instead — mark that organization
    role **required** (B1) and put it in the last level's kept-informed job, which C5 enforces
    like any other required job. So A5 must no longer be emitted, while the predicate it used
    stays (it still pre-fills the cast when a donor is added).
    """
    step = last_standard_step(db, kl_road_project)
    assert step is not None
    saved = list(step.informed_roles or [])
    try:
        step.informed_roles = [rk for rk in saved if rk not in donor_informed_role_keys(step)]
        db.flush()
        assert donor_informed_ok(db, kl_road_project) is False

        report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
        assert not any(c.id in {"A3", "A5"} for c in report.checks)
    finally:
        step.informed_roles = saved
        db.flush()


def test_b1_blocks_when_a_required_organization_is_missing(db, kl_road_project):
    """B1 replaces A3/A5 and is a **blocker** — a project cannot go live without the
    organizations its own type says it needs, named in the author's words."""
    from ticketing.services.project_types import get_project_type

    pt = get_project_type(db, kl_road_project.project_type_key)
    assert pt is not None, "KL Road must have a type — the back-fill gave every project one"
    saved_roles = list(pt.actor_roles or [])
    saved_ia = kl_road_project.implementing_agency_org_id
    try:
        # A required role nothing fills — and not the anchor, so the legacy field cannot
        # satisfy it by accident.
        pt.actor_roles = saved_roles + [
            {
                "key": "ward_office",
                "label": "Ward Office",
                "description": "",
                "required": True,
                "required_package": False,
                "scope": "project",
            }
        ]
        db.flush()

        report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
        b1 = next(c for c in report.checks if c.id == "B1")
        assert b1.status == "fail" and b1.severity == "block"
        # The author's label, not the key — that is the whole point of the catalog.
        assert "Ward Office" in b1.message
        assert report.can_activate is False
        assert "Ward Office" in (go_live_svc.activation_block_message(report) or "")
    finally:
        pt.actor_roles = saved_roles
        kl_road_project.implementing_agency_org_id = saved_ia
        db.flush()


def test_b1_accepts_the_legacy_anchor_field(db, kl_road_project):
    """A project set up before the catalog came back kept its anchor organization on the
    project row. That is still a true statement about the project, so B1 reads it (§4) —
    otherwise the change would have blocked every existing project on activation."""
    from ticketing.models.project import ProjectOrganization
    from ticketing.services.project_types import get_project_type

    pt = get_project_type(db, kl_road_project.project_type_key)
    assert "implementing_agency" in {r["key"] for r in pt.actor_roles}
    ia_links = [
        po for po in kl_road_project.organizations if po.org_role == "implementing_agency"
    ]
    saved = [(po.organization_id, po.org_role) for po in ia_links]
    saved_ia = kl_road_project.implementing_agency_org_id
    try:
        for po in ia_links:
            db.delete(po)
        kl_road_project.implementing_agency_org_id = ORG_DOR
        db.flush()
        db.refresh(kl_road_project)

        report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
        b1 = next(c for c in report.checks if c.id == "B1")
        assert b1.status == "pass", b1.message
    finally:
        for org_id, role in saved:
            if db.get(ProjectOrganization, (kl_road_project.project_id, org_id)) is None:
                db.add(
                    ProjectOrganization(
                        project_id=kl_road_project.project_id,
                        organization_id=org_id,
                        org_role=role,
                    )
                )
        kl_road_project.implementing_agency_org_id = saved_ia
        db.flush()
        db.refresh(kl_road_project)


def test_apply_donor_informed_defaults_populates_and_is_idempotent(db, kl_road_project):
    step = last_standard_step(db, kl_road_project)
    saved = list(step.informed_roles or [])
    try:
        step.informed_roles = []
        db.flush()
        added = apply_donor_informed_defaults(db, kl_road_project)
        db.flush()
        assert set(added) == {"donor_consultant", "donor_hq", "donor_national"}
        assert donor_informed_ok(db, kl_road_project) is True
        # Idempotent — a second call adds nothing.
        assert apply_donor_informed_defaults(db, kl_road_project) == []
    finally:
        step.informed_roles = saved
        db.flush()


# ── C5 all-levels-staffed go-live block (DECISION §7, §9) ─────────────────────

def test_go_live_c5_passes_for_staffed_demo(db, kl_road_project):
    """Regression: the demo staffs every standard level → C5 passes (project activatable)."""
    report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
    c5 = next(c for c in report.checks if c.id == "C5")
    assert c5.status == "pass"


def test_go_live_c5_blocks_on_unstaffed_level(db, kl_road_project):
    """Point the final step at a role nobody is scoped to → C5 fails + blocks activation."""
    step = last_standard_step(db, kl_road_project)
    saved_role = step.assigned_role_key
    try:
        step.assigned_role_key = "adb_hq_project"  # no officer scoped to it on KL Road
        db.flush()
        report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
        c5 = next(c for c in report.checks if c.id == "C5")
        assert c5.status == "fail" and c5.severity == "block"
        assert report.can_activate is False
        assert f"L{step.step_order}" in c5.message
    finally:
        step.assigned_role_key = saved_role
        db.flush()


# ── SEAH leak-proofing of the donor cast (DECISION §3, §9) ────────────────────

def _fake_final_step(informed_roles: list[str]) -> WorkflowStep:
    """A transient step object — _apply_step_tier_roles only reads the cast fields."""
    return WorkflowStep(
        step_id=str(uuid.uuid4()),
        workflow_id=str(uuid.uuid4()),
        step_order=99,
        step_key="TEST_FINAL",
        display_name="Test final",
        assigned_role_key="pd_piu_safeguards_focal",
        supervisor_role=None,
        informed_roles=informed_roles,
        observer_roles=[],
    )


def _make_ticket(ctx, *, is_seah: bool) -> Ticket:
    wf = ctx.db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == "KL_ROAD_STANDARD")
    ).scalar_one()
    step = ctx.db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == wf.workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one()
    row = Ticket(
        ticket_id=str(uuid.uuid4()),
        grievance_id=f"test-grv-{uuid.uuid4().hex[:10]}",
        organization_id=ORG_DOR,
        location_code="P1_JHA_BIR",
        project_code="KL_ROAD",
        current_workflow_id=wf.workflow_id,
        current_step_id=step.step_id,
        assigned_to_user_id="someone@grm.local",
        status_code="OPEN",
        is_seah=is_seah,
        is_deleted=False,
        sla_breached=False,
        priority="NORMAL",
    )
    ctx.db.add(row)
    ctx.db.flush()
    ctx.ticket_ids.append(row.ticket_id)
    return row


def _donor_is_viewer(db, ticket_id: str, donor_uid: str) -> bool:
    return (
        db.execute(
            select(TicketViewer).where(
                TicketViewer.ticket_id == ticket_id,
                TicketViewer.user_id == donor_uid,
            )
        ).scalar_one_or_none()
        is not None
    )


# ── Donor CRUD endpoints (doc 13 §3 — the UI-wireable surface) ────────────────

def _super_admin_client(db):
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
    from ticketing.api.main import app

    def override_user():
        return CurrentUser(user_id="super@grm.local", role_keys=["super_admin"])

    def override_db():
        yield db

    app.dependency_overrides[get_authenticated_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), app


def test_add_and_remove_donor_endpoint(db, kl_road_project):
    from ticketing.models.organization import Organization
    from ticketing.models.project import ProjectDonor

    donor_org_id = f"DONOR_{uuid.uuid4().hex[:6].upper()}"
    db.add(Organization(
        organization_id=donor_org_id, name="Test Donor Bank", country_code="NP",
        org_category="donor", unit_type="development_partner",
    ))
    db.commit()
    client, app = _super_admin_client(db)
    try:
        # Add — 201 + row created + last-step cast auto-populated.
        res = client.post(f"/api/v1/projects/{kl_road_project.project_id}/donors/{donor_org_id}")
        assert res.status_code == 201, res.text
        assert db.get(ProjectDonor, (kl_road_project.project_id, donor_org_id)) is not None
        step = last_standard_step(db, kl_road_project)
        assert donor_informed_role_keys(step), "donor add must auto-populate the informed cast"

        # Listed by GET.
        got = client.get(f"/api/v1/projects/{kl_road_project.project_id}/donors")
        assert got.status_code == 200
        assert donor_org_id in [d["organization_id"] for d in got.json()]

        # Remove — 204 + row gone.
        rem = client.delete(f"/api/v1/projects/{kl_road_project.project_id}/donors/{donor_org_id}")
        assert rem.status_code == 204, rem.text
        assert db.get(ProjectDonor, (kl_road_project.project_id, donor_org_id)) is None
    finally:
        app.dependency_overrides.clear()
        db.execute(delete(ProjectDonor).where(ProjectDonor.organization_id == donor_org_id))
        org = db.get(Organization, donor_org_id)
        if org:
            db.delete(org)
        db.commit()


# ── R2: legacy-donor fallback (M1a) + endpoint project-scope (M1b) ────────────

def test_project_donor_org_ids_counts_legacy_org_role(db, kl_road_project):
    """M1a: a donor represented ONLY as a legacy org_role='donor' link (no project_donors
    row) is still counted. The predicate feeds the informed-cast pre-fill, and go-live's B1
    reads it for a 'donor' slot on a project that predates the catalog."""
    from ticketing.models.project import ProjectDonor, ProjectOrganization

    # Remove KL Road's dedicated ProjectDonor rows so ADB is present ONLY via the legacy
    # org_role='donor' link (the seed sets both). No commit — restored in finally.
    saved = db.execute(
        select(ProjectDonor).where(ProjectDonor.project_id == kl_road_project.project_id)
    ).scalars().all()
    saved_keys = [(r.project_id, r.organization_id) for r in saved]
    try:
        for r in saved:
            db.delete(r)
        db.flush()
        # ADB is still linked as org_role='donor' (ProjectOrganization) → must still count.
        assert ORG_ADB in project_donor_org_ids(db, kl_road_project.project_id)
        # And the organization gate still runs (B1 — A5 was deleted 2026-08-04).
        report = go_live_svc.evaluate_go_live(db, kl_road_project.project_id)
        assert any(c.id == "B1" for c in report.checks)
    finally:
        for pid, oid in saved_keys:
            if db.get(ProjectDonor, (pid, oid)) is None:
                db.add(ProjectDonor(project_id=pid, organization_id=oid))
        db.flush()


def test_donor_endpoint_rejects_foreign_project_admin(db, kl_road_project):
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.services.admin_access import AdminScopeRow

    def scope(project_id: str) -> AdminScopeRow:
        return AdminScopeRow(
            admin_scope_id=str(uuid.uuid4()), user_id="pa@grm.local", role_key="project_admin",
            country_code="NP", project_id=project_id, organization_id=None, package_id=None,
            workflow_track="standard",
        )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        # project_admin scoped to a DIFFERENT project → 403 on KL Road's donor endpoint.
        app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
            user_id="pa@grm.local", role_keys=["project_admin"],
            admin_scopes=[scope("SOME_OTHER_PROJECT")],
        )
        client = TestClient(app)
        res = client.post(f"/api/v1/projects/{kl_road_project.project_id}/donors/{ORG_ADB}")
        assert res.status_code == 403, res.text
        assert "administer this project" in res.text

        # project_admin scoped to KL Road → passes the scope gate (not 403).
        app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
            user_id="pa@grm.local", role_keys=["project_admin"],
            admin_scopes=[scope(kl_road_project.project_id)],
        )
        client = TestClient(app)
        res2 = client.post(f"/api/v1/projects/{kl_road_project.project_id}/donors/{ORG_ADB}")
        assert res2.status_code != 403, res2.text
    finally:
        app.dependency_overrides.clear()
        db.rollback()  # discard any donor mutation the second call committed


def test_add_donor_endpoint_rejects_non_donor_org(db, kl_road_project):
    client, app = _super_admin_client(db)
    try:
        # DOR is government — not a valid donor.
        res = client.post(f"/api/v1/projects/{kl_road_project.project_id}/donors/{ORG_DOR}")
        assert res.status_code == 422, res.text
        assert "donor-category" in res.text
    finally:
        app.dependency_overrides.clear()


def test_donor_cast_on_standard_ticket_but_suppressed_on_seah(ctx):
    """A donor officer is added to a STANDARD ticket's informed cast, but receives NOTHING
    on a SEAH ticket (the final-step guardrail is standard-track only)."""
    donor_uid = f"donor-{uuid.uuid4().hex[:8]}@grm.local"
    # Province-wide donor scope covering the ticket's district (P1 ⊇ P1_JHA_BIR).
    ctx.add_scope(
        donor_uid,
        role_key=DONOR_ROLE,
        organization_id=ORG_DOR,
        location_code="P1",
        project_code="KL_ROAD",
        includes_children=True,
    )

    step = _fake_final_step([DONOR_ROLE])

    std = _make_ticket(ctx, is_seah=False)
    _apply_step_tier_roles(ctx.db, std, step)
    ctx.db.flush()
    assert _donor_is_viewer(ctx.db, std.ticket_id, donor_uid) is True

    seah = _make_ticket(ctx, is_seah=True)
    _apply_step_tier_roles(ctx.db, seah, step)
    ctx.db.flush()
    assert _donor_is_viewer(ctx.db, seah.ticket_id, donor_uid) is False, (
        "SEAH leak: donor tier must never be cast on a SEAH ticket"
    )


# ── Project-actors role sync (implementing agency + donors are actor roles now) ──

def test_participant_role_sync(db):
    """Setting the 'Implementing Agency' / 'Donor' role in the Project-actors table syncs the
    dedicated implementing_agency_org_id / project_donors fields (the separate panel retired),
    and rejects an org that is invalid for the role."""
    from fastapi import HTTPException

    from ticketing.api.routers.locations import _sync_participant_role
    from ticketing.models.project import ProjectDonor

    proj = Project(
        project_id=f"sync-{uuid.uuid4().hex[:8]}", country_code="NP",
        short_code=f"SYNC{uuid.uuid4().hex[:4].upper()}", name="Sync Test",
    )
    db.add(proj)
    db.commit()
    try:
        # DOR (government) → implementing_agency stamps the dedicated field; clearing reverts.
        _sync_participant_role(db, proj, ORG_DOR, None, "implementing_agency")
        assert proj.implementing_agency_org_id == ORG_DOR
        _sync_participant_role(db, proj, ORG_DOR, "implementing_agency", None)
        assert proj.implementing_agency_org_id is None

        # ADB (donor) → donor creates the ProjectDonor row; removing the role deletes it.
        _sync_participant_role(db, proj, ORG_ADB, None, "donor")
        assert db.get(ProjectDonor, (proj.project_id, ORG_ADB)) is not None
        _sync_participant_role(db, proj, ORG_ADB, "donor", None)
        assert db.get(ProjectDonor, (proj.project_id, ORG_ADB)) is None

        # A donor org cannot be the implementing agency (validation preserved).
        with pytest.raises(HTTPException) as exc:
            _sync_participant_role(db, proj, ORG_ADB, None, "implementing_agency")
        assert exc.value.status_code == 422
    finally:
        db.execute(delete(ProjectDonor).where(ProjectDonor.project_id == proj.project_id))
        obj = db.get(Project, proj.project_id)
        if obj:
            db.delete(obj)
        db.commit()
