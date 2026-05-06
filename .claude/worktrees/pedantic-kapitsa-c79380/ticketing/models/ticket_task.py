"""
ticketing.ticket_tasks

In-thread task assignment — coordination feature used by supervisors and field officers.
A task fires TASK_ASSIGNED / TASK_COMPLETED events into ticket_events so it appears in
the thread at the right time.

PII rules: same as ticket.py — no PII, only user_ids.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class TicketTask(Base):
    __tablename__ = "ticket_tasks"
    __table_args__ = (
        Index("idx_ticket_tasks_ticket_id", "ticket_id"),
        Index("idx_ticket_tasks_assigned_to", "assigned_to_user_id", "status"),
        {"schema": "ticketing"},
    )

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Task type: SITE_VISIT | FOLLOW_UP_CALL | SYSTEM_NOTE | DOCUMENT_PHOTO
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Assignments (user_ids — no FK into public.*)
    assigned_to_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # Content
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Lifecycle: PENDING | DONE | DISMISSED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
