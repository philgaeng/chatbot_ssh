# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add chatbot_base_url to ticketing.projects

Each project can point to a different local chatbot backend URL, enabling
the ticketing system to proxy complainant-info edits back to the correct
chatbot instance in a multi-country deployment.

Revision ID: h5e7g9i1k3m5_add_project_chatbot_url
Revises: g4d6f8b0c2e5
Create Date: 2026-04-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h5e7g9i1k3m5_add_project_chatbot_url"
down_revision: Union[str, None] = "g4d6f8b0c2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen alembic_version.version_num to accommodate long revision IDs.
    # The default VARCHAR(32) is too narrow for IDs like this one (35 chars).
    op.execute(
        """
        ALTER TABLE ticketing.alembic_version
        ALTER COLUMN version_num TYPE VARCHAR(128);
        """
    )
    op.execute(
        """
        ALTER TABLE ticketing.projects
        ADD COLUMN IF NOT EXISTS chatbot_base_url TEXT;
        """
    )
    # Seed the known local value for the KL Road project so existing rows work
    # immediately after migration without a re-seed.
    op.execute(
        """
        UPDATE ticketing.projects
        SET chatbot_base_url = 'http://backend:5001'
        WHERE short_code = 'KL_ROAD'
          AND chatbot_base_url IS NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ticketing.projects
        DROP COLUMN IF EXISTS chatbot_base_url;
        """
    )
