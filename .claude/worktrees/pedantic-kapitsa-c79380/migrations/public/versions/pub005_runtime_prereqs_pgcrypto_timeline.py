"""public runtime prerequisites: pgcrypto + status_update_timeline

Revision ID: pub005_runtime_prereqs_pgcrypto_timeline
Revises: pub004_phase2_canonical_consolidation
Create Date: 2026-04-27

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub005_runtime_prereqs_pgcrypto_timeline"
down_revision: Union[str, None] = "pub004_phase2_canonical_consolidation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Required by encryption-enabled paths used by complainant/grievance services.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Required by backend.config.database_constants timeline bootstrap.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.status_update_timeline (
            status_update_code TEXT NOT NULL,
            grievance_high_priority BOOLEAN NOT NULL DEFAULT FALSE,
            sensitive_issues_detected BOOLEAN NOT NULL DEFAULT FALSE,
            timeline INTEGER NOT NULL,
            PRIMARY KEY (
                status_update_code,
                grievance_high_priority,
                sensitive_issues_detected
            )
        );
        """
    )

    op.execute(
        """
        INSERT INTO public.status_update_timeline (
            status_update_code,
            grievance_high_priority,
            sensitive_issues_detected,
            timeline
        )
        VALUES
            ('SUBMITTED', FALSE, FALSE, 15),
            ('SUBMITTED', TRUE, TRUE, 15),
            ('UNDER_REVIEW', FALSE, FALSE, 15),
            ('UNDER_REVIEW', TRUE, TRUE, 15),
            ('IN_PROGRESS', FALSE, FALSE, 15),
            ('IN_PROGRESS', TRUE, TRUE, 15),
            ('NEEDS_INFO', FALSE, FALSE, 15),
            ('NEEDS_INFO', TRUE, TRUE, 15),
            ('ESCALATED', FALSE, FALSE, 15),
            ('ESCALATED', TRUE, TRUE, 15),
            ('RESOLVED', FALSE, FALSE, 15),
            ('RESOLVED', TRUE, TRUE, 15),
            ('REJECTED', FALSE, FALSE, 15),
            ('REJECTED', TRUE, TRUE, 15),
            ('CLOSED', FALSE, FALSE, 15),
            ('CLOSED', TRUE, TRUE, 15)
        ON CONFLICT (
            status_update_code,
            grievance_high_priority,
            sensitive_issues_detected
        )
        DO UPDATE SET timeline = EXCLUDED.timeline;
        """
    )


def downgrade() -> None:
    # Keep pgcrypto installed (shared runtime prerequisite); only drop seeded table.
    op.execute("DROP TABLE IF EXISTS public.status_update_timeline;")
