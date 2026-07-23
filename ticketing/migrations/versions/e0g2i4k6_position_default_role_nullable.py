# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""position_types.default_role_key -> nullable (positions are display-only titles)

Positions become literal job titles with no role/tier link (DESIGN-cast-model §3.2); the
tier is chosen at per-package staffing. The column stays (a soft String(64) ref, no FK)
but is no longer NOT NULL — a new title carries no default role.

Revision ID: e0g2i4k6
Revises: c8e0g2i4
Create Date: 2026-07-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e0g2i4k6"
down_revision: Union[str, None] = "c8e0g2i4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "position_types",
        "default_role_key",
        existing_type=sa.String(64),
        nullable=True,
        schema="ticketing",
    )


def downgrade() -> None:
    # Restore NOT NULL — backfill any rows created without a default first (defensive).
    op.execute(
        "UPDATE ticketing.position_types "
        "SET default_role_key = 'site_safeguards_focal_person' "
        "WHERE default_role_key IS NULL"
    )
    op.alter_column(
        "position_types",
        "default_role_key",
        existing_type=sa.String(64),
        nullable=False,
        schema="ticketing",
    )
