# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Project participants (doc 13 / DECISION 2026-07-10): implementing agency + donors.

Adds the two thin participant structures that replace the per-project actor-role catalog:

* ``projects.implementing_agency_org_id`` — the single accountable org (the signing
  ministry; routing + reporting anchor). Back-filled from the legacy
  ``project_organizations.org_role = 'implementing_agency'`` mapping.
* ``project_donors`` — 0..n optional funder orgs (category ``donor``). Back-filled from
  ``project_organizations.org_role = 'donor'``. Exists solely to hang the last-step-informed
  donor guardrail (OC-04 §5.6).

**Expand phase only.** The legacy ``project_actor_roles`` table, ``project_organizations.org_role``,
and ``project_types.routing_org_role`` are *kept* here (routing reads the new field with a
back-compat fallback to ``org_role``); the frontend still references them. Their physical
drop is a later *contract* migration, once the rebuilt Settings UI no longer reads them.

Revision ID: u1w3y5a7
Revises: s9u1w3y5
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u1w3y5a7"
down_revision: Union[str, None] = "s9u1w3y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Implementing agency — a single defaulted org pointer on the project.
    op.add_column(
        "projects",
        sa.Column("implementing_agency_org_id", sa.String(length=64), nullable=True),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_projects_implementing_agency",
        "projects",
        "organizations",
        ["implementing_agency_org_id"],
        ["organization_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_projects_implementing_agency",
        "projects",
        ["implementing_agency_org_id"],
        schema="ticketing",
    )
    # Back-fill from the legacy org_role='implementing_agency' link (an arbitrary matching
    # row per project — IA is singular in practice, so this is deterministic enough).
    op.execute(
        """
        UPDATE ticketing.projects p
        SET implementing_agency_org_id = po.organization_id
        FROM ticketing.project_organizations po
        WHERE po.project_id = p.project_id
          AND po.org_role = 'implementing_agency'
          AND p.implementing_agency_org_id IS NULL
        """
    )

    # 2. project_donors — 0..n donor orgs per project.
    op.create_table(
        "project_donors",
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("project_id", "organization_id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["ticketing.projects.project_id"],
            name="fk_project_donors_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["ticketing.organizations.organization_id"],
            name="fk_project_donors_org",
            ondelete="CASCADE",
        ),
        schema="ticketing",
    )
    # Back-fill from legacy org_role='donor' links.
    op.execute(
        """
        INSERT INTO ticketing.project_donors (project_id, organization_id)
        SELECT DISTINCT po.project_id, po.organization_id
        FROM ticketing.project_organizations po
        WHERE po.org_role = 'donor'
        ON CONFLICT (project_id, organization_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("project_donors", schema="ticketing")
    op.drop_index(
        "idx_projects_implementing_agency", table_name="projects", schema="ticketing"
    )
    op.drop_constraint(
        "fk_projects_implementing_agency", "projects", schema="ticketing", type_="foreignkey"
    )
    op.drop_column("projects", "implementing_agency_org_id", schema="ticketing")
