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
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chatbot_app') THEN
    EXECUTE format('CREATE ROLE chatbot_app LOGIN PASSWORD %L', :'chatbot_pw');
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO chatbot_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chatbot_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatbot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO chatbot_app;

-- ── ticketing role: ticketing.* (+ read paths it needs in public) ────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ticketing_app') THEN
    EXECUTE format('CREATE ROLE ticketing_app LOGIN PASSWORD %L', :'ticketing_pw');
  END IF;
END $$;
GRANT USAGE ON SCHEMA ticketing TO ticketing_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ticketing TO ticketing_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ticketing TO ticketing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA ticketing
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ticketing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA ticketing GRANT USAGE, SELECT ON SEQUENCES TO ticketing_app;
-- Ticketing reads (not writes) the grievance source rows for sync:
GRANT USAGE ON SCHEMA public TO ticketing_app;
DO $$ BEGIN IF to_regclass('public.grievances') IS NOT NULL THEN
  GRANT SELECT ON public.grievances TO ticketing_app; END IF; END $$;

-- ── keycloak role: keycloak schema only ──────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keycloak_app') THEN
    EXECUTE format('CREATE ROLE keycloak_app LOGIN PASSWORD %L', :'kc_pw');
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS keycloak AUTHORIZATION keycloak_app;
GRANT ALL ON SCHEMA keycloak TO keycloak_app;
