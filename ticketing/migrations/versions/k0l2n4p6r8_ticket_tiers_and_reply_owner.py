# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""ticket tiers (viewer.tier column) + complainant_reply_owner_id on tickets

Implements spec 12 tier lifecycle:
  - ticket_viewers.tier: 'observer' | 'informed' (default 'observer', back-compat)
  - tickets.complainant_reply_owner_id: user_id holding reply-to-complainant capability

Revision ID: k0l2n4p6r8
Revises: j8l0n2p4r6
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k0l2n4p6r8"
down_revision: Union[str, None] = "j8l0n2p4r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add tier to ticket_viewers ────────────────────────────────────────
    op.add_column(
        "ticket_viewers",
        sa.Column(
            "tier",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'observer'"),
        ),
        schema="ticketing",
    )
    op.create_index(
        "idx_ticket_viewers_tier",
        "ticket_viewers",
        ["ticket_id", "tier"],
        schema="ticketing",
    )

    # ── 2. Add complainant_reply_owner_id to tickets ──────────────────────────
    op.add_column(
        "tickets",
        sa.Column("complainant_reply_owner_id", sa.String(128), nullable=True),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("tickets", "complainant_reply_owner_id", schema="ticketing")
    op.drop_index("idx_ticket_viewers_tier", table_name="ticket_viewers", schema="ticketing")
    op.drop_column("ticket_viewers", "tier", schema="ticketing")
