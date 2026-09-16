# SPDX-License-Identifier: Apache-2.0

"""
ticketing.resolution_actions — the catalog of what an officer can record as *done* on a case —
and ticketing.workflow_resolution_actions, each workflow's ordered selection from it (GRM-116).

Org-scoped like every other catalog item (doc 11 §3.3) with **one difference: nothing is global**
(Q-10). Every action belongs to one organization. An action owned by a **ministry** (a top
organization, no parent) is **shared**; one owned below its ministry is **local** and must *count as*
one shared action of that ministry (`counts_as_code`), so national totals stay whole. An action is
usable by a workflow owned at its organization or below.

⚠ `owner_organization_id` is ON DELETE RESTRICT, unlike `workflow_definitions`' SET NULL: an org
deleted out from under its actions would detach one ministry's vocabulary from its ministry. Actions
are never deleted — historical ticket events cite their codes.

"Same ministry" and "shared" are facts about the organization tree, so `counts_as_code` is checked
in ``services/resolution_catalog.py``, not by a constraint.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ResolutionAction(Base):
    __tablename__ = "resolution_actions"
    __table_args__ = (
        Index("idx_resolution_actions_owner_org", "owner_organization_id"),
        {"schema": "ticketing"},
    )

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    default_wording: Mapped[str] = mapped_column(Text, nullable=False)
    owner_organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # No screen sets it in this lane; kept for clean-up (GRM-123).
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The shared action of the same ministry a local action counts as in national reports.
    # Required for a local action, NULL for a shared one.
    counts_as_code: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.resolution_actions.code", ondelete="RESTRICT"),
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class WorkflowResolutionAction(Base):
    __tablename__ = "workflow_resolution_actions"
    __table_args__ = (
        Index("idx_workflow_resolution_actions_code", "code"),
        {"schema": "ticketing"},
    )

    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.workflow_definitions.workflow_id", ondelete="CASCADE"),
        primary_key=True,
    )
    code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.resolution_actions.code", ondelete="RESTRICT"),
        primary_key=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
