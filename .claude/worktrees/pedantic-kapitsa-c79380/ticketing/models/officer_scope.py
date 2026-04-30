"""
ticketing.officer_scopes — maps officers to their jurisdictions.

One row = "this officer acts as [role_key] for tickets in [org / location / project]".
Multiple rows per officer = multiple jurisdictions.
location_code = None  → covers all locations in that org
project_code  = None  → covers all projects in that location
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
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
        Index("idx_officer_scopes_user",    "user_id"),
        Index("idx_officer_scopes_package", "package_id"),
        {"schema": "ticketing"},
    )

    scope_id:          Mapped[str]        = mapped_column(String(36),  primary_key=True, default=_uuid)
    user_id:           Mapped[str]        = mapped_column(String(64),  nullable=False)
    role_key:          Mapped[str]        = mapped_column(String(64),  nullable=False)
    organization_id:   Mapped[str]        = mapped_column(String(64),  nullable=False)
    location_code:     Mapped[str | None] = mapped_column(String(64),  nullable=True)
    # project_id replaces project_code — proper FK to ticketing.projects
    project_id:        Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.projects.project_id", ondelete="SET NULL"),
        nullable=True,
    )
    # project_code kept for backwards compat; deprecated — use project_id
    project_code:      Mapped[str | None] = mapped_column(String(64),  nullable=True)
    # When set: scope is restricted to this specific civil-works package
    # L1 officers for a contractor are scoped to their package only
    package_id:        Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ticketing.project_packages.package_id", ondelete="SET NULL"),
        nullable=True,
    )
    # When True: scope covers this location AND all descendant nodes
    includes_children: Mapped[bool]       = mapped_column(Boolean, nullable=False, default=False)
    created_at:        Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
