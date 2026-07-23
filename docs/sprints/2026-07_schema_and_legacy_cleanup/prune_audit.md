# CL-01 prune audit — `public.*` canonical baseline

Column/table-usage audit backing the squash+prune in
`migrations/public/versions/pub000_public_core_baseline.py`. Evidence gathered by
grepping every column name across `backend/`, `ticketing/`, `ops/`,
`rasa_chatbot/`, `channels/`, `scripts/`, `dev-scripts/`, ORM models, seed
scripts and raw SQL. **Rule: ambiguous usage (`SELECT *`, `RETURNING *`, ORM
reflection, serializers/`to_dict`, dynamic field-mapping, seed-by-position) ⇒
KEEP.** The safety net is the full migrate → seed → pytest → app-smoke run.

Pre-prune reference: `pg_dump --schema-only` of the live `grievance_db`
(`alembic_version_public = pub007`), captured read-only.

---

## 1. Tables DROPPED (7) — product-owner-confirmed dead, 0 rows (AUDIT_FINDINGS §1c)

| Table | Evidence it is unused |
|---|---|
| `grievance_history` | Legacy; base_manager dropped it at startup and migrated data into `grievance_status_history`. The only migrate-and-drop code (`migrate_to_enhanced_history_system`) had **no callers** and is deleted. No reader/writer remains. |
| `users` | No creator in either DDL source, no reader. Sole reference was a drop-list in `scripts/database/init.py`'s verify list — now removed. Orphan. |
| `contact_info` | Created only by the retired `pub002`; no app SQL reads/writes it (the `'contact_info'` strings in code are a Celery op-key, not the table). |
| `resource_persons` | Created only by retired `pub002`; zero code references. |
| `grievance_reveal_sessions` | Retired `pub003` SEAH vault-audit foundation, never wired. **0 writers, 0 readers** (verified by grep). Real reveal-audit logs `REVEAL_ORIGINAL` into `ticketing.*`. |
| `grievance_sensitive_access_audit` | Same as above — `pub003`, unwired. **0 writers, 0 readers.** |
| `grievance_vault_payloads` | `pub003`; the single writer was `postgres_services.submit_seah_to_db` (INSERT only, **no readers anywhere**). That dead write is removed (see §3). Abandoned with the trio. |

## 2. Tables EXCLUDED from the Alembic-managed set (AUDIT_FINDINGS §1d)

- **`events`** (Rasa `SQLTrackerStore`) — Rasa-owned schema; left untouched, never created/dropped by the public stream. See the future-Rasa note in `PROGRESS.md`.
- **`alembic_version_public`** — Alembic infra; bootstrapped by `migrations/public/env.py`, not by a migration.

## 3. Columns PRUNED inside kept tables — **none**

After a column-by-column audit, **no column of any kept table can be pruned
without unacceptable ambiguity.** Every column falls into at least one "keep"
bucket below. Dropping a column a `SELECT *` / serializer / dynamic writer
depended on is a runtime break, and the runbook mandates keep-on-ambiguous.

### 3a. `SELECT *` tables — all columns kept (dropping any risks a wildcard consumer)

`grievances`, `grievance_statuses`, `task_statuses`, `processing_statuses`,
`field_names`, `grievance_classification_statuses`, `grievance_transcriptions`,
`grievance_translations`, `grievance_voice_recordings`, `seah_contact_points`,
`seah_service_providers` are each read via `SELECT * FROM <table>` (e.g.
`backend/config/database_tables.py` `DatabaseLookupService._load_cache`,
`postgres_services.find_seah_*`). `RETURNING *` = 0 occurrences (checked).

### 3b. Dynamic field-mapping / hashing — columns written without a literal name

`complainants.complainant_full_name_hash` appears **only** in DDL as a literal,
but `_hash_sensitive_data` writes `{field}_hash` for every `field` in
`HASHED_FIELDS` (which includes `complainant_full_name`) — so the column IS
written dynamically. Same pattern guards `complainant_phone_hash` /
`complainant_email_hash` and every `complainants.level_N_name/level_N_code`
(written by `submit_seah_to_db`'s complainant payload and read via decrypt/field
mapping). Kept.

### 3c. Cohesive used features — columns individually referenced

- `grievances.vault_payload_ref`, `grievances.vault_last_updated_at` — read/updated by grievance services; also on a `SELECT *` table. Kept (the write was to the dropped `grievance_vault_payloads` table, removed in §4, but the columns stay).
- `grievances.is_archived`, `grievances.archived_at`, `file_attachments.storage_tier`, `file_attachments.archived_at`, `file_attachments.storage_key` — the archiving/retention feature (`ticketing/services/archiving.py`, `postgres_services.is_grievance_archived`, `backend/api/routers/files.py`). **These were the former `pub008` additions**; the live DB (pub007) lacks them but the code needs them, so they are folded into the baseline. Kept.
- `grievances.case_sensitivity`, `grievance_categories_alternative`, `grievance_timeline` — heavily referenced (33 / 26 / many hits). Kept.
- `office_user.*` — the table's only real readers are the **dead gsheet channels** (`backend/api/routers/gsheet.py`, `gsheet_monitoring_api.py`) removed by CL-02. Per AUDIT §1a the table itself is a KEEP; column pruning is out of scope for CL-01 and deferred with the table.
- All reference/lookup tables (`grievance_classification_taxonomy` — 14 cols read+written by `ticketing/services/grievance_categories_catalog.py`; `status_update_timeline`, `projects`, `office_*`, `reference_*`) — every column used by explicit queries.

## 4. Table ADDED to the baseline (was app-startup DDL only)

- **`seah_service_providers`** — the former `pub009` table, also created lazily by `postgres_services._ensure_seah_service_providers_table`. It **is** used (`find_seah_service_providers`, `SELECT *`), so it is a KEEP table folded into the baseline; the app-startup `CREATE TABLE` is removed.

## 5. Net result

- 33 live tables − 7 dead − `events` − `alembic_version_public` = **24 kept**, **+ `seah_service_providers`** = **25 tables** created by the baseline.
- **0 columns pruned** inside kept tables (all justified above).
- `grievance_statuses` seeded with the live **UPPERCASE** vocab (SUBMITTED … CLOSED) + `archived`, replacing the retired lowercase `pub000` seed.

Acceptance (fresh DB → public/ticketing/ops migrate → seed → pytest → app smoke)
is recorded in `PROGRESS.md`; a pruned column that broke a test/smoke would be
restored and this audit corrected — none did.
