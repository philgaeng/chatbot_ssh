"""
ticketing.admin_scopes — scoped admin assignments (country_admin / project_admin).

workflow_track on each row selects Standard vs SEAH behaviour for that assignment.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


ADMIN_ROLE_KEYS = frozenset({"country_admin", "project_admin"})
WORKFLOW_TRACKS = frozenset({"standard", "seah"})


class AdminScope(Base):
    __tablename__ = "admin_scopes"
    __table_args__ = (
        Index("idx_admin_scopes_user", "user_id"),
        Index("idx_admin_scopes_project", "project_id"),
        Index("idx_admin_scopes_country_track", "country_code", "workflow_track"),
        {"schema": "ticketing"},
    )

    admin_scope_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role_key: Mapped[str] = mapped_column(String(64), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    package_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_track: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
