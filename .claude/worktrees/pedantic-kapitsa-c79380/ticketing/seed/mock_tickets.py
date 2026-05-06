"""
Mock tickets for May 10 demo.

Demo scenario 1 — Standard GRM:
  Dust / health complaint along KL Road (L1 → L2 → L3 in progress)

Demo scenario 2 — SEAH:
  Harassment by construction worker (L1 investigation in progress)

Also seeds a few supporting tickets to make the queue look realistic.

Run full seed (workflows + tickets):
  python -m ticketing.seed.mock_tickets

Reset and re-seed:
  python -m ticketing.seed.mock_tickets --reset
"""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.user import UserRole
from ticketing.seed.kl_road_seah import (
    STEP_SEAH_L1_ID,
    STEP_SEAH_L2_ID,
    WORKFLOW_SEAH_ID,
    seed_seah,
)
from ticketing.seed.kl_road_standard import (
    LOC_JHAPA_CODE,
    LOC_MORANG_CODE,
    LOC_PROVINCE1_CODE,
    LOC_SUNSARI_CODE,
    ORG_ADB_ID,
    ORG_DOR_ID,
    STEP_L1_ID,
    STEP_L2_ID,
    STEP_L3_ID,
    STEP_L4_ID,
    WORKFLOW_STANDARD_ID,
    seed_standard,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ago(days: int = 0, hours: int = 0) -> datetime:
    return _now() - timedelta(days=days, hours=hours)


def _id() -> str:
    return str(uuid.uuid4())


# ── Mock officer user IDs (will be replaced by Cognito subs in production) ────

OFFICER_SITE_L1 = "mock-officer-site-l1"
OFFICER_PIU_L2 = "mock-officer-piu-l2"
OFFICER_GRC_CHAIR = "mock-officer-grc-chair"
OFFICER_GRC_MEMBER_1 = "mock-officer-grc-member-1"
OFFICER_GRC_MEMBER_2 = "mock-officer-grc-member-2"
OFFICER_SEAH_NATIONAL = "mock-officer-seah-national"
OFFICER_SEAH_HQ = "mock-officer-seah-hq"
OFFICER_ADB_OBSERVER = "mock-officer-adb-observer"
OFFICER_SUPER_ADMIN = "mock-super-admin"


def seed_mock_officers(db: Session) -> None:
    """Assign GRM roles to mock officer user IDs."""
    from sqlalchemy import select
    from ticketing.models.user import Role as RoleModel

    def _get_role_id(role_key: str) -> str | None:
        r = db.execute(
            select(RoleModel).where(RoleModel.role_key == role_key)
        ).scalar_one_or_none()
        return r.role_id if r else None

    assignments = [
        (OFFICER_SUPER_ADMIN,    "super_admin",                 ORG_DOR_ID, None),
        (OFFICER_SITE_L1,        "site_safeguards_focal_person", ORG_DOR_ID, LOC_MORANG_CODE),
        (OFFICER_PIU_L2,         "pd_piu_safeguards_focal",      ORG_DOR_ID, LOC_PROVINCE1_CODE),
        (OFFICER_GRC_CHAIR,      "grc_chair",                   ORG_DOR_ID, LOC_PROVINCE1_CODE),
        (OFFICER_GRC_MEMBER_1,   "grc_member",                  ORG_DOR_ID, LOC_PROVINCE1_CODE),
        (OFFICER_GRC_MEMBER_2,   "grc_member",                  ORG_DOR_ID, LOC_PROVINCE1_CODE),
        (OFFICER_SEAH_NATIONAL,  "seah_national_officer",       ORG_DOR_ID, LOC_PROVINCE1_CODE),
        (OFFICER_SEAH_HQ,        "seah_hq_officer",             ORG_ADB_ID, None),
        (OFFICER_ADB_OBSERVER,   "adb_hq_safeguards",           ORG_ADB_ID, None),
    ]

    for user_id, role_key, org_id, loc_code in assignments:
        role_id = _get_role_id(role_key)
        if not role_id:
            logger.warning("  ! role not found: %s — skipping %s", role_key, user_id)
            continue
        # Check if already assigned
        existing = db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.organization_id == org_id,
            )
        ).scalar_one_or_none()
        if not existing:
            ur = UserRole(
                user_id=user_id,
                role_id=role_id,
                organization_id=org_id,
                location_code=loc_code,
            )
            db.add(ur)
            logger.info("  + officer role: %s → %s @ %s", user_id, role_key, org_id)
        else:
            logger.info("  = officer role already assigned: %s → %s", user_id, role_key)
    db.flush()


