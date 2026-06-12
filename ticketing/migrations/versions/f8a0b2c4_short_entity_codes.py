# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Shorten package_code values; migrate KL Road lot ids to 01–05.

Revision ID: f8a0b2c4
Revises: e7f9a1b3
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f8a0b2c4"
down_revision = "e7f9a1b3"
branch_labels = None
depends_on = None

_LEGACY_TO_SHORT = (
    ("SHEP/OCB/KL/01", "01"),
    ("SHEP/OCB/KL/02", "02"),
    ("SHEP/OCB/KL/03", "03"),
    ("SHEP/OCB/MBKL/04", "04"),
    ("SHEP/OCB/MBKL/05", "05"),
)


def upgrade() -> None:
    for old_code, new_code in _LEGACY_TO_SHORT:
        op.execute(
            sa.text(
                """
                UPDATE ticketing.project_packages
                SET package_code = :new_code, updated_at = NOW()
                WHERE package_code = :old_code
                """
            ).bindparams(old_code=old_code, new_code=new_code)
        )

    op.alter_column(
        "project_packages",
        "package_code",
        existing_type=sa.String(128),
        type_=sa.String(8),
        existing_nullable=False,
        schema="ticketing",
    )


def downgrade() -> None:
    op.alter_column(
        "project_packages",
        "package_code",
        existing_type=sa.String(8),
        type_=sa.String(128),
        existing_nullable=False,
        schema="ticketing",
    )

    for old_code, new_code in _LEGACY_TO_SHORT:
        op.execute(
            sa.text(
                """
                UPDATE ticketing.project_packages
                SET package_code = :old_code, updated_at = NOW()
                WHERE package_code = :new_code
                  AND project_id IN (
                      SELECT project_id FROM ticketing.projects WHERE short_code = 'KL_ROAD'
                  )
                """
            ).bindparams(old_code=old_code, new_code=new_code)
        )
