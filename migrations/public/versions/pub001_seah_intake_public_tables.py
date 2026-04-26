"""SEAH intake public tables: complainants_seah (+ grievances_seah FK).

Revision ID: pub001_seah_reporter_category
Revises:
Create Date: 2026-04-23

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub001_seah_reporter_category"
down_revision: Union[str, None] = "pub000_public_core_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # complainants_seah first (parent for grievances_seah FK)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS complainants_seah (
            complainant_id TEXT PRIMARY KEY,
            complainant_full_name TEXT,
            complainant_phone TEXT,
            complainant_email TEXT,
            complainant_province TEXT,
            complainant_district TEXT,
            complainant_municipality TEXT,
            complainant_ward TEXT,
            complainant_village TEXT,
            complainant_address TEXT,
            seah_reporter_category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        ALTER TABLE complainants_seah
          ADD COLUMN IF NOT EXISTS seah_reporter_category TEXT;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievances_seah (
            seah_case_id TEXT PRIMARY KEY,
            seah_public_ref TEXT UNIQUE NOT NULL,
            complainant_id TEXT NOT NULL,
            grievance_description TEXT,
            grievance_summary TEXT,
            grievance_categories TEXT,
            grievance_sensitive_issue BOOLEAN DEFAULT TRUE,
            grievance_status TEXT,
            grievance_timeline TEXT,
            language_code TEXT DEFAULT 'en',
            submission_type TEXT DEFAULT 'seah_intake',
            seah_payload JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complainant_id) REFERENCES complainants_seah(complainant_id)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS grievances_seah;")
    op.execute("DROP TABLE IF EXISTS complainants_seah;")
