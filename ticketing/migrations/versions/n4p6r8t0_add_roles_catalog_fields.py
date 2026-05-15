# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add description and workflow_scope to ticketing.roles

Revision ID: n4p6r8t0
Revises: l2m4o6q8s0
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "n4p6r8t0"
down_revision: Union[str, None] = "l2m4o6q8s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("description", sa.Text(), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "roles",
        sa.Column("workflow_scope", sa.String(length=32), nullable=True),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("roles", "workflow_scope", schema="ticketing")
    op.drop_column("roles", "description", schema="ticketing")