def _make_ticket(
    grievance_id: str,
    workflow_id: str,
    step_id: str | None,
    is_seah: bool,
    status_code: str,
    priority: str,
    location_code: str,
    project_code: str,
    summary: str,
    categories: str,
    grievance_location: str,
    assigned_to: str | None,
    created_days_ago: int,
    sla_breached: bool = False,
    complainant_id: str | None = None,
    session_id: str | None = None,
) -> Ticket:
    created_at = _ago(days=created_days_ago)
    return Ticket(
        ticket_id=_id(),
        grievance_id=grievance_id,
        complainant_id=complainant_id,
        session_id=session_id,
        chatbot_id="nepal_grievance_bot",
        grievance_summary=summary,
        grievance_categories=categories,
        grievance_location=grievance_location,
        country_code="NP",
        organization_id=ORG_DOR_ID,
        location_code=location_code,
        project_code=project_code,
        status_code=status_code,
        current_workflow_id=workflow_id,
        current_step_id=step_id,
        priority=priority,
        is_seah=is_seah,
        assigned_to_user_id=assigned_to,
        sla_breached=sla_breached,
        is_deleted=False,
        step_started_at=_ago(days=created_days_ago - 1),
        created_at=created_at,
        updated_at=created_at,
    )


def _event(
    ticket: Ticket,
    event_type: str,
    days_ago: int,
    note: str | None = None,
    old_status: str | None = None,
    new_status: str | None = None,
    step_id: str | None = None,
    old_assigned: str | None = None,
    new_assigned: str | None = None,
    created_by: str | None = None,
    seen: bool = True,
    notify_user_id: str | None = None,
) -> TicketEvent:
    ts = _ago(days=days_ago)
    return TicketEvent(
        event_id=_id(),
        ticket_id=ticket.ticket_id,
        event_type=event_type,
        old_status_code=old_status,
        new_status_code=new_status,
        old_assigned_to=old_assigned,
        new_assigned_to=new_assigned,
        workflow_step_id=step_id,
        note=note,
        payload=None,
        seen=seen,
        assigned_to_user_id=notify_user_id,
        created_by_user_id=created_by,
        created_at=ts,
    )


