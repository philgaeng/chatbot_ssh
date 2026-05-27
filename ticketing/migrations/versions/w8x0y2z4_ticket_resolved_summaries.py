# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add ticketing.ticket_resolved_summaries

Revision ID: w8x0y2z4
Revises: v5x7y9z1
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w8x0y2z4"
down_revision: Union[str, None] = "v5x7y9z1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_resolved_summaries",
        sa.Column("ticket_id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("grievance_id", sa.String(64), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_by_user_id", sa.String(128), nullable=True),
        sa.Column("source_resolution_event_id", sa.String(36), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("summary_public_json", sa.JSON(), nullable=True),
        sa.Column("summary_text_en", sa.Text(), nullable=True),
        sa.Column("summary_text_primary", sa.Text(), nullable=True),
        sa.Column("primary_language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("closure_public_token", sa.String(64), nullable=False, unique=True),
        sa.Column("closure_public_url", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation_model", sa.String(64), nullable=False, server_default="pending"),
        sa.Column("generation_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_table("ticket_resolved_summaries", schema="ticketing")
