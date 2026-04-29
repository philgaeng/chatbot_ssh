"""
Seed data: KL Road SEAH (Sexual Exploitation, Abuse and Harassment) workflow.

Creates:
  - Workflow: KL_ROAD_SEAH (2-level SEAH-only workflow)
  - Workflow assignment: DOR + Province 1 + KL_ROAD + priority=SEAH → SEAH workflow

SEAH tickets are invisible to standard officers — enforced at DB query level
via Ticket.is_seah filter in the tickets router (CLAUDE.md SEAH gate).

Run standalone:
  python -m ticketing.seed.kl_road_seah
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.workflow import WorkflowAssignment, WorkflowDefinition, WorkflowStep
from ticketing.seed.kl_road_standard import (
    ORG_DOR_ID,
    LOC_PROVINCE1_CODE,
    seed_organizations,
    seed_locations,
    seed_roles,
    seed_settings,
)

logger = logging.getLogger(__name__)

# ── Stable IDs ────────────────────────────────────────────────────────────────

WORKFLOW_SEAH_ID = "00000000-0000-0000-0002-000000000001"

STEP_SEAH_L1_ID = "00000000-0000-0000-0002-000000000011"
STEP_SEAH_L2_ID = "00000000-0000-0000-0002-000000000012"

ASSIGNMENT_SEAH_ID          = "00000000-0000-0000-0002-000000000021"
ASSIGNMENT_SEAH_FALLBACK_ID = "00000000-0000-0000-0002-000000000022"


def seed_seah_workflow(db: Session) -> None:
    """Seed the KL_ROAD_SEAH 2-level workflow."""
    existing = db.get(WorkflowDefinition, WORKFLOW_SEAH_ID)
    if existing:
        logger.info("  = workflow already exists: KL_ROAD_SEAH")
        return

    workflow = WorkflowDefinition(
        workflow_id=WORKFLOW_SEAH_ID,
        workflow_key="KL_ROAD_SEAH",
        display_name="KL Road – SEAH Restricted Workflow",
        description=(
            "SEAH National Officer → SEAH HQ Officer.\n"
            "Confidential — invisible to all standard GRM roles.\n"
            "Managed by dedicated SEAH officers only."
        ),
        workflow_type="SEAH",
    )
    db.add(workflow)
    logger.info("  + workflow: KL_ROAD_SEAH")

    steps = [
        WorkflowStep(
            step_id=STEP_SEAH_L1_ID,
            workflow_id=WORKFLOW_SEAH_ID,
            step_order=1,
            step_key="SEAH_LEVEL_1_NATIONAL",
            display_name="SEAH Level 1 – National Officer Investigation",
            assigned_role_key="seah_national_officer",
            stakeholders=["SEAH National Officer", "Complainant (confidential)"],
            response_time_hours=24,
            resolution_time_days=7,
            expected_actions=[
                "Acknowledge grievance confidentially within 24 hours",
                "Conduct initial safety assessment for complainant",
                "Open confidential investigation",
                "Document findings — SEAH officers only",
                "Provide interim support / referral if needed",
            ],
        ),
        WorkflowStep(
            step_id=STEP_SEAH_L2_ID,
            workflow_id=WORKFLOW_SEAH_ID,
            step_order=2,
            step_key="SEAH_LEVEL_2_HQ",
            display_name="SEAH Level 2 – HQ Officer Review",
            assigned_role_key="seah_hq_officer",
            stakeholders=["SEAH HQ Officer", "SEAH National Officer", "Legal if required"],
            response_time_hours=24,
            resolution_time_days=15,
            expected_actions=[
                "Review L1 investigation and findings",
                "Escalate to police / legal institutions if criminal",
                "File formal complaint with relevant authority",
                "Document referral and case outcome",
                "Close case with resolution summary",
            ],
        ),
    ]
    for step in steps:
        db.add(step)
        logger.info("  + SEAH step: %s (order=%d)", step.step_key, step.step_order)

    db.flush()


def seed_seah_assignment(db: Session) -> None:
    """Map DOR + KL_ROAD + SEAH priority → SEAH workflow (two rows for coverage).

    Row 1: province-scoped (NP_P1) — preferred match for province-level tickets.
    Row 2: location=None fallback — catches tickets from the sync task which
           passes location_code=None (public.grievances has no location column).
    """
    existing = db.get(WorkflowAssignment, ASSIGNMENT_SEAH_ID)
    if not existing:
        db.add(WorkflowAssignment(
            assignment_id=ASSIGNMENT_SEAH_ID,
            organization_id=ORG_DOR_ID,
            location_code=LOC_PROVINCE1_CODE,
            project_code="KL_ROAD",
            priority="SEAH",
            workflow_id=WORKFLOW_SEAH_ID,
        ))
        logger.info("  + workflow assignment: DOR + NP_P1 + KL_ROAD + SEAH → KL_ROAD_SEAH")
    else:
        logger.info("  = workflow assignment already exists (SEAH NP_P1)")

    existing_fb = db.get(WorkflowAssignment, ASSIGNMENT_SEAH_FALLBACK_ID)
    if not existing_fb:
        db.add(WorkflowAssignment(
            assignment_id=ASSIGNMENT_SEAH_FALLBACK_ID,
            organization_id=ORG_DOR_ID,
            location_code=None,          # wildcard: catches sync-created SEAH tickets
            project_code="KL_ROAD",
            priority="SEAH",
            workflow_id=WORKFLOW_SEAH_ID,
        ))
        logger.info("  + workflow assignment: DOR + (any loc) + KL_ROAD + SEAH → KL_ROAD_SEAH (fallback)")
    else:
        logger.info("  = workflow assignment already exists (SEAH fallback)")

    db.flush()


def seed_seah(db: Session | None = None) -> None:
    """Run all SEAH seed steps. Includes foundation data if not already present."""
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        logger.info("Seeding KL Road SEAH workflow...")
        # Foundation data (idempotent — skips if already seeded by standard)
        seed_organizations(db)
        seed_locations(db)
        seed_roles(db)
        seed_settings(db)
        # SEAH-specific
        seed_seah_workflow(db)
        seed_seah_assignment(db)
        db.commit()
        logger.info("SEAH seed complete.")
    except Exception:
        db.rollback()
        logger.exception("SEAH seed FAILED — rolled back")
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed_seah()
