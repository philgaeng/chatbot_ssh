"""
ticketing.officer_positions — an officer holds a position type at an org unit (OC-03).

Descriptive HR/org-chart layer. Invite-by-position *generates* the enforcement rows
(user_roles + officer_scopes) from the position→role matrix + the unit's territory; the
position row itself is never read for access control. Multiple active rows per officer =
dual-hat. `reports_to_user_id` is an admin/HR override only (deputation / acting) — it does
NOT feed grievance supervision (that is the per-(project, step) resolver, DECISION §5).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class OfficerPosition(Base):
    __tablename__ = "officer_positions"
    __table_args__ = (
        Index("idx_officer_positions_user", "user_id"),
        Index("idx_officer_positions_position_type", "position_type_id"),
        {"schema": "ticketing"},
    )

    officer_position_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    position_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.position_types.position_type_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    # HR/admin override only (deputation / acting) — NOT used for supervision resolution.
    reports_to_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Transfers end the old row (is_active=False) and add a new one; history is retained.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
