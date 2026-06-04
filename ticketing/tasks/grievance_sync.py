"""
Grievance sync task — keeps ticketing.tickets aligned with public.grievances.

Runs every 2 minutes via Celery Beat (see celery_app.py beat_schedule).

Design (TP-14 / 04-classification-status-spec):
  - No is_temporary filter on read
  - UPDATE existing tickets when summary/categories/location change
  - CREATE tickets for grievances not yet in ticketing.tickets (idempotent)
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from celery import shared_task
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.grievance_content import _coerce_categories

logger = logging.getLogger(__name__)

DEFAULT_ORG_ID = "DOR"
DEFAULT_PROJECT_CODE = "KL_ROAD"
DEFAULT_CHATBOT_ID = "nepal_grievance_bot"
DEFAULT_COUNTRY_CODE = "NP"


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
    from ticketing.engine.workflow_engine import resolve_workflow

    return resolve_workflow(
        organization_id=organization_id,
        location_code=location_code,
        project_code=project_code,
        is_seah=is_seah,
        priority=priority,
        db=db,
    )


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


def _fetch_all_grievance_rows(db: Session) -> list[dict]:
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
        ORDER BY grievance_creation_date ASC
    """))
    return [dict(r) for r in result.mappings().all()]


def _cache_needs_update(ticket: Ticket, g: dict) -> bool:
    cats = _coerce_categories(g.get("grievance_categories"))
    if g.get("grievance_summary") and ticket.grievance_summary != g.get("grievance_summary"):
        return True
    if cats and ticket.grievance_categories != cats:
        return True
    if g.get("grievance_location") and ticket.grievance_location != g.get("grievance_location"):
        return True
    return False


def _apply_cache(ticket: Ticket, g: dict) -> None:
    ticket.grievance_summary = g.get("grievance_summary") or ticket.grievance_summary
    cats = _coerce_categories(g.get("grievance_categories"))
    if cats:
        ticket.grievance_categories = cats
    if g.get("grievance_location"):
        ticket.grievance_location = g.get("grievance_location")
    ticket.updated_at = _now()


def _create_ticket_from_grievance(db: Session, g: dict) -> Optional[Ticket]:
    is_seah = bool(g.get("grievance_sensitive_issue", False))
    priority = _map_priority(bool(g.get("grievance_high_priority", False)), is_seah)

    workflow = _lookup_workflow(
        db=db,
        organization_id=DEFAULT_ORG_ID,
        location_code=None,
        project_code=DEFAULT_PROJECT_CODE,
        is_seah=is_seah,
        priority=priority,
    )
    if not workflow:
        logger.warning(
            "sync: no workflow for grievance %s (is_seah=%s, priority=%s)",
            g["grievance_id"], is_seah, priority,
        )
        return None

    first_step = _first_step(db, workflow.workflow_id)
    ticket_id = _new_id()
    now = _now()
    cats = _coerce_categories(g.get("grievance_categories"))

    ticket = Ticket(
        ticket_id=ticket_id,
        grievance_id=g["grievance_id"],
        complainant_id=g.get("complainant_id"),
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
        grievance_categories=cats,
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


@shared_task(
    bind=True,
    name="ticketing.tasks.grievance_sync.sync_grievances",
    max_retries=3,
    default_retry_delay=60,
)
def sync_grievances(self) -> dict:
    db: Session = SessionLocal()
    created = updated = skipped = errors = 0

    try:
        grievances = _fetch_all_grievance_rows(db)
        if not grievances:
            return {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        tickets_by_gid = {
            t.grievance_id: t
            for t in db.execute(select(Ticket).where(Ticket.is_deleted.is_(False))).scalars().all()
        }

        for g in grievances:
            gid = g["grievance_id"]
            try:
                existing = tickets_by_gid.get(gid)
                if existing:
                    if _cache_needs_update(existing, g):
                        _apply_cache(existing, g)
                        updated += 1
                        logger.info("grievance_sync: updated cache for ticket %s", existing.ticket_id)
                    else:
                        skipped += 1
                else:
                    ticket = _create_ticket_from_grievance(db, g)
                    if ticket:
                        tickets_by_gid[gid] = ticket
                        created += 1
                        logger.info(
                            "grievance_sync: created ticket %s for %s",
                            ticket.ticket_id, gid,
                        )
                    else:
                        skipped += 1
            except Exception as exc:
                errors += 1
                logger.error("grievance_sync: %s: %s", gid, exc, exc_info=True)

        if created > 0 or updated > 0:
            db.commit()
            logger.info("grievance_sync: committed created=%d updated=%d", created, updated)

    except Exception as exc:
        db.rollback()
        logger.exception("grievance_sync: fatal error")
        raise self.retry(exc=exc)
    finally:
        db.close()

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
