"""OC-04 — chart-driven behaviors + SEAH leak-proofing (doc 16 §5/§6).

Integration (@pytest.mark.integration, live seeded DB). The two SEAH-leak assertions are
the headline acceptance: (1) a non-SEAH supervisor of a SEAH officer sees NONE of their
SEAH tickets in Watching (§5.3); (2) escalating a SEAH ticket notifies a supervisor only
if they independently hold a SEAH role (§5.5).
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from ticketing.api.dependencies import CurrentUser

pytestmark = pytest.mark.integration

_ROLE_STD = "site_safeguards_focal_person"
_ROLE_L2 = "pd_piu_safeguards_focal"
_ROLE_SEAH = "seah_national_officer"


def _db():
    from ticketing.models.base import SessionLocal
    return SessionLocal()


# ── §5.4 prefer-own-office ranking ───────────────────────────────────────────

def test_prefer_own_office_ranking(ctx):
    """Among scope-matched candidates, the officer whose office territory covers the ticket
    location is chosen even when more loaded; when neither covers, least-loaded wins."""
    from ticketing.engine.workflow_engine import auto_assign_officer
    from ticketing.models.country import Location
    from ticketing.models.organization import Organization
    from ticketing.models.officer_position import OfficerPosition
    from ticketing.models.position_type import PositionType

    db = ctx.db
    sfx = uuid.uuid4().hex[:6].upper()
    loc = f"TL_{sfx}"  # a self-contained location so the org territory FK is satisfied
    covering_org = f"COV_{sfx}"
    a = f"cov-a-{sfx}@grm.local"   # covers (position at covering_org) — but heavily loaded
    b = f"cov-b-{sfx}@grm.local"   # does not cover — idle
    pt_id = db.execute(sa.select(PositionType.position_type_id)).scalars().first()
    try:
        db.add(Location(location_code=loc, country_code="NP", level_number=2, is_active=True))
        db.flush()
        # An org whose territory covers the ticket location (exact match here).
        db.add(Organization(organization_id=covering_org, name="Covering Office",
                            org_category="government", country_code="NP",
                            territory_location_code=loc, territory_includes_children=True))
        db.flush()
        for uid in (a, b):
            ctx.add_scope(uid, role_key=_ROLE_STD, organization_id="DOR",
                          location_code=loc, project_code="KL_ROAD")
        db.add(OfficerPosition(user_id=a, position_type_id=pt_id,
                              organization_id=covering_org, is_active=True))
        db.flush()
        # Load A up so least-loaded alone would pick B; territory preference must still pick A.
        for _ in range(3):
            ctx.add_open_ticket(a, location_code=loc)

        chosen = auto_assign_officer(_ROLE_STD, "DOR", loc, "KL_ROAD", db)
        assert chosen == a  # covering office wins over lower load
    finally:
        db.execute(sa.delete(OfficerPosition).where(OfficerPosition.user_id == a))
        obj = db.get(Organization, covering_org)
        if obj:
            db.delete(obj)
        db.flush()
        lobj = db.get(Location, loc)
        if lobj:
            db.delete(lobj)
        db.flush()


# ── §5.5 escalation-notify + SEAH suppression (headline) ─────────────────────

def _seah_holder(db, uid: str) -> None:
    from ticketing.models.officer_scope import OfficerScope
    db.add(OfficerScope(scope_id=str(uuid.uuid4()), user_id=uid, role_key=_ROLE_SEAH,
                        organization_id="DOR", location_code="P1_JHA",
                        project_code="KL_ROAD", includes_children=False))
    db.flush()


def test_escalation_supervisor_notify_and_seah_suppression(ctx):
    """§5.5: the resolved supervisor (next-step handler pool) is notified on escalation; on a
    SEAH ticket a non-SEAH supervisor receives NOTHING, a SEAH-holder receives it."""
    from ticketing.engine.escalation import notify_escalation_supervisor
    from ticketing.models.ticket import TicketEvent
    from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

    db = ctx.db
    wf = db.execute(sa.select(WorkflowDefinition).where(
        WorkflowDefinition.workflow_key == "KL_ROAD_STANDARD")).scalar_one()
    steps = db.execute(sa.select(WorkflowStep).where(
        WorkflowStep.workflow_id == wf.workflow_id, WorkflowStep.is_deleted.is_(False))
        .order_by(WorkflowStep.step_order)).scalars().all()
    step1, step2 = steps[0], steps[1]  # supervisor of step1 = step2's handler pool

    sup = f"sup-{uuid.uuid4().hex[:6]}@grm.local"
    # Scope the supervisor at the EXACT ticket location so _scope_candidates matches without
    # relying on the (unseeded) location hierarchy.
    ctx.add_scope(sup, role_key=step2.assigned_role_key, organization_id="DOR",
                  location_code="P1_JHA_BIR", project_code="KL_ROAD")

    def _notices(ticket_id):
        return db.execute(sa.select(sa.func.count()).select_from(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "ESCALATION_SUPERVISOR_NOTICE",
            TicketEvent.assigned_to_user_id == sup)).scalar()

    # (1) standard ticket → supervisor notified
    std = ctx.add_open_ticket(f"oic-{uuid.uuid4().hex[:6]}@grm.local", location_code="P1_JHA_BIR")
    notify_escalation_supervisor(db, std, step1)
    db.flush()
    assert _notices(std.ticket_id) == 1

    # (2) SEAH ticket, non-SEAH supervisor → nothing (leak-proof)
    seah = ctx.add_open_ticket(f"oic2-{uuid.uuid4().hex[:6]}@grm.local", location_code="P1_JHA_BIR")
    seah.is_seah = True
    db.flush()
    notify_escalation_supervisor(db, seah, step1)
    db.flush()
    assert _notices(seah.ticket_id) == 0  # HEADLINE: non-SEAH supervisor receives nothing

    # (3) same SEAH ticket, supervisor now independently holds a SEAH role → notified
    _seah_holder(db, sup)
    notify_escalation_supervisor(db, seah, step1)
    db.flush()
    assert _notices(seah.ticket_id) == 1

    # escalation target/assignment untouched by the notify (side-effect only)
    assert std.current_step_id == step1.step_id  # notify did not advance the step


# ── §5.3 Watching visibility + SEAH leak (headline) ──────────────────────────

def test_watching_reports_visibility_seah_leakproof():
    """§5.3: a supervisor (subtree visibility) sees a report's standard ticket in the queue,
    but a non-SEAH supervisor sees NONE of the report's SEAH tickets; a SEAH-holder does."""
    from fastapi.testclient import TestClient
    from ticketing.api.dependencies import get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.models.officer_position import OfficerPosition
    from ticketing.models.officer_scope import OfficerScope
    from ticketing.models.organization import Organization
    from ticketing.models.position_type import PositionType
    from ticketing.models.ticket import Ticket
    from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

    db = _db()
    sfx = uuid.uuid4().hex[:6].upper()
    sup_org, sub_org = f"SUP_{sfx}", f"SUB_{sfx}"
    sup_user = f"sv-{sfx}@grm.local"
    sub_user = f"rp-{sfx}@grm.local"
    created_tickets: list[str] = []
    try:
        # org tree: SUP_ORG → SUB_ORG
        db.add(Organization(organization_id=sup_org, name="Sup Office", org_category="government", country_code="NP"))
        db.add(Organization(organization_id=sub_org, name="Sub Office", org_category="government",
                            parent_organization_id=sup_org, country_code="NP"))
        # a subtree-visibility position type
        pt = PositionType(position_key=f"sv_pt_{sfx.lower()}", display_name="Supervisor Position",
                          default_role_key=_ROLE_L2, visibility_mode="subtree", workflow_track="standard")
        db.add(pt)
        db.flush()
        db.add(OfficerPosition(user_id=sup_user, position_type_id=pt.position_type_id,
                              organization_id=sup_org, is_active=True))
        db.add(OfficerPosition(user_id=sub_user, position_type_id=pt.position_type_id,
                              organization_id=sub_org, is_active=True))
        # supervisor needs an officer_scope to enter the scoped (non-admin) query branch
        db.add(OfficerScope(scope_id=str(uuid.uuid4()), user_id=sup_user, role_key=_ROLE_L2,
                            organization_id="DOR", location_code="P1_JHA", project_code="KL_ROAD"))
        # two tickets assigned to the report: one standard, one SEAH
        wf = db.execute(sa.select(WorkflowDefinition).where(
            WorkflowDefinition.workflow_key == "KL_ROAD_STANDARD")).scalar_one()
        step = db.execute(sa.select(WorkflowStep).where(WorkflowStep.workflow_id == wf.workflow_id)
                          .order_by(WorkflowStep.step_order).limit(1)).scalar_one()
        for is_seah in (False, True):
            tid = str(uuid.uuid4())
            created_tickets.append(tid)
            db.add(Ticket(ticket_id=tid, grievance_id=f"grv-{uuid.uuid4().hex[:8]}",
                          organization_id="DOR", location_code="P1_JHA_BIR", project_code="KL_ROAD",
                          current_workflow_id=wf.workflow_id, current_step_id=step.step_id,
                          assigned_to_user_id=sub_user, status_code="OPEN", is_seah=is_seah,
                          is_deleted=False, sla_breached=False, priority="NORMAL"))
        db.commit()

        def _visible_ids(role_keys):
            def _override():
                return CurrentUser(user_id=sup_user, role_keys=role_keys, organization_id="DOR")
            s = _db()

            def _dbov():
                yield s
            app.dependency_overrides[get_authenticated_user] = _override
            app.dependency_overrides[get_db] = _dbov
            try:
                res = TestClient(app).get("/api/v1/tickets?limit=200")
                assert res.status_code == 200, res.text
                return {t["ticket_id"] for t in res.json().get("items", res.json())}
            finally:
                app.dependency_overrides.clear()
                s.close()

        std_tid, seah_tid = created_tickets
        # non-SEAH supervisor: sees the report's standard ticket, NOT the SEAH one
        seen = _visible_ids([_ROLE_L2])
        assert std_tid in seen           # §5.3 subtree visibility works
        assert seah_tid not in seen      # HEADLINE: no SEAH leak through the reporting line
        # supervisor who independently holds a SEAH role: sees the SEAH ticket too
        seen_seah = _visible_ids([_ROLE_L2, _ROLE_SEAH])
        assert seah_tid in seen_seah
    finally:
        s = _db()
        s.execute(sa.delete(Ticket).where(Ticket.ticket_id.in_(created_tickets)))
        s.execute(sa.delete(OfficerPosition).where(OfficerPosition.user_id.in_([sup_user, sub_user])))
        s.execute(sa.delete(OfficerScope).where(OfficerScope.user_id == sup_user))
        for pk in db.execute(sa.select(PositionType).where(PositionType.position_key == f"sv_pt_{sfx.lower()}")).scalars().all():
            s.delete(s.get(PositionType, pk.position_type_id))
        for oid in (sub_org, sup_org):
            o = s.get(Organization, oid)
            if o:
                s.delete(o)
        s.commit()
        s.close()
        db.close()


