# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add ticketing.admin_audit_log for officer management audit trail

Revision ID: p6q8s0t2
Revises: o5p7q9r1
Create Date: 2026-05-15
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p6q8s0t2"
down_revision: Union[str, None] = "o5p7q9r1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column("audit_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_user_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("audit_id"),
        schema="ticketing",
    )
    op.create_index(
        "idx_admin_audit_target",
        "admin_audit_log",
        ["target_user_id", "created_at"],
        unique=False,
        schema="ticketing",
    )
    op.create_index(
        "idx_admin_audit_actor",
        "admin_audit_log",
        ["actor_user_id", "created_at"],
        unique=False,
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_admin_audit_actor", table_name="admin_audit_log", schema="ticketing")
    op.drop_index("idx_admin_audit_target", table_name="admin_audit_log", schema="ticketing")
    op.drop_table("admin_audit_log", schema="ticketing")
