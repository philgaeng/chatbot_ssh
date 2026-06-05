"""complainant location_geo + file attachment client metadata

Revision ID: pub007_complainant_location_geo
Revises: pub006_keycloak_schema
Create Date: 2026-06-03

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub007_complainant_location_geo"
down_revision: Union[str, None] = "pub006_keycloak_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_location_geo_column(table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = '{table_name}'
            ) THEN
                ALTER TABLE {table_name}
                ADD COLUMN IF NOT EXISTS location_geo TEXT;
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    _add_location_geo_column("complainants")
    _add_location_geo_column("complainants_seah")
    _add_location_geo_column("contact_info")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'file_attachments'
            ) THEN
                ALTER TABLE file_attachments
                ADD COLUMN IF NOT EXISTS client_metadata JSONB;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'file_attachments'
            ) THEN
                ALTER TABLE file_attachments DROP COLUMN IF EXISTS client_metadata;
            END IF;
        END $$;
        """
    )
    for table_name in ("contact_info", "complainants_seah", "complainants"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = '{table_name}'
                ) THEN
                    ALTER TABLE {table_name} DROP COLUMN IF EXISTS location_geo;
                END IF;
            END $$;
            """
        )
