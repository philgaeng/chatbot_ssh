# SPDX-License-Identifier: Apache-2.0

"""
Celery tasks: LLM translation and findings generation.

Two tasks:
  translate_note(event_id)     — translates a NOTE_ADDED event's note to English,
                                  stores result in TicketEvent.payload["translation_en"]
  generate_findings(ticket_id) — builds PII-clean context via context_builder,
                                  calls LLM for structured JSON findings,
                                  stores summary_en → Ticket.ai_summary_en
                                  and full findings → TicketContextCache.findings_json

LLM provider: whatever `LLM_BASE_URL` points at, via ticketing/clients/llm_client.py.
  Standard tickets: the `ticket_findings` model      (cost-optimised, temperature=0)
  SEAH tickets:     the `ticket_findings_seah` model (more careful reasoning)
Both names — and the endpoint, and the key — are declared once in backend/config/llm_config.py
and resolved with `model_for(findings_task(is_seah))`. This module names no model: it used to
name two, in two places, and one of them fed a persisted provenance field.

The service-layer boundary stands: no imports from backend/services/. `backend/config/` is
configuration shared by both surfaces, not the chatbot's service layer (DPG-17).
"""

import logging
from datetime import datetime, timezone

from backend.config.llm_config import findings_task, model_for
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
      2. Call LLM with the context (the ticket_findings / ticket_findings_seah model)
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
            # Resolved, not re-derived: this line used to restate the ternary as a literal, so
            # the log could disagree with the call it was logging.
            model_for(findings_task(ticket.is_seah)).model,
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


# ─────────────────────────────────────────────────────────────────────────────
# generate_resolved_case_summary
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="ticketing.tasks.llm.generate_resolved_case_summary",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def generate_resolved_case_summary(self, ticket_id: str, force: bool = False) -> dict:
    """Build officer + public closure documents (spec §3). Waits up to 30s for findings."""
    import time

    from ticketing.clients.llm_client import generate_resolved_case_summary_llm
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import Ticket
    from ticketing.models.ticket_context_cache import TicketContextCache
    from ticketing.models.ticket_resolved_summary import TicketResolvedSummary
    from ticketing.services.resolved_summary_builder import (
        assemble_llm_bundle,
        assemble_summary_input,
        build_flat_narrative,
        build_public_summary_json,
        build_summary_json,
        upsert_resolved_summary,
        with_investigation_activity_preamble,
    )
    from ticketing.tasks.notifications import notify_complainant

    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if not ticket:
            return {"ticket_id": ticket_id, "status": "not_found"}

        data = assemble_summary_input(db, ticket_id)
        resolution_ev = data.get("resolution_ev")
        if not resolution_ev:
            return {"ticket_id": ticket_id, "status": "no_resolution_record"}

        source_id = resolution_ev.event_id
        existing = db.get(TicketResolvedSummary, ticket_id)
        if (
            existing
            and existing.source_resolution_event_id == source_id
            and existing.generation_status == "complete"
            and not force
        ):
            return {"ticket_id": ticket_id, "status": "skipped"}

        prior_findings = None
        for _ in range(6):
            cache = db.get(TicketContextCache, ticket_id)
            if cache and cache.findings_json:
                prior_findings = cache.findings_json
                break
            time.sleep(5)

        bundle = assemble_llm_bundle(data, prior_findings)
        llm_out = generate_resolved_case_summary_llm(
            bundle,
            is_seah=ticket.is_seah,
            primary_language=data["primary_language"],
        )
        # D-36: a missing narrative is worth one more attempt before it becomes permanent — the
        # usual cause is transient provider trouble, and the ladder costs the complainant nothing
        # because nobody is waiting on this task. After that, publish what we have.
        if llm_out is None and self.request.retries < 2:
            logger.warning(
                "generate_resolved_case_summary: no LLM narrative for ticket_id=%s, retrying "
                "(attempt %s)", ticket_id, self.request.retries + 1,
            )
            raise self.retry(countdown=30 * (self.request.retries + 1))

        llm_out = with_investigation_activity_preamble(data, llm_out)
        # ⚠ This reached into the client module's privates (`_llm._MODEL_SEAH`) rather than
        # restating the literal, so `grep "gpt-"` could not find it — DPG-12's own acceptance
        # grep would have passed with this line untouched. It feeds the same `generation_model`
        # provenance column as the summary builder, so the two must agree by construction.
        model = model_for(findings_task(ticket.is_seah)).model
        status = "complete" if llm_out else "llm_failed"

        summary_json = build_summary_json(db, data, llm_out)
        if llm_out:
            fs = summary_json.setdefault("findings_summary", {})
            fs["field_reports_digest_en"] = llm_out.get("field_reports_digest_en", "")
            fs["other_notes_digest_en"] = llm_out.get("other_notes_digest_en", "")
            fs["combined_digest_en"] = llm_out.get("combined_digest_en", "")
        summary_json["findings_summary"]["ai_summary_en"] = (
            (prior_findings or {}).get("summary_en") or ticket.ai_summary_en
        )

        public_json = build_public_summary_json(data, summary_json, llm_out)
        narrative = build_flat_narrative(public_json)

        row = upsert_resolved_summary(
            db,
            ticket_id,
            source_resolution_event_id=source_id,
            summary_json=summary_json,
            summary_public_json=public_json,
            summary_text_primary=narrative,
            primary_language=data["primary_language"],
            generation_model=model,
            generation_status=status,
        )
        row.summary_text_en = summary_json.get("findings_summary", {}).get("combined_digest_en")
        db.commit()

        # ⚠ **The complainant is notified whenever there is something to read — not only when the
        # model succeeded** (D-36). This gate was `status == "complete"`, so an unavailable model
        # meant the person was told their case was resolved and never received the outcome, and
        # nothing ever retried the document. The deterministic record — dates, duration, who
        # resolved it, the resolution category and **the officer's own resolution text** — is built
        # either way; only the AI narrative is missing, and that is not worth withholding a closure
        # document over. `generation_status` still records the difference for the officer view.
        publishable = bool((public_json or {}).get("resolution_text_public"))
        if publishable and row.closure_public_url:
            notify_complainant.delay(
                ticket_id,
                (
                    "Your grievance has been resolved. "
                    f"Read the outcome here: {row.closure_public_url}"
                ),
                "RESOLVED_CLOSURE",
            )
        elif not publishable:
            logger.error(
                "generate_resolved_case_summary: nothing publishable for ticket_id=%s "
                "(status=%s) — the complainant was NOT notified", ticket_id, status,
            )

        return {"ticket_id": ticket_id, "status": status, "token": row.closure_public_token}

    except Exception as exc:
        db.rollback()
        logger.exception(
            "generate_resolved_case_summary error ticket_id=%s: %s", ticket_id, exc
        )
        raise self.retry(exc=exc)
    finally:
        db.close()
