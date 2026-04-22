"""add ticketing.ticket_files table

Revision ID: b2f1a9c34d87
Revises: e3ca0a118dbf
Create Date: 2026-04-21

# Safe to run: only creates ticketing.ticket_files
# Does NOT touch: grievances, complainants, or any existing public.* table
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b2f1a9c34d87"
down_revision = "e3ca0a118dbf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_files",
        sa.Column("file_id",              sa.String(36),  primary_key=True, nullable=False),
        sa.Column("ticket_id",            sa.String(36),  nullable=False),
        sa.Column("file_name",            sa.String(255), nullable=False),
        sa.Column("file_path",            sa.String(512), nullable=False),
        sa.Column("file_type",            sa.String(50),  nullable=True),
        sa.Column("file_size",            sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("caption",              sa.String(500), nullable=True),
        sa.Column("uploaded_by_user_id",  sa.String(64),  nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="ticketing",
    )
    op.create_index(
        "idx_ticket_files_ticket_id",
        "ticket_files",
        ["ticket_id"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_ticket_files_ticket_id", table_name="ticket_files", schema="ticketing")
    op.drop_table("ticket_files", schema="ticketing")
