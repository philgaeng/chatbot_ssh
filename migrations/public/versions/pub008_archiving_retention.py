"""grievance + file_attachments archiving columns and ARCHIVED status

Revision ID: pub008_archiving_retention
Revises: pub007_complainant_location_geo
Create Date: 2026-06-08

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub008_archiving_retention"
down_revision: Union[str, None] = "pub007_complainant_location_geo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'grievances'
            ) THEN
                ALTER TABLE grievances
                    ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;
                ALTER TABLE grievances
                    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'file_attachments'
            ) THEN
                ALTER TABLE file_attachments
                    ADD COLUMN IF NOT EXISTS storage_tier VARCHAR(16) NOT NULL DEFAULT 'active';
                ALTER TABLE file_attachments
                    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;
                ALTER TABLE file_attachments
                    ADD COLUMN IF NOT EXISTS storage_key TEXT NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        INSERT INTO grievance_statuses
            (status_code, status_name_en, status_name_ne, sort_order, is_active)
        VALUES
            ('archived', 'Archived', 'संग्रहित', 5, TRUE)
        ON CONFLICT (status_code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM grievance_statuses WHERE status_code = 'archived';")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'file_attachments'
            ) THEN
                ALTER TABLE file_attachments DROP COLUMN IF EXISTS storage_key;
                ALTER TABLE file_attachments DROP COLUMN IF EXISTS archived_at;
                ALTER TABLE file_attachments DROP COLUMN IF EXISTS storage_tier;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'grievances'
            ) THEN
                ALTER TABLE grievances DROP COLUMN IF EXISTS archived_at;
                ALTER TABLE grievances DROP COLUMN IF EXISTS is_archived;
            END IF;
        END $$;
        """
    )
