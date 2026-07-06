# CL-01 — Public schema: single source of truth

> Workstream: schema-truth · Branch `cleanup/cl-01-schema` · **The CI blocker — do first.**
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §1. This is **`public.*` (chatbot) schema** — CLAUDE.md "change with care." Every step is idempotent and reconciles **to the live shape** (what prod runs), proven by a schema-diff gate.

---

## Goal

Make the Alembic **public** stream (`migrations/public/`) the single source of truth for `public.*`, so a fresh-from-migrations database is byte-identical to the running app's schema — which finally lets CI's `backend-tests` seed and run pytest. Today the schema is co-owned by app-startup DDL (`base_manager.py` + others) and Alembic, and they've drifted (7 of 9 shared tables + 13 app-only tables + 7 dead tables — see AUDIT_FINDINGS §1).

## Acceptance gate (write this harness FIRST — it defines "done")

A schema-equality check, runnable in-container and in CI:
1. **DB-A (migrations):** empty DB → run public → ticketing → ops migrations. `pg_dump --schema-only --schema=public` → normalize (strip comments/whitespace/ordering) → `schema_migrations.sql`.
2. **DB-B (app truth):** the canonical shape. Prefer a `pg_dump --schema-only --schema=public` of the **live `grievance_db`** (the audit's reference) captured once as `schema_app.sql`; if unavailable, an app-bootstrap run of `base_manager` on an empty DB.
3. `diff schema_migrations.sql schema_app.sql` must be **empty** (except the intentionally-dropped dead tables and excluded `events`/Rasa). Commit the normalizer script + the expected baseline.

Everything below exists to make that diff empty.

## Steps

1. **Capture canonical schema.** `pg_dump --schema-only --schema=public grievance_db` (the live DB, :5432) → the target. Also enumerate every app-startup DDL source to be neutralized later: `backend/services/database_services/base_manager.py`, `ticketing/services/grievance_categories_catalog.py`, `backend/config/database_tables.py`, `backend/services/database_services/postgres_services.py`.

2. **Author the reconciliation migration(s)** in `migrations/public/versions/` (chain on the current public head; confirm with `alembic -c migrations/public/alembic.ini heads`; safety header noting public-schema scope). One logical migration (or a small ordered set) that brings ANY public DB — empty CI or the live one — to canonical, **idempotently and data-preservingly**:
   - **Add the 13 app-only tables** (AUDIT §1a) verbatim from their app-startup definitions, `CREATE TABLE IF NOT EXISTS`. These are live and kept (incl. the voice tables `grievance_voice_recordings`/`grievance_transcriptions` and `seah_contact_points`).
   - **Reconcile the 7 drifted tables** (AUDIT §1b) to the live shape:
     - Column gaps → `ALTER TABLE … ADD COLUMN IF NOT EXISTS …` (e.g. `file_attachments.id`/`client_metadata`, `grievance_status_history.change_type`/`field_changes`, `task_statuses.status_name`).
     - Extra migration-only columns the app lacks (`tasks.metadata`, `task_entities.id`, `grievance_statuses.updated_at`) → drop them **only if** the live DB doesn't have them (guard with an information_schema check so it's safe both ways).
     - **`grievance_classification_taxonomy` (completely divergent):** detect shape via `information_schema` — if the old `category_code` shape is present (fresh CI DBs), `DROP … CASCADE` + `CREATE` the correct `category_key` shape; if already the live `category_key` shape, no-op. Re-seed is handled by the seed step (reference data). **Do NOT unconditionally drop** — that would delete the live 24 rows.
     - **`grievance_statuses`:** reconcile columns to live, and standardize on the **live UPPERCASE vocabulary** (`SUBMITTED/UNDER_EVALUATION/ESCALATED/…`); do not let the `pub000` lowercase seed reintroduce a second vocab. If both coexist in a DB, keep uppercase.
   - **Drop the 7 dead tables** (AUDIT §1c) `DROP TABLE IF EXISTS … CASCADE`: `grievance_history`, `users`, `contact_info`, `resource_persons`, `grievance_reveal_sessions`, `grievance_sensitive_access_audit`, `grievance_vault_payloads`.
   - **Exclude `events`** (Rasa) entirely — do not create, alter, or drop it.
   - Real `downgrade()` where sensible (recreate dropped tables' shells; note that a perfect inverse of a reconciliation isn't always meaningful — document what downgrade does).

3. **Neutralize the app-startup DDL** so it can't re-diverge the schema. Remove the overlapping `CREATE TABLE` / `ALTER TABLE` statements from `base_manager.py` and the other DDL sources for the tables migrations now own. Keep the **non-DDL** behavior (data seeding, the `grievance_history`→`grievance_status_history` data migration if any live DB still needs it — but the table is being dropped, so retire that too). If fully removing is too risky in one pass, the fallback is to gate the app-startup DDL behind a flag that is **off by default** and document migrations as authoritative — but the clean target is removal.

4. **Guarantee migrations run before app startup** in every bring-up path (since app code no longer creates tables): check `docker-compose*.yml` service start order / entrypoints, `Makefile` bring-up targets, and `docs/deployment/03_operations.md`. Document/enforce "migrate, then start app." (CI already migrates before pytest.)

5. **Wire/verify CI.** The HR-05 `backend-tests` job already runs public→ticketing→ops then seeds then pytest. With this ticket, the seed step succeeds and pytest runs. Add the schema-diff gate as a CI step (fail if the fresh-migration schema drifts from the committed canonical baseline) so this can never silently regress.

## Testing (acceptance)

- [ ] **Schema-diff gate green:** DB-A (migrations) `pg_dump` == canonical `schema_app.sql` (empty diff, minus the dropped/excluded set). Committed normalizer + baseline.
- [ ] **Safe on the live shape:** run the reconciliation migration against a **copy of the live `grievance_db`** (dump/restore into a scratch DB, or the container DB) — it must be a near-no-op (adds nothing, drops only the 7 dead tables, does NOT drop/rebuild the correctly-shaped taxonomy or lose data). Assert row counts of kept tables unchanged.
- [ ] **Fresh CI path:** empty DB → migrations → **seed succeeds** (`import_locations_json` + `mock_tickets --reset`) → `pytest tests/ticketing tests/orchestrator tests/actions` runs to completion. Record the real pass/fail (this is also where the hardening sprint's "4 pre-existing failures" finally get adjudicated on a clean DB).
- [ ] Migration round-trip `upgrade → downgrade → upgrade` clean on a scratch DB.
- [ ] App-bootstrap no longer creates/alters these tables (grep base_manager etc. → the DDL is gone or gated off); app still starts with a migrated DB.

## Constraints

- `public.*` only via the `migrations/public/` Alembic stream (never `ticketing`/`ops` streams). Idempotent, reconcile-to-live, data-preserving.
- Do not touch `events`/Rasa. Do not alter `ticketing.*` or `ops.*`.
- No behavior change to the app beyond *where* tables are defined; seeds/data semantics unchanged (except the intentional `grievance_statuses` vocab standardization and the 7 drops).
- If the drift turns out deeper than AUDIT §1 (new tables/columns surface during the schema-diff), extend the reconciliation to cover them — the **empty diff is the real bar**, not the audit's table list.

## Done means

Schema-diff gate green in CI; reconciliation migration verified safe on a live-DB copy; CI `backend-tests` seeds + runs pytest (real results recorded); base_manager no longer owns public DDL; the 7 dead tables dropped; [`PROGRESS.md`](PROGRESS.md) updated; future-Rasa-removal note filed.
