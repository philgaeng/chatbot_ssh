# Submission mapping and fallback (action_submit_grievance / action_submit_seah)

## Scope

This spec defines **submit-time behavior** for location persistence in:

- `backend/actions/action_submit_grievance.py` (`ActionSubmitGrievance`)
- `backend/actions/action_submit_grievance.py` (`ActionSubmitSeah`)

It complements:

- `01_ticketing_geography_reference_model.md` (canonical geography tables)
- `02_public_contact_info_and_party_links.md` (contact schema with `level_1_name..level_6_name`)

## Required submission rule (LOCKED)

At submission time, processing order is:

1. **Collect free-text levels first** from slots into `level_1_name..level_6_name`.
2. Attempt canonical mapping to `ticketing.locations` for each level.
3. Persist successful mappings to `level_n_code`.
4. Persist `location_code` as deepest mapped code.
5. Persist `location_resolution_status`.

Submission **must not fail** solely because canonical mapping is partial or absent.

## Why this order

- User data is never dropped when geography datasets are incomplete.
- Canonical codes are captured when available for analytics/routing.
- Works across countries with uneven reference coverage.

## Contract for write payloads

### Contact payload (new `public.contact_info`)

Always include:

- `country_code`
- `level_1_name..level_6_name` (nullable, but write what was captured)
- `level_1_code..level_6_code` (nullable)
- `location_code` (nullable, deepest mapped)
- `location_resolution_status` (`mapped_full` / `mapped_partial` / `free_text_only`)

### Existing legacy payloads (during transition)

During dual-write, continue current legacy fields (`complainant_province`, `complainant_district`, `complainant_municipality`, `complainant_village`, `complainant_address`) while additionally writing normalized contact payload fields.

## Mapping outcomes

### A. Full mapping available

- All expected country levels map to codes.
- `location_resolution_status = mapped_full`

### B. Partial mapping (common)

- Example: country has only 2 canonical levels configured.
- Write available `level_1_code`, `level_2_code`; keep `level_3..6_code = NULL`.
- Keep all `level_n_name` text.
- `location_resolution_status = mapped_partial`

### C. No mapping

- All codes null, all names preserved.
- `location_code = NULL`
- `location_resolution_status = free_text_only`

## Nepal default behavior

- Province/district/municipality may map when datasets exist.
- Lower levels such as ward or village/tole remain free text in `level_4_name` / `level_5_name` when no canonical rows exist.
- Do not introduce dedicated `ward`/`village` columns in `contact_info`.

## Suggested implementation shape

Add a submit-time helper (service/repo function) used by both grievance and SEAH submit actions:

- Input: tracker slots + `country_code`
- Output:
  - normalized names (`level_n_name`)
  - mapped codes (`level_n_code`)
  - `location_code`
  - `location_resolution_status`

Actions should call this helper before database persistence and merge the result into DB payloads.

## `complainant_manager.py` query updates (required)

Current `ComplainantDbManager` CRUD is hardcoded around legacy columns (`complainant_province`, `complainant_district`, `complainant_municipality`, `complainant_ward`, `complainant_village`, `complainant_address`).
For the contact refactor, keep backward compatibility but extend query/write logic as follows:

1. **Keep legacy reads/writes during transition**
   - Do not remove legacy columns from `SELECT`/`INSERT`/`UPDATE` yet.
   - Existing flows (status check, modify contact, OTP follow-ups) depend on them.

2. **Add contact-link field support**
   - Include `contact_id` in:
     - `ALLOWED_UPDATE_FIELDS`
     - `create_complainant()` allowed fields
     - `update_complainant()` allowed fields
     - `get_complainant_by_id()` and `get_complainants_by_phone()` selects
     - `get_complainant_from_grievance_id()` output
   - `contact_id` is not encrypted/hashed; treat as opaque identifier.

3. **Add normalized location field support (if stored on complainants during dual-write)**
   - Add optional columns to create/update/select sets:
     - `country_code`
     - `location_code`
     - `level_1_name`..`level_6_name`
     - `level_1_code`..`level_6_code`
     - `location_resolution_status`
   - These are plain text metadata fields (not encrypted by current policy).

4. **Dual-write precedence rule**
   - Submit actions write normalized location payload first.
   - Legacy fields are still populated for compatibility.
   - Read paths prefer normalized fields when present; fallback to legacy.

5. **No encryption-surface regressions**
   - Keep current encrypted/hashed sets for PII (`phone`, `email`, `full_name`, `address`).
   - Do not add `level_n_name`/`level_n_code` to encrypted/hashes unless policy changes explicitly.

