-- Least-privilege DB roles (opt-in) — docs/services/12_security_monitoring_service.md §3 item 9.
--
-- The app currently connects as the broad `user` role. `ops_app` already ships
-- least-privilege via the ops Alembic stream (ops001_init). This script provides
-- the OTHER scoped roles as an OPT-IN hardening step for prod: create them, set
-- passwords, then point each service's POSTGRES_USER/PASSWORD (env.local) at the
-- matching role and restart.
--
-- DO NOT run blindly against a live DB without updating service credentials in the
-- same change window — the app will lose access to schemas the broad role had.
--
-- Usage (prod, deliberate):
--   psql "$DATABASE_URL" -v chatbot_pw="'...'" -v ticketing_pw="'...'" -v kc_pw="'...'" \
--        -f scripts/ops/create_scoped_roles.sql
--
-- Verify afterwards:
--   \du
--   SELECT grantee, table_schema, privilege_type
--     FROM information_schema.role_table_grants WHERE grantee LIKE '%_app' LIMIT 50;

\set ON_ERROR_STOP on

-- ── chatbot/backend role: public.* (chatbot data + PII vault) ────────────────
-- psql does NOT interpolate :'chatbot_pw' inside a $$-quoted block (it errors at the
-- colon), so this must stay outside one. \gexec runs the row the SELECT returns.
SELECT format('CREATE ROLE chatbot_app LOGIN PASSWORD %L', :'chatbot_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chatbot_app')
\gexec
GRANT USAGE ON SCHEMA public TO chatbot_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chatbot_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO chatbot_app;

-- ── ticketing role: ticketing.* (+ the enumerated public.* surface below) ────
-- psql does NOT interpolate :'ticketing_pw' inside a $$-quoted block (it errors at the
-- colon), so this must stay outside one. \gexec runs the row the SELECT returns.
SELECT format('CREATE ROLE ticketing_app LOGIN PASSWORD %L', :'ticketing_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ticketing_app')
\gexec
GRANT USAGE ON SCHEMA ticketing TO ticketing_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ticketing TO ticketing_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ticketing TO ticketing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA ticketing
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ticketing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA ticketing GRANT USAGE, SELECT ON SEQUENCES TO ticketing_app;
-- ── ticketing's public.* surface ─────────────────────────────────────────────
-- Corrected 2026-07-15 (T3-07). This block used to say "Ticketing reads (not writes)
-- the grievance source rows for sync" and grant SELECT on public.grievances alone.
-- Both halves were wrong: ticketing issues 11 statements across 5 tables and 3 of
-- them are WRITES. Adopting the old block would have broken 4 paths — file listing,
-- archiving, the category catalog resync, and the sync job's complainant/party joins.
--
-- The grants below mirror CLAUDE.md §Data rules rule 1 exactly, and that list is
-- gated by tests/ticketing/test_boundary_policy.py. **If that contract changes, change
-- this block in the same commit** — a scoped role that lags the contract fails closed,
-- in prod, as a permission error on a Celery beat job.
--
-- Evidence: docs/sprints/2026-08_tier3_structural/00-reassessment.md §6.
GRANT USAGE ON SCHEMA public TO ticketing_app;

-- services/grievance_content.py, tasks/grievance_sync.py — read-only.
-- Grievance *state* changes go over HTTP (POST /api/grievance/{id}/status), never SQL,
-- so ticketing deliberately gets no INSERT/UPDATE/DELETE here. Keep it that way.
DO $$ BEGIN IF to_regclass('public.grievances') IS NOT NULL THEN
  GRANT SELECT ON public.grievances TO ticketing_app; END IF; END $$;

-- api/ticket_access.py, api/routers/tickets/files.py, engine/ticket_actions.py read;
-- services/archiving.py UPDATEs storage_tier/storage_key/archived_at.
DO $$ BEGIN IF to_regclass('public.file_attachments') IS NOT NULL THEN
  GRANT SELECT, UPDATE ON public.file_attachments TO ticketing_app; END IF; END $$;

-- services/grievance_categories_catalog.py resyncs the catalog by DELETE-then-INSERT
-- (the DELETE is an unqualified full-table wipe — see §6). seed/kl_road_standard.py
-- COUNT(*)s it.
DO $$ BEGIN IF to_regclass('public.grievance_classification_taxonomy') IS NOT NULL THEN
  GRANT SELECT, INSERT, DELETE ON public.grievance_classification_taxonomy TO ticketing_app;
  END IF; END $$;

-- tasks/grievance_sync.py LEFT JOINs these every 2 minutes.
--
-- complainants is COLUMN-scoped on purpose: it is the PII table, and ticketing needs
-- exactly two non-PII columns from it. This makes CLAUDE.md §Data rules rule 3
-- ("public.complainants is not a PII source for ticketing") enforced by Postgres rather
-- than by convention — a SELECT of complainant_phone fails at the DB, not at review.
-- It is the single best reason to adopt this script.
DO $$ BEGIN IF to_regclass('public.complainants') IS NOT NULL THEN
  GRANT SELECT (complainant_id, location_code) ON public.complainants TO ticketing_app;
  END IF; END $$;
DO $$ BEGIN IF to_regclass('public.grievance_parties') IS NOT NULL THEN
  GRANT SELECT ON public.grievance_parties TO ticketing_app; END IF; END $$;

-- ── keycloak role: keycloak schema only ──────────────────────────────────────
-- psql does NOT interpolate :'kc_pw' inside a $$-quoted block (it errors at the
-- colon), so this must stay outside one. \gexec runs the row the SELECT returns.
SELECT format('CREATE ROLE keycloak_app LOGIN PASSWORD %L', :'kc_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keycloak_app')
\gexec
CREATE SCHEMA IF NOT EXISTS keycloak AUTHORIZATION keycloak_app;
GRANT ALL ON SCHEMA keycloak TO keycloak_app;
