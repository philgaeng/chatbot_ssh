# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add is_archived and archived_at to ticketing.tickets

Revision ID: z1a3b5c7
Revises: y0z2a4b6
Create Date: 2026-06-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z1a3b5c7"
down_revision: Union[str, None] = "y0z2a4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="ticketing",
    )
    op.add_column(
        "tickets",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        schema="ticketing",
    )
    op.create_index(
        "idx_tickets_is_archived_status",
        "tickets",
        ["is_archived", "status_code"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_tickets_is_archived_status", table_name="tickets", schema="ticketing")
    op.drop_column("tickets", "archived_at", schema="ticketing")
    op.drop_column("tickets", "is_archived", schema="ticketing")
