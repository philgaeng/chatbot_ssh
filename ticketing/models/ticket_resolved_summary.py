"""
ticketing.ticket_resolved_summaries — closure document (officer + complainant views).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class TicketResolvedSummary(Base):
    __tablename__ = "ticket_resolved_summaries"
    __table_args__ = {"schema": "ticketing"}

    ticket_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    grievance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_resolution_event_id: Mapped[str] = mapped_column(String(36), nullable=False)

    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary_public_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text_primary: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")

    closure_public_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    closure_public_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    generation_model: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    generation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
