# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""roles.archetype — permission-template family, groups the role pickers by function

Revision ID: b6d8f0h2
Revises: w3y5a7c9
Create Date: 2026-07-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b6d8f0h2"
down_revision: Union[str, None] = "w3y5a7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen at this revision (do NOT import the catalog — migrations are historical snapshots).
# Mirrors ticketing.constants.grm_role_catalog archetypes for the seed operational roles.
# Admin-ladder roles and pre-archetype custom rows stay NULL (ungrouped in the picker).
ROLE_ARCHETYPE: dict[str, str] = {
    "site_safeguards_focal_person": "field_actor",
    "country_l1_fallback": "field_actor",
    "pd_piu_safeguards_focal": "supervisor",
    "grc_chair": "grc_committee",
    "grc_member": "grc_member",
    "adb_national_project_director": "observer",
    "adb_hq_safeguards": "observer",
    "adb_hq_project": "observer",
    "adb_hq_exec": "observer",
    "donor_consultant": "observer",
    "donor_national": "observer",
    "donor_hq": "observer",
    "seah_national_officer": "seah_handler",
    "seah_hq_officer": "seah_handler",
}


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("archetype", sa.String(32), nullable=True),
        schema="ticketing",
    )
    # Backfill known seed operational roles so non-reseeded DBs group correctly.
    when = "\n".join(
        f"WHEN role_key = '{k}' THEN '{v}'" for k, v in ROLE_ARCHETYPE.items()
    )
    op.get_bind().execute(
        sa.text(
            f"""
            UPDATE ticketing.roles
            SET archetype = CASE
                {when}
                ELSE archetype
            END
            """
        )
    )


def downgrade() -> None:
    op.drop_column("roles", "archetype", schema="ticketing")
