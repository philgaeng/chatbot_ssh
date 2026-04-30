"""phase 2 canonical consolidation: one grievance + one complainant + grievance_parties

Revision ID: pub004_phase2_canonical_consolidation
Revises: pub003_vault_reveal_audit_foundation
Create Date: 2026-04-27

# Safe to run: only creates/modifies public.* (default schema) chatbot tables
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub004_phase2_canonical_consolidation"
down_revision: Union[str, None] = "pub003_vault_reveal_audit_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure canonical complainants timestamps expected by this migration exist.
    op.execute(
        """
        ALTER TABLE complainants
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """
    )
    op.execute(
        """
        ALTER TABLE complainants
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """
    )

    # 1) Canonical per-case party-role table.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_parties (
            party_id TEXT PRIMARY KEY,
            grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id) ON DELETE CASCADE,
            complainant_id TEXT REFERENCES complainants(complainant_id) ON DELETE SET NULL,
            party_role TEXT NOT NULL,
            is_primary_reporter BOOLEAN NOT NULL DEFAULT FALSE,
            contact_allowed BOOLEAN,
            contact_channel JSONB,
            consent_scope JSONB,
            notes_safe TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_grievance_parties_role
                CHECK (
                    party_role IN (
                        'victim_survivor',
                        'witness',
                        'relative_or_representative',
                        'seah_focal_point',
                        'reporter_other'
                    )
                )
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grievance_parties_grievance_id
        ON grievance_parties(grievance_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grievance_parties_complainant_id
        ON grievance_parties(complainant_id);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_grievance_parties_primary_reporter
        ON grievance_parties(grievance_id)
        WHERE is_primary_reporter = TRUE;
        """
    )

    # 2) Backfill complainants_seah -> complainants (single canonical complainant table).
    # Guard: only run when complainants_seah has the plaintext PII schema (complainant_full_name).
    # Brownfield DBs that already use the vault-first schema (phone_hash / phone_encrypted) skip this.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'complainants_seah'
                  AND column_name  = 'complainant_full_name'
            ) THEN
                INSERT INTO complainants (
                    complainant_id, complainant_unique_id, complainant_full_name,
                    complainant_phone, complainant_email, complainant_province,
                    complainant_district, complainant_municipality, complainant_ward,
                    complainant_village, complainant_address, contact_id,
                    country_code, location_code, location_resolution_status,
                    level_1_name, level_2_name, level_3_name, level_4_name,
                    level_5_name, level_6_name,
                    level_1_code, level_2_code, level_3_code, level_4_code,
                    level_5_code, level_6_code,
                    created_at, updated_at
                )
                SELECT
                    cs.complainant_id,
                    cs.complainant_id AS complainant_unique_id,
                    cs.complainant_full_name, cs.complainant_phone, cs.complainant_email,
                    cs.complainant_province, cs.complainant_district,
                    cs.complainant_municipality, cs.complainant_ward,
                    cs.complainant_village, cs.complainant_address, cs.contact_id,
                    cs.country_code, cs.location_code, cs.location_resolution_status,
                    cs.level_1_name, cs.level_2_name, cs.level_3_name, cs.level_4_name,
                    cs.level_5_name, cs.level_6_name,
                    cs.level_1_code, cs.level_2_code, cs.level_3_code, cs.level_4_code,
                    cs.level_5_code, cs.level_6_code,
                    COALESCE(cs.created_at, CURRENT_TIMESTAMP),
                    COALESCE(cs.updated_at, CURRENT_TIMESTAMP)
                FROM complainants_seah cs
                ON CONFLICT (complainant_id) DO NOTHING;
            END IF;
        END
        $$;
        """
    )

    # 3) Backfill grievances_seah -> grievances using canonical grievance_id.
    # Guard: only run when grievances_seah has seah_case_id (the consolidated schema).
    # Canonical identifier policy: grievance_id remains canonical; for migrated SEAH rows we use seah_case_id.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'grievances_seah'
                  AND column_name  = 'seah_case_id'
            ) THEN
                INSERT INTO grievances (
                    grievance_id, complainant_id, grievance_categories,
                    grievance_summary, grievance_sensitive_issue, grievance_description,
                    grievance_timeline, grievance_classification_status,
                    source, language_code, grievance_creation_date,
                    grievance_modification_date, case_sensitivity,
                    vault_payload_ref, vault_last_updated_at
                )
                SELECT
                    gs.seah_case_id AS grievance_id,
                    gs.complainant_id,
                    CASE
                        WHEN gs.grievance_categories IS NULL OR gs.grievance_categories = '' THEN NULL
                        ELSE to_jsonb(ARRAY[gs.grievance_categories])
                    END AS grievance_categories,
                    gs.grievance_summary,
                    TRUE AS grievance_sensitive_issue,
                    NULL AS grievance_description,
                    gs.grievance_timeline,
                    gs.grievance_status AS grievance_classification_status,
                    gs.submission_type AS source,
                    gs.language_code,
                    COALESCE(gs.created_at, CURRENT_TIMESTAMP),
                    COALESCE(gs.updated_at, CURRENT_TIMESTAMP),
                    'seah' AS case_sensitivity,
                    gs.vault_payload_ref,
                    gs.vault_last_updated_at
                FROM grievances_seah gs
                ON CONFLICT (grievance_id) DO NOTHING;
            END IF;
        END
        $$;
        """
    )

    # 4) Backfill vault payloads from historical SEAH free-text where available.
    # Guard: only run when grievance_vault_payloads exists and grievances_seah has seah_case_id.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'grievance_vault_payloads'
            ) AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'grievances_seah'
                  AND column_name  = 'seah_case_id'
            ) THEN
                INSERT INTO grievance_vault_payloads (
                    vault_payload_id, grievance_id, seah_case_id,
                    case_sensitivity, payload_type, content_ciphertext,
                    content_redacted, source_channel, source_language_code, created_by
                )
                SELECT
                    'vault-seah-' || gs.seah_case_id AS vault_payload_id,
                    gs.seah_case_id AS grievance_id,
                    gs.seah_case_id,
                    'seah' AS case_sensitivity,
                    'original_grievance' AS payload_type,
                    gs.grievance_description AS content_ciphertext,
                    NULL AS content_redacted,
                    'chatbot' AS source_channel,
                    gs.language_code,
                    'migration_pub004'
                FROM grievances_seah gs
                WHERE gs.grievance_description IS NOT NULL
                  AND gs.grievance_description <> ''
                ON CONFLICT (vault_payload_id) DO NOTHING;

                UPDATE grievances g
                SET
                    vault_payload_ref     = COALESCE(g.vault_payload_ref, 'vault-seah-' || g.grievance_id),
                    vault_last_updated_at = COALESCE(g.vault_last_updated_at, CURRENT_TIMESTAMP)
                WHERE g.case_sensitivity = 'seah'
                  AND EXISTS (
                      SELECT 1 FROM grievance_vault_payloads v
                      WHERE v.vault_payload_id = 'vault-seah-' || g.grievance_id
                  );
            END IF;
        END
        $$;
        """
    )

    # 5) Backfill grievance_parties.
    # SEAH parties: guard on seah_case_id column (not present in vault-first brownfield schema).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'grievances_seah'
                  AND column_name  = 'seah_case_id'
            ) THEN
                INSERT INTO grievance_parties (
                    party_id, grievance_id, complainant_id,
                    party_role, is_primary_reporter, contact_allowed,
                    created_at, updated_at
                )
                SELECT
                    'party-seah-primary-' || gs.seah_case_id AS party_id,
                    gs.seah_case_id AS grievance_id,
                    CASE WHEN gs.complainant_id IS NULL OR gs.complainant_id = '' THEN NULL
                         ELSE gs.complainant_id END,
                    CASE
                        WHEN gs.seah_payload ->> 'seah_victim_survivor_role' = 'victim_survivor'
                            THEN 'victim_survivor'
                        WHEN gs.seah_payload ->> 'seah_victim_survivor_role' = 'not_victim_survivor'
                            THEN 'relative_or_representative'
                        WHEN gs.seah_payload ->> 'seah_victim_survivor_role' = 'focal_point'
                            THEN 'seah_focal_point'
                        ELSE 'victim_survivor'
                    END AS party_role,
                    TRUE AS is_primary_reporter,
                    CASE
                        WHEN gs.seah_payload ->> 'seah_contact_provided' = 'false' THEN FALSE
                        ELSE TRUE
                    END AS contact_allowed,
                    COALESCE(gs.created_at, CURRENT_TIMESTAMP),
                    COALESCE(gs.updated_at, CURRENT_TIMESTAMP)
                FROM grievances_seah gs
                ON CONFLICT (party_id) DO NOTHING;
            END IF;
        END
        $$;
        """
    )

    # Standard grievances: ensure one default primary party when missing.
    # Only runs if grievances.complainant_id column exists (pub003 adds it).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'grievances'
                  AND column_name  = 'complainant_id'
            ) THEN
                INSERT INTO grievance_parties (
                    party_id, grievance_id, complainant_id,
                    party_role, is_primary_reporter, contact_allowed
                )
                SELECT
                    'party-standard-primary-' || g.grievance_id AS party_id,
                    g.grievance_id,
                    g.complainant_id,
                    'victim_survivor' AS party_role,
                    TRUE AS is_primary_reporter,
                    TRUE AS contact_allowed
                FROM grievances g
                WHERE NOT EXISTS (
                    SELECT 1 FROM grievance_parties gp
                    WHERE gp.grievance_id = g.grievance_id
                );
            END IF;
        END
        $$;
        """
    )

    # 6) Cutover hard-stop in DB model:
    # Drop legacy SEAH physical tables immediately after backfill (dev policy).
    op.execute("DROP TABLE IF EXISTS grievances_seah;")
    op.execute("DROP TABLE IF EXISTS complainants_seah;")


def downgrade() -> None:
    # Intentional: rollback is handled by DB snapshot policy for this migration phase.
    # Keep downgrade minimal and explicit to avoid partial destructive reconstruction.
    pass
