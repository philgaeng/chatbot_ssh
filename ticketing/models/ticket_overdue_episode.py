"""SLA overdue stint per workflow step — see docs/ticketing_system/12_reports §14."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class TicketOverdueEpisode(Base):
    __tablename__ = "ticket_overdue_episodes"
    __table_args__ = (
        Index("idx_overdue_episodes_ticket_started", "ticket_id", "started_at"),
        Index("idx_overdue_episodes_ticket_ended", "ticket_id", "ended_at"),
        {"schema": "ticketing"},
    )

    episode_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_step_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ticketing.workflow_steps.step_id", ondelete="SET NULL"),
        nullable=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    assigned_to_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assigned_role_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    days_overdue: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, default="SLA_WATCHDOG")

    ticket: Mapped["Ticket"] = relationship(  # type: ignore[name-defined]
        "Ticket",
        foreign_keys=[ticket_id],
        back_populates="overdue_episodes",
    )
