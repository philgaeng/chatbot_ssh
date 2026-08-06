# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""A workflow level says whether it is staffed once for the project, or lot by lot.

Decided 2026-08-04 (Philippe): *"typically higher levels are at the project level while lower
levels are by package"*, and **the type decides it, not the project** — a project cannot deviate
from its type, so the flag belongs to the workflow the type binds, next to `tier_labels` and
`required_tiers` (DECISION-author-defined-slots §3.2: jobs at a level stay on the workflow).

Until now nothing recorded this. Staffing was project-wide, and a lot differed only if somebody
happened to add an override inside that lot's row. So the system could not tell *"staffed
project-wide, deliberately"* from *"per-lot, and nobody has done it yet"* — which is exactly
what go-live's staffing checks had to guess at (C1 required a Level-1 officer per lot but
accepted a project-wide one as a fallback, because it had no way to know which was intended).

`False` = staffed once for the whole project. That is what every existing step did, so the
default preserves current behaviour exactly.

Revision ID: p2r4t6v8
Revises: n0p2r4t6
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p2r4t6v8"
down_revision: Union[str, None] = "n0p2r4t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_steps",
        sa.Column(
            "staff_per_package",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("workflow_steps", "staff_per_package", schema="ticketing")
