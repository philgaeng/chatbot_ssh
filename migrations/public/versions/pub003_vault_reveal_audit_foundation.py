"""public vault + reveal + audit foundation for SEAH/privacy split

Revision ID: pub003_vault_reveal_audit_foundation
Revises: pub002_contact_info_and_normalized_location
Create Date: 2026-04-27

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub003_vault_reveal_audit_foundation"
down_revision: Union[str, None] = "pub002_contact_info_and_normalized_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Normalize case sensitivity classification in canonical grievance tables.
    op.execute(
        """
        ALTER TABLE grievances
        ADD COLUMN IF NOT EXISTS case_sensitivity TEXT NOT NULL DEFAULT 'standard';
        """
    )
    op.execute(
        """
        ALTER TABLE grievances
        ADD COLUMN IF NOT EXISTS vault_payload_ref TEXT;
        """
    )
    op.execute(
        """
        ALTER TABLE grievances
        ADD COLUMN IF NOT EXISTS vault_last_updated_at TIMESTAMP;
        """
    )
    op.execute(
        """
        ALTER TABLE grievances_seah
        ADD COLUMN IF NOT EXISTS case_sensitivity TEXT NOT NULL DEFAULT 'seah';
        """
    )
    op.execute(
        """
        ALTER TABLE grievances_seah
        ADD COLUMN IF NOT EXISTS vault_payload_ref TEXT;
        """
    )
    op.execute(
        """
        ALTER TABLE grievances_seah
        ADD COLUMN IF NOT EXISTS vault_last_updated_at TIMESTAMP;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grievances_case_sensitivity
        ON grievances(case_sensitivity);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grievances_seah_case_sensitivity
        ON grievances_seah(case_sensitivity);
        """
    )

    # 2) Vault payloads for original grievance narratives and sensitive free text.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_vault_payloads (
            vault_payload_id TEXT PRIMARY KEY,
            grievance_id TEXT,
            seah_case_id TEXT,
            case_sensitivity TEXT NOT NULL,
            payload_type TEXT NOT NULL,
            content_ciphertext TEXT,
            content_redacted TEXT,
            content_hash TEXT,
            pii_detection_metadata JSONB,
            source_channel TEXT,
            source_language_code TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_vault_case_sensitivity
                CHECK (case_sensitivity IN ('standard', 'seah')),
            CONSTRAINT chk_vault_payload_type
                CHECK (payload_type IN ('original_grievance', 'follow_up_message', 'attachment_ocr', 'other'))
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vault_payloads_grievance_id
        ON grievance_vault_payloads(grievance_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vault_payloads_seah_case_id
        ON grievance_vault_payloads(seah_case_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vault_payloads_sensitivity_created_at
        ON grievance_vault_payloads(case_sensitivity, created_at DESC);
        """
    )

    # 3) Reveal session lifecycle (short-lived access windows).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_reveal_sessions (
            reveal_session_id TEXT PRIMARY KEY,
            grievance_id TEXT,
            seah_case_id TEXT,
            case_sensitivity TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_role TEXT,
            reason_code TEXT NOT NULL,
            reason_text TEXT,
            decision TEXT NOT NULL,
            deny_code TEXT,
            decision_policy_version TEXT,
            request_id TEXT,
            source_ip TEXT,
            user_agent TEXT,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            closed_at TIMESTAMP,
            duration_seconds INTEGER,
            close_reason TEXT,
            CONSTRAINT chk_reveal_case_sensitivity
                CHECK (case_sensitivity IN ('standard', 'seah')),
            CONSTRAINT chk_reveal_decision
                CHECK (decision IN ('grant', 'deny'))
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reveal_sessions_grievance_id
        ON grievance_reveal_sessions(grievance_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reveal_sessions_actor_time
        ON grievance_reveal_sessions(actor_id, opened_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reveal_sessions_sensitivity_time
        ON grievance_reveal_sessions(case_sensitivity, opened_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reveal_sessions_request_id
        ON grievance_reveal_sessions(request_id);
        """
    )

    # 4) Immutable reveal/decrypt audit stream (authoritative on public side).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_sensitive_access_audit (
            audit_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            grievance_id TEXT,
            seah_case_id TEXT,
            case_sensitivity TEXT NOT NULL,
            actor_id TEXT,
            actor_role TEXT,
            reason_code TEXT,
            reason_text TEXT,
            decision TEXT,
            deny_code TEXT,
            decision_policy_version TEXT,
            reveal_session_id TEXT,
            request_id TEXT,
            source_ip TEXT,
            user_agent TEXT,
            metadata JSONB,
            created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_audit_case_sensitivity
                CHECK (case_sensitivity IN ('standard', 'seah')),
            CONSTRAINT chk_audit_event_type
                CHECK (
                    event_type IN (
                        'reveal_requested',
                        'reveal_granted',
                        'reveal_denied',
                        'reveal_closed',
                        'reveal_expired',
                        'decrypt_attempt',
                        'decrypt_denied',
                        'decrypt_success'
                    )
                )
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sensitive_audit_grievance_id
        ON grievance_sensitive_access_audit(grievance_id, created_at_utc DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sensitive_audit_actor_time
        ON grievance_sensitive_access_audit(actor_id, created_at_utc DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sensitive_audit_reveal_session_id
        ON grievance_sensitive_access_audit(reveal_session_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sensitive_audit_sensitivity_time
        ON grievance_sensitive_access_audit(case_sensitivity, created_at_utc DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sensitive_audit_sensitivity_time;")
    op.execute("DROP INDEX IF EXISTS idx_sensitive_audit_reveal_session_id;")
    op.execute("DROP INDEX IF EXISTS idx_sensitive_audit_actor_time;")
    op.execute("DROP INDEX IF EXISTS idx_sensitive_audit_grievance_id;")
    op.execute("DROP TABLE IF EXISTS grievance_sensitive_access_audit;")

    op.execute("DROP INDEX IF EXISTS idx_reveal_sessions_request_id;")
    op.execute("DROP INDEX IF EXISTS idx_reveal_sessions_sensitivity_time;")
    op.execute("DROP INDEX IF EXISTS idx_reveal_sessions_actor_time;")
    op.execute("DROP INDEX IF EXISTS idx_reveal_sessions_grievance_id;")
    op.execute("DROP TABLE IF EXISTS grievance_reveal_sessions;")

    op.execute("DROP INDEX IF EXISTS idx_vault_payloads_sensitivity_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_vault_payloads_seah_case_id;")
    op.execute("DROP INDEX IF EXISTS idx_vault_payloads_grievance_id;")
    op.execute("DROP TABLE IF EXISTS grievance_vault_payloads;")

    op.execute("DROP INDEX IF EXISTS idx_grievances_seah_case_sensitivity;")
    op.execute("DROP INDEX IF EXISTS idx_grievances_case_sensitivity;")

    op.execute("ALTER TABLE grievances_seah DROP COLUMN IF EXISTS vault_last_updated_at;")
    op.execute("ALTER TABLE grievances_seah DROP COLUMN IF EXISTS vault_payload_ref;")
    op.execute("ALTER TABLE grievances_seah DROP COLUMN IF EXISTS case_sensitivity;")
    op.execute("ALTER TABLE grievances DROP COLUMN IF EXISTS vault_last_updated_at;")
    op.execute("ALTER TABLE grievances DROP COLUMN IF EXISTS vault_payload_ref;")
    op.execute("ALTER TABLE grievances DROP COLUMN IF EXISTS case_sensitivity;")
