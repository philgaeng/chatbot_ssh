"""ticketing.project_workflows — dynamic workflow bindings per project."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ProjectWorkflow(Base):
    """
    Links a published workflow to a project with routing rules:
    - classifications: taxonomy groups from grievance catalog
    - intake_routes: chatbot path signals (fast_track, seah_intake, …)
    - is_default: catch-all when no rule matches
    """

    __tablename__ = "project_workflows"
    __table_args__ = (
        Index("idx_project_workflows_project", "project_id"),
        {"schema": "ticketing"},
    )

    project_workflow_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.workflow_definitions.workflow_id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_label: Mapped[str] = mapped_column(Text, nullable=False)
    classifications: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    intake_routes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    project: Mapped["Project"] = relationship("Project", back_populates="workflow_links")
