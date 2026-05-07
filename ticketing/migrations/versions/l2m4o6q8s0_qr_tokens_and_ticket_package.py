# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add qr_tokens table and package_id to tickets

Revision ID: l2m4o6q8s0
Revises: k0l2n4p6r8
Create Date: 2026-05-07
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "l2m4o6q8s0"
down_revision: Union[str, None] = "k0l2n4p6r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ticketing.qr_tokens ───────────────────────────────────────────────────
    op.create_table(
        "qr_tokens",
        sa.Column("token",               sa.String(32),  nullable=False),
        sa.Column("package_id",          sa.String(36),  nullable=False),
        sa.Column("is_active",           sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("created_at",          sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by_user_id",  sa.String(128), nullable=True),
        sa.Column("expires_at",          sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("token"),
        sa.ForeignKeyConstraint(
            ["package_id"], ["ticketing.project_packages.package_id"],
            ondelete="CASCADE",
        ),
        schema="ticketing",
    )
    op.create_index(
        "idx_qr_tokens_package", "qr_tokens", ["package_id"], schema="ticketing"
    )

    # ── ticketing.tickets — add package_id ────────────────────────────────────
    op.add_column(
        "tickets",
        sa.Column("package_id", sa.String(36), nullable=True),
        schema="ticketing",
    )
    # Soft FK — no hard constraint so tickets created without a QR token are fine
    op.create_index(
        "idx_tickets_package", "tickets", ["package_id"], schema="ticketing"
    )


def downgrade() -> None:
    op.drop_index("idx_tickets_package", table_name="tickets", schema="ticketing")
    op.drop_column("tickets", "package_id", schema="ticketing")
    op.drop_index("idx_qr_tokens_package", table_name="qr_tokens", schema="ticketing")
    op.drop_table("qr_tokens", schema="ticketing")
