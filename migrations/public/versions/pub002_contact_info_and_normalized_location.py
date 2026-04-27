"""public contact info and normalized location fields

Revision ID: pub002_contact_info_and_normalized_location
Revises: pub001_seah_reporter_category
Create Date: 2026-04-24

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub002_contact_info_and_normalized_location"
down_revision: Union[str, None] = "pub001_seah_reporter_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_info (
            contact_id TEXT PRIMARY KEY,
            country_code TEXT NOT NULL,
            location_code TEXT,
            level_1_name TEXT,
            level_2_name TEXT,
            level_3_name TEXT,
            level_4_name TEXT,
            level_5_name TEXT,
            level_6_name TEXT,
            level_1_code TEXT,
            level_2_code TEXT,
            level_3_code TEXT,
            level_4_code TEXT,
            level_5_code TEXT,
            level_6_code TEXT,
            phone_e164 TEXT,
            email TEXT,
            address_line TEXT,
            location_resolution_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_persons (
            resource_person_id TEXT PRIMARY KEY,
            contact_id TEXT,
            full_name TEXT,
            birthdate DATE,
            country_code TEXT,
            role_key TEXT,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_contact_info_country_location
            ON contact_info(country_code, location_code);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resource_persons_contact_id
            ON resource_persons(contact_id);
        """
    )

    for table_name in ("complainants", "complainants_seah"):
        op.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS contact_id TEXT;")
        op.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS country_code TEXT;")
        op.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS location_code TEXT;")
        op.execute(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS location_resolution_status TEXT;"
        )
        for level in range(1, 7):
            op.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS level_{level}_name TEXT;")
            op.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS level_{level}_code TEXT;")

    op.execute("CREATE INDEX IF NOT EXISTS idx_complainants_contact_id ON complainants(contact_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_complainants_location_code ON complainants(location_code);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_complainants_seah_contact_id ON complainants_seah(contact_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_complainants_seah_contact_id;")
    op.execute("DROP INDEX IF EXISTS idx_complainants_location_code;")
    op.execute("DROP INDEX IF EXISTS idx_complainants_contact_id;")
    op.execute("DROP INDEX IF EXISTS idx_resource_persons_contact_id;")
    op.execute("DROP INDEX IF EXISTS idx_contact_info_country_location;")
    op.execute("DROP TABLE IF EXISTS resource_persons;")
    op.execute("DROP TABLE IF EXISTS contact_info;")