6. **Merge-by-phone utility**
   - `check_and_merge_complainants_by_phone_number()` and related methods remain valid.
   - Ensure any merge operation preserves `contact_id` linkage policy (target row keeps canonical `contact_id`; source rows archived or reconciled by migration strategy).

### Method checklist (implementation gate)

Use this checklist during implementation/PR review to avoid missing query paths in
`backend/services/database_services/complainant_manager.py`.

- [ ] `ALLOWED_UPDATE_FIELDS` includes `contact_id`, `country_code`, `location_code`, `level_1_name..level_6_name`, `level_1_code..level_6_code`, `location_resolution_status`.
- [ ] `get_complainants_by_phone()` `SELECT` includes `contact_id` and normalized location columns.
- [ ] `get_complainant_by_id()` `SELECT` includes `contact_id` and normalized location columns.
- [ ] `create_complainant()` allowed field whitelist includes `contact_id` and normalized location columns.
- [ ] `update_complainant()` allowed field whitelist includes `contact_id` and normalized location columns.
- [ ] `get_complainant_from_grievance_id()` returns `contact_id` and normalized location columns.
- [ ] `get_complainant_id_from_grievance_id()` unchanged (still returns `complainant_id` only).
- [ ] `merge_complainants_with_same_phone_number()` strategy defined for `contact_id` winner (documented deterministic rule).
- [ ] `check_and_merge_complainants_by_phone_number()` verified to preserve/propagate canonical `contact_id`.
- [ ] `get_all_complainant_full_names_query()` / `get_all_complainant_full_names()` unchanged unless name storage policy changes.

### Related callers checklist

To avoid silent gaps, also verify these caller paths after query changes:

- [ ] `backend/actions/forms/form_grievance.py` (`create_or_update_complainant` paths)
- [ ] `backend/actions/action_submit_grievance.py` (`submit_grievance_to_db` / `submit_seah_to_db` paths)
- [ ] `backend/actions/forms/form_modify_contact.py` (`update_complainant` field map)
- [ ] `backend/orchestrator/state_machine.py` add-missing-info OTP persistence (`update_complainant`)

### Additional DB-service query checklist (`backend/services/database_services`)

These query/service paths also touch complainant/contact/location fields and must be reviewed:

- [ ] `postgres_services.py`:
  - [ ] `create_complainant()` pass-through accepts new fields (`contact_id`, normalized location keys) without dropping them.
  - [ ] `create_or_update_complainant()` update-vs-create path preserves new fields.
  - [ ] `submit_grievance_to_db()` + `update_grievance()` carry normalized location/contact fields via `get_complainant_and_grievance_fields()`.
  - [ ] `submit_seah_to_db()` `complainant_payload` includes/derives new contact/location fields as decided by migration phase.
  - [ ] `_ensure_seah_tables()` DDL and migration docs stay consistent (no drift between runtime fallback DDL and Alembic).

- [ ] `base_manager.py`:
  - [ ] `get_complainant_and_grievance_fields()` still routes all complainant-related keys correctly (all `complainant_*` + any explicit non-prefixed keys like `contact_id`/`country_code` if introduced).
  - [ ] schema bootstrap (`_create_tables`) for `complainants` includes newly required columns in fallback environments.
  - [ ] indexes reviewed for new lookup patterns (e.g., `contact_id`, `location_code`, optional `level_n_code`), without over-indexing free text.

- [ ] `grievance_manager.py`:
  - [ ] `get_grievance_by_complainant_phone()` `SELECT` includes the fields needed by downstream consumers after migration (legacy + normalized as required).
  - [ ] decrypt pipeline still valid when non-encrypted normalized fields are added to result rows.

- [ ] `gsheet_query_manager.py`:
  - [ ] `get_grievances_for_gsheet()` `SELECT` and municipality filter strategy validated against dual-write period.
  - [ ] if reports should move to normalized location fields, add explicit transition rule (legacy municipality fallback).

- [ ] `mysql_services.py` (if still used by any environment):
  - [ ] export/upsert payload mapping reviewed so contact/location contract changes do not silently drop fields.

## Error handling

- Mapping lookup errors should log warning and degrade to `free_text_only`.
- DB write errors remain blocking as today.
- Mapping errors are **non-blocking** for submission.

## Telemetry / observability

Emit structured logs per submission:

- `country_code`
- `location_resolution_status`
- deepest mapped level number (or `0` for none)

This helps prioritize dataset improvements by country.

## Tests (minimum)

1. `mapped_full` path: all codes present.
2. `mapped_partial` path: top levels mapped, lower free text only.
3. `free_text_only` path: no codes mapped, submit succeeds.
4. Regression: submission still succeeds when resolver raises recoverable lookup error.
