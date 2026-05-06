"""
ticketing.ticket_viewers

Case viewers (watchers) — UI_SPEC.md §2.7.

A viewer can read the case thread and post notes. They cannot acknowledge/escalate/resolve
or assign tasks. Senior roles (L2, GRC, SEAH, ADB, admin) and the assigned officer may
add viewers.

PII rules: same as ticket.py — user_ids only, no name/phone/email stored here.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class TicketViewer(Base):
    __tablename__ = "ticket_viewers"
    __table_args__ = (
        Index("idx_ticket_viewers_ticket_id", "ticket_id"),
        Index("idx_ticket_viewers_user_id", "user_id"),
        UniqueConstraint("ticket_id", "user_id", name="uq_ticket_viewers_ticket_user"),
        {"schema": "ticketing"},
    )

    viewer_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    added_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    # tier: 'observer' (read-only, no notifications) | 'informed' (notes + tasks + notifications)
    # Default 'observer' is back-compat with all existing viewer rows.
    tier: Mapped[str] = mapped_column(String(32), nullable=False, default="observer")
