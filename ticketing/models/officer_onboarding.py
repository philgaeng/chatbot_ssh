"""Per-officer onboarding status (invited vs active), keyed by ticketing user_id."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OfficerOnboarding(Base):
    """Mirrors Keycloak onboarding; updated via webhook (and invite sets invited)."""

    __tablename__ = "officer_onboarding"
    __table_args__ = {"schema": "ticketing"}

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
