# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Add email + address to ticketing.organizations (SH-4).

Additive nullable columns backing the org duplicate-candidate finder (corporate
email-domain + address match signals, design §2.4). No backfill — existing rows
get NULL.

Revision ID: k1m3o5q7
Revises: h2j4l6n8
Create Date: 2026-07-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1m3o5q7"
down_revision: Union[str, None] = "h2j4l6n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("email", sa.String(length=255), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "organizations",
        sa.Column("address", sa.Text(), nullable=True),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("organizations", "address", schema="ticketing")
    op.drop_column("organizations", "email", schema="ticketing")
