"""
Grievance sync task — polls public.grievances for newly submitted grievances
and auto-creates ticketing.tickets entries.

Runs every 2 minutes via Celery Beat (see celery_app.py beat_schedule).

Design:
  - Reads public.grievances WHERE is_temporary = false (fully submitted)
  - Skips any grievance_id already in ticketing.tickets (idempotent)
  - Uses grievance_sensitive_issue = True to route to SEAH workflow
  - session_id stored as None — INTEGRATION POINT for session lookup

SEAH INTEGRATION POINT:
  When feat/seah-sensitive-intake is merged, there will be a dedicated
  SEAH submissions table (separate from public.grievances). Add a second
  query block here to sync those as well, also with is_seah=True.

Does NOT join ticketing.* and public.* — two separate queries, compliant
with the "no cross-schema joins" architecture rule.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from celery import shared_task
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowAssignment, WorkflowDefinition, WorkflowStep

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

# Default org for KL Road project — used when grievance has no org context
DEFAULT_ORG_ID = "DOR"
DEFAULT_PROJECT_CODE = "KL_ROAD"
DEFAULT_CHATBOT_ID = "nepal_grievance_bot"
DEFAULT_COUNTRY_CODE = "NP"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _lookup_workflow(
    db: Session,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    is_seah: bool,
    priority: str,
) -> Optional[WorkflowDefinition]:
    """
    Resolve the best-matching workflow for this ticket.
    Returns None if no assignment found (logged as warning, ticket skipped).
    """
    lookup_priority = "SEAH" if is_seah else priority

    for loc in ([location_code, None] if location_code else [None]):
        for proj in ([project_code, None] if project_code else [None]):
            for pri in ([lookup_priority, None]):
                assignment = db.execute(
                    select(WorkflowAssignment).where(
                        WorkflowAssignment.organization_id == organization_id,
                        WorkflowAssignment.location_code == loc,
                        WorkflowAssignment.project_code == proj,
                        WorkflowAssignment.priority == pri,
                    )
                ).scalar_one_or_none()
                if assignment:
                    wf = db.get(WorkflowDefinition, assignment.workflow_id)
                    if wf:
                        return wf
    return None


def _first_step(db: Session, workflow_id: str) -> Optional[WorkflowStep]:
    return db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()


def _map_priority(grievance_high_priority: bool, is_seah: bool) -> str:
    if is_seah:
        return "HIGH"
    return "HIGH" if grievance_high_priority else "NORMAL"


def _fetch_new_grievances(db: Session) -> list[dict]:
    """
    Query public.grievances for fully-submitted grievances not yet in ticketing.tickets.

    Uses two separate queries (no cross-schema JOIN — architecture rule).
    """
    # Step 1: get all grievance_ids already tracked
    existing = db.execute(
        select(Ticket.grievance_id)
    ).scalars().all()
    existing_set = set(existing)

    # Step 2: read new submitted grievances from public schema (read-only)
    result = db.execute(text("""
        SELECT
            grievance_id,
            complainant_id,
            grievance_summary,
            grievance_categories,
            grievance_location,
            grievance_high_priority,
            grievance_sensitive_issue,
            grievance_creation_date,
            source
        FROM public.grievances
        WHERE is_temporary = false
        ORDER BY grievance_creation_date ASC
    """))
    rows = result.mappings().all()

    return [dict(r) for r in rows if r["grievance_id"] not in existing_set]


def _create_ticket_from_grievance(db: Session, g: dict) -> Optional[Ticket]:
    """
    Create a single Ticket + CREATED event from a public.grievances row.
    Returns the Ticket on success, None if workflow cannot be resolved.
    """
    is_seah = bool(g.get("grievance_sensitive_issue", False))
    priority = _map_priority(bool(g.get("grievance_high_priority", False)), is_seah)

    # Resolve workflow
    workflow = _lookup_workflow(
        db=db,
        organization_id=DEFAULT_ORG_ID,
        location_code=None,  # grievances table has no location_code column
        project_code=DEFAULT_PROJECT_CODE,
        is_seah=is_seah,
        priority=priority,
    )
    if not workflow:
        logger.warning(
            "sync: no workflow found for grievance %s (is_seah=%s, priority=%s) — skipping",
            g["grievance_id"], is_seah, priority,
        )
        return None

    first_step = _first_step(db, workflow.workflow_id)
    ticket_id = _new_id()
    now = _now()

    ticket = Ticket(
        ticket_id=ticket_id,
        grievance_id=g["grievance_id"],
        complainant_id=g.get("complainant_id"),
        # session_id: not available in public.grievances — stored as None.
        # INTEGRATION POINT: to enable chatbot reply, look up the Rasa sender_id
        # from public.events WHERE data::jsonb @> '{"value": {"grievance_id": "<id>"}}'
        # and store it here. See docs/claude-tickets/session-3-cursor-handoff.md.
        session_id=None,
        chatbot_id=DEFAULT_CHATBOT_ID,
        country_code=DEFAULT_COUNTRY_CODE,
        organization_id=DEFAULT_ORG_ID,
        location_code=None,
        project_code=DEFAULT_PROJECT_CODE,
        priority=priority,
        is_seah=is_seah,
        status_code="OPEN",
        current_workflow_id=workflow.workflow_id,
        current_step_id=first_step.step_id if first_step else None,
        assigned_to_user_id=None,
        sla_breached=False,
        is_deleted=False,
        step_started_at=now,
        grievance_summary=g.get("grievance_summary"),
        grievance_categories=g.get("grievance_categories"),
        grievance_location=g.get("grievance_location"),
        created_at=g.get("grievance_creation_date") or now,
        updated_at=now,
    )
    db.add(ticket)

    event = TicketEvent(
        event_id=_new_id(),
        ticket_id=ticket_id,
        event_type="CREATED",
        new_status_code="OPEN",
        workflow_step_id=first_step.step_id if first_step else None,
        note=f"Auto-created by grievance sync from {g.get('source', 'bot')}",
        seen=True,
        created_by_user_id="system",
        created_at=now,
    )
    db.add(event)
    return ticket


# ── Celery task ───────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    name="ticketing.tasks.grievance_sync.sync_grievances",
    max_retries=3,
    default_retry_delay=60,
)
def sync_grievances(self) -> dict:
    """
    Poll public.grievances for new fully-submitted grievances and create tickets.

    Also checks for SEAH-specific tables once feat/seah-sensitive-intake is merged.
    INTEGRATION POINT: add second query block for SEAH table when available.

    Returns summary dict: {"created": N, "skipped": N, "errors": N}
    """
    db: Session = SessionLocal()
    created = skipped = errors = 0

    try:
        new_grievances = _fetch_new_grievances(db)

        if not new_grievances:
            logger.debug("grievance_sync: no new submissions found")
            return {"created": 0, "skipped": 0, "errors": 0}

        logger.info("grievance_sync: found %d new grievance(s) to process", len(new_grievances))

        for g in new_grievances:
            try:
                ticket = _create_ticket_from_grievance(db, g)
                if ticket:
                    created += 1
                    logger.info(
                        "grievance_sync: created ticket %s for grievance %s (is_seah=%s)",
                        ticket.ticket_id, g["grievance_id"], ticket.is_seah,
                    )
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                logger.error(
                    "grievance_sync: error processing %s: %s",
                    g.get("grievance_id"), exc, exc_info=True,
                )

        if created > 0:
            db.commit()
            logger.info("grievance_sync: committed %d new ticket(s)", created)

    except Exception as exc:
        db.rollback()
        logger.exception("grievance_sync: fatal error — rolled back")
        raise self.retry(exc=exc)
    finally:
        db.close()

    return {"created": created, "skipped": skipped, "errors": errors}
