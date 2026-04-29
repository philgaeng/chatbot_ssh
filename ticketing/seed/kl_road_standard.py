"""
Seed data: KL Road Standard 4-level GRM workflow.

Creates:
  - Organization: DOR (Department of Roads), ADB
  - Locations: Province 1 + KL Road districts
  - Roles: all 12 GRM roles with permissions
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
from ticketing.models.user import Role
from ticketing.models.workflow import WorkflowAssignment, WorkflowDefinition, WorkflowStep

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

ASSIGNMENT_STANDARD_ID = "00000000-0000-0000-0001-000000000021"


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
    """Seed all 12 GRM roles with their permissions."""
    roles_data = [
        {
            "role_key": "super_admin",
            "display_name": "Super Administrator",
            "permissions": ["*"],  # full access
        },
        {
            "role_key": "local_admin",
            "display_name": "Local Administrator",
            "permissions": ["tickets:read", "tickets:write", "users:manage", "settings:write"],
        },
        {
            "role_key": "site_safeguards_focal_person",
            "display_name": "Site Safeguards Focal Person (L1)",
            "permissions": ["tickets:read", "tickets:acknowledge", "tickets:note", "tickets:resolve"],
        },
        {
            "role_key": "pd_piu_safeguards_focal",
            "display_name": "PD/PIU Safeguards Focal Person (L2)",
            "permissions": ["tickets:read", "tickets:acknowledge", "tickets:note", "tickets:escalate", "tickets:resolve"],
        },
        {
            "role_key": "grc_chair",
            "display_name": "GRC Chair (L3 — Convene + Decide)",
            "permissions": ["tickets:read", "tickets:acknowledge", "tickets:note", "tickets:escalate", "tickets:resolve", "grc:convene", "grc:decide"],
        },
        {
            "role_key": "grc_member",
            "display_name": "GRC Member (L3 — Input)",
            "permissions": ["tickets:read", "tickets:note"],
        },
        {
            "role_key": "adb_national_project_director",
            "display_name": "ADB National Project Director (Observer)",
            "permissions": ["tickets:read", "reports:read"],
        },
        {
            "role_key": "adb_hq_safeguards",
            "display_name": "ADB HQ Safeguards (Observer)",
            "permissions": ["tickets:read", "reports:read"],
        },
        {
            "role_key": "adb_hq_project",
            "display_name": "ADB HQ Project (Observer)",
            "permissions": ["tickets:read", "reports:read"],
        },
        {
            "role_key": "seah_national_officer",
            "display_name": "SEAH National Officer",
            "permissions": ["tickets:read", "tickets:acknowledge", "tickets:note", "tickets:escalate", "tickets:resolve", "seah:access"],
        },
        {
            "role_key": "seah_hq_officer",
            "display_name": "SEAH HQ Officer",
            "permissions": ["tickets:read", "tickets:acknowledge", "tickets:note", "tickets:escalate", "tickets:resolve", "seah:access"],
        },
        {
            "role_key": "adb_hq_exec",
            "display_name": "ADB HQ Executive (Senior Oversight)",
            "permissions": ["tickets:read", "reports:read", "seah:access"],
        },
    ]

    from sqlalchemy import select
    from ticketing.models.user import Role as RoleModel

    for rd in roles_data:
        existing = db.execute(
            select(RoleModel).where(RoleModel.role_key == rd["role_key"])
        ).scalar_one_or_none()
        if not existing:
            role = RoleModel(
                role_id=_id(),
                role_key=rd["role_key"],
                display_name=rd["display_name"],
                permissions=rd["permissions"],
            )
            db.add(role)
            logger.info("  + role: %s", rd["role_key"])
        else:
            logger.info("  = role already exists: %s", rd["role_key"])
    db.flush()


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
            stakeholders=[
                "Legal Institutions",
                "GRC",
                "PIU",
                "Site Office",
                "Affected Persons",
            ],
            response_time_hours=None,   # no specific timeline at L4
            resolution_time_days=None,  # legal process — no auto-escalation
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
    """Map DOR + Province 1 + KL_ROAD + NORMAL priority → standard workflow."""
    existing = db.get(WorkflowAssignment, ASSIGNMENT_STANDARD_ID)
    if existing:
        logger.info("  = workflow assignment already exists (standard)")
        return

    assignment = WorkflowAssignment(
        assignment_id=ASSIGNMENT_STANDARD_ID,
        organization_id=ORG_DOR_ID,
        location_code=LOC_PROVINCE1_CODE,
        project_code="KL_ROAD",
        priority="NORMAL",
        workflow_id=WORKFLOW_STANDARD_ID,
    )
    db.add(assignment)
    logger.info("  + workflow assignment: DOR + PROVINCE_1 + KL_ROAD + NORMAL → KL_ROAD_STANDARD")
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
