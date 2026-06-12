"""
ticketing.project_types — super-admin archetypes (construction_road, …).

Instantiated on project create: workflows, actor role vocabulary, routing rules.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectType(Base):
    __tablename__ = "project_types"
    __table_args__ = {"schema": "ticketing"}

    type_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_workflow_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ticketing.workflow_definitions.workflow_id", ondelete="SET NULL"),
        nullable=True,
    )
    seah_workflow_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ticketing.workflow_definitions.workflow_id", ondelete="SET NULL"),
        nullable=True,
    )
    # Project actor role used to resolve ticket.organization_id (future) and L1 staffing checks.
    routing_org_role: Mapped[str] = mapped_column(String(64), nullable=False, default="implementing_agency")
    # List[{key, label, description, required, scope: project|package}]
    actor_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # List[{display_label, workflow_id, is_default, classifications, intake_routes, sort_order}]
    workflow_bindings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
