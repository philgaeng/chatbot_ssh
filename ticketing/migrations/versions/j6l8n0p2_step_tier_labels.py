# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Author-named jobs per level: workflow_steps.tier_labels + required_tiers.

doc 12 §2 has documented both columns since June and doc 13 §5A builds the staffing screen
and go-live check A4 on them — but they existed in no migration, model, schema or endpoint.
The staffing screen therefore fell back to generic tier words, and A4 gated on a set nothing
could populate. See DECISION-author-defined-slots.md §3.2.

  tier_labels     {tier: {label, description}} — the author's name for each job at this level.
                  Absent tier = use the bound role's display name, then the generic word.
  required_tiers  the non-actor tiers the author marks mandatory. The ACTOR IS ALWAYS
                  REQUIRED and is never listed here — a level with nobody to work it is not
                  a level. Drives the project staffing gate (13 §5A.5 / §7 A4).

Both default to empty, so every existing step keeps today's behaviour until an author
edits it.

Revision ID: j6l8n0p2
Revises: h4j6l8n0
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j6l8n0p2"
down_revision: Union[str, None] = "h4j6l8n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_steps",
        sa.Column("tier_labels", sa.JSON(), nullable=False, server_default="{}"),
        schema="ticketing",
    )
    op.add_column(
        "workflow_steps",
        sa.Column("required_tiers", sa.JSON(), nullable=False, server_default="[]"),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("workflow_steps", "required_tiers", schema="ticketing")
    op.drop_column("workflow_steps", "tier_labels", schema="ticketing")
