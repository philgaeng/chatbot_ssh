# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Project types belong to a top-level organization.

DECISION-author-defined-slots §3.1: a type is a reusable template owned by the organization
that runs the projects. "New project" asks for the organization first and then offers only
that organization's types, and an `org_admin` may author types within its own subtree instead
of filing a request with a super admin.

NULL = a global type, seeded by `super_admin` and offered to everyone. Every existing type is
global, so nothing changes for current data.

Revision ID: l8n0p2r4
Revises: j6l8n0p2
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l8n0p2r4"
down_revision: Union[str, None] = "j6l8n0p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_types",
        sa.Column("owner_organization_id", sa.String(64), nullable=True),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_project_types_owner_org",
        "project_types",
        "organizations",
        ["owner_organization_id"],
        ["organization_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_project_types_owner",
        "project_types",
        ["owner_organization_id"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_project_types_owner", table_name="project_types", schema="ticketing")
    op.drop_constraint("fk_project_types_owner_org", "project_types", schema="ticketing", type_="foreignkey")
    op.drop_column("project_types", "owner_organization_id", schema="ticketing")
