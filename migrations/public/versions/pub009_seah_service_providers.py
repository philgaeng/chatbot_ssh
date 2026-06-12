"""SEAH service providers directory (municipality-scoped support centres).

Revision ID: pub009_seah_service_providers
Revises: pub008_archiving_retention
Create Date: 2026-06-12

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub009_seah_service_providers"
down_revision: Union[str, None] = "pub008_archiving_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS seah_service_providers (
            seah_service_provider_id TEXT PRIMARY KEY,
            country_code TEXT NOT NULL DEFAULT 'NP',
            province_code TEXT,
            district_code TEXT,
            municipality_code TEXT,
            province TEXT,
            district TEXT,
            municipality TEXT,
            ward TEXT,
            seah_center_name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            opening_days TEXT,
            opening_hours TEXT,
            remarks TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_seah_service_providers_municipality_code
            ON seah_service_providers (municipality_code)
            WHERE municipality_code IS NOT NULL AND is_active = TRUE;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_seah_service_providers_district_code
            ON seah_service_providers (district_code)
            WHERE is_active = TRUE;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_seah_service_providers_district_code;")
    op.execute("DROP INDEX IF EXISTS idx_seah_service_providers_municipality_code;")
    op.execute("DROP TABLE IF EXISTS seah_service_providers;")
