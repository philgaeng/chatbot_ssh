# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""roles.actor_category — actor affiliation, soft-narrows the role picker by office type

Revision ID: c8e0g2i4
Revises: b6d8f0h2
Create Date: 2026-07-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8e0g2i4"
down_revision: Union[str, None] = "b6d8f0h2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen at this revision (do NOT import the catalog). Mirrors grm_role_catalog actor_category
# for the seed operational roles. Admin-ladder + custom rows stay NULL (neutral: never demoted).
ROLE_ACTOR_CATEGORY: dict[str, str] = {
    "site_safeguards_focal_person": "government",
    "country_l1_fallback": "government",
    "pd_piu_safeguards_focal": "government",
    "grc_chair": "government",
    "grc_member": "government",
    "seah_national_officer": "government",
    "seah_hq_officer": "government",
    "adb_national_project_director": "donor",
    "adb_hq_safeguards": "donor",
    "adb_hq_project": "donor",
    "adb_hq_exec": "donor",
    "donor_consultant": "donor",
    "donor_national": "donor",
    "donor_hq": "donor",
}


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("actor_category", sa.String(32), nullable=True),
        schema="ticketing",
    )
    when = "\n".join(
        f"WHEN role_key = '{k}' THEN '{v}'" for k, v in ROLE_ACTOR_CATEGORY.items()
    )
    op.get_bind().execute(
        sa.text(
            f"""
            UPDATE ticketing.roles
            SET actor_category = CASE
                {when}
                ELSE actor_category
            END
            """
        )
    )


def downgrade() -> None:
    op.drop_column("roles", "actor_category", schema="ticketing")
