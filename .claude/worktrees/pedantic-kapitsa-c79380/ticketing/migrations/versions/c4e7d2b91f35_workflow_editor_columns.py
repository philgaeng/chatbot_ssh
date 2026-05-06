"""add workflow editor columns (status, version, template, is_deleted)

Revision ID: c4e7d2b91f35
Revises: b2f1a9c34d87
Create Date: 2026-04-21

# Safe to run: only alters ticketing.workflow_definitions and ticketing.workflow_steps
# Does NOT touch: grievances, complainants, or any existing public.* table
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "c4e7d2b91f35"
down_revision = "b2f1a9c34d87"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── workflow_definitions ──────────────────────────────────────────────────
    op.add_column("workflow_definitions",
        sa.Column("status", sa.String(32), nullable=False, server_default="published"),
        schema="ticketing")
    op.add_column("workflow_definitions",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        schema="ticketing")
    op.add_column("workflow_definitions",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default="false"),
        schema="ticketing")
    op.add_column("workflow_definitions",
        sa.Column("template_source_id", sa.String(36), nullable=True),
        schema="ticketing")
    op.add_column("workflow_definitions",
        sa.Column("updated_by_user_id", sa.String(64), nullable=True),
        schema="ticketing")

    # ── workflow_steps ────────────────────────────────────────────────────────
    op.add_column("workflow_steps",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        schema="ticketing")


def downgrade() -> None:
    op.drop_column("workflow_steps", "is_deleted", schema="ticketing")
    for col in ["updated_by_user_id", "template_source_id", "is_template", "version", "status"]:
        op.drop_column("workflow_definitions", col, schema="ticketing")
