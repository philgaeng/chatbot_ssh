# Safe to run: only adds nullable columns to ticketing.organizations and ticketing.user_roles
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add default_language to organizations + preferred_language to user_roles

Revision ID: d2e8f4a1b093
Revises: c1d5f8a2e047
Create Date: 2026-04-27 00:00:00.000001

Adds language preference fields (TODO item 8):
  - organizations.default_language VARCHAR(8) DEFAULT 'ne'
    → 'ne' for DOR (Nepali-first field officers)
    → 'en' for ADB (English-first observers/supervisors)

  - user_roles.preferred_language VARCHAR(8) DEFAULT NULL
    → NULL = inherit org default
    → 'en' / 'ne' = officer override

Effective language resolution:
  1. user_roles.preferred_language (if set)
  2. organizations.default_language (org default)
  3. 'en' (hard fallback if org has no language set)

After adding columns we patch the known organisations:
  - DOR already defaults to 'ne' (column default above)
  - ADB is explicitly set to 'en'
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d2e8f4a1b093"
down_revision = "c1d5f8a2e047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add default_language to organizations (default 'ne' — Nepali-first for most field orgs)
    op.add_column(
        "organizations",
        sa.Column("default_language", sa.String(8), nullable=False, server_default="ne"),
        schema="ticketing",
    )
    # Add per-officer override to user_roles (NULL = use org default)
    op.add_column(
        "user_roles",
        sa.Column("preferred_language", sa.String(8), nullable=True),
        schema="ticketing",
    )
    # Patch ADB to English-first
    op.execute(
        "UPDATE ticketing.organizations SET default_language = 'en' "
        "WHERE organization_id = 'ADB'"
    )


def downgrade() -> None:
    op.drop_column("user_roles", "preferred_language", schema="ticketing")
    op.drop_column("organizations", "default_language", schema="ticketing")
