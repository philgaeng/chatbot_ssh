"""
ticketing.organizations

Location model has moved to country.py (full redesign with multilingual support).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "ticketing"}

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable: cross-country orgs (e.g. ADB) have no single country
    country_code: Mapped[str | None] = mapped_column(
        String(8),
        ForeignKey("ticketing.countries.country_code", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Language preference for this org's officers. 'ne' = Nepali-first (DOR), 'en' = English-first (ADB).
    # Individual officers can override via ticketing.user_roles.preferred_language.
    default_language: Mapped[str] = mapped_column(String(8), nullable=False, default="ne")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
