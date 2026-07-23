# CL-01 — Canonical `public.*` schema (squashed baseline + column prune)

> Workstream: schema-truth · Branch/land on `dev/hardening` · **The CI blocker.**
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §1. **prod not live — 0 records** → clean **rebuild**.
> Decisions: **squash** the drifted `pub000..pub009` into one canonical baseline; **prune unused columns/tables** (not just match the current app shape).

---

## Goal

One canonical Alembic baseline that IS the `public.*` schema — no dual ownership, no drift, and no dead weight. A fresh DB migrates to exactly this baseline; the app + full test suite + seed all run against it.

## Two-part canonicalization

1. **Squash** — replace the drifted `pub000…pub009` lineage with a **single** canonical baseline migration; reset `alembic_version_public` to it. Safe because 0 records / not-live.
2. **Prune** — the canonical schema is the **used** subset of the app's real shape: audit column-level usage and **drop columns/tables that nothing reads or writes**. (This is why the gate is not "diff == current app" — we are intentionally shrinking it.)

## Approach

1. **Capture the starting point:** `pg_dump --schema-only --schema=public grievance_db` (live DB :5432, user `nepal_grievance_admin`, READ ONLY) → the pre-prune reference.
2. **Column-usage audit → prune list.** For every kept table (AUDIT §1a/§1b), determine which columns are actually referenced by live code — grep column names across `backend/`, `ticketing/`, `rasa_chatbot/`, `channels/REST_webchat/`, ORM models, seed scripts, and raw SQL. Classify each column **used / dead**. Produce a committed `prune_audit.md` listing every dropped column + the evidence it's unused. **Beware hidden usage:** `SELECT *`, `RETURNING *`, ORM reflection, `to_dict()`/serializers, and CSV/seed loaders that map by position — when a column's usage is ambiguous, **keep it** and note it. Excludes the 7 dead tables (§1c) and `events` (§1d) entirely.
3. **Author the single canonical baseline** in `migrations/public/versions/` (delete the old `pub001..pub009`; make one authoritative baseline — keep the `pub000` filename/revision or a fresh one, document the choice). It creates each kept table with **only the used columns**, at the app's types, `grievance_statuses` on the live **UPPERCASE** vocab. Real `downgrade()` drops them. `ticketing`/`ops` streams untouched.
4. **Delete app-startup DDL** (`base_manager.py`, `grievance_categories_catalog.py`, `config/database_tables.py`, `postgres_services.py`): remove all `CREATE/ALTER TABLE`; keep only data-seeding; delete the `grievance_history` migrate-and-drop. **Also remove any code that reads/writes the pruned columns** (that's what makes the prune real — if code still references a dropped column, either it was actually used (keep the column) or the code is dead (remove it), decided per case in the audit).
5. **Migrate-before-start** enforced in every bring-up path (compose/entrypoints/Makefile/`03_operations.md`).
6. **CI self-consistency gate:** a fresh-migration `pg_dump` must equal the committed canonical baseline dump (the schema can't silently drift from its own baseline again). Since we pruned, the gate is *baseline-vs-fresh-migration*, not *vs the old app*.

## Coordinate with CL-03
CL-03 renames env vars (`APP_ENV`) the CI/migration invocation reads. Use `APP_ENV` if CL-03 landed; else current vars + note the follow-up. Schema work is independent of the var names.

## Testing (acceptance — the real bar, since we can't diff against the old app)

- [ ] **Everything works on the rebuilt+pruned schema:** empty DB → public→ticketing→ops migrations → **seed succeeds** (`import_locations_json` + `mock_tickets --reset`) → `pytest tests/ticketing tests/orchestrator tests/actions` runs to completion. Record real pass/fail (adjudicates the hardening "4 pre-existing failures" on a clean DB).
- [ ] **App smoke:** the backend + ticketing apps boot against the migrated DB and a key flow works (submit a grievance → chatbot → ticket intake), catching any `SELECT *`/serializer that depended on a pruned column.
- [ ] **Prune is justified:** `prune_audit.md` lists every dropped column/table with non-use evidence; nothing ambiguous was dropped.
- [ ] **No app-startup DDL:** `grep -rn "CREATE TABLE" backend/ ticketing/` → gone; app boots against a migrated DB only.
- [ ] **Self-consistency gate green:** fresh-migration `pg_dump` == committed baseline dump; `upgrade→downgrade→upgrade` clean; 7 dead tables + `events` absent.

## Constraints
- `migrations/public/` stream only; test on scratch DBs; read `grievance_db` only.
- **When column usage is ambiguous, keep the column.** A wrong prune that a `SELECT *`/serializer relied on is a runtime break — the full test + smoke run is the safety net, so a pruned column that breaks a test means: restore it and fix the audit.
- Excludes the 7 dead tables and Rasa `events`.

## Done means
One squashed canonical baseline with only used columns; `prune_audit.md` committed; app-startup DDL gone; fresh migrate → seed → pytest + smoke all green (results recorded); self-consistency gate in CI; [`PROGRESS.md`](PROGRESS.md) updated; future-Rasa note filed.
