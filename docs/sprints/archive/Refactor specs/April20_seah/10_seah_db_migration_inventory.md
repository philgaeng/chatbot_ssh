# 10 - SEAH DB Migration Inventory and Rollout Order

## Objective

List all database migrations/DDL changes needed for the SEAH flow, with clear status and rollout order for the current phase:

- **Now:** `table_manager` + Python migration script (pre-ticketing merge).
- **Later:** consolidate to one Alembic history after ticketing merge.

This spec is a child of:

- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Related specs:

- `docs/Refactor specs/April20_seah/03_seah_submission_and_storage.md`
- `docs/Refactor specs/April20_seah/08_seah_outro_and_project_catalog.md`
- `docs/features_to_add/projects_catalog_admin_layers_and_settings.md`

Follow:

- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Current status snapshot

| Item | Status | Current owner |
|------|--------|---------------|
| `complainants_seah` | Implemented | Runtime DDL in `postgres_services.py` (`_ensure_seah_tables`) |
| `grievances_seah` | Implemented | Runtime DDL in `postgres_services.py` (`_ensure_seah_tables`) |
| `seah_contact_points` | Implemented (base seed only) | Runtime DDL in `postgres_services.py` (`_ensure_seah_contact_points_table`) |
| `projects` (catalog) | **Not implemented yet** | Planned migration work |

Note: implemented tables are created lazily (`CREATE TABLE IF NOT EXISTS`) at runtime today.

---

## Migration inventory (SEAH route)

## A. Already implemented (keep track for cutover)

1. `complainants_seah`
   - Purpose: store complainant profile for SEAH records.
   - Used by: `submit_seah_to_db`.

2. `grievances_seah`
   - Purpose: store SEAH case row plus `seah_payload` JSON.
   - Used by: `submit_seah_to_db`.

3. `seah_contact_points`
   - Purpose: referral/contact center lookup for `action_seah_outro`.
   - Seed present: `default-national-seah`.

## B. Required next (this phase)

4. `projects` table (new)
   - Required by: project picker contract in `08`.
   - Expected core fields:
     - `project_uuid` (PK)
     - `country` or `country_code`
     - `administrative_layer_level_1`
     - `administrative_layer_level_2`
     - optional `administrative_layer_level_3`
     - `name_en`, `name_local`
     - short denomination/code (for reporting)
     - `adb` (bool)
     - `inactive_at` (nullable)
     - timestamps

5. `projects` seed rows (new)
   - Minimum seed includes business-required rows (for example KL ROAD in Koshi/Jhapa).
   - Data rule: admin layer values must match cleaned location dataset naming.

6. `seah_contact_points` content seed expansion (new)
   - Add realistic mock rows for target district/municipalities (for testing and demos).
   - Keep `default-national-seah` fallback row.

## C. Optional / future migrations

7. `government_agency` + project M2M (if enabled in v1 scope from `08`).
8. Rename legacy geography columns in `seah_contact_points` to admin-layer naming (only if consistency refactor is approved).
9. Add indexes tuned to query patterns:
   - `projects(administrative_layer_level_1, administrative_layer_level_2, inactive_at)`
   - `seah_contact_points(province, district, municipality, project_uuid, is_active)` or equivalent renamed columns.

---

## Rollout order (current phase: no Alembic yet)

1. Create one idempotent Python migration script for this phase:
   - create `projects` if missing,
   - apply/verify required columns and indexes,
   - seed required project rows,
   - seed/upsync `seah_contact_points` rows.
2. Run script in local, stage, prod in that order.
3. Validate:
   - `action_submit_seah` still succeeds,
   - `action_seah_outro` resolves a contact point for test locations,
   - DB rows include `project_uuid` where set.
4. Keep runtime `_ensure_*` in place for now to avoid breakage during transition.

---

## Alembic cutover plan (post ticketing merge)

1. Create consolidated Alembic baseline reflecting live schema at cutover date.
2. Stamp environments or create safe `IF NOT EXISTS` revisions so already-migrated DBs remain compatible.
3. From cutover onward: new schema changes only through Alembic.
4. Remove or reduce runtime DDL (`_ensure_seah_tables`, `_ensure_seah_contact_points_table`) once migration ownership is stable.

---

## Acceptance checklist

- [ ] `projects` table exists in all target environments.
- [ ] Required project seed rows exist and are queryable.
- [ ] `seah_contact_points` contains district/municipality mock rows plus national fallback.
- [ ] SEAH submit + outro path works with DB data after migration.
- [ ] Cutover note to single Alembic ownership is documented in release notes.
