# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Gap A — add owner_organization_id to ticketing.organizations (contractor authorship).

A `third_party` contractor created by an org_admin is an independent root (parent NULL)
outside every org subtree, so the subtree-only maintenance guard (update/delete) left it
editable by super_admin alone. This column stamps the creating org_admin's org node so the
creator + any ancestor-org admin can still maintain it (authority = owner in caller subtree,
in ticketing.services.admin_access.can_admin_org_or_owned). NULL = not owned (institutional
roots, seeded orgs). Mirrors the catalog owner_organization_id added in q7s9u1w3.

Revision ID: h4j6l8n0
Revises: g2i4k6m8
Create Date: 2026-07-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h4j6l8n0"
down_revision: Union[str, None] = "g2i4k6m8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("owner_organization_id", sa.String(length=64), nullable=True),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_organizations_owner_org",
        "organizations",
        "organizations",
        ["owner_organization_id"],
        ["organization_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_organizations_owner_org",
        "organizations",
        ["owner_organization_id"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_organizations_owner_org", table_name="organizations", schema="ticketing"
    )
    op.drop_constraint(
        "fk_organizations_owner_org", "organizations", schema="ticketing", type_="foreignkey"
    )
    op.drop_column("organizations", "owner_organization_id", schema="ticketing")
