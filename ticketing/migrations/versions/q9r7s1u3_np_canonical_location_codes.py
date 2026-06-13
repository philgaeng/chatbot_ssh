# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""rewrite Nepal location PKs from legacy NP_* to canonical P1 / P1_* (LOCATION_CODES.md)

Revision ID: q9r7s1u3
Revises: p6q8s0t2
Create Date: 2026-05-16
"""
from __future__ import annotations

from typing import Union

from alembic import op

revision: str = "q9r7s1u3"
down_revision: Union[str, None] = "p6q8s0t2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Data migration only — invoked by Alembic; helper uses raw SQL (no ORM) for schema safety.
    from ticketing.seed.migrate_np_legacy_location_codes import migrate

    bind = op.get_bind()
    migrate(bind)


def downgrade() -> None:
    # Irreversible: canonical codes intentionally replace NP_* identifiers.
    pass
