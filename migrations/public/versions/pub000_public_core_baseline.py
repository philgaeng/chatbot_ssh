"""public schema canonical baseline (CL-01 squash + prune)

Revision ID: pub000_public_core_baseline
Revises:
Create Date: 2026-07-06

Safe to run: only creates/modifies public.* chatbot tables (+ the `keycloak`
schema and the `pgcrypto` extension, both runtime prerequisites).
Does NOT touch ticketing.* or ops.* — those are separate Alembic streams.

CL-01 (docs/sprints/2026-07_schema_and_legacy_cleanup/01-public-schema-source-of-truth-spec.md):
  This single revision SQUASHES the drifted pub000..pub009 lineage into one
  authoritative baseline and PRUNES dead weight. It is the sole source of truth
  for public.* DDL — the app no longer creates/alters public tables at startup.

  * Shapes reproduce the live (base_manager) schema — that is what prod ran —
    plus the used additions from the former pub008 (archiving columns) and
    pub009 (seah_service_providers).
  * `grievance_statuses` carries the live UPPERCASE vocabulary (+ 'archived'),
    not the retired lowercase pub000 seed.
  * DROPPED (product-owner-confirmed dead, 0 rows — see AUDIT_FINDINGS §1c):
    grievance_history, users, contact_info, resource_persons,
    grievance_reveal_sessions, grievance_sensitive_access_audit,
    grievance_vault_payloads.
  * EXCLUDED (external-owned, AUDIT_FINDINGS §1d): `events` (Rasa SQLTrackerStore)
    and `alembic_version_public` (Alembic infra, bootstrapped by env.py).
  * Column prune: no columns pruned inside kept tables — every column is read
    via SELECT * (10 tables), written via dynamic encrypt/hash field mapping
    (complainant_*_hash), or part of a cohesive used feature. See prune_audit.md.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub000_public_core_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Runtime prerequisites (were pub005 / pub006)
    # ------------------------------------------------------------------ #
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    # Keycloak stores its own state in a dedicated schema in the same instance;
    # Postgres will not auto-create it before the keycloak container starts.
    op.execute("CREATE SCHEMA IF NOT EXISTS keycloak;")

    # ------------------------------------------------------------------ #
    # Lookup / reference tables (parents first)
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE TABLE grievance_statuses (
            status_code TEXT PRIMARY KEY,
            status_name_en TEXT NOT NULL,
            status_name_ne TEXT NOT NULL,
            description_en TEXT,
            description_ne TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            sort_order INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX idx_status_active ON grievance_statuses (is_active);")
    op.execute("CREATE INDEX idx_status_order ON grievance_statuses (sort_order);")
    op.execute(
        """
        INSERT INTO grievance_statuses
            (status_code, status_name_en, status_name_ne, description_en, description_ne, sort_order)
        VALUES
            ('SUBMITTED', 'Submitted', 'जमा भएको',
             'Grievance has been submitted by the complainant', 'गुनासो जमा भएको छ', 0),
            ('UNDER_EVALUATION', 'Under Evaluation', 'समीक्षा भइरहेको',
             'Grievance is under evaluation by assigned officer', 'गुनासो समीक्षा भइरहेको छ', 0),
            ('ESCALATED', 'Escalated', 'विस्तारित भएको',
             'Grievance has been escalated to higher authority', 'गुनासो विस्तारित भएको छ', 0),
            ('RESOLVED', 'Resolved', 'समाधान भएको',
             'Grievance has been resolved by the officer', 'गुनासो समाधान भएको छ', 0),
            ('DENIED', 'Denied', 'अस्वीकृत',
             'Grievance has been denied', 'गुनासो अस्वीकृत भएको छ', 0),
            ('DISPUTED', 'Disputed', 'विरोध भएको',
             'Grievance resolution is not accepted by the complainant who requests the case to be reopened',
             'गुनासो विरोध भएको छ', 0),
            ('CLOSED', 'Closed', 'बन्द भएको',
             'Grievance case is closed', 'गुनासो केस बन्द भएको छ', 0),
            ('archived', 'Archived', 'संग्रहित', NULL, NULL, 5)
        ON CONFLICT (status_code) DO NOTHING;
        """
    )

    op.execute(
        """
        CREATE TABLE processing_statuses (
            status_code TEXT PRIMARY KEY,
            status_name TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        """
        INSERT INTO processing_statuses (status_code, status_name, description) VALUES
            ('PROCESSING', 'Processing', 'Transcription is in progress'),
            ('COMPLETED', 'Completed', 'Transcription is completed'),
            ('FAILED', 'Failed', 'Transcription is failed'),
            ('FOR_VERIFICATION', 'For Verification', 'Transcription is for verification'),
            ('VERIFICATION_IN_PROGRESS', 'Verification In Progress', 'Transcription is in verification by dedicated team'),
            ('VERIFIED', 'Verified', 'Transcription is verified by dedicated team'),
            ('VERIFIED_AND_AMENDED', 'Verified and Amended', 'Transcription is verified and amended by dedicated team')
        ON CONFLICT (status_code) DO NOTHING;
        """
    )

    op.execute(
        """
        CREATE TABLE task_statuses (
            task_status_code TEXT PRIMARY KEY,
            task_status_name TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            status_name TEXT
        );
        """
    )
    op.execute("CREATE INDEX idx_task_status_active ON task_statuses (is_active);")
    op.execute(
        """
        INSERT INTO task_statuses (task_status_code, task_status_name, description) VALUES
            ('started', 'Started', 'Task is started'),
            ('SUCCESS', 'Success', 'Task is successful'),
            ('failed', 'Failed', 'Task is failed'),
            ('retrying', 'Retrying', 'Task is retrying')
        ON CONFLICT (task_status_code) DO NOTHING;
        """
    )

    op.execute(
        """
        CREATE TABLE grievance_classification_statuses (
            code VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_classification_status_code ON grievance_classification_statuses (code);"
    )
    op.execute(
        """
        INSERT INTO grievance_classification_statuses (code, name, description) VALUES
            ('pending', 'Pending', 'Classification not started or LLM in progress'),
            ('LLM_generated', 'LLM Generated', 'Summary and categories generated by LLM'),
            ('LLM_failed', 'LLM Failed', 'LLM classification failed'),
            ('LLM_skipped', 'LLM Skipped', 'Complainant skipped LLM classification; officer must classify'),
            ('complainant_confirmed', 'Complainant Confirmed', 'Complainant confirmed summary and categories'),
            ('officer_confirmed', 'Officer Confirmed', 'Officer confirmed summary and categories'),
            ('LLM_error', 'LLM Error', 'Deprecated — use LLM_failed'),
            ('slot_skipped', 'slot_skipped', 'Deprecated — use LLM_skipped'),
            ('REVIEWING', 'Reviewing', 'Deprecated — session-only while editing')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    op.execute(
        """
        CREATE TABLE field_names (
            field_name TEXT PRIMARY KEY,
            description TEXT
        );
        """
    )
    op.execute(
        """
        INSERT INTO field_names (field_name, description) VALUES
            ('grievance_description', 'Grievance details'),
            ('complainant_full_name', 'User full name'),
            ('complainant_phone', 'User contact phone'),
            ('complainant_email', 'User contact email'),
            ('complainant_municipality', 'User municipality'),
            ('complainant_village', 'User village'),
            ('complainant_address', 'User address'),
            ('complainant_province', 'User province'),
            ('complainant_district', 'User district'),
            ('complainant_ward', 'User ward'),
            ('grievance_summary', 'Grievance summary'),
            ('grievance_high_priority', 'Grievance high priority'),
            ('grievance_sensitive_issue', 'Grievance sensitive issue'),
            ('grievance_categories', 'Grievance categories'),
            ('grievance_categories_alternative', 'Grievance categories alternative for manual selection by user'),
            ('follow_up_question', 'Grievance follow up question'),
            ('grievance_location', 'Grievance location'),
            ('grievance_claimed_amount', 'Grievance claimed amount')
        ON CONFLICT (field_name) DO NOTHING;
        """
    )

    op.execute(
        """
        CREATE TABLE grievance_classification_taxonomy (
            category_key TEXT PRIMARY KEY,
            generic_grievance_name TEXT,
            generic_grievance_name_ne TEXT,
            short_description TEXT,
            short_description_ne TEXT,
            classification TEXT,
            classification_ne TEXT,
            description TEXT,
            description_ne TEXT,
            follow_up_question_description TEXT,
            follow_up_question_description_ne TEXT,
            follow_up_question_quantification TEXT,
            follow_up_question_quantification_ne TEXT,
            high_priority BOOLEAN DEFAULT FALSE
        );
        """
    )

    op.execute(
        """
        CREATE TABLE reference_municipality_villages (
            id SERIAL PRIMARY KEY,
            municipality TEXT NOT NULL,
            ward TEXT NOT NULL,
            village TEXT NOT NULL,
            CONSTRAINT uq_ref_mv UNIQUE (municipality, ward, village)
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_ref_mv_municipality ON reference_municipality_villages (municipality);"
    )

    op.execute(
        """
        CREATE TABLE reference_grm_office_in_charge (
            id SERIAL PRIMARY KEY,
            office_id TEXT,
            office_name TEXT,
            office_address TEXT,
            office_email TEXT,
            office_pic_name TEXT,
            office_phone TEXT,
            district TEXT,
            municipality TEXT
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_ref_grm_dist_mun ON reference_grm_office_in_charge (district, municipality);"
    )

    op.execute(
        """
        CREATE TABLE status_update_timeline (
            id SERIAL PRIMARY KEY,
            status_update_code VARCHAR(50) NOT NULL,
            grievance_high_priority BOOLEAN NOT NULL,
            sensitive_issues_detected BOOLEAN NOT NULL,
            timeline INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT status_update_timeline_status_update_code_grievance_high_pr_key
                UNIQUE (status_update_code, grievance_high_priority, sensitive_issues_detected)
        );
        """
    )
    op.execute("CREATE INDEX idx_timeline_status_code ON status_update_timeline (status_update_code);")
    op.execute("CREATE INDEX idx_timeline_priority ON status_update_timeline (grievance_high_priority);")
    op.execute("CREATE INDEX idx_timeline_sensitive ON status_update_timeline (sensitive_issues_detected);")
    op.execute(
        """
        INSERT INTO status_update_timeline
            (status_update_code, grievance_high_priority, sensitive_issues_detected, timeline)
        VALUES
            ('SUBMITTED', FALSE, FALSE, 15), ('SUBMITTED', TRUE, TRUE, 15),
            ('UNDER_REVIEW', FALSE, FALSE, 15), ('UNDER_REVIEW', TRUE, TRUE, 15),
            ('IN_PROGRESS', FALSE, FALSE, 15), ('IN_PROGRESS', TRUE, TRUE, 15),
            ('NEEDS_INFO', FALSE, FALSE, 15), ('NEEDS_INFO', TRUE, TRUE, 15),
            ('ESCALATED', FALSE, FALSE, 15), ('ESCALATED', TRUE, TRUE, 15),
            ('RESOLVED', FALSE, FALSE, 15), ('RESOLVED', TRUE, TRUE, 15),
            ('REJECTED', FALSE, FALSE, 15), ('REJECTED', TRUE, TRUE, 15),
            ('CLOSED', FALSE, FALSE, 15), ('CLOSED', TRUE, TRUE, 15)
        ON CONFLICT (status_update_code, grievance_high_priority, sensitive_issues_detected)
        DO UPDATE SET timeline = EXCLUDED.timeline;
        """
    )

    op.execute(
        """
        CREATE TABLE projects (
            project_uuid TEXT PRIMARY KEY,
            country TEXT NOT NULL DEFAULT 'Nepal',
            administrative_layer_level_1 TEXT,
            administrative_layer_level_2 TEXT,
            administrative_layer_level_3 TEXT,
            name_en TEXT NOT NULL,
            name_local TEXT,
            project_short_denomination TEXT,
            adb BOOLEAN DEFAULT TRUE,
            inactive_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_projects_short_denomination ON projects (project_short_denomination);"
    )
    op.execute(
        """
        CREATE INDEX idx_projects_geo_active ON projects
            (country, administrative_layer_level_1, administrative_layer_level_2, inactive_at);
        """
    )

    op.execute(
        """
        CREATE TABLE seah_contact_points (
            seah_contact_point_id TEXT PRIMARY KEY,
            province TEXT,
            district TEXT,
            municipality TEXT,
            ward TEXT,
            project_uuid TEXT,
            seah_center_name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            opening_days TEXT,
            opening_hours TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            sort_order INTEGER DEFAULT 0
        );
        """
    )

    # seah_service_providers — was pub009; also created lazily by the app
    # (postgres_services._ensure_seah_service_providers_table, now removed).
    op.execute(
        """
        CREATE TABLE seah_service_providers (
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
        CREATE INDEX idx_seah_service_providers_municipality_code
            ON seah_service_providers (municipality_code)
            WHERE municipality_code IS NOT NULL AND is_active = TRUE;
        """
    )
    op.execute(
        """
        CREATE INDEX idx_seah_service_providers_district_code
            ON seah_service_providers (district_code)
            WHERE is_active = TRUE;
        """
    )

    # ------------------------------------------------------------------ #
    # Office directory
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE TABLE office_management (
            office_id TEXT PRIMARY KEY,
            office_name TEXT NOT NULL,
            office_address TEXT,
            office_email TEXT,
            office_pic_name TEXT,
            office_phone TEXT,
            district TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX idx_office_management_district ON office_management (district);")
    op.execute("CREATE INDEX idx_office_management_name ON office_management (office_name);")

    op.execute(
        """
        CREATE TABLE office_municipality_ward (
            id SERIAL PRIMARY KEY,
            office_id TEXT NOT NULL REFERENCES office_management(office_id) ON DELETE CASCADE,
            municipality TEXT NOT NULL,
            ward INTEGER NOT NULL,
            village TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT office_municipality_ward_office_id_municipality_ward_villag_key
                UNIQUE (office_id, municipality, ward, village)
        );
        """
    )
    op.execute("CREATE INDEX idx_office_municipality_ward_office ON office_municipality_ward (office_id);")
    op.execute("CREATE INDEX idx_office_municipality_ward_municipality ON office_municipality_ward (municipality);")
    op.execute("CREATE INDEX idx_office_municipality_ward_ward ON office_municipality_ward (ward);")
    op.execute("CREATE INDEX idx_office_municipality_ward_village ON office_municipality_ward (village);")
    op.execute("CREATE INDEX idx_office_municipality_ward_office_municipality ON office_municipality_ward (office_id, municipality);")

    op.execute(
        """
        CREATE TABLE office_user (
            id TEXT PRIMARY KEY,
            us_unique_id TEXT UNIQUE,
            user_name TEXT,
            user_phone TEXT,
            user_email TEXT,
            user_office_id TEXT,
            user_login TEXT,
            user_password TEXT,
            user_role TEXT,
            user_status TEXT,
            user_created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            user_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            user_last_login TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # ------------------------------------------------------------------ #
    # Complainants + grievances (core)
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE TABLE complainants (
            complainant_id TEXT PRIMARY KEY,
            complainant_unique_id TEXT UNIQUE,
            complainant_full_name TEXT,
            complainant_phone TEXT,
            complainant_email TEXT,
            complainant_province TEXT,
            complainant_district TEXT,
            complainant_municipality TEXT,
            complainant_ward TEXT,
            complainant_village TEXT,
            complainant_address TEXT,
            complainant_phone_hash TEXT,
            complainant_email_hash TEXT,
            complainant_full_name_hash TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            complainant_phone_verified BOOLEAN DEFAULT FALSE,
            contact_id TEXT,
            country_code TEXT,
            location_code TEXT,
            location_resolution_status TEXT,
            level_1_name TEXT, level_1_code TEXT,
            level_2_name TEXT, level_2_code TEXT,
            level_3_name TEXT, level_3_code TEXT,
            level_4_name TEXT, level_4_code TEXT,
            level_5_name TEXT, level_5_code TEXT,
            level_6_name TEXT, level_6_code TEXT,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            location_geo TEXT
        );
        """
    )
    op.execute("CREATE INDEX idx_complainant_phone ON complainants (complainant_phone);")
    op.execute("CREATE INDEX idx_complainant_email ON complainants (complainant_email);")
    op.execute("CREATE INDEX idx_complainant_unique_id ON complainants (complainant_unique_id);")
    op.execute("CREATE INDEX idx_complainants_phone_hash ON complainants (complainant_phone_hash);")
    op.execute("CREATE INDEX idx_complainants_email_hash ON complainants (complainant_email_hash);")
    op.execute("CREATE INDEX idx_complainants_contact_id ON complainants (contact_id);")
    op.execute("CREATE INDEX idx_complainants_location_code ON complainants (location_code);")

    op.execute(
        """
        CREATE TABLE grievances (
            grievance_id TEXT PRIMARY KEY,
            complainant_id TEXT REFERENCES complainants(complainant_id),
            grievance_categories TEXT,
            grievance_categories_alternative TEXT,
            follow_up_question TEXT,
            grievance_summary TEXT,
            grievance_description TEXT,
            grievance_claimed_amount NUMERIC,
            grievance_location TEXT,
            language_code TEXT DEFAULT 'ne',
            grievance_classification_status TEXT DEFAULT 'pending',
            grievance_creation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            grievance_modification_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            is_temporary BOOLEAN DEFAULT TRUE,
            source TEXT DEFAULT 'bot',
            grievance_sensitive_issue BOOLEAN DEFAULT FALSE,
            grievance_high_priority BOOLEAN DEFAULT FALSE,
            grievance_timeline TEXT,
            case_sensitivity TEXT NOT NULL DEFAULT 'standard',
            vault_payload_ref TEXT,
            vault_last_updated_at TIMESTAMP WITHOUT TIME ZONE,
            is_archived BOOLEAN NOT NULL DEFAULT FALSE,
            archived_at TIMESTAMP WITH TIME ZONE
        );
        """
    )
    op.execute("CREATE INDEX idx_grievance_complainant ON grievances (complainant_id);")
    op.execute("CREATE INDEX idx_grievances_complainant_id ON grievances (complainant_id);")
    op.execute("CREATE INDEX idx_grievance_creation_date ON grievances (grievance_creation_date);")
    op.execute("CREATE INDEX idx_grievance_modification_date ON grievances (grievance_modification_date);")
    op.execute("CREATE INDEX idx_grievance_source ON grievances (source);")
    op.execute("CREATE INDEX idx_grievance_temporary ON grievances (is_temporary);")
    op.execute("CREATE INDEX idx_grievance_language ON grievances (language_code);")
    op.execute("CREATE INDEX idx_grievances_language_code ON grievances (language_code);")
    op.execute("CREATE INDEX idx_grievance_timeline ON grievances (grievance_timeline);")
    op.execute("CREATE INDEX idx_grievances_case_sensitivity ON grievances (case_sensitivity);")

    op.execute(
        """
        CREATE TABLE grievance_parties (
            party_id TEXT PRIMARY KEY,
            grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id) ON DELETE CASCADE,
            complainant_id TEXT REFERENCES complainants(complainant_id) ON DELETE SET NULL,
            party_role TEXT NOT NULL,
            is_primary_reporter BOOLEAN NOT NULL DEFAULT FALSE,
            contact_allowed BOOLEAN,
            contact_channel JSONB,
            consent_scope JSONB,
            notes_safe TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_grievance_parties_role CHECK (
                party_role IN ('victim_survivor', 'witness', 'relative_or_representative',
                               'seah_focal_point', 'reporter_other')
            )
        );
        """
    )
    op.execute("CREATE INDEX idx_grievance_parties_grievance_id ON grievance_parties (grievance_id);")
    op.execute("CREATE INDEX idx_grievance_parties_complainant_id ON grievance_parties (complainant_id);")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_grievance_parties_primary_reporter
            ON grievance_parties (grievance_id) WHERE is_primary_reporter = TRUE;
        """
    )

    op.execute(
        """
        CREATE TABLE file_attachments (
            id SERIAL PRIMARY KEY,
            file_id UUID NOT NULL,
            grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id),
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            client_metadata JSONB,
            storage_tier VARCHAR(16) NOT NULL DEFAULT 'active',
            archived_at TIMESTAMP WITH TIME ZONE,
            storage_key TEXT
        );
        """
    )
    op.execute("CREATE INDEX idx_file_attachments_grievance_id ON file_attachments (grievance_id);")
    op.execute("CREATE INDEX idx_file_attachments_file_id ON file_attachments (file_id);")
    op.execute("CREATE INDEX idx_file_attachments_upload_timestamp ON file_attachments (upload_timestamp);")

    op.execute(
        """
        CREATE TABLE grievance_status_history (
            id SERIAL PRIMARY KEY,
            grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id),
            status_code TEXT NOT NULL REFERENCES grievance_statuses(status_code),
            assigned_to TEXT,
            notes TEXT,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            change_type TEXT NOT NULL DEFAULT 'status_change',
            field_changes JSONB,
            CONSTRAINT status_or_fields_check CHECK (
                (change_type IN ('status_change', 'creation') AND status_code IS NOT NULL)
                OR (change_type IN ('field_update', 'complainant_update', 'system_update')
                    AND field_changes IS NOT NULL)
            )
        );
        """
    )
    op.execute("CREATE INDEX idx_status_history_grievance ON grievance_status_history (grievance_id);")
    op.execute("CREATE INDEX idx_status_history_status ON grievance_status_history (status_code);")
    op.execute("CREATE INDEX idx_status_history_created ON grievance_status_history (created_at);")
    op.execute("CREATE INDEX idx_status_history_assigned ON grievance_status_history (assigned_to);")
    op.execute("CREATE INDEX idx_grievance_status_history_grievance_id ON grievance_status_history (grievance_id, created_at DESC);")
    op.execute("CREATE INDEX idx_status_history_change_type ON grievance_status_history (change_type);")
    op.execute("CREATE INDEX idx_status_history_field_changes ON grievance_status_history USING GIN (field_changes);")
    op.execute("CREATE INDEX idx_status_history_grievance_change_type ON grievance_status_history (grievance_id, change_type);")

    # ------------------------------------------------------------------ #
    # Tasks + entity links
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            task_name TEXT NOT NULL,
            task_status_code TEXT REFERENCES task_statuses(task_status_code),
            started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT,
            result JSONB,
            retry_count INTEGER DEFAULT 0,
            retry_history JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX idx_tasks_status ON tasks (task_status_code);")
    op.execute("CREATE INDEX idx_tasks_created ON tasks (created_at);")
    op.execute("CREATE INDEX idx_tasks_completed ON tasks (completed_at);")

    op.execute(
        """
        CREATE TABLE task_entities (
            task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            entity_key TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (task_id, entity_key, entity_id),
            CONSTRAINT task_entities_entity_key_check CHECK (
                entity_key IN ('grievance_id', 'complainant_id', 'transcription_id',
                               'translation_id', 'recording_id', 'task_id', 'ticket_id')
            )
        );
        """
    )
    op.execute("CREATE INDEX idx_task_entities_entity ON task_entities (entity_key, entity_id);")
    op.execute("CREATE INDEX idx_task_entities_lookup ON task_entities (entity_key, entity_id);")

    # ------------------------------------------------------------------ #
    # Voice / transcription / translation
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE TABLE grievance_voice_recordings (
            recording_id TEXT PRIMARY KEY,
            complainant_id TEXT REFERENCES complainants(complainant_id),
            grievance_id TEXT REFERENCES grievances(grievance_id),
            task_id TEXT,
            file_path TEXT NOT NULL,
            field_name TEXT NOT NULL,
            duration_seconds INTEGER,
            file_size INTEGER,
            processing_status TEXT DEFAULT 'PROCESSING' REFERENCES processing_statuses(status_code),
            language_code TEXT,
            language_code_detect TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX idx_voice_recordings_grievance_id ON grievance_voice_recordings (grievance_id);")
    op.execute("CREATE INDEX idx_voice_recordings_status ON grievance_voice_recordings (processing_status);")
    op.execute("CREATE INDEX idx_voice_recordings_type ON grievance_voice_recordings (field_name);")
    op.execute("CREATE INDEX idx_voice_recordings_created ON grievance_voice_recordings (created_at);")
    op.execute("CREATE INDEX idx_voice_recordings_language ON grievance_voice_recordings (language_code);")
    op.execute("CREATE INDEX idx_voice_recordings_detected_language ON grievance_voice_recordings (language_code_detect);")

    op.execute(
        """
        CREATE TABLE grievance_transcriptions (
            transcription_id TEXT PRIMARY KEY,
            recording_id TEXT REFERENCES grievance_voice_recordings(recording_id),
            grievance_id TEXT REFERENCES grievances(grievance_id),
            field_name TEXT NOT NULL,
            automated_transcript TEXT,
            verified_transcript TEXT,
            verification_status TEXT DEFAULT 'FOR_VERIFICATION' REFERENCES processing_statuses(status_code),
            confidence_score DOUBLE PRECISION,
            verification_notes TEXT,
            verified_by TEXT,
            verified_at TIMESTAMP WITH TIME ZONE,
            language_code TEXT,
            language_code_detect TEXT,
            task_id TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX idx_transcriptions_recording_id ON grievance_transcriptions (recording_id);")
    op.execute("CREATE INDEX idx_transcriptions_grievance_id ON grievance_transcriptions (grievance_id);")
    op.execute("CREATE INDEX idx_transcriptions_status ON grievance_transcriptions (verification_status);")
    op.execute("CREATE INDEX idx_transcriptions_created ON grievance_transcriptions (created_at);")
    op.execute("CREATE INDEX idx_transcriptions_language ON grievance_transcriptions (language_code);")
    op.execute("CREATE INDEX idx_transcriptions_detected_language ON grievance_transcriptions (language_code_detect);")

    op.execute(
        """
        CREATE TABLE grievance_translations (
            translation_id TEXT PRIMARY KEY,
            grievance_id TEXT REFERENCES grievances(grievance_id),
            task_id TEXT,
            grievance_description_en TEXT,
            grievance_summary_en TEXT,
            grievance_categories_en TEXT,
            source_language TEXT NOT NULL DEFAULT 'ne',
            translation_method TEXT NOT NULL,
            confidence_score DOUBLE PRECISION,
            verified_by TEXT,
            verified_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT grievance_translations_grievance_id_translation_method_key
                UNIQUE (grievance_id, translation_method)
        );
        """
    )
    op.execute("CREATE INDEX idx_translations_verified ON grievance_translations (verified_at);")
    op.execute("CREATE INDEX idx_translations_method ON grievance_translations (translation_method);")
    op.execute("CREATE INDEX idx_translations_source_language ON grievance_translations (source_language);")
    op.execute("CREATE INDEX idx_translations_created ON grievance_translations (created_at);")


def downgrade() -> None:
    # Reverse dependency order. pgcrypto is left installed (shared prerequisite).
    for table in (
        "grievance_translations",
        "grievance_transcriptions",
        "grievance_voice_recordings",
        "task_entities",
        "tasks",
        "grievance_status_history",
        "file_attachments",
        "grievance_parties",
        "grievances",
        "complainants",
        "office_user",
        "office_municipality_ward",
        "office_management",
        "seah_service_providers",
        "seah_contact_points",
        "projects",
        "status_update_timeline",
        "reference_grm_office_in_charge",
        "reference_municipality_villages",
        "grievance_classification_taxonomy",
        "field_names",
        "grievance_classification_statuses",
        "task_statuses",
        "processing_statuses",
        "grievance_statuses",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    op.execute("DROP SCHEMA IF EXISTS keycloak CASCADE;")