def seed_mock_tickets(db: Session) -> None:
    """
    Seed demo scenario tickets.

    Scenario 1: Dust / health complaint — currently at L3 (GRC)
    Scenario 2: SEAH harassment — currently at L1 investigation
    Plus 5 supporting tickets at various stages for a realistic queue.
    """

    # ── Scenario 1: Dust / health complaint (at GRC, L3) ─────────────────────
    t_dust = _make_ticket(
        grievance_id="GRV-2025-001",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L3_ID,
        is_seah=False,
        status_code="IN_PROGRESS",  # GRC chair has acknowledged (last event); ready for CONVENE
        priority="HIGH",
        location_code=LOC_MORANG_CODE,
        project_code="KL_ROAD",
        summary="Dust from road construction is entering homes, children are falling sick. Contractor has not implemented any dust suppression measures despite multiple complaints.",
        categories="Environmental Impact, Health and Safety",
        grievance_location="Urlabari, Morang District, Province 1",
        assigned_to=OFFICER_GRC_CHAIR,
        created_days_ago=14,
        sla_breached=False,
        complainant_id="CPL-2025-001",
        session_id="session-demo-dust-001",
    )
    db.add(t_dust)

    dust_events = [
        _event(t_dust, "CREATED", 14, new_status="OPEN", step_id=STEP_L1_ID,
               created_by="system", note="Ticket created from grievance GRV-2025-001"),
        _event(t_dust, "ASSIGNED", 14, new_assigned=OFFICER_SITE_L1, step_id=STEP_L1_ID,
               created_by=OFFICER_SUPER_ADMIN, notify_user_id=OFFICER_SITE_L1, seen=False),
        _event(t_dust, "ACKNOWLEDGED", 13, old_status="OPEN", new_status="IN_PROGRESS",
               step_id=STEP_L1_ID, created_by=OFFICER_SITE_L1,
               note="Visited site. Confirmed dust issue. Notified contractor CSC."),
        _event(t_dust, "ESCALATED", 11, old_status="IN_PROGRESS", new_status="ESCALATED",
               step_id=STEP_L2_ID, created_by=OFFICER_SITE_L1,
               note="Contractor failed to act after 2 days. Auto-escalated to L2 PD/PIU.",
               notify_user_id=OFFICER_PIU_L2, seen=False),
        _event(t_dust, "ACKNOWLEDGED", 10, old_status="ESCALATED", new_status="IN_PROGRESS",
               step_id=STEP_L2_ID, created_by=OFFICER_PIU_L2,
               note="Reviewing L1 findings. Meeting with contractor scheduled."),
        _event(t_dust, "ESCALATED", 7, old_status="IN_PROGRESS", new_status="ESCALATED",
               step_id=STEP_L3_ID, created_by=OFFICER_PIU_L2,
               note="Contractor disputes findings. Contractor-PIU disagreement unresolved after 7 days. Escalating to GRC.",
               notify_user_id=OFFICER_GRC_CHAIR, seen=False),
        _event(t_dust, "ACKNOWLEDGED", 6, old_status="ESCALATED", new_status="IN_PROGRESS",
               step_id=STEP_L3_ID, created_by=OFFICER_GRC_CHAIR,
               note="GRC hearing convened for May 3. All GRC members notified.",
               notify_user_id=OFFICER_GRC_MEMBER_1, seen=False),
        _event(t_dust, "NOTE_ADDED", 3, step_id=STEP_L3_ID, created_by=OFFICER_GRC_MEMBER_1,
               note="Technical assessment confirms dust levels exceed WHO guidelines. Wet-spray twice daily would suffice."),
    ]
    for e in dust_events:
        db.add(e)

    # ── Scenario 2: SEAH harassment (at L1, investigation) ───────────────────
    t_seah = _make_ticket(
        grievance_id="GRV-2025-SEAH-001",
        workflow_id=WORKFLOW_SEAH_ID,
        step_id=STEP_SEAH_L1_ID,
        is_seah=True,
        status_code="IN_PROGRESS",
        priority="HIGH",
        location_code=LOC_SUNSARI_CODE,
        project_code="KL_ROAD",
        summary="Complainant reports verbal harassment and inappropriate physical contact by a construction worker at the road site.",
        categories="SEAH – Harassment",
        grievance_location="Inaruwa, Sunsari District, Province 1",
        assigned_to=OFFICER_SEAH_NATIONAL,
        created_days_ago=5,
        sla_breached=False,
        complainant_id="CPL-2025-SEAH-001",
        session_id="session-demo-seah-001",
    )
    db.add(t_seah)

    seah_events = [
        _event(t_seah, "CREATED", 5, new_status="OPEN", step_id=STEP_SEAH_L1_ID,
               created_by="system", note="SEAH ticket created — restricted access"),
        _event(t_seah, "ASSIGNED", 5, new_assigned=OFFICER_SEAH_NATIONAL,
               step_id=STEP_SEAH_L1_ID, created_by=OFFICER_SUPER_ADMIN,
               notify_user_id=OFFICER_SEAH_NATIONAL, seen=False),
        _event(t_seah, "ACKNOWLEDGED", 4, old_status="OPEN", new_status="IN_PROGRESS",
               step_id=STEP_SEAH_L1_ID, created_by=OFFICER_SEAH_NATIONAL,
               note="Contacted complainant confidentially. Safe accommodation arranged. Investigation opened."),
        _event(t_seah, "NOTE_ADDED", 3, step_id=STEP_SEAH_L1_ID, created_by=OFFICER_SEAH_NATIONAL,
               note="Worker identified from site roster. Supervisor interviewed. Incident corroborated by witness."),
        _event(t_seah, "NOTE_ADDED", 2, step_id=STEP_SEAH_L1_ID, created_by=OFFICER_SEAH_NATIONAL,
               note="Complainant requests formal police referral. Escalating to SEAH HQ for authorization."),
    ]
    for e in seah_events:
        db.add(e)

    # ── Supporting tickets: realistic queue ───────────────────────────────────

    # T3: L1 new, unacknowledged (shows red NEW badge)
    t3 = _make_ticket(
        grievance_id="GRV-2025-003",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L1_ID,
        is_seah=False,
        status_code="OPEN",
        priority="NORMAL",
        location_code=LOC_JHAPA_CODE,
        project_code="KL_ROAD",
        summary="Road widening has damaged boundary wall of residential property. Owner requesting compensation.",
        categories="Property Damage, Compensation",
        grievance_location="Birtamod, Jhapa District, Province 1",
        assigned_to=OFFICER_SITE_L1,
        created_days_ago=1,
        complainant_id="CPL-2025-003",
    )
    db.add(t3)
    db.add(_event(t3, "CREATED", 1, new_status="OPEN", step_id=STEP_L1_ID, created_by="system"))
    db.add(_event(t3, "ASSIGNED", 1, new_assigned=OFFICER_SITE_L1, step_id=STEP_L1_ID,
                  notify_user_id=OFFICER_SITE_L1, seen=False))

    # T4: L2 in progress, SLA close
    t4 = _make_ticket(
        grievance_id="GRV-2025-004",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L2_ID,
        is_seah=False,
        status_code="IN_PROGRESS",
        priority="HIGH",
        location_code=LOC_MORANG_CODE,
        project_code="KL_ROAD",
        summary="Blasting noise during nighttime hours is disturbing village residents and livestock. Contractor violating project environmental covenants.",
        categories="Environmental Impact, Noise Pollution",
        grievance_location="Biratnagar outskirts, Morang District",
        assigned_to=OFFICER_PIU_L2,
        created_days_ago=8,
        sla_breached=False,
        complainant_id="CPL-2025-004",
    )
    db.add(t4)
    db.add(_event(t4, "CREATED", 8, new_status="OPEN", step_id=STEP_L1_ID, created_by="system"))
    db.add(_event(t4, "ESCALATED", 5, old_status="IN_PROGRESS", new_status="ESCALATED",
                  step_id=STEP_L2_ID, created_by=OFFICER_SITE_L1))
    db.add(_event(t4, "ACKNOWLEDGED", 4, old_status="ESCALATED", new_status="IN_PROGRESS",
                  step_id=STEP_L2_ID, created_by=OFFICER_PIU_L2,
                  note="Contacted contractor operations manager. Awaiting blast schedule review."))

    # T5: Resolved (shows historical view)
    t5 = _make_ticket(
        grievance_id="GRV-2025-002",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L1_ID,
        is_seah=False,
        status_code="RESOLVED",
        priority="NORMAL",
        location_code=LOC_SUNSARI_CODE,
        project_code="KL_ROAD",
        summary="Access road to farm blocked by construction material stockpile for 3 days.",
        categories="Access Disruption",
        grievance_location="Dharan, Sunsari District, Province 1",
        assigned_to=OFFICER_SITE_L1,
        created_days_ago=20,
        complainant_id="CPL-2025-002",
    )
    db.add(t5)
    db.add(_event(t5, "CREATED", 20, new_status="OPEN", created_by="system"))
    db.add(_event(t5, "ACKNOWLEDGED", 19, old_status="OPEN", new_status="IN_PROGRESS",
                  created_by=OFFICER_SITE_L1))
    db.add(_event(t5, "RESOLVED", 17, old_status="IN_PROGRESS", new_status="RESOLVED",
                  created_by=OFFICER_SITE_L1,
                  note="Contractor removed stockpile within 24 hours. Complainant confirmed access restored."))

    # T6: SLA breached at L1 — shows overdue indicator
    t6 = _make_ticket(
        grievance_id="GRV-2025-005",
        workflow_id=WORKFLOW_STANDARD_ID,
        step_id=STEP_L1_ID,
        is_seah=False,
        status_code="OPEN",
        priority="NORMAL",
        location_code=LOC_PROVINCE1_CODE,
        project_code="KL_ROAD",
        summary="Culvert installation is blocking irrigation channel serving 12 farms. Crops at risk.",
        categories="Agricultural Impact, Water Access",
        grievance_location="Itahari, Sunsari District, Province 1",
        assigned_to=OFFICER_SITE_L1,
        created_days_ago=4,
        sla_breached=True,  # SLA of 2 days breached
        complainant_id="CPL-2025-005",
    )
    db.add(t6)
    db.add(_event(t6, "CREATED", 4, new_status="OPEN", step_id=STEP_L1_ID, created_by="system"))
    db.add(_event(t6, "ASSIGNED", 4, new_assigned=OFFICER_SITE_L1,
                  notify_user_id=OFFICER_SITE_L1, seen=False))

    db.flush()
    logger.info("  + scenario 1 (dust): GRV-2025-001 at L3 GRC")
    logger.info("  + scenario 2 (SEAH): GRV-2025-SEAH-001 at L1 investigation")
    logger.info("  + supporting tickets: GRV-2025-002 through GRV-2025-005")


