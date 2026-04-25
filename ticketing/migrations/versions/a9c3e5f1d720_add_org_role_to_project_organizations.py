"""add org_role to project_organizations + seed default org roles in settings

Revision ID: a9c3e5f1d720
Revises: e8d4b6a0f291
Create Date: 2026-04-24

Safe to run: only modifies ticketing.project_organizations + inserts into ticketing.settings
Does NOT touch: grievances, complainants, or any existing public.* table
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "a9c3e5f1d720"
down_revision = "e8d4b6a0f291"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Default org-role vocabulary for public-works / ADB-financed projects.
# Super-admins can edit this later via Settings → System Config.
# ---------------------------------------------------------------------------
DEFAULT_ORG_ROLES = [
    {
        "key": "donor",
        "label": "Donor",
        "description": (
            "Financing institution (e.g. ADB, World Bank, AIIB). "
            "Provides the loan or grant and sets fiduciary / safeguard requirements."
        ),
    },
    {
        "key": "executing_agency",
        "label": "Executing Agency",
        "description": (
            "Government entity formally accountable to the donor; "
            "legal owner of the project (maître d'ouvrage). "
            "e.g. Ministry of Physical Infrastructure and Transport (MoPIT)."
        ),
    },
    {
        "key": "implementing_agency",
        "label": "Implementing Agency",
        "description": (
            "Government body managing day-to-day implementation and contract supervision "
            "(maître d'œuvre). e.g. Department of Roads (DOR)."
        ),
    },
    {
        "key": "main_contractor",
        "label": "Main Contractor",
        "description": "Primary civil-works contractor awarded the construction contract.",
    },
    {
        "key": "subcontractor_t1",
        "label": "Subcontractor (Tier 1)",
        "description": "First-tier subcontractor nominated or approved by the main contractor.",
    },
    {
        "key": "subcontractor_t2",
        "label": "Subcontractor (Tier 2)",
        "description": "Second-tier or specialist subcontractor.",
    },
    {
        "key": "supervision_consultant",
        "label": "Supervision Consultant",
        "description": (
            "Consultant firm contracted to administer the works contract on behalf of the "
            "implementing agency (Engineer's Representative / Contract Administrator)."
        ),
    },
    {
        "key": "specialized_consultant",
        "label": "Specialized Consultant",
        "description": (
            "Technical specialist firm: environmental, social safeguards, resettlement, "
            "community liaison, gender specialist, etc."
        ),
    },
]


def upgrade() -> None:
    # ── 1. Add org_role column to project_organizations ───────────────────────
    op.add_column(
        "project_organizations",
        sa.Column("org_role", sa.String(64), nullable=True),
        schema="ticketing",
    )

    # ── 2. Seed default org roles into settings (skip if already present) ─────
    # Use Python string embed (safe — we own DEFAULT_ORG_ROLES, no user input).
    # Escape single quotes in the JSON just in case (there are none, but be safe).
    roles_json = json.dumps(DEFAULT_ORG_ROLES).replace("'", "''")
    op.execute(
        sa.text(
            f"""
            INSERT INTO ticketing.settings (key, value, updated_at)
            VALUES ('org_roles', '{roles_json}'::jsonb, NOW())
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM ticketing.settings WHERE key = 'org_roles'")
    )
    op.drop_column("project_organizations", "org_role", schema="ticketing")
