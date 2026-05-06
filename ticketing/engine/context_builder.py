"""
context_builder.py — PII-clean ticket context assembly (Layer 1)

This is the SINGLE place that reads raw ticket events and assembles them into
the structured JSON document sent to the LLM. Field whitelist is explicit —
PII cannot leak structurally because user_ids, complainant data, and contact
details are never included.

Public API:
    build_ticket_context(ticket_id, db) -> dict
        Pure function: assembles context dict without writing to DB.
        Use for ad-hoc inspection or testing.

    build_and_store(ticket_id, db) -> TicketContextCache
        Builds context and upserts into ticketing.ticket_context_cache.
        Called by the generate_findings Celery task.

Token estimate: rough 1 token ≈ 4 chars, applied to JSON-serialised context.
Typical ticket (20 events): ~700–1 100 tokens input.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_context_cache import TicketContextCache

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Event types that carry meaningful signal for the LLM.
# MENTION and NOTIFICATION_ONLY types are excluded — they are badge-driving
# plumbing events with no case-content value.
_CONTEXT_EVENT_TYPES = {
    "CREATED",
    "ACKNOWLEDGED",
    "NOTE_ADDED",
    "COMPLAINANT_MESSAGE",
    "ESCALATED",
    "RESOLVED",
    "CLOSED",
    "ASSIGNED",
    "REPLY_SENT",
    "GRC_CONVENED",
    "GRC_DECIDED",
    "COMPLAINANT_UPDATED",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_estimate(obj: dict) -> int:
    """Rough token count: 1 token ≈ 4 characters of serialised JSON."""
    try:
        return len(json.dumps(obj, separators=(",", ":"))) // 4
    except Exception:
        return 0


def build_ticket_context(ticket_id: str, db: Session) -> dict:
    """
    Assemble a PII-clean context document for *ticket_id*.

    NEVER includes:
      - created_by_user_id  (actual user accounts)
      - complainant_id / session_id / chatbot_id
      - name / phone / email / address (never stored in ticketing.* anyway)

    ALWAYS uses:
      - actor_role  (role key snapshot at write time — sufficient for LLM reasoning)
      - event_type, note, payload subset, timestamps
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise ValueError(f"Ticket not found: {ticket_id}")

    events = db.execute(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type.in_(_CONTEXT_EVENT_TYPES),
        )
        .order_by(TicketEvent.created_at)
    ).scalars().all()

    timeline: list[dict] = []
    field_reports: list[dict] = []

    for i, ev in enumerate(events, 1):
        payload = ev.payload or {}
        is_field_report = bool(payload.get("is_field_report"))

        # Prefer English translation if translator task has run
        note = payload.get("translation_en") or ev.note

        entry: dict = {
            "seq": i,
            "at": ev.created_at.isoformat() if ev.created_at else None,
            "type": ev.event_type,
            "by_role": ev.actor_role,   # role key only — NEVER user_id
            "note": note,
        }

        # Carry selected payload fields that add context (no PII)
        if ev.event_type == "ESCALATED":
            entry["trigger"] = payload.get("trigger", "MANUAL")
        elif ev.event_type in ("GRC_CONVENED", "GRC_DECIDED"):
            entry["hearing_date"] = payload.get("hearing_date")
            entry["decision"] = payload.get("grc_decision")
        elif ev.event_type == "COMPLAINANT_MESSAGE":
            entry["intent"] = payload.get("intent", "OTHER")
        elif is_field_report:
            entry["is_field_report"] = True

        timeline.append(entry)

        if is_field_report and note:
            field_reports.append({
                "at": entry["at"],
                "by_role": ev.actor_role,
                "text": note,
            })

    context = {
        "ticket_id": ticket_id,
        "generated_at": _now().isoformat(),
        "case": {
            # All fields below are cached at ticket creation and are non-PII per CLAUDE.md rule 4
            "grievance_id": ticket.grievance_id,
            "summary": ticket.grievance_summary,
            "categories": ticket.grievance_categories,
            "location": ticket.grievance_location,
            "priority": ticket.priority,
            "is_seah": ticket.is_seah,
            "status": ticket.status_code,
            "workflow_level": (
                ticket.current_step.display_name
                if ticket.current_step else None
            ),
        },
        "timeline": timeline,
        "field_reports": field_reports,
        "event_count": len(timeline),
    }

    return context


def build_and_store(ticket_id: str, db: Session) -> TicketContextCache:
    """
    Build context and upsert into ticketing.ticket_context_cache.
    Does NOT run the LLM — just prepares the input document.
    Called before generate_findings or independently when summary_regen_required.
    """
    context = build_ticket_context(ticket_id, db)

    cache = db.get(TicketContextCache, ticket_id)
    if cache is None:
        cache = TicketContextCache(ticket_id=ticket_id)
        db.add(cache)

    cache.context_json = context
    cache.event_count = context["event_count"]
    cache.token_estimate = _token_estimate(context)
    cache.context_updated_at = _now()
    # findings_json intentionally NOT cleared — preserve last good output until
    # a new findings run succeeds.

    db.flush()  # caller commits
    logger.debug(
        "context_builder: built context for ticket_id=%s events=%d tokens≈%d",
        ticket_id, cache.event_count, cache.token_estimate,
    )
    return cache
