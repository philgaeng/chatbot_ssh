"""
ticketing.organizations and ticketing.locations
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "ticketing"}

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, default="NP")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    locations: Mapped[list["Location"]] = relationship(
        "Location", back_populates="organization", lazy="select"
    )


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = {"schema": "ticketing"}

    location_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, default="NP")
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_location: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.locations.location_code", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    organization: Mapped["Organization | None"] = relationship(
        "Organization", back_populates="locations"
    )
