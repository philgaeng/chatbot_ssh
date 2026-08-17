# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Officer lifecycle: soft-deactivation flag on officer_onboarding (Frame-11).

Adds ``officer_onboarding.is_active`` (default TRUE) + ``deactivated_at`` so an
officer's GRM access can be revoked without hard-deleting their history
(user_roles / officer_scopes / ticket audit trail). Independent of the existing
``status`` (invited|active) column — reactivation keeps the original onboarding status.

Revision ID: w3y5a7c9
Revises: u1w3y5a7
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w3y5a7c9"
down_revision: Union[str, None] = "u1w3y5a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "officer_onboarding",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema="ticketing",
    )
    op.add_column(
        "officer_onboarding",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        schema="ticketing",
    )
    # Drop the transient server_default now that existing rows are backfilled to TRUE;
    # the ORM model owns the default going forward.
    op.alter_column(
        "officer_onboarding",
        "is_active",
        server_default=None,
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("officer_onboarding", "deactivated_at", schema="ticketing")
    op.drop_column("officer_onboarding", "is_active", schema="ticketing")
