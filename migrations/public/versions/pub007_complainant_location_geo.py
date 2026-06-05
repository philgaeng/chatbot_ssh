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


def upgrade() -> None:
    for table_name in ("complainants", "complainants_seah"):
        op.execute(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS location_geo TEXT;"
        )
    op.execute("ALTER TABLE contact_info ADD COLUMN IF NOT EXISTS location_geo TEXT;")
    op.execute(
        "ALTER TABLE file_attachments ADD COLUMN IF NOT EXISTS client_metadata JSONB;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE file_attachments DROP COLUMN IF EXISTS client_metadata;")
    op.execute("ALTER TABLE contact_info DROP COLUMN IF EXISTS location_geo;")
    for table_name in ("complainants_seah", "complainants"):
        op.execute(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS location_geo;")