# ── §5.1 display ─────────────────────────────────────────────────────────────

def test_visible_report_ids_bounded_by_visibility_mode():
    """visible_report_user_ids honors none/direct_reports/subtree."""
    from ticketing.services.chart_behaviors import visible_report_user_ids
    from ticketing.models.officer_position import OfficerPosition
    from ticketing.models.organization import Organization
    from ticketing.models.position_type import PositionType

    db = _db()
    sfx = uuid.uuid4().hex[:6].upper()
    root, kid, grandkid = f"VR_{sfx}", f"VRK_{sfx}", f"VRG_{sfx}"
    boss = f"boss-{sfx}@grm.local"
    r1 = f"r1-{sfx}@grm.local"
    r2 = f"r2-{sfx}@grm.local"
    try:
        db.add(Organization(organization_id=root, name="R", org_category="government", country_code="NP"))
        db.add(Organization(organization_id=kid, name="K", org_category="government", parent_organization_id=root, country_code="NP"))
        db.add(Organization(organization_id=grandkid, name="G", org_category="government", parent_organization_id=kid, country_code="NP"))
        pt_sub = PositionType(position_key=f"vr_sub_{sfx.lower()}", display_name="Sub", default_role_key=_ROLE_L2, visibility_mode="subtree")
        pt_none = PositionType(position_key=f"vr_none_{sfx.lower()}", display_name="None", default_role_key=_ROLE_L2, visibility_mode="none")
        db.add_all([pt_sub, pt_none]); db.flush()
        db.add(OfficerPosition(user_id=r1, position_type_id=pt_sub.position_type_id, organization_id=kid, is_active=True))
        db.add(OfficerPosition(user_id=r2, position_type_id=pt_sub.position_type_id, organization_id=grandkid, is_active=True))
        db.flush()
        # boss with subtree at root → sees r1 (kid) and r2 (grandkid)
        db.add(OfficerPosition(user_id=boss, position_type_id=pt_sub.position_type_id, organization_id=root, is_active=True)); db.flush()
        assert visible_report_user_ids(db, boss) >= {r1, r2}
        # swap boss to a none-visibility position → sees nobody
        db.execute(sa.delete(OfficerPosition).where(OfficerPosition.user_id == boss))
        db.add(OfficerPosition(user_id=boss, position_type_id=pt_none.position_type_id, organization_id=root, is_active=True)); db.flush()
        assert visible_report_user_ids(db, boss) == set()
    finally:
        db.rollback()
        db.close()
