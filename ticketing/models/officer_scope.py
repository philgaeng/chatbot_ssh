"""
ticketing.officer_scopes — maps officers to their jurisdictions.

One row = "this officer acts as [role_key] for tickets in [org / location / project]".
Multiple rows per officer = multiple jurisdictions.
location_code = None  → covers all locations in that org
project_code  = None  → covers all projects in that location
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class OfficerScope(Base):
    __tablename__ = "officer_scopes"
    __table_args__ = (
        Index(
            "idx_officer_scopes_lookup",
            "role_key", "organization_id", "location_code", "project_code",
        ),
        Index("idx_officer_scopes_user", "user_id"),
        {"schema": "ticketing"},
    )

    scope_id:        Mapped[str]       = mapped_column(String(36),  primary_key=True, default=_uuid)
    user_id:         Mapped[str]       = mapped_column(String(64),  nullable=False)
    role_key:        Mapped[str]       = mapped_column(String(64),  nullable=False)
    organization_id: Mapped[str]       = mapped_column(String(64),  nullable=False)
    location_code:   Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_code:    Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at:      Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
