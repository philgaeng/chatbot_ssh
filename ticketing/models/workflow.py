"""
ticketing.workflow_definitions, ticketing.workflow_steps, ticketing.workflow_assignments
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = {"schema": "ticketing"}

    workflow_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workflow_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "standard" or "seah"
    workflow_type: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    # "draft" | "published" | "archived"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep",
        back_populates="workflow",
        order_by="WorkflowStep.step_order",
        lazy="select",
    )
    assignments: Mapped[list["WorkflowAssignment"]] = relationship(
        "WorkflowAssignment", back_populates="workflow", lazy="select"
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        Index("idx_workflow_steps_workflow_order", "workflow_id", "step_order"),
        {"schema": "ticketing"},
    )

    step_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.workflow_definitions.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_role_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # SLA — null = no specific timeline (e.g. Level 4 legal)
    response_time_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stakeholders: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expected_actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition", back_populates="steps"
    )


class WorkflowAssignment(Base):
    __tablename__ = "workflow_assignments"
    __table_args__ = (
        Index(
            "idx_workflow_assign_org_loc_pri",
            "organization_id", "location_code", "project_code", "priority",
        ),
        {"schema": "ticketing"},
    )

    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    location_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.workflow_definitions.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition", back_populates="assignments"
    )
