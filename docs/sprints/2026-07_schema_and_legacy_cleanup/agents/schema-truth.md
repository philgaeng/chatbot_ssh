# Agent runbook — CL-01: Canonical public schema (squash + prune)

**Branch:** land on `dev/hardening` · **Model:** Opus (high effort — the app boots against this schema; wrong prune = runtime break) · **Spec:** [`../01-public-schema-source-of-truth-spec.md`](../01-public-schema-source-of-truth-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §1 first. **Unblocks the hardening CI.**

**0 records → REBUILD.** Two moves: **squash** the drifted migrations into one baseline, and **prune** columns/tables nothing uses.

## Mission
One canonical Alembic baseline that IS `public.*` — no dual ownership, no drift, no dead weight. Fresh DB migrates to it; app + full tests + seed run against it.

## Steps
1. **Capture starting point:** `pg_dump --schema-only --schema=public grievance_db` (live :5432, user `nepal_grievance_admin`, READ ONLY).
2. **Column-usage audit → prune list.** For each kept table (AUDIT §1a/§1b) grep every column name across `backend/`, `ticketing/`, `rasa_chatbot/`, `channels/REST_webchat/`, ORM models, seed scripts, raw SQL. Classify used/dead → commit `prune_audit.md` (each dropped column + evidence). **Ambiguous (`SELECT *`, `RETURNING *`, ORM reflection, serializers/`to_dict`, seed-by-position) ⇒ KEEP.** Exclude the 7 dead tables (§1c) + `events` (§1d) entirely.
3. **One canonical baseline** (`migrations/public/`): delete the old `pub001..pub009`; author a single authoritative baseline (document whether you reuse `pub000` or a fresh revision); reset `alembic_version_public`. It creates each kept table with **used columns only**, app types, `grievance_statuses` UPPERCASE vocab. Real downgrade. Don't touch `ticketing`/`ops`.
4. **Delete app-startup DDL** (`base_manager.py`, `grievance_categories_catalog.py`, `config/database_tables.py`, `postgres_services.py`): remove all `CREATE/ALTER TABLE`; keep only data-seeding; delete `grievance_history` migrate-and-drop. Remove code that reads/writes pruned columns (or, if it turns out live, keep the column — decide per case in the audit).
5. **Migrate-before-start** in every bring-up path (compose/entrypoints/Makefile/`03_operations.md`).
6. **Verify** (scratch DBs; stack up — DB `nepal_chatbot_seah-db-1`, live `grievance_db` :5432): empty DB → public→ticketing→ops → **seed succeeds → `pytest tests/ticketing tests/orchestrator tests/actions` runs → app smoke** (submit grievance → chatbot → ticket intake). Record real pass/fail + the "4 pre-existing failures" verdict. Self-consistency: fresh-migration `pg_dump` == committed baseline dump. `upgrade→downgrade→upgrade` clean.
7. **CI self-consistency gate** in `.github/workflows/ci.yml`. (No gh → add the step, note verification pending.)

## Coordinate with CL-03
CL-03 renames env vars (`APP_ENV`). Use it if landed; else current vars + note follow-up. Schema is independent of var names.

## Constraints
- `migrations/public/` only. Scratch DBs; read `grievance_db` only. **Ambiguous column usage ⇒ keep.** A pruned column that breaks a test/smoke ⇒ restore it + fix the audit. Exclude the 7 dead tables + `events`.

## Done means
One squashed baseline, used columns only; `prune_audit.md` committed; app-startup DDL gone; fresh migrate → seed → pytest → smoke green (recorded); self-consistency gate in CI; PROGRESS updated; future-Rasa note filed.
