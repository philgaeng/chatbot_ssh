CREATE SCHEMA public;
COMMENT ON SCHEMA public IS 'standard public schema';
CREATE TABLE public.alembic_version_public (
    version_num text NOT NULL
);
CREATE TABLE public.complainants (
    complainant_id text NOT NULL,
    complainant_unique_id text,
    complainant_full_name text,
    complainant_phone text,
    complainant_email text,
    complainant_province text,
    complainant_district text,
    complainant_municipality text,
    complainant_ward text,
    complainant_village text,
    complainant_address text,
    complainant_phone_hash text,
    complainant_email_hash text,
    complainant_full_name_hash text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    complainant_phone_verified boolean DEFAULT false,
    contact_id text,
    country_code text,
    location_code text,
    location_resolution_status text,
    level_1_name text,
    level_1_code text,
    level_2_name text,
    level_2_code text,
    level_3_name text,
    level_3_code text,
    level_4_name text,
    level_4_code text,
    level_5_name text,
    level_5_code text,
    level_6_name text,
    level_6_code text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    location_geo text
);
CREATE TABLE public.field_names (
    field_name text NOT NULL,
    description text
);
CREATE TABLE public.file_attachments (
    id integer NOT NULL,
    file_id uuid NOT NULL,
    grievance_id text NOT NULL,
    file_name text NOT NULL,
    file_path text NOT NULL,
    file_type text NOT NULL,
    file_size integer NOT NULL,
    upload_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    client_metadata jsonb,
    storage_tier character varying(16) DEFAULT 'active'::character varying NOT NULL,
    archived_at timestamp with time zone,
    storage_key text
);
CREATE SEQUENCE public.file_attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.file_attachments_id_seq OWNED BY public.file_attachments.id;
CREATE TABLE public.grievance_classification_statuses (
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.grievance_classification_taxonomy (
    category_key text NOT NULL,
    generic_grievance_name text,
    generic_grievance_name_ne text,
    short_description text,
    short_description_ne text,
    classification text,
    classification_ne text,
    description text,
    description_ne text,
    follow_up_question_description text,
    follow_up_question_description_ne text,
    follow_up_question_quantification text,
    follow_up_question_quantification_ne text,
    high_priority boolean DEFAULT false
);
CREATE TABLE public.grievance_parties (
    party_id text NOT NULL,
    grievance_id text NOT NULL,
    complainant_id text,
    party_role text NOT NULL,
    is_primary_reporter boolean DEFAULT false NOT NULL,
    contact_allowed boolean,
    contact_channel jsonb,
    consent_scope jsonb,
    notes_safe text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_grievance_parties_role CHECK ((party_role = ANY (ARRAY['victim_survivor'::text, 'witness'::text, 'relative_or_representative'::text, 'seah_focal_point'::text, 'reporter_other'::text])))
);
CREATE TABLE public.grievance_status_history (
    id integer NOT NULL,
    grievance_id text NOT NULL,
    status_code text NOT NULL,
    assigned_to text,
    notes text,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    change_type text DEFAULT 'status_change'::text NOT NULL,
    field_changes jsonb,
    CONSTRAINT status_or_fields_check CHECK ((((change_type = ANY (ARRAY['status_change'::text, 'creation'::text])) AND (status_code IS NOT NULL)) OR ((change_type = ANY (ARRAY['field_update'::text, 'complainant_update'::text, 'system_update'::text])) AND (field_changes IS NOT NULL))))
);
CREATE SEQUENCE public.grievance_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.grievance_status_history_id_seq OWNED BY public.grievance_status_history.id;
CREATE TABLE public.grievance_statuses (
    status_code text NOT NULL,
    status_name_en text NOT NULL,
    status_name_ne text NOT NULL,
    description_en text,
    description_ne text,
    is_active boolean DEFAULT true,
    sort_order integer,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.grievance_transcriptions (
    transcription_id text NOT NULL,
    recording_id text,
    grievance_id text,
    field_name text NOT NULL,
    automated_transcript text,
    verified_transcript text,
    verification_status text DEFAULT 'FOR_VERIFICATION'::text,
    confidence_score double precision,
    verification_notes text,
    verified_by text,
    verified_at timestamp with time zone,
    language_code text,
    language_code_detect text,
    task_id text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.grievance_translations (
    translation_id text NOT NULL,
    grievance_id text,
    task_id text,
    grievance_description_en text,
    grievance_summary_en text,
    grievance_categories_en text,
    source_language text DEFAULT 'ne'::text NOT NULL,
    translation_method text NOT NULL,
    confidence_score double precision,
    verified_by text,
    verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.grievance_voice_recordings (
    recording_id text NOT NULL,
    complainant_id text,
    grievance_id text,
    task_id text,
    file_path text NOT NULL,
    field_name text NOT NULL,
    duration_seconds integer,
    file_size integer,
    processing_status text DEFAULT 'PROCESSING'::text,
    language_code text,
    language_code_detect text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.grievances (
    grievance_id text NOT NULL,
    complainant_id text,
    grievance_categories text,
    grievance_categories_alternative text,
    follow_up_question text,
    grievance_summary text,
    grievance_description text,
    grievance_claimed_amount numeric,
    grievance_location text,
    language_code text DEFAULT 'ne'::text,
    grievance_classification_status text DEFAULT 'pending'::text,
    grievance_creation_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    grievance_modification_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_temporary boolean DEFAULT true,
    source text DEFAULT 'bot'::text,
    grievance_sensitive_issue boolean DEFAULT false,
    grievance_high_priority boolean DEFAULT false,
    grievance_timeline text,
    case_sensitivity text DEFAULT 'standard'::text NOT NULL,
    vault_payload_ref text,
    vault_last_updated_at timestamp without time zone,
    is_archived boolean DEFAULT false NOT NULL,
    archived_at timestamp with time zone
);
CREATE TABLE public.office_management (
    office_id text NOT NULL,
    office_name text NOT NULL,
    office_address text,
    office_email text,
    office_pic_name text,
    office_phone text,
    district text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.office_municipality_ward (
    id integer NOT NULL,
    office_id text NOT NULL,
    municipality text NOT NULL,
    ward integer NOT NULL,
    village text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE SEQUENCE public.office_municipality_ward_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.office_municipality_ward_id_seq OWNED BY public.office_municipality_ward.id;
CREATE TABLE public.office_user (
    id text NOT NULL,
    us_unique_id text,
    user_name text,
    user_phone text,
    user_email text,
    user_office_id text,
    user_login text,
    user_password text,
    user_role text,
    user_status text,
    user_created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    user_updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    user_last_login timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.processing_statuses (
    status_code text NOT NULL,
    status_name text NOT NULL,
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.projects (
    project_uuid text NOT NULL,
    country text DEFAULT 'Nepal'::text NOT NULL,
    administrative_layer_level_1 text,
    administrative_layer_level_2 text,
    administrative_layer_level_3 text,
    name_en text NOT NULL,
    name_local text,
    project_short_denomination text,
    adb boolean DEFAULT true,
    inactive_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.reference_grm_office_in_charge (
    id integer NOT NULL,
    office_id text,
    office_name text,
    office_address text,
    office_email text,
    office_pic_name text,
    office_phone text,
    district text,
    municipality text
);
CREATE SEQUENCE public.reference_grm_office_in_charge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.reference_grm_office_in_charge_id_seq OWNED BY public.reference_grm_office_in_charge.id;
CREATE TABLE public.reference_municipality_villages (
    id integer NOT NULL,
    municipality text NOT NULL,
    ward text NOT NULL,
    village text NOT NULL
);
CREATE SEQUENCE public.reference_municipality_villages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.reference_municipality_villages_id_seq OWNED BY public.reference_municipality_villages.id;
CREATE TABLE public.seah_contact_points (
    seah_contact_point_id text NOT NULL,
    province text,
    district text,
    municipality text,
    ward text,
    project_uuid text,
    seah_center_name text NOT NULL,
    address text,
    phone text,
    opening_days text,
    opening_hours text,
    is_active boolean DEFAULT true,
    sort_order integer DEFAULT 0
);
CREATE TABLE public.seah_service_providers (
    seah_service_provider_id text NOT NULL,
    country_code text DEFAULT 'NP'::text NOT NULL,
    province_code text,
    district_code text,
    municipality_code text,
    province text,
    district text,
    municipality text,
    ward text,
    seah_center_name text NOT NULL,
    address text,
    phone text,
    opening_days text,
    opening_hours text,
    remarks text,
    is_active boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.status_update_timeline (
    id integer NOT NULL,
    status_update_code character varying(50) NOT NULL,
    grievance_high_priority boolean NOT NULL,
    sensitive_issues_detected boolean NOT NULL,
    timeline integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE SEQUENCE public.status_update_timeline_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.status_update_timeline_id_seq OWNED BY public.status_update_timeline.id;
CREATE TABLE public.task_entities (
    task_id text NOT NULL,
    entity_key text NOT NULL,
    entity_id text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT task_entities_entity_key_check CHECK ((entity_key = ANY (ARRAY['grievance_id'::text, 'complainant_id'::text, 'transcription_id'::text, 'translation_id'::text, 'recording_id'::text, 'task_id'::text, 'ticket_id'::text])))
);
CREATE TABLE public.task_statuses (
    task_status_code text NOT NULL,
    task_status_name text NOT NULL,
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    status_name text
);
CREATE TABLE public.tasks (
    task_id text NOT NULL,
    task_name text NOT NULL,
    task_status_code text,
    started_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamp with time zone,
    error_message text,
    result jsonb,
    retry_count integer DEFAULT 0,
    retry_history jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE ONLY public.file_attachments ALTER COLUMN id SET DEFAULT nextval('public.file_attachments_id_seq'::regclass);
ALTER TABLE ONLY public.grievance_status_history ALTER COLUMN id SET DEFAULT nextval('public.grievance_status_history_id_seq'::regclass);
ALTER TABLE ONLY public.office_municipality_ward ALTER COLUMN id SET DEFAULT nextval('public.office_municipality_ward_id_seq'::regclass);
ALTER TABLE ONLY public.reference_grm_office_in_charge ALTER COLUMN id SET DEFAULT nextval('public.reference_grm_office_in_charge_id_seq'::regclass);
ALTER TABLE ONLY public.reference_municipality_villages ALTER COLUMN id SET DEFAULT nextval('public.reference_municipality_villages_id_seq'::regclass);
ALTER TABLE ONLY public.status_update_timeline ALTER COLUMN id SET DEFAULT nextval('public.status_update_timeline_id_seq'::regclass);
ALTER TABLE ONLY public.alembic_version_public
    ADD CONSTRAINT alembic_version_public_pkc PRIMARY KEY (version_num);
ALTER TABLE ONLY public.complainants
    ADD CONSTRAINT complainants_complainant_unique_id_key UNIQUE (complainant_unique_id);
ALTER TABLE ONLY public.complainants
    ADD CONSTRAINT complainants_pkey PRIMARY KEY (complainant_id);
ALTER TABLE ONLY public.field_names
    ADD CONSTRAINT field_names_pkey PRIMARY KEY (field_name);
ALTER TABLE ONLY public.file_attachments
    ADD CONSTRAINT file_attachments_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.grievance_classification_statuses
    ADD CONSTRAINT grievance_classification_statuses_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.grievance_classification_taxonomy
    ADD CONSTRAINT grievance_classification_taxonomy_pkey PRIMARY KEY (category_key);
ALTER TABLE ONLY public.grievance_parties
    ADD CONSTRAINT grievance_parties_pkey PRIMARY KEY (party_id);
ALTER TABLE ONLY public.grievance_status_history
    ADD CONSTRAINT grievance_status_history_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.grievance_statuses
    ADD CONSTRAINT grievance_statuses_pkey PRIMARY KEY (status_code);
ALTER TABLE ONLY public.grievance_transcriptions
    ADD CONSTRAINT grievance_transcriptions_pkey PRIMARY KEY (transcription_id);
ALTER TABLE ONLY public.grievance_translations
    ADD CONSTRAINT grievance_translations_grievance_id_translation_method_key UNIQUE (grievance_id, translation_method);
ALTER TABLE ONLY public.grievance_translations
    ADD CONSTRAINT grievance_translations_pkey PRIMARY KEY (translation_id);
ALTER TABLE ONLY public.grievance_voice_recordings
    ADD CONSTRAINT grievance_voice_recordings_pkey PRIMARY KEY (recording_id);
ALTER TABLE ONLY public.grievances
    ADD CONSTRAINT grievances_pkey PRIMARY KEY (grievance_id);
ALTER TABLE ONLY public.office_management
    ADD CONSTRAINT office_management_pkey PRIMARY KEY (office_id);
ALTER TABLE ONLY public.office_municipality_ward
    ADD CONSTRAINT office_municipality_ward_office_id_municipality_ward_villag_key UNIQUE (office_id, municipality, ward, village);
ALTER TABLE ONLY public.office_municipality_ward
    ADD CONSTRAINT office_municipality_ward_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.office_user
    ADD CONSTRAINT office_user_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.office_user
    ADD CONSTRAINT office_user_us_unique_id_key UNIQUE (us_unique_id);
ALTER TABLE ONLY public.processing_statuses
    ADD CONSTRAINT processing_statuses_pkey PRIMARY KEY (status_code);
ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (project_uuid);
ALTER TABLE ONLY public.reference_grm_office_in_charge
    ADD CONSTRAINT reference_grm_office_in_charge_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.reference_municipality_villages
    ADD CONSTRAINT reference_municipality_villages_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.seah_contact_points
    ADD CONSTRAINT seah_contact_points_pkey PRIMARY KEY (seah_contact_point_id);
ALTER TABLE ONLY public.seah_service_providers
    ADD CONSTRAINT seah_service_providers_pkey PRIMARY KEY (seah_service_provider_id);
ALTER TABLE ONLY public.status_update_timeline
    ADD CONSTRAINT status_update_timeline_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.status_update_timeline
    ADD CONSTRAINT status_update_timeline_status_update_code_grievance_high_pr_key UNIQUE (status_update_code, grievance_high_priority, sensitive_issues_detected);
ALTER TABLE ONLY public.task_entities
    ADD CONSTRAINT task_entities_pkey PRIMARY KEY (task_id, entity_key, entity_id);
ALTER TABLE ONLY public.task_statuses
    ADD CONSTRAINT task_statuses_pkey PRIMARY KEY (task_status_code);
ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (task_id);
ALTER TABLE ONLY public.reference_municipality_villages
    ADD CONSTRAINT uq_ref_mv UNIQUE (municipality, ward, village);
CREATE INDEX idx_classification_status_code ON public.grievance_classification_statuses USING btree (code);
CREATE INDEX idx_complainant_email ON public.complainants USING btree (complainant_email);
CREATE INDEX idx_complainant_phone ON public.complainants USING btree (complainant_phone);
CREATE INDEX idx_complainant_unique_id ON public.complainants USING btree (complainant_unique_id);
CREATE INDEX idx_complainants_contact_id ON public.complainants USING btree (contact_id);
CREATE INDEX idx_complainants_email_hash ON public.complainants USING btree (complainant_email_hash);
CREATE INDEX idx_complainants_location_code ON public.complainants USING btree (location_code);
CREATE INDEX idx_complainants_phone_hash ON public.complainants USING btree (complainant_phone_hash);
CREATE INDEX idx_file_attachments_file_id ON public.file_attachments USING btree (file_id);
CREATE INDEX idx_file_attachments_grievance_id ON public.file_attachments USING btree (grievance_id);
CREATE INDEX idx_file_attachments_upload_timestamp ON public.file_attachments USING btree (upload_timestamp);
CREATE INDEX idx_grievance_complainant ON public.grievances USING btree (complainant_id);
CREATE INDEX idx_grievance_creation_date ON public.grievances USING btree (grievance_creation_date);
CREATE INDEX idx_grievance_language ON public.grievances USING btree (language_code);
CREATE INDEX idx_grievance_modification_date ON public.grievances USING btree (grievance_modification_date);
CREATE INDEX idx_grievance_parties_complainant_id ON public.grievance_parties USING btree (complainant_id);
CREATE INDEX idx_grievance_parties_grievance_id ON public.grievance_parties USING btree (grievance_id);
CREATE INDEX idx_grievance_source ON public.grievances USING btree (source);
CREATE INDEX idx_grievance_status_history_grievance_id ON public.grievance_status_history USING btree (grievance_id, created_at DESC);
CREATE INDEX idx_grievance_temporary ON public.grievances USING btree (is_temporary);
CREATE INDEX idx_grievance_timeline ON public.grievances USING btree (grievance_timeline);
CREATE INDEX idx_grievances_case_sensitivity ON public.grievances USING btree (case_sensitivity);
CREATE INDEX idx_grievances_complainant_id ON public.grievances USING btree (complainant_id);
CREATE INDEX idx_grievances_language_code ON public.grievances USING btree (language_code);
CREATE INDEX idx_office_management_district ON public.office_management USING btree (district);
CREATE INDEX idx_office_management_name ON public.office_management USING btree (office_name);
CREATE INDEX idx_office_municipality_ward_municipality ON public.office_municipality_ward USING btree (municipality);
CREATE INDEX idx_office_municipality_ward_office ON public.office_municipality_ward USING btree (office_id);
CREATE INDEX idx_office_municipality_ward_office_municipality ON public.office_municipality_ward USING btree (office_id, municipality);
CREATE INDEX idx_office_municipality_ward_village ON public.office_municipality_ward USING btree (village);
CREATE INDEX idx_office_municipality_ward_ward ON public.office_municipality_ward USING btree (ward);
CREATE INDEX idx_projects_geo_active ON public.projects USING btree (country, administrative_layer_level_1, administrative_layer_level_2, inactive_at);
CREATE INDEX idx_ref_grm_dist_mun ON public.reference_grm_office_in_charge USING btree (district, municipality);
CREATE INDEX idx_ref_mv_municipality ON public.reference_municipality_villages USING btree (municipality);
CREATE INDEX idx_seah_service_providers_district_code ON public.seah_service_providers USING btree (district_code) WHERE (is_active = true);
CREATE INDEX idx_seah_service_providers_municipality_code ON public.seah_service_providers USING btree (municipality_code) WHERE ((municipality_code IS NOT NULL) AND (is_active = true));
CREATE INDEX idx_status_active ON public.grievance_statuses USING btree (is_active);
CREATE INDEX idx_status_history_assigned ON public.grievance_status_history USING btree (assigned_to);
CREATE INDEX idx_status_history_change_type ON public.grievance_status_history USING btree (change_type);
CREATE INDEX idx_status_history_created ON public.grievance_status_history USING btree (created_at);
CREATE INDEX idx_status_history_field_changes ON public.grievance_status_history USING gin (field_changes);
CREATE INDEX idx_status_history_grievance ON public.grievance_status_history USING btree (grievance_id);
CREATE INDEX idx_status_history_grievance_change_type ON public.grievance_status_history USING btree (grievance_id, change_type);
CREATE INDEX idx_status_history_status ON public.grievance_status_history USING btree (status_code);
CREATE INDEX idx_status_order ON public.grievance_statuses USING btree (sort_order);
CREATE INDEX idx_task_entities_entity ON public.task_entities USING btree (entity_key, entity_id);
CREATE INDEX idx_task_entities_lookup ON public.task_entities USING btree (entity_key, entity_id);
CREATE INDEX idx_task_status_active ON public.task_statuses USING btree (is_active);
CREATE INDEX idx_tasks_completed ON public.tasks USING btree (completed_at);
CREATE INDEX idx_tasks_created ON public.tasks USING btree (created_at);
CREATE INDEX idx_tasks_status ON public.tasks USING btree (task_status_code);
CREATE INDEX idx_timeline_priority ON public.status_update_timeline USING btree (grievance_high_priority);
CREATE INDEX idx_timeline_sensitive ON public.status_update_timeline USING btree (sensitive_issues_detected);
CREATE INDEX idx_timeline_status_code ON public.status_update_timeline USING btree (status_update_code);
CREATE INDEX idx_transcriptions_created ON public.grievance_transcriptions USING btree (created_at);
CREATE INDEX idx_transcriptions_detected_language ON public.grievance_transcriptions USING btree (language_code_detect);
CREATE INDEX idx_transcriptions_grievance_id ON public.grievance_transcriptions USING btree (grievance_id);
CREATE INDEX idx_transcriptions_language ON public.grievance_transcriptions USING btree (language_code);
CREATE INDEX idx_transcriptions_recording_id ON public.grievance_transcriptions USING btree (recording_id);
CREATE INDEX idx_transcriptions_status ON public.grievance_transcriptions USING btree (verification_status);
CREATE INDEX idx_translations_created ON public.grievance_translations USING btree (created_at);
CREATE INDEX idx_translations_method ON public.grievance_translations USING btree (translation_method);
CREATE INDEX idx_translations_source_language ON public.grievance_translations USING btree (source_language);
CREATE INDEX idx_translations_verified ON public.grievance_translations USING btree (verified_at);
CREATE INDEX idx_voice_recordings_created ON public.grievance_voice_recordings USING btree (created_at);
CREATE INDEX idx_voice_recordings_detected_language ON public.grievance_voice_recordings USING btree (language_code_detect);
CREATE INDEX idx_voice_recordings_grievance_id ON public.grievance_voice_recordings USING btree (grievance_id);
CREATE INDEX idx_voice_recordings_language ON public.grievance_voice_recordings USING btree (language_code);
CREATE INDEX idx_voice_recordings_status ON public.grievance_voice_recordings USING btree (processing_status);
CREATE INDEX idx_voice_recordings_type ON public.grievance_voice_recordings USING btree (field_name);
CREATE UNIQUE INDEX uq_grievance_parties_primary_reporter ON public.grievance_parties USING btree (grievance_id) WHERE (is_primary_reporter = true);
CREATE UNIQUE INDEX uq_projects_short_denomination ON public.projects USING btree (project_short_denomination);
ALTER TABLE ONLY public.file_attachments
    ADD CONSTRAINT file_attachments_grievance_id_fkey FOREIGN KEY (grievance_id) REFERENCES public.grievances(grievance_id);
ALTER TABLE ONLY public.grievance_parties
    ADD CONSTRAINT grievance_parties_complainant_id_fkey FOREIGN KEY (complainant_id) REFERENCES public.complainants(complainant_id) ON DELETE SET NULL;
ALTER TABLE ONLY public.grievance_parties
    ADD CONSTRAINT grievance_parties_grievance_id_fkey FOREIGN KEY (grievance_id) REFERENCES public.grievances(grievance_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.grievance_status_history
    ADD CONSTRAINT grievance_status_history_grievance_id_fkey FOREIGN KEY (grievance_id) REFERENCES public.grievances(grievance_id);
ALTER TABLE ONLY public.grievance_status_history
    ADD CONSTRAINT grievance_status_history_status_code_fkey FOREIGN KEY (status_code) REFERENCES public.grievance_statuses(status_code);
ALTER TABLE ONLY public.grievance_transcriptions
    ADD CONSTRAINT grievance_transcriptions_grievance_id_fkey FOREIGN KEY (grievance_id) REFERENCES public.grievances(grievance_id);
ALTER TABLE ONLY public.grievance_transcriptions
    ADD CONSTRAINT grievance_transcriptions_recording_id_fkey FOREIGN KEY (recording_id) REFERENCES public.grievance_voice_recordings(recording_id);
ALTER TABLE ONLY public.grievance_transcriptions
    ADD CONSTRAINT grievance_transcriptions_verification_status_fkey FOREIGN KEY (verification_status) REFERENCES public.processing_statuses(status_code);
ALTER TABLE ONLY public.grievance_translations
    ADD CONSTRAINT grievance_translations_grievance_id_fkey FOREIGN KEY (grievance_id) REFERENCES public.grievances(grievance_id);
ALTER TABLE ONLY public.grievance_voice_recordings
    ADD CONSTRAINT grievance_voice_recordings_complainant_id_fkey FOREIGN KEY (complainant_id) REFERENCES public.complainants(complainant_id);
ALTER TABLE ONLY public.grievance_voice_recordings
    ADD CONSTRAINT grievance_voice_recordings_grievance_id_fkey FOREIGN KEY (grievance_id) REFERENCES public.grievances(grievance_id);
ALTER TABLE ONLY public.grievance_voice_recordings
    ADD CONSTRAINT grievance_voice_recordings_processing_status_fkey FOREIGN KEY (processing_status) REFERENCES public.processing_statuses(status_code);
ALTER TABLE ONLY public.grievances
    ADD CONSTRAINT grievances_complainant_id_fkey FOREIGN KEY (complainant_id) REFERENCES public.complainants(complainant_id);
ALTER TABLE ONLY public.office_municipality_ward
    ADD CONSTRAINT office_municipality_ward_office_id_fkey FOREIGN KEY (office_id) REFERENCES public.office_management(office_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.task_entities
    ADD CONSTRAINT task_entities_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_task_status_code_fkey FOREIGN KEY (task_status_code) REFERENCES public.task_statuses(task_status_code);
