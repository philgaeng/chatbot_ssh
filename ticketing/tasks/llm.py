"""
Celery tasks: LLM translation and findings generation.

Two tasks:
  translate_note(event_id)     — translates a NOTE_ADDED event's note to English,
                                  stores result in TicketEvent.payload["translation_en"]
  generate_findings(ticket_id) — aggregates key events + notes for a ticket and
                                  produces an AI summary stored in Ticket.ai_summary_en

LLM provider: OpenAI gpt-4 via ticketing/clients/llm_client.py
Key:          OPENAI_API_KEY (already in env.local — same key as chatbot)

DO NOT import from backend/services/ — keep ticketing independent.
"""

import logging
import uuid
from datetime import datetime, timezone

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Event types included in the findings summary (chronological context)
_FINDINGS_EVENT_TYPES = {
    "NOTE_ADDED",
    "ESCALATED",
    "GRC_CONVENED",
    "GRC_DECIDED",
    "RESOLVED",
    "CLOSED",
    "ACKNOWLEDGED",
}


# ─────────────────────────────────────────────────────────────────────────────
# translate_note
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="ticketing.tasks.llm.translate_note",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def translate_note(self, event_id: str) -> dict:
    """
    Translate a NOTE_ADDED event's note field to English.

    Idempotent: skips if payload["translation_en"] already present.
    Stores result in TicketEvent.payload["translation_en"].

    Called automatically from tickets.py after NOTE action commit:
        translate_note.delay(event.event_id)
    """
    from ticketing.clients.llm_client import translate_to_english
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import TicketEvent

    db = SessionLocal()
    try:
        event = db.get(TicketEvent, event_id)
        if not event:
            logger.warning("translate_note: event_id=%s not found", event_id)
            return {"event_id": event_id, "status": "not_found"}

        if event.event_type != "NOTE_ADDED":
            return {"event_id": event_id, "status": "skipped_not_a_note"}

        # Idempotency: already translated
        existing_payload = event.payload or {}
        if existing_payload.get("translation_en"):
            return {"event_id": event_id, "status": "already_translated"}

        note_text = event.note or ""
        if not note_text.strip():
            return {"event_id": event_id, "status": "skipped_empty"}

        translation = translate_to_english(note_text)
        if translation is None:
            logger.error("translate_note: translation returned None for event_id=%s", event_id)
            return {"event_id": event_id, "status": "translation_error"}

        # Merge into existing payload (preserve any other keys)
        new_payload = dict(existing_payload)
        new_payload["translation_en"] = translation
        event.payload = new_payload

        db.commit()
        logger.info("translate_note: translated event_id=%s", event_id)
        return {"event_id": event_id, "status": "translated"}

    except Exception as exc:
        db.rollback()
        logger.exception("translate_note error for event_id=%s: %s", event_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# generate_findings
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="ticketing.tasks.llm.generate_findings",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def generate_findings(self, ticket_id: str) -> dict:
    """
    Generate an AI case-findings summary for a ticket.

    Aggregates all NOTE_ADDED events plus key status events (ESCALATED,
    GRC_CONVENED, GRC_DECIDED, RESOLVED, CLOSED, ACKNOWLEDGED) into a
    formatted text block, then calls generate_case_findings().

    Stores the result in Ticket.ai_summary_en + Ticket.ai_summary_updated_at.

    Called:
      - Automatically when a ticket is RESOLVED (tickets.py)
      - On demand via POST /api/v1/tickets/{id}/findings (admin/supervisor only)
    """
    from ticketing.clients.llm_client import generate_case_findings
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import Ticket, TicketEvent

    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            logger.warning("generate_findings: ticket_id=%s not found", ticket_id)
            return {"ticket_id": ticket_id, "status": "not_found"}

        # Fetch relevant events in chronological order
        events = (
            db.query(TicketEvent)
            .filter(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.event_type.in_(_FINDINGS_EVENT_TYPES),
            )
            .order_by(TicketEvent.created_at)
            .all()
        )

        if not events:
            logger.info("generate_findings: no relevant events for ticket_id=%s", ticket_id)
            return {"ticket_id": ticket_id, "status": "no_events"}

        # Build case text
        lines: list[str] = []
        lines.append(f"Case: {ticket.grievance_id}")
        if ticket.grievance_summary:
            lines.append(f"Summary: {ticket.grievance_summary}")
        lines.append("")

        for ev in events:
            ts = ev.created_at.strftime("%Y-%m-%d") if ev.created_at else "unknown"
            # Prefer English translation if available; fall back to original note
            payload = ev.payload or {}
            note_text = payload.get("translation_en") or ev.note or ""

            if ev.event_type == "NOTE_ADDED" and note_text:
                lines.append(f"[{ts}] Note: {note_text}")
            elif ev.event_type == "ESCALATED":
                lines.append(f"[{ts}] Escalated to next level.")
            elif ev.event_type == "GRC_CONVENED":
                hearing = payload.get("hearing_date", "")
                lines.append(f"[{ts}] GRC hearing convened{f' for {hearing}' if hearing else ''}.")
            elif ev.event_type == "GRC_DECIDED":
                decision = payload.get("grc_decision", "")
                lines.append(f"[{ts}] GRC decision: {decision}. {note_text}")
            elif ev.event_type == "RESOLVED":
                lines.append(f"[{ts}] Case resolved. {note_text}")
            elif ev.event_type == "CLOSED":
                lines.append(f"[{ts}] Case closed. {note_text}")
            elif ev.event_type == "ACKNOWLEDGED":
                lines.append(f"[{ts}] Case acknowledged by officer.")

        case_text = "\n".join(lines)

        findings = generate_case_findings(case_text)
        if findings is None:
            logger.error("generate_findings: LLM returned None for ticket_id=%s", ticket_id)
            return {"ticket_id": ticket_id, "status": "llm_error"}

        ticket.ai_summary_en = findings
        ticket.ai_summary_updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("generate_findings: generated findings for ticket_id=%s", ticket_id)
        return {"ticket_id": ticket_id, "status": "generated"}

    except Exception as exc:
        db.rollback()
        logger.exception("generate_findings error for ticket_id=%s: %s", ticket_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
