# CL-01 — Canonical `public.*` schema (single Alembic baseline)

> Workstream: schema-truth · Branch/land on `dev/hardening` · **The CI blocker.**
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §1. **prod is not live — 0 records** (§4), so this is a clean **rebuild**, not a data-preserving reconciliation.

---

## Goal

Make the Alembic **public** stream the single, canonical source of truth for `public.*`, matching what the app actually runs, so a fresh-from-migrations DB is exactly the app's schema — which lets CI's `backend-tests` seed and run pytest. Kill the base_manager-vs-Alembic dual ownership entirely.

## Why this is now simple

With **0 real records**, we don't reconcile drift or preserve data. We: (1) define the canonical schema (the app's real shape), (2) express it as one clean Alembic baseline, (3) delete the app-startup DDL, (4) drop the dead tables. No `information_schema` shape-detection, no idempotent-only-when-wrong guards, no "safe on live copy" gymnastics — just build the canonical thing.

## Canonical shape = the app's real schema

The truth is what the running app uses: the `base_manager.py` table definitions (+ the other app-startup DDL sources), which the audit captured as the live `grievance_db` schema. That is the target — **not** the drifted `pub000` definitions. AUDIT §1a (13 app-only tables to include), §1b (7 drift cases → use the live/base_manager column set), §1c (7 dead tables to exclude entirely), §1d (`events` excluded — Rasa).

## Approach — re-baseline the public stream

1. **Capture the canonical schema:** `pg_dump --schema-only --schema=public grievance_db` → normalize → `schema_app.sql` (commit it as the reference).
2. **Author one canonical baseline migration** (re-baseline the public stream; since 0 records / not-live, this replaces the drifted `pub000…pub009` lineage — squash them into a single canonical baseline, or add one authoritative migration that drops-and-recreates the whole `public` app schema; pick the cleaner of the two and document the choice). It:
   - Creates every **live** public table with the app's real columns (the ~22 kept tables incl. the 13 app-only ones + the reconciled 7, all at the live/base_manager shape).
   - Does **not** create the 7 dead tables (AUDIT §1c) or `events`.
   - `grievance_statuses` uses the live **UPPERCASE** vocabulary (drop the `pub000` lowercase seed entirely).
   - Real `downgrade()` (drop the schema's tables).
   - Keep the `ticketing` and `ops` streams untouched (they're clean).
3. **Delete the app-startup DDL:** remove the `CREATE TABLE` / `ALTER TABLE` from `base_manager.py`, `grievance_categories_catalog.py`, `config/database_tables.py`, `postgres_services.py`. Migrations own structure now; app code keeps only **data seeding** (which runs against a migrated DB). Delete the `grievance_history` migrate-and-drop logic (table is gone). If a startup path still needs a table to exist, it must rely on migrations having run — do not reintroduce `CREATE TABLE IF NOT EXISTS`.
4. **Migrate-before-start everywhere:** app services must run against an already-migrated DB. Verify/fix the bring-up order (compose start order/entrypoints, Makefile, `docs/deployment/03_operations.md`) so migrations run before the app. (CI already does.)
5. **CI schema-diff gate:** add a `backend-tests` step that fails if `pg_dump` of a fresh-migration DB drifts from the committed `schema_app.sql` — so the canonical schema can never silently diverge again.

## Coordinate with CL-04

CL-04 renames env vars (`APP_ENV` etc.) that the CI job and migration invocation read. If CL-04 lands first (recommended order), use `APP_ENV`; if CL-01 goes first, use the current vars and note the follow-up. Don't block on it — the schema work is independent of the var names.

## Testing (acceptance)

- [ ] **Fresh-build works:** empty DB → public → ticketing → ops migrations → **seed succeeds** (`import_locations_json` + `mock_tickets --reset`) → `pytest tests/ticketing tests/orchestrator tests/actions` runs to completion. Record real pass/fail — this finally adjudicates the hardening sprint's "4 pre-existing failures" on a clean canonical DB (do they pass now, or are they genuinely broken?).
- [ ] **Schema-diff gate green:** fresh-migration `pg_dump --schema-only --schema=public` == committed `schema_app.sql` (empty diff; the 7 dead tables and `events` intentionally absent).
- [ ] **App startup owns no DDL:** `grep -rn "CREATE TABLE" backend/ ticketing/` shows the app-startup DDL gone; the app boots against a migrated DB.
- [ ] Migration round-trip `upgrade → downgrade → upgrade` clean on a scratch DB.
- [ ] `grep` confirms the 7 dead tables and Rasa `events` are not created by any migration.

## Constraints

- `migrations/public/` stream only. Do not touch `ticketing`/`ops`/`events`.
- Test on **scratch DBs**; read `grievance_db` only for the canonical dump (don't run migrations against it — not for data-safety now, just hygiene).
- The **canonical schema = the app's real shape.** Where `pub000` and base_manager disagree, base_manager wins (that's what the app runs). If new drift surfaces beyond AUDIT §1, extend the baseline until the schema-diff is empty.

## Done means

Fresh migrate → seed → pytest works (results recorded); one canonical public baseline; base_manager (+ other app-startup DDL) owns no schema; 7 dead tables + `events` excluded; schema-diff gate in CI; [`PROGRESS.md`](PROGRESS.md) updated; future-Rasa-removal note filed.
