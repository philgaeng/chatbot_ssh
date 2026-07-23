# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Create ticketing.officer_positions (OC-03, doc 16 §3.3).

An officer_position records that an officer holds a position type at an org unit. It is
**descriptive** — invite-by-position *generates* the enforcement rows (user_roles +
officer_scopes) via the existing helpers; positions are never read for access control.
Multiple active positions per officer are allowed (dual-hat). `reports_to_user_id` is an
HR/admin override only — it does NOT feed grievance supervision (that is the per-(project,
step) resolver, DECISION 2026-07-10 §5).

Revision ID: s9u1w3y5
Revises: q7s9u1w3
Create Date: 2026-07-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s9u1w3y5"
down_revision: Union[str, None] = "q7s9u1w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "officer_positions",
        sa.Column("officer_position_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("position_type_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("reports_to_user_id", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        # RESTRICT: a position type in use by any position cannot be deleted (the router's
        # delete guard surfaces this as a friendly 409 before the DB backstop fires).
        sa.ForeignKeyConstraint(
            ["position_type_id"],
            ["ticketing.position_types.position_type_id"],
            name="fk_officer_positions_position_type",
            ondelete="RESTRICT",
        ),
        # A position is meaningless without its org unit — cascade if the org is deleted.
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["ticketing.organizations.organization_id"],
            name="fk_officer_positions_org",
            ondelete="CASCADE",
        ),
        schema="ticketing",
    )
    op.create_index(
        "idx_officer_positions_user", "officer_positions", ["user_id"], schema="ticketing"
    )
    op.create_index(
        "idx_officer_positions_position_type",
        "officer_positions",
        ["position_type_id"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_officer_positions_position_type", table_name="officer_positions", schema="ticketing")
    op.drop_index("idx_officer_positions_user", table_name="officer_positions", schema="ticketing")
    op.drop_table("officer_positions", schema="ticketing")
