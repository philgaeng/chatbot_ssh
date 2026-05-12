# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add ticketing.officer_onboarding for invited vs active (Keycloak webhook)

Revision ID: o5p7q9r1
Revises: n4p6r8t0
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "o5p7q9r1"
down_revision: Union[str, None] = "n4p6r8t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "officer_onboarding",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
        schema="ticketing",
    )

    # Existing roster users are treated as already onboarded.
    op.execute(
        """
        INSERT INTO ticketing.officer_onboarding (user_id, status, updated_at)
        SELECT DISTINCT ur.user_id, 'active', now()
        FROM ticketing.user_roles ur
        ON CONFLICT (user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("officer_onboarding", schema="ticketing")
