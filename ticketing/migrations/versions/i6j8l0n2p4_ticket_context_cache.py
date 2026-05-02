# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add ticketing.ticket_context_cache

Stores one PII-clean context document per ticket (input to LLM) and the
structured findings JSON (output from LLM).  Rebuilt by context_builder.py
whenever summary_regen_required events are committed.

Revision ID: i6j8l0n2p4
Revises: h5e7g9i1k3m5_add_project_chatbot_url
Create Date: 2026-05-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i6j8l0n2p4"
down_revision: Union[str, None] = "h5e7g9i1k3m5_add_project_chatbot_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_context_cache",
        sa.Column("ticket_id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "context_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("findings_updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_table("ticket_context_cache", schema="ticketing")
