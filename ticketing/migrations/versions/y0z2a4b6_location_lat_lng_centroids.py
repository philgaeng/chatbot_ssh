# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add latitude/longitude to locations and seed NP district centroids

Revision ID: y0z2a4b6
Revises: x9y1z3a5
Create Date: 2026-06-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y0z2a4b6"
down_revision: Union[str, None] = "x9y1z3a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "locations",
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "locations",
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        schema="ticketing",
    )

    from ticketing.seed.seed_location_centroids import apply_district_centroids

    apply_district_centroids(op.get_bind())


def downgrade() -> None:
    op.drop_column("locations", "longitude", schema="ticketing")
    op.drop_column("locations", "latitude", schema="ticketing")
