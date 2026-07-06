# Agent runbook — CL-01: Public schema single source of truth

**Branch:** `cleanup/cl-01-schema` off the agreed base · **Model:** Opus (high effort — live chatbot schema, exact reconciliation) · **Spec:** [`../01-public-schema-source-of-truth-spec.md`](../01-public-schema-source-of-truth-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §1 first. **Run first — unblocks the hardening CI.**

⚠️ **This rewrites who owns the live `public.*` chatbot schema. Every DDL statement is idempotent, reconciles TO the live shape, and is data-preserving. Test against a COPY of the live DB, never destructively against it.**

## Mission

Make the Alembic `public` stream the single source of truth for `public.*` so a fresh-from-migrations DB is byte-identical to the running app's schema — which lets CI's `backend-tests` seed and finally run pytest. Kill the base_manager-vs-Alembic dual ownership.

## Steps

1. **Build the acceptance gate FIRST** (spec §Acceptance gate). Capture canonical schema: `pg_dump --schema-only --schema=public` of the live `grievance_db` (:5432, user `nepal_grievance_admin`) → `schema_app.sql`. Write a normalizer (strip comments/ordering/whitespace) + a `diff` harness. Commit both. This defines "done."
2. **Enumerate all app-startup DDL sources** to neutralize later: `base_manager.py`, `grievance_categories_catalog.py`, `config/database_tables.py`, `postgres_services.py`. And confirm the public head: `alembic -c migrations/public/alembic.ini heads`.
3. **Author the reconciliation migration** (chain on head; safety header). Per AUDIT §1a/§1b/§1c and spec §Steps.2:
   - `+13` app-only tables (`CREATE TABLE IF NOT EXISTS`, verbatim from app definitions) — incl. voice + `seah_contact_points`.
   - Reconcile the 7 drifted tables to live shape (`ADD COLUMN IF NOT EXISTS`; guarded drops of migration-only extras). **`grievance_classification_taxonomy`:** shape-detect via `information_schema`; drop+recreate to `category_key` shape ONLY when the old `category_code` shape is present; else no-op. **`grievance_statuses`:** live UPPERCASE vocab.
   - Drop the 7 dead tables (`DROP TABLE IF EXISTS … CASCADE`): `grievance_history`, `users`, `contact_info`, `resource_persons`, `grievance_reveal_sessions`, `grievance_sensitive_access_audit`, `grievance_vault_payloads`.
   - **Never** touch `events` (Rasa). Real `downgrade()` (document what it can/can't invert).
4. **Neutralize app-startup DDL:** remove the overlapping `CREATE/ALTER TABLE` from base_manager (+ other sources) for tables migrations now own; keep non-DDL seeding. Retire the `grievance_history` migrate-and-drop (table is being dropped).
5. **Guarantee migrate-before-start** in every bring-up path (compose start order/entrypoints, Makefile, `docs/deployment/03_operations.md`).
6. **Verify** (all in-container against scratch/copy DBs — the stack is up; DB container `nepal_chatbot_seah-db-1`, live DB `grievance_db` on :5432): schema-diff empty; reconciliation safe on a **copy of live** (row counts of kept tables unchanged, only the 7 drops); fresh empty DB → migrations → **seed succeeds** → `pytest tests/ticketing tests/orchestrator tests/actions` runs (record real results — this adjudicates the hardening sprint's "4 pre-existing failures" on a clean DB); `upgrade→downgrade→upgrade` clean.
7. **CI:** add the schema-diff gate as a `backend-tests` step so drift can never silently return.

## Constraints
- `migrations/public/` stream only. Idempotent, reconcile-to-live, data-preserving. Don't touch `ticketing`/`ops`/`events`.
- The **empty schema-diff is the real bar** — if drift is deeper than AUDIT §1, extend the migration until the diff is empty.
- No app behavior change beyond *where* tables are defined (+ the intentional `grievance_statuses` vocab fix and 7 drops).

## Done means
Schema-diff gate green; migration verified safe on a live-DB copy; CI seeds + runs pytest (results recorded); base_manager no longer owns public DDL; 7 dead tables dropped; PROGRESS updated; future-Rasa-removal note filed.
