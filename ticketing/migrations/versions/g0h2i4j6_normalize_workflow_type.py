# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Normalize workflow_definitions.workflow_type to lowercase.

Revision ID: g0h2i4j6
Revises: f8a0b2c4
"""
from __future__ import annotations

from alembic import op

revision = "g0h2i4j6"
down_revision = "f8a0b2c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE ticketing.workflow_definitions
        SET workflow_type = lower(workflow_type)
        WHERE workflow_type IS NOT NULL
          AND workflow_type <> lower(workflow_type)
        """
    )


def downgrade() -> None:
    pass
