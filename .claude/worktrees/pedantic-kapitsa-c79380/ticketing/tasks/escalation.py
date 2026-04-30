"""
Celery task: SLA watchdog.

Runs every 15 minutes (configured in celery_app.py beat_schedule).
Scans all active tickets, auto-escalates those that have exceeded their SLA.

Worker command:
  celery -A ticketing.tasks worker -Q grm_ticketing -l info -c 2

Beat command (runs scheduler):
  celery -A ticketing.tasks beat -l info
"""
import logging

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="ticketing.tasks.escalation.check_sla_watchdog",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def check_sla_watchdog(self) -> dict:
    """
    SLA watchdog: find all tickets with exceeded resolution time and escalate.

    Runs every 15 minutes via Celery Beat.
    Uses run_sla_check() which handles its own DB session and commit.
    """
    from ticketing.engine.escalation import run_sla_check
    from ticketing.models.base import SessionLocal

    logger.info("SLA watchdog starting...")
    db = SessionLocal()
    try:
        summary = run_sla_check(db)
        logger.info("SLA watchdog complete: %s", summary)
        return summary
    except Exception as exc:
        logger.exception("SLA watchdog error: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="ticketing.tasks.escalation.escalate_single_ticket",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def escalate_single_ticket(self, ticket_id: str, triggered_by: str = "MANUAL", note: str | None = None) -> dict:
    """
    Escalate a single ticket asynchronously.
    Can be triggered by the API for async escalation if needed.
    For proto, the API escalates synchronously; this task is used for Celery Beat paths.
    """
    from ticketing.engine.escalation import escalate_ticket
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import Ticket
    from sqlalchemy import select

    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if not ticket or ticket.is_deleted:
            logger.warning("escalate_single_ticket: ticket_id=%s not found", ticket_id)
            return {"ticket_id": ticket_id, "escalated": False, "reason": "not_found"}

        result = escalate_ticket(ticket, db, triggered_by=triggered_by, note=note)
        db.commit()
        return {
            "ticket_id": ticket_id,
            "escalated": result is not None,
            "event_id": result.event_id if result else None,
        }
    except Exception as exc:
        db.rollback()
        logger.exception("escalate_single_ticket error: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