def seed_all(reset: bool = False) -> None:
    """Full seed: workflows + officers + mock tickets."""
    db = SessionLocal()
    try:
        if reset:
            logger.info("Reset mode: deleting all ticketing.* rows...")
            db.execute(TicketEvent.__table__.delete())
            db.execute(Ticket.__table__.delete())
            db.execute(UserRole.__table__.delete())
            from ticketing.models.workflow import WorkflowAssignment, WorkflowStep, WorkflowDefinition
            from ticketing.models.organization import Organization
            from ticketing.models.user import Role
            from ticketing.models.settings import Settings
            db.execute(WorkflowAssignment.__table__.delete())
            db.execute(WorkflowStep.__table__.delete())
            db.execute(WorkflowDefinition.__table__.delete())
            # Locations live in ticketing.locations (imported geodata) — not reset here.
            # Only reset org/role/settings that are seeded by mock_tickets.
            db.execute(Organization.__table__.delete())
            db.execute(Role.__table__.delete())
            db.execute(Settings.__table__.delete())
            db.commit()
            logger.info("Reset complete.")

        # Seed workflows (each is idempotent)
        seed_standard(db)
        seed_seah(db)

        # Seed mock officers and tickets
        logger.info("Seeding mock officers...")
        seed_mock_officers(db)
        logger.info("Seeding mock tickets (demo scenarios)...")
        seed_mock_tickets(db)

        db.commit()
        logger.info("All seed data committed successfully.")

    except Exception:
        db.rollback()
        logger.exception("Seed FAILED — rolled back")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    reset = "--reset" in sys.argv
    seed_all(reset=reset)
