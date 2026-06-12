"""
Celery tasks: officer + complainant notifications.

Officer notifications:
  - In-app badge via ASSIGNMENT_NOTIFICATION TicketEvent
  - Project-level SMS on assignment (link-only, no PII) via notify_officer_assignment

Complainant notifications:
  - Primary: POST /message to orchestrator (session_id stored on ticket)
  - Fallback: POST /api/messaging/send-sms (when session expired)

INTEGRATION POINT: upgrade officer notifications to SSE in v2
"""
import logging
from typing import Optional

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── Notification gate (spec 12 §4) ────────────────────────────────────────────

def should_notify(
    workflow_slug: str,
    event_type: str,
    tier: str,
    channel: str,
    db,
) -> bool:
    """
    Return True if the given channel should fire for this workflow / event / tier combination.

    Reads `notification_rules` from ticketing.settings (seeded by migration j8l0n2p4r6).
    Falls back to False on any missing key so the system is safe by default.

    Args:
        workflow_slug: "standard" | "seah"
        event_type:    "ticket_created" | "ticket_escalated" | "ticket_resolved" |
                       "sla_breach" | "grc_convened" | "assignment" | "quarterly_report"
        tier:          "actor" | "supervisor" | "informed" | "observer"
        channel:       "app" | "email" | "sms"
        db:            SQLAlchemy session
    """
    try:
        from sqlalchemy import select
        from ticketing.models.settings import Settings

        row = db.execute(
            select(Settings).where(Settings.key == "notification_rules")
        ).scalar_one_or_none()

        if not row or not row.value:
            return False

        rules = row.value  # JSON dict already deserialised by SQLAlchemy
        channels: list = (
            rules
            .get(workflow_slug, {})
            .get(event_type, {})
            .get(tier, [])
        )
        return channel in channels

    except Exception:
        logger.exception("should_notify failed — defaulting to False")
        return False


@celery_app.task(
    name="ticketing.tasks.notifications.notify_complainant",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def notify_complainant(
    self,
    ticket_id: str,
    message_text: str,
    event_type: str = "STATUS_UPDATE",
) -> dict:
    """
    Send a status update to the complainant.

    1. Try orchestrator POST /message using session_id
    2. Fall back to SMS via messaging_api if orchestrator fails
    3. Log outcome as a TicketEvent
    """
    from ticketing.clients.messaging_api import send_sms
    from ticketing.clients.orchestrator import send_message_to_complainant
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import Ticket, TicketEvent

    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            return {"ticket_id": ticket_id, "delivered": False, "reason": "not_found"}

        delivered_via = None

        # Primary: orchestrator
        if ticket.session_id:
            try:
                send_message_to_complainant(
                    session_id=ticket.session_id,
                    text=message_text,
                    chatbot_id=ticket.chatbot_id,
                )
                delivered_via = "chatbot"
                logger.info(
                    "Complainant notified via chatbot: ticket_id=%s event_type=%s",
                    ticket_id, event_type,
                )
            except Exception as e:
                logger.warning(
                    "Orchestrator failed for ticket_id=%s: %s — trying SMS fallback",
                    ticket_id, e,
                )

        # Fallback: SMS
        # INTEGRATION POINT: fetch complainant phone from grievance API
        # from ticketing.clients.grievance_api import get_grievance_detail
        # detail = get_grievance_detail(ticket.grievance_id)
        # phone = detail.get("complainant", {}).get("phone")
        if delivered_via is None:
            logger.warning(
                "No session_id and no SMS fallback implemented yet for ticket_id=%s",
                ticket_id,
            )
            # INTEGRATION POINT: uncomment when grievance API returns phone
            # if phone:
            #     send_sms(phone, message_text)
            #     delivered_via = "sms"

        # Log notification event
        import uuid
        from datetime import datetime, timezone
        event = TicketEvent(
            event_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            event_type="COMPLAINANT_NOTIFIED",
            note=message_text[:500],
            payload={
                "event_type": event_type,
                "delivered_via": delivered_via,
            },
            seen=True,
            created_by_user_id="system",
        )
        db.add(event)
        db.commit()

        return {
            "ticket_id": ticket_id,
            "delivered": delivered_via is not None,
            "delivered_via": delivered_via,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("notify_complainant error for ticket_id=%s: %s", ticket_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


def enqueue_assignment_notifications(
    ticket_id: str,
    assigned_to_user_id: str | None,
    step_id: str | None,
    *,
    old_assigned: str | None = None,
    event: str = "assignment",
) -> None:
    """Queue in-app badge + officer SMS after assignment commit."""
    if not assigned_to_user_id:
        return
    if old_assigned is not None and old_assigned == assigned_to_user_id:
        return
    try:
        notify_assignment.delay(ticket_id, assigned_to_user_id, step_id, event)
    except Exception as exc:
        logger.warning("Celery enqueue notify_assignment failed (non-fatal): %s", exc)


@celery_app.task(
    name="ticketing.tasks.notifications.notify_officer_assignment",
    bind=True,
    max_retries=2,
)
def notify_officer_assignment(
    self,
    ticket_id: str,
    assigned_to_user_id: str,
    step_id: str | None,
    event: str = "assignment",
) -> dict:
    """Send link-only officer SMS when project messaging config allows."""
    from ticketing.models.base import SessionLocal
    from ticketing.services.officer_messaging import notify_officer_assignment_sync

    db = SessionLocal()
    try:
        return notify_officer_assignment_sync(
            db,
            ticket_id,
            assigned_to_user_id,
            step_id,
            event=event,
        )
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="ticketing.tasks.notifications.notify_assignment",
    bind=True,
    max_retries=2,
)
def notify_assignment(
    self,
    ticket_id: str,
    assigned_to_user_id: str,
    step_id: str | None = None,
    event: str = "assignment",
) -> dict:
    """
    Create an unread notification event for the newly assigned officer.
    Also queues officer SMS when project messaging is enabled for the step level.

    INTEGRATION POINT: trigger SSE push here in v2 for real-time badge update.
    """
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import Ticket, TicketEvent
    import uuid

    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            return {"ticket_id": ticket_id, "notified": False}

        ev = TicketEvent(
            event_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            event_type="ASSIGNMENT_NOTIFICATION",
            note=f"You have been assigned ticket {ticket.grievance_id}",
            seen=False,
            assigned_to_user_id=assigned_to_user_id,
            created_by_user_id="system",
        )
        db.add(ev)
        db.commit()

        try:
            notify_officer_assignment.delay(
                ticket_id, assigned_to_user_id, step_id, event
            )
        except Exception as exc:
            logger.warning(
                "Celery enqueue notify_officer_assignment failed (non-fatal): %s",
                exc,
            )

        return {"ticket_id": ticket_id, "notified": True, "user_id": assigned_to_user_id}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
