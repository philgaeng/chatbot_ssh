# SPDX-License-Identifier: Apache-2.0

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
    # The organization this workflow or template belongs to (doc 11 §3.3). Every one has one since
    # GRM-116's migration: it decides which resolution actions the workflow can offer, and who may
    # change it. Chosen on create and changed in Settings (GRM-122). SET NULL on org delete leaves a
    # workflow that can offer no action — GRM-120 decides that rule.
    owner_organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
    )
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
    owner_organization: Mapped["Organization | None"] = relationship(  # noqa: F821
        "Organization", foreign_keys=[owner_organization_id], lazy="select", viewonly=True
    )

    @property
    def owner_name(self) -> str | None:
        """The owning organization's name, for the workflow list and editor (GRM-122)."""
        return self.owner_organization.name if self.owner_organization else None


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
    # ── Tier model (spec 12) ─────────────────────────────────────────────────
    # supervisor_role: role key for the step supervisor (notified on escalation/SLA)
    supervisor_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # informed_roles: role keys auto-added as Informed when ticket enters this step
    # (e.g. grc_member at L3). Previous-step actors are added dynamically by the engine.
    informed_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # observer_roles: role keys granted read-only viewer access, zero notifications
    observer_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # informed_pii_access: if True, Informed-tier users can see complainant PII
    informed_pii_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # tier_labels: {tier: {label, description}} — the AUTHOR'S name for each job at this level
    # ("Escalation Lead"), shown read-only wherever the job appears (staffing, case view) instead
    # of a generic tier word. Absent tier → fall back to the bound role's display name, then the
    # generic word. doc 12 §6.2 / doc 13 §5A.1.
    tier_labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # required_tiers: which NON-ACTOR tiers the author marks mandatory ⊆ {supervisor, informed,
    # observer}. The actor is always required and is never listed. Drives the go-live staffing
    # gate (doc 13 §5A.5 / §7 A4).
    required_tiers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # staff_per_package: is this level staffed lot by lot, or once for the whole project?
    # Decided by the WORKFLOW AUTHOR (so, from a project's side, by its type — a typed project
    # cannot deviate). Typically the lower levels are per lot and the upper ladder is
    # project-wide. False = staffed once for the project, which is what every step did before
    # this column existed (migration `p2r4t6v8`). Drives the staffing screen's shape and the
    # go-live staffing gate, which no longer has to guess which was meant.
    staff_per_package: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # actor_can_reassign: per-step self-serve toggle (DESIGN-cast-model §3.4) — when on, the
    # Actor is a reassignment authority for this step (chain: Dispatcher → Supervisor → Actor → PA)
    actor_can_reassign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # stakeholders: legacy display field (human-readable names, not role keys) — kept for UI compat
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
