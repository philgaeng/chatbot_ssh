# Agent runbook — CL-01: Canonical public schema

**Branch:** land on `dev/hardening` · **Model:** Opus (high effort — the app boots against this schema) · **Spec:** [`../01-public-schema-source-of-truth-spec.md`](../01-public-schema-source-of-truth-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §1 first. **Unblocks the hardening CI.**

**0 records → REBUILD, don't reconcile.** No data preservation, no idempotent-shape-detection. Define the canonical schema (the app's real shape) and build one clean baseline.

## Mission

Make the Alembic `public` stream the single canonical source of truth for `public.*`, matching what the app runs, so a fresh-from-migrations DB is exactly the app schema — letting CI's `backend-tests` seed and run pytest. Delete the base_manager-vs-Alembic dual ownership.

## Steps

1. **Capture canonical schema:** `pg_dump --schema-only --schema=public grievance_db` (live DB, :5432, user `nepal_grievance_admin`, READ ONLY) → normalize → commit `schema_app.sql` as the reference. This is the target (the app's real shape = base_manager, NOT the drifted `pub000`).
2. **One canonical baseline migration** (`migrations/public/`): since 0 records / not-live, re-baseline — squash the drifted `pub000..pub009` into a single authoritative baseline (or one drop-and-recreate migration; document the choice). It creates every **live** table (AUDIT §1a + the reconciled §1b, all at the base_manager/live shape), **excludes** the 7 dead tables (§1c) and `events` (§1d), and uses the live **UPPERCASE** `grievance_statuses` vocab. Real downgrade. Don't touch `ticketing`/`ops` streams.
3. **Delete app-startup DDL:** remove `CREATE/ALTER TABLE` from `base_manager.py`, `grievance_categories_catalog.py`, `config/database_tables.py`, `postgres_services.py`; keep only data-seeding (runs against a migrated DB); delete the `grievance_history` migrate-and-drop. No reintroducing `CREATE TABLE IF NOT EXISTS`.
4. **Migrate-before-start** in every bring-up path (compose start order/entrypoints, Makefile, `03_operations.md`).
5. **Verify** (scratch DBs; the stack is up — DB container `nepal_chatbot_seah-db-1`, live `grievance_db` :5432): empty DB → public→ticketing→ops migrations → **seed succeeds** (`import_locations_json` + `mock_tickets --reset`) → `pytest tests/ticketing tests/orchestrator tests/actions` runs — **record real pass/fail** and the verdict on the hardening "4 pre-existing failures" on a clean DB. Schema-diff: fresh-migration `pg_dump` == `schema_app.sql` (empty). `upgrade→downgrade→upgrade` clean.
6. **Add the schema-diff gate to `.github/workflows/ci.yml`** (backend-tests) so drift can't return. (Can't run live Actions — no gh; just add the step, note pending.)

## Coordinate with CL-04
CL-04 renames env vars (`APP_ENV`) the CI/migration invocation reads. If CL-04 landed, use `APP_ENV`; else use current vars + note the follow-up. Schema work is independent of var names.

## Constraints
- `migrations/public/` only. Test on scratch DBs; read `grievance_db` only. Canonical shape = the app's real shape (base_manager wins over `pub000`). Extend the baseline until schema-diff is empty.

## Done means
Fresh migrate → seed → pytest works (results recorded); one canonical public baseline; base_manager owns no schema DDL; 7 dead tables + `events` excluded; schema-diff gate in CI; PROGRESS updated; future-Rasa note filed.
