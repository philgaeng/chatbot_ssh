"""
Celery tasks: LLM translation and findings generation.

Two tasks:
  translate_note(event_id)     — translates a NOTE_ADDED event's note to English,
                                  stores result in TicketEvent.payload["translation_en"]
  generate_findings(ticket_id) — builds PII-clean context via context_builder,
                                  calls LLM for structured JSON findings,
                                  stores summary_en → Ticket.ai_summary_en
                                  and full findings → TicketContextCache.findings_json

LLM provider: OpenAI via ticketing/clients/llm_client.py
  Standard tickets: gpt-4o-mini  (cost-optimised, temperature=0)
  SEAH tickets:     gpt-4o        (more careful reasoning)
Key: OPENAI_API_KEY in env.local

DO NOT import from backend/services/ — keep ticketing independent.
"""

import logging
from datetime import datetime, timezone

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


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

        if event.event_type not in {"NOTE_ADDED", "COMPLAINANT_MESSAGE"}:
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
    Generate structured AI case-findings for a ticket.

    Steps:
      1. Build PII-clean context via context_builder.build_and_store()
         → writes to ticketing.ticket_context_cache.context_json
      2. Call LLM with the context (gpt-4o-mini standard / gpt-4o SEAH)
         → returns {summary_en, key_findings, recommended_action, urgency, languages_detected}
      3. Store full findings_json in ticket_context_cache
      4. Store summary_en in Ticket.ai_summary_en (backward-compat with frontend)

    Called:
      - Automatically when a ticket is RESOLVED (tickets.py)
      - On demand via POST /api/v1/tickets/{id}/findings (admin/supervisor only)
    """
    from ticketing.clients.llm_client import generate_case_findings
    from ticketing.engine.context_builder import build_and_store
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import Ticket
    from ticketing.models.ticket_context_cache import TicketContextCache

    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            logger.warning("generate_findings: ticket_id=%s not found", ticket_id)
            return {"ticket_id": ticket_id, "status": "not_found"}

        # ── Step 1: build and persist PII-clean context ──────────────────
        cache = build_and_store(ticket_id, db)
        db.commit()

        if cache.event_count == 0:
            logger.info("generate_findings: no relevant events for ticket_id=%s", ticket_id)
            return {"ticket_id": ticket_id, "status": "no_events"}

        # ── Step 2: call LLM ──────────────────────────────────────────────
        findings = generate_case_findings(cache.context_json, is_seah=ticket.is_seah)
        if findings is None:
            logger.error("generate_findings: LLM returned None for ticket_id=%s", ticket_id)
            return {"ticket_id": ticket_id, "status": "llm_error"}

        # ── Step 3: store structured output in cache ──────────────────────
        # Re-fetch cache in case session was refreshed
        cache = db.get(TicketContextCache, ticket_id)
        cache.findings_json = findings
        cache.findings_updated_at = datetime.now(timezone.utc)

        # ── Step 4: populate Ticket.ai_summary_en (frontend reads this) ───
        ticket.ai_summary_en = findings.get("summary_en", "")
        ticket.ai_summary_updated_at = datetime.now(timezone.utc)

        db.commit()
        logger.info(
            "generate_findings: ok ticket_id=%s urgency=%s model=%s tokens≈%d",
            ticket_id,
            findings.get("urgency"),
            "gpt-4o" if ticket.is_seah else "gpt-4o-mini",
            cache.token_estimate,
        )
        return {
            "ticket_id": ticket_id,
            "status": "generated",
            "urgency": findings.get("urgency"),
            "token_estimate": cache.token_estimate,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("generate_findings error for ticket_id=%s: %s", ticket_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
