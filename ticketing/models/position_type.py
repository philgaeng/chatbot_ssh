# SPDX-License-Identifier: Apache-2.0

"""
ticketing.position_types — the org-chart position catalog + position→role matrix (OC-02).

A position type is a title (e.g. "Senior Divisional Engineer") that exists at one or more
org-unit levels and carries a `default_role_key` (the matrix). Positions are descriptive;
they generate user_roles/officer_scopes at invite time (OC-03), never replace them.
~20–50 rows expected — not individual seats.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Domain values (doc 16 §3.2). Kept here as the canonical tuples the router/tests import.
VISIBILITY_MODES = ("none", "direct_reports", "subtree")
REPORTS_TO_LOCI = ("same_unit", "parent_unit")
POSITION_WORKFLOW_TRACKS = ("standard", "seah", "both")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class PositionType(Base):
    __tablename__ = "position_types"
    __table_args__ = (
        CheckConstraint(
            "visibility_mode IN ('none', 'direct_reports', 'subtree')",
            name="ck_position_types_visibility_mode",
        ),
        CheckConstraint(
            "reports_to_locus IS NULL OR reports_to_locus IN ('same_unit', 'parent_unit')",
            name="ck_position_types_reports_to_locus",
        ),
        CheckConstraint(
            "workflow_track IN ('standard', 'seah', 'both')",
            name="ck_position_types_workflow_track",
        ),
        Index("idx_position_types_owner_org", "owner_organization_id"),
        {"schema": "ticketing"},
    )

    position_type_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Slug — immutable after create (PositionTypeUpdate omits it, mirroring roles.role_key).
    position_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name_ne: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON list of unit_type values this position exists at (validated app-side ⊆ UNIT_TYPES).
    allowed_unit_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Default reporting rule — by position_key (string ref, no hard FK), + locus.
    reports_to_position_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reports_to_locus: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Legacy role link — nullable (DESIGN-cast-model §3.2): a position is a display-only
    # title with no role/tier, so new titles carry no default. Kept as a soft String(64)
    # ref for back-compat; the tier is chosen at per-package staffing, never here.
    default_role_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visibility_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    workflow_track: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    # Org-scoped catalog (doc 11 §3.3): available at this org node + descendants; NULL = global.
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
