"""
ticketing.ticket_context_cache

One row per ticket. Stores:
  context_json   — PII-clean assembled input sent to the LLM (built by context_builder.py)
  findings_json  — structured JSON output from the LLM (nullable until first generation)

The context document is rebuilt by context_builder.build_and_store() whenever an event
with summary_regen_required=True is committed. The findings are populated by the
generate_findings Celery task.

Ticket.ai_summary_en is still populated from findings_json["summary_en"] for
backward-compatible frontend rendering.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class TicketContextCache(Base):
    __tablename__ = "ticket_context_cache"
    __table_args__ = {"schema": "ticketing"}

    # String ref — no FK into ticketing.tickets to keep this a pure cache table
    ticket_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Input: PII-clean assembled context sent to LLM
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Output: structured findings from LLM (null until first generate_findings run)
    findings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Diagnostics
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    context_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    findings_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
