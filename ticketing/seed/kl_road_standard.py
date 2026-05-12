"""
Seed data: KL Road Standard 4-level GRM workflow.

Creates:
  - Organization: DOR (Department of Roads), ADB
  - Locations: Province 1 + KL Road districts
  - Roles: GRM catalog (ticketing.constants.grm_role_catalog) upserted into ticketing.roles
  - Workflow: KL_ROAD_STANDARD (4 levels matching Escalation_rules.md)
  - Workflow assignment: DOR + Province 1 + KL_ROAD → standard workflow
  - Settings: integration URLs

Run standalone:
  python -m ticketing.seed.kl_road_standard

Or call seed_standard() from mock_tickets.py.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.country import Location
from ticketing.models.organization import Organization
from ticketing.models.project import Project
from ticketing.models.settings import Settings
from ticketing.models.workflow import WorkflowAssignment, WorkflowDefinition, WorkflowStep
from ticketing.seed.grm_roles import upsert_grm_roles

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


# ── Master IDs (stable across seed runs) ─────────────────────────────────────
# Using fixed UUIDs so re-runs are idempotent (upsert by PK)

ORG_DOR_ID = "DOR"
ORG_ADB_ID = "ADB"

# Real Nepal location codes matching the imported geodata (ticketing.locations)
LOC_PROVINCE1_CODE = "NP_P1"    # Koshi Province (Province 1)
LOC_MORANG_CODE    = "NP_D006"  # Morang District
LOC_SUNSARI_CODE   = "NP_D011"  # Sunsari District
LOC_JHAPA_CODE     = "NP_D004"  # Jhapa District

WORKFLOW_STANDARD_ID = "00000000-0000-0000-0001-000000000001"

STEP_L1_ID = "00000000-0000-0000-0001-000000000011"
STEP_L2_ID = "00000000-0000-0000-0001-000000000012"
STEP_L3_ID = "00000000-0000-0000-0001-000000000013"
STEP_L4_ID = "00000000-0000-0000-0001-000000000014"

ASSIGNMENT_STANDARD_ID          = "00000000-0000-0000-0001-000000000021"
# Fallback: location=None catches district-level tickets (NP_D006 etc.) that
# don't match the province-scoped assignment. resolve_workflow() tries None
# after the specific location code, so this fires for all DOR/KL_ROAD tickets.
ASSIGNMENT_STANDARD_FALLBACK_ID = "00000000-0000-0000-0001-000000000022"


def seed_organizations(db: Session) -> None:
    orgs = [
        Organization(
            organization_id=ORG_DOR_ID,
            name="Department of Roads (DOR)",
            country_code="NP",
            is_active=True,
        ),
        Organization(
            organization_id=ORG_ADB_ID,
            name="Asian Development Bank (ADB)",
            country_code="NP",
            is_active=True,
        ),
    ]
    for org in orgs:
        existing = db.get(Organization, org.organization_id)
        if not existing:
            db.add(org)
            logger.info("  + organization: %s", org.organization_id)
        else:
            logger.info("  = organization already exists: %s", org.organization_id)
    db.flush()


def seed_locations(db: Session) -> None:
    """
    Verify that the KL Road locations exist in ticketing.locations.
    Locations are loaded from the Nepal geodata CSV/JSON import — this function
    does NOT insert them (they have a different schema from the old placeholder model).
    Missing codes indicate the import script hasn't been run.
    """
    required = [LOC_PROVINCE1_CODE, LOC_MORANG_CODE, LOC_SUNSARI_CODE, LOC_JHAPA_CODE]
    for code in required:
        existing = db.get(Location, code)
        if existing:
            logger.info("  = location OK: %s", code)
        else:
            logger.warning(
                "  ! location NOT found: %s — run import_locations_csv.py first", code
            )


def seed_roles(db: Session) -> None:
    """Seed or refresh all GRM roles from ticketing.constants.grm_role_catalog."""
    upsert_grm_roles(db)


def seed_standard_workflow(db: Session) -> None:
    """Seed KL_ROAD_STANDARD 4-level workflow (Escalation_rules.md)."""
    existing = db.get(WorkflowDefinition, WORKFLOW_STANDARD_ID)
    if existing:
        logger.info("  = workflow already exists: KL_ROAD_STANDARD")
        return

    workflow = WorkflowDefinition(
        workflow_id=WORKFLOW_STANDARD_ID,
        workflow_key="KL_ROAD_STANDARD",
        display_name="KL Road – 4-Level Standard GRM Workflow",
        description=(
            "Site (L1) → PD/PIU (L2) → GRC (L3) → Legal (L4)\n"
            "Time-based escalation per ADB Loan 52097-003 requirements."
        ),
        workflow_type="STANDARD",
    )
    db.add(workflow)
    logger.info("  + workflow: KL_ROAD_STANDARD")

    steps = [
        WorkflowStep(
            step_id=STEP_L1_ID,
            workflow_id=WORKFLOW_STANDARD_ID,
            step_order=1,
            step_key="LEVEL_1_SITE",
            display_name="Level 1 – Site Safeguards",
            assigned_role_key="site_safeguards_focal_person",
            supervisor_role="pd_piu_safeguards_focal",
            informed_roles=[],
            observer_roles=[],
            informed_pii_access=False,
            stakeholders=["Contractor", "CSC (Construction Supervision Consultant)", "Site Project Office"],
            response_time_hours=24,
            resolution_time_days=2,
            expected_actions=[
                "Acknowledge grievance within 24 hours",
                "Conduct initial assessment at site",
                "Attempt basic resolution",
                "Document actions taken and outcome",
            ],
        ),
        WorkflowStep(
            step_id=STEP_L2_ID,
            workflow_id=WORKFLOW_STANDARD_ID,
            step_order=2,
            step_key="LEVEL_2_PIU",
            display_name="Level 2 – PD/PIU Safeguards",
            assigned_role_key="pd_piu_safeguards_focal",
            supervisor_role="adb_national_project_director",
            informed_roles=[],
            observer_roles=[],
            informed_pii_access=False,
            stakeholders=["Project Directorate (PD)", "Project Implementation Unit (PIU)"],
            response_time_hours=24,
            resolution_time_days=7,
            expected_actions=[
                "Review Level 1 actions and findings",
                "Coordinate with relevant departments",
                "Conduct detailed investigation",
                "Prepare and submit resolution proposal",
            ],
        ),
        WorkflowStep(
            step_id=STEP_L3_ID,
            workflow_id=WORKFLOW_STANDARD_ID,
            step_order=3,
            step_key="LEVEL_3_GRC",
            display_name="Level 3 – Grievance Redress Committee (GRC)",
            assigned_role_key="grc_chair",
            supervisor_role="adb_hq_safeguards",
            informed_roles=["grc_member"],   # GRC members are standing Informed at L3
            observer_roles=[],
            informed_pii_access=False,
            stakeholders=[
                "GRC (all members)",
                "PIU",
                "Site Office",
                "Affected Persons / Community Representatives",
            ],
            response_time_hours=24,
            resolution_time_days=15,
            expected_actions=[
                "GRC Chair convenes formal hearing (notifies all GRC members)",
                "Conduct stakeholder consultation with affected persons",
                "GRC reviews evidence and L1/L2 findings",
                "GRC Chair records decision and recommended resolution",
                "Notify complainant of GRC outcome",
            ],
        ),
        WorkflowStep(
            step_id=STEP_L4_ID,
            workflow_id=WORKFLOW_STANDARD_ID,
            step_order=4,
            step_key="LEVEL_4_LEGAL",
            display_name="Level 4 – Legal Institutions",
            assigned_role_key="adb_hq_safeguards",
            supervisor_role=None,            # no supervisor at L4
            informed_roles=[],
            observer_roles=[],
            informed_pii_access=False,
            stakeholders=[
                "Legal Institutions",
                "GRC",
                "PIU",
                "Site Office",
                "Affected Persons",
            ],
            response_time_hours=None,        # no specific timeline at L4
            resolution_time_days=None,       # legal process — no auto-escalation
            expected_actions=[
                "Refer case to appropriate legal institution",
                "Support legal review process",
                "Court proceedings if necessary",
                "Document legal resolution",
            ],
        ),
    ]
    for step in steps:
        db.add(step)
        logger.info("  + step: %s (order=%d)", step.step_key, step.step_order)

    db.flush()


def seed_workflow_assignment(db: Session) -> None:
    """Map DOR + KL_ROAD + NORMAL → standard workflow (two rows for coverage).

    Row 1: province-scoped (NP_P1) — preferred match for province-level tickets.
    Row 2: location=None fallback — catches district/municipality-level tickets
           (NP_D006, NP_D011, NP_D004 etc.) that don't match the province row.
           resolve_workflow() tries None after the specific location code.
    """
    existing = db.get(WorkflowAssignment, ASSIGNMENT_STANDARD_ID)
    if not existing:
        db.add(WorkflowAssignment(
            assignment_id=ASSIGNMENT_STANDARD_ID,
            organization_id=ORG_DOR_ID,
            location_code=LOC_PROVINCE1_CODE,
            project_code="KL_ROAD",
            priority="NORMAL",
            workflow_id=WORKFLOW_STANDARD_ID,
        ))
        logger.info("  + workflow assignment: DOR + NP_P1 + KL_ROAD + NORMAL → KL_ROAD_STANDARD")
    else:
        logger.info("  = workflow assignment already exists (standard NP_P1)")

    existing_fb = db.get(WorkflowAssignment, ASSIGNMENT_STANDARD_FALLBACK_ID)
    if not existing_fb:
        db.add(WorkflowAssignment(
            assignment_id=ASSIGNMENT_STANDARD_FALLBACK_ID,
            organization_id=ORG_DOR_ID,
            location_code=None,          # wildcard: any location under DOR
            project_code="KL_ROAD",
            priority="NORMAL",
            workflow_id=WORKFLOW_STANDARD_ID,
        ))
        logger.info("  + workflow assignment: DOR + (any loc) + KL_ROAD + NORMAL → KL_ROAD_STANDARD (fallback)")
    else:
        logger.info("  = workflow assignment already exists (standard fallback)")

    db.flush()


def seed_settings(db: Session) -> None:
    """Seed default integration settings."""
    from ticketing.config.settings import get_settings
    s = get_settings()

    defaults = {
        "messaging_api_base_url": {"url": s.backend_grievance_base_url},
        "orchestrator_base_url": {"url": s.orchestrator_base_url},
        "report_schedule": {
            "frequency": "quarterly",
            "day_of_month": 5,
            "recipients_by_role": [
                "adb_national_project_director",
                "adb_hq_safeguards",
                "adb_hq_project",
            ],
        },
        "sla_watchdog_interval_minutes": {"value": 15},
        # ── Tier-based notification rules (spec 12) ───────────────────────────
        "notification_rules": {
            "standard": {
                "ticket_created":   {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": [],        "observer": []},
                "ticket_escalated": {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": ["email"], "observer": []},
                "ticket_resolved":  {"actor": ["app", "email"], "supervisor": ["app"],          "informed": [],        "observer": []},
                "sla_breach":       {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": ["email"], "observer": []},
                "grc_convened":     {"actor": ["app", "email"], "supervisor": ["app"],          "informed": ["app"],   "observer": []},
                "assignment":       {"actor": ["sms", "app"],   "supervisor": [],               "informed": [],        "observer": []},
                "quarterly_report": {"actor": [],               "supervisor": ["email"],        "informed": ["email"], "observer": []},
            },
            "seah": {
                "ticket_created":   {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": [],        "observer": []},
                "ticket_escalated": {"actor": ["app"],          "supervisor": ["app"],          "informed": [],        "observer": []},
                "ticket_resolved":  {"actor": ["app"],          "supervisor": ["app"],          "informed": [],        "observer": []},
                "sla_breach":       {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": [],        "observer": []},
                "assignment":       {"actor": ["app"],          "supervisor": [],               "informed": [],        "observer": []},
            },
        },
        "complainant_notifications": {
            "ticket_created":      {"chatbot": True, "sms_fallback": True},
            "ticket_acknowledged": {"chatbot": True, "sms_fallback": True},
            "ticket_resolved":     {"chatbot": True, "sms_fallback": True},
            "reply_sent":          {"chatbot": True, "sms_fallback": True},
        },
    }
    for key, value in defaults.items():
        existing = db.get(Settings, key)
        if not existing:
            db.add(Settings(key=key, value=value))
            logger.info("  + setting: %s", key)
        else:
            logger.info("  = setting already exists: %s", key)
    db.flush()


def seed_project(db: Session) -> None:
    """
    Ensure the KL_ROAD Project record exists with the correct chatbot_base_url.

    project.chatbot_base_url tells the ticketing API where to proxy complainant
    edits for this project.  In a multi-country deployment each project gets its
    own local chatbot URL.  'http://backend:5001' is the Docker-network alias for
    the Nepal chatbot backend.
    """
    from sqlalchemy import select
    existing = db.execute(
        select(Project).where(Project.short_code == "KL_ROAD")
    ).scalar_one_or_none()

    if existing:
        # Backfill chatbot_base_url if it was seeded before this field existed
        if not existing.chatbot_base_url:
            existing.chatbot_base_url = "http://backend:5001"
            logger.info("  ~ project KL_ROAD: backfilled chatbot_base_url")
        else:
            logger.info("  = project already exists: KL_ROAD")
    else:
        db.add(Project(
            short_code="KL_ROAD",
            country_code="NP",
            name="Kakarbhitta–Laukahi Road (ADB 52097-003)",
            description="KL Road GRM project — Province 1, Nepal",
            chatbot_base_url="http://backend:5001",
            is_active=True,
        ))
        logger.info("  + project: KL_ROAD")
    db.flush()


def seed_standard(db: Session | None = None) -> None:
    """Run all standard seed steps inside a single transaction."""
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        logger.info("Seeding KL Road Standard workflow...")
        seed_organizations(db)
        seed_locations(db)
        seed_roles(db)
        seed_standard_workflow(db)
        seed_workflow_assignment(db)
        seed_project(db)
        seed_settings(db)
        db.commit()
        logger.info("Standard seed complete.")
    except Exception:
        db.rollback()
        logger.exception("Standard seed FAILED — rolled back")
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed_standard()
