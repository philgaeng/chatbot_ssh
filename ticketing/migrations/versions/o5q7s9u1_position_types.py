# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Create ticketing.position_types + the position→role matrix (OC-02, doc 16 §3.2).

Position types are the org-chart directory layer: a title (e.g. "Senior Divisional
Engineer") that lives at one or more unit levels and carries a default role (the matrix).
They are descriptive — they *generate* user_roles/officer_scopes at invite time
(OC-03); they never replace the enforcement rows.

`owner_organization_id` is the first org-scoped-catalog column (doc 11 §3.3): a position
type is available at its owning org node + descendants (`NULL` = global). SH-7 wires the
availability filter and extends the same column to roles / workflow_definitions.

Revision ID: o5q7s9u1
Revises: m3o5q7s9
Create Date: 2026-07-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o5q7s9u1"
down_revision: Union[str, None] = "m3o5q7s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "position_types",
        sa.Column("position_type_id", sa.String(length=36), primary_key=True),
        sa.Column("position_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("display_name_ne", sa.Text(), nullable=True),
        sa.Column("allowed_unit_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("reports_to_position_key", sa.String(length=64), nullable=True),
        sa.Column("reports_to_locus", sa.String(length=16), nullable=True),
        sa.Column("default_role_key", sa.String(length=64), nullable=False),
        sa.Column("visibility_mode", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("workflow_track", sa.String(length=16), nullable=False, server_default="standard"),
        sa.Column("owner_organization_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("position_key", name="uq_position_types_position_key"),
        sa.ForeignKeyConstraint(
            ["owner_organization_id"],
            ["ticketing.organizations.organization_id"],
            name="fk_position_types_owner_org",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "visibility_mode IN ('none', 'direct_reports', 'subtree')",
            name="ck_position_types_visibility_mode",
        ),
        sa.CheckConstraint(
            "reports_to_locus IS NULL OR reports_to_locus IN ('same_unit', 'parent_unit')",
            name="ck_position_types_reports_to_locus",
        ),
        sa.CheckConstraint(
            "workflow_track IN ('standard', 'seah', 'both')",
            name="ck_position_types_workflow_track",
        ),
        schema="ticketing",
    )
    op.create_index(
        "idx_position_types_owner_org",
        "position_types",
        ["owner_organization_id"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_position_types_owner_org", table_name="position_types", schema="ticketing")
    op.drop_table("position_types", schema="ticketing")
