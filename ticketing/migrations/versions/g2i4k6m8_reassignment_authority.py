# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""reassignment authority — step actor_can_reassign toggle + reassign_dispatcher role

DESIGN-cast-model §3.4: reassignment is a capability resolved by a fallback chain that can
never dead-end (Dispatcher → Supervisor → Actor self-serve → project_admin). This adds the
per-step Actor self-serve toggle and seeds the system `reassign_dispatcher` plumbing role
(staffed per project/package as the optional Dispatcher).

Revision ID: g2i4k6m8
Revises: e0g2i4k6
Create Date: 2026-07-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g2i4k6m8"
down_revision: Union[str, None] = "e0g2i4k6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_steps",
        sa.Column("actor_can_reassign", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="ticketing",
    )
    # System plumbing role for the optional Dispatcher (staffed per project/package). Idempotent.
    op.execute(
        """
        INSERT INTO ticketing.roles
            (role_id, role_key, display_name, description, workflow_scope, jurisdiction_mode,
             permissions, role_kind, role_origin, created_at, updated_at)
        SELECT gen_random_uuid(), 'reassign_dispatcher', 'Dispatcher',
               'Reassignment authority (cast model plumbing — not user-editable).',
               'Both', 'field', '[]'::json, 'operational', 'system', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM ticketing.roles WHERE role_key = 'reassign_dispatcher')
        """
    )


def downgrade() -> None:
    op.drop_column("workflow_steps", "actor_can_reassign", schema="ticketing")
    op.execute("DELETE FROM ticketing.roles WHERE role_key = 'reassign_dispatcher'")
