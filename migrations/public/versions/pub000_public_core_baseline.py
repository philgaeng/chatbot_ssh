"""public core chatbot tables baseline

Revision ID: pub000_public_core_baseline
Revises:
Create Date: 2026-04-26

Safe to run: only creates/modifies public.* chatbot tables.
Does NOT touch ticketing.* schema.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub000_public_core_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Core complainants table used across intake, status-check, and submission.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS complainants (
            complainant_id TEXT PRIMARY KEY,
            complainant_unique_id TEXT UNIQUE,
            complainant_full_name TEXT,
            complainant_full_name_hash TEXT,
            complainant_phone TEXT,
            complainant_phone_hash TEXT,
            complainant_phone_verified BOOLEAN DEFAULT FALSE,
            complainant_email TEXT,
            complainant_email_hash TEXT,
            complainant_province TEXT,
            complainant_district TEXT,
            complainant_municipality TEXT,
            complainant_ward TEXT,
            complainant_village TEXT,
            complainant_address TEXT,
            contact_id TEXT,
            country_code TEXT,
            location_code TEXT,
            location_resolution_status TEXT,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_complainants_phone_hash
            ON complainants(complainant_phone_hash);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_complainants_email_hash
            ON complainants(complainant_email_hash);
        """
    )

    # Grievances table consumed by orchestrator, LLM workers, and review forms.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievances (
            grievance_id TEXT PRIMARY KEY,
            complainant_id TEXT REFERENCES complainants(complainant_id) ON DELETE SET NULL,
            grievance_categories JSONB,
            grievance_categories_alternative JSONB,
            follow_up_question TEXT,
            grievance_summary TEXT,
            grievance_sensitive_issue BOOLEAN DEFAULT FALSE,
            grievance_high_priority BOOLEAN DEFAULT FALSE,
            grievance_description TEXT,
            grievance_claimed_amount TEXT,
            grievance_location TEXT,
            grievance_timeline TEXT,
            grievance_classification_status TEXT,
            is_temporary BOOLEAN DEFAULT FALSE,
            source TEXT,
            language_code TEXT,
            grievance_creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            grievance_modification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grievances_complainant_id
            ON grievances(complainant_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grievances_language_code
            ON grievances(language_code);
        """
    )

    # File uploads linked to grievances.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS file_attachments (
            file_id TEXT PRIMARY KEY,
            grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id) ON DELETE CASCADE,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT,
            file_size BIGINT,
            upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id
            ON file_attachments(grievance_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_attachments_upload_timestamp
            ON file_attachments(upload_timestamp);
        """
    )

    # Status catalog + status history used by status-check and GRM updates.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_statuses (
            status_code TEXT PRIMARY KEY,
            status_name_en TEXT,
            status_name_ne TEXT,
            description_en TEXT,
            description_ne TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        INSERT INTO grievance_statuses
            (status_code, status_name_en, status_name_ne, sort_order, is_active)
        VALUES
            ('received', 'Received', 'प्राप्त भयो', 1, TRUE),
            ('in_progress', 'In Progress', 'प्रक्रियामा', 2, TRUE),
            ('resolved', 'Resolved', 'समाधान भयो', 3, TRUE),
            ('closed', 'Closed', 'बन्द', 4, TRUE)
        ON CONFLICT (status_code) DO NOTHING;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_status_history (
            id BIGSERIAL PRIMARY KEY,
            grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id) ON DELETE CASCADE,
            status_code TEXT NOT NULL REFERENCES grievance_statuses(status_code),
            assigned_to TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grievance_status_history_grievance_id
            ON grievance_status_history(grievance_id, created_at DESC);
        """
    )

    # Task tracking tables used by Celery/task-status API.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS task_statuses (
            task_status_code TEXT PRIMARY KEY,
            status_name TEXT NOT NULL
        );
        """
    )
    op.execute(
        """
        INSERT INTO task_statuses (task_status_code, status_name)
        VALUES
            ('PENDING', 'Pending'),
            ('STARTED', 'Started'),
            ('SUCCESS', 'Success'),
            ('FAILURE', 'Failure'),
            ('RETRY', 'Retry')
        ON CONFLICT (task_status_code) DO NOTHING;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            task_name TEXT,
            task_status_code TEXT REFERENCES task_statuses(task_status_code) ON DELETE SET NULL,
            result JSONB,
            metadata JSONB,
            retry_count INTEGER DEFAULT 0,
            retry_history JSONB,
            error_message TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS task_entities (
            id BIGSERIAL PRIMARY KEY,
            task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            entity_key TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_task_entities_lookup
            ON task_entities(entity_key, entity_id);
        """
    )

    # Optional LLM taxonomy table loaded at startup; keep empty by default.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_classification_taxonomy (
            category_code TEXT PRIMARY KEY,
            category_name_en TEXT,
            category_name_ne TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS grievance_classification_taxonomy;")
    op.execute("DROP TABLE IF EXISTS task_entities;")
    op.execute("DROP TABLE IF EXISTS tasks;")
    op.execute("DROP TABLE IF EXISTS task_statuses;")
    op.execute("DROP TABLE IF EXISTS grievance_status_history;")
    op.execute("DROP TABLE IF EXISTS grievance_statuses;")
    op.execute("DROP TABLE IF EXISTS file_attachments;")
    op.execute("DROP TABLE IF EXISTS grievances;")
    op.execute("DROP TABLE IF EXISTS complainants;")
