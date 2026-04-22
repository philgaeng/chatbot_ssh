"""add ticketing.officer_scopes table

Revision ID: d5f3e1a09c28
Revises: c4e7d2b91f35
Create Date: 2026-04-22

# Safe to run: only creates ticketing.officer_scopes
# Does NOT touch: grievances, complainants, or any existing public.* table
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d5f3e1a09c28"
down_revision = "c4e7d2b91f35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "officer_scopes",
        sa.Column("scope_id",        sa.String(36),  nullable=False),
        sa.Column("user_id",         sa.String(64),  nullable=False),
        sa.Column("role_key",        sa.String(64),  nullable=False),
        sa.Column("organization_id", sa.String(64),  nullable=False),
        sa.Column("location_code",   sa.String(64),  nullable=True),
        sa.Column("project_code",    sa.String(64),  nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scope_id"),
        schema="ticketing",
    )
    op.create_index(
        "idx_officer_scopes_lookup",
        "officer_scopes",
        ["role_key", "organization_id", "location_code", "project_code"],
        schema="ticketing",
    )
    op.create_index(
        "idx_officer_scopes_user",
        "officer_scopes",
        ["user_id"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_officer_scopes_user",   table_name="officer_scopes", schema="ticketing")
    op.drop_index("idx_officer_scopes_lookup", table_name="officer_scopes", schema="ticketing")
    op.drop_table("officer_scopes", schema="ticketing")
