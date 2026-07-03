# 08 - Phase 2 query and submit amendments (canonical public model)

## Objective

List every query and submit-path function that must be amended for phase 2 after choosing:

- single canonical grievance table (`grievances`)
- single canonical complainant table (`complainants`)
- per-case role table (`grievance_parties`)
- vault as source of truth for original narrative (`grievance_vault_payloads`)
- legacy SEAH tables dropped (`grievances_seah`, `complainants_seah`)

Scope for this checklist is intentionally limited to:

- `backend/actions/action_submit_grievance.py`
- `backend/services/database_services/complainant_manager.py`
- `backend/services/database_services/grievance_manager.py`
- `backend/services/database_services/postgres_services.py`

---

## Global implementation rules for all files

1. Stop all reads/writes to `grievances_seah` and `complainants_seah`.
2. For SEAH submit path, write to canonical `grievances` + `complainants` + `grievance_parties`.
3. Store original narrative in `grievance_vault_payloads`; do not persist raw narrative in secondary snapshots.
4. Use `grievance_id` as canonical internal identifier.
5. `seah_public_ref` no longer used as public id (decision Q2: replace with canonical id).

---

## A) `backend/actions/action_submit_grievance.py`

### 1) `BaseActionSubmit.collect_grievance_data(...)`

- [ ] Ensure payload always includes `case_sensitivity`:
  - standard flow -> `standard`
  - SEAH flow -> `seah`
- [ ] Ensure payload includes role-link inputs needed by `grievance_parties` creation:
  - `seah_victim_survivor_role`
  - `seah_anonymous_route`
  - `seah_contact_consent_channel`
  - `complainant_consent`
- [ ] Ensure no required submit fields depend on legacy SEAH table schema.

### 2) `ActionSubmitSeah.execute_action(...)`

- [ ] Keep action name (`action_submit_seah`) but switch DB write target to canonical submit function.
- [ ] Replace returned reference semantics:
  - use canonical `grievance_id` in user-facing confirmation (decision Q2).
  - remove/stop slot dependency on `seah_public_ref`.
- [ ] Keep role slot collection, but treat it as party-role input, not separate table payload.
- [ ] Ensure final submit path no longer depends on `submit_seah_to_db` behavior that assumes legacy tables.

### 3) Confirmation text and slot setting

- [ ] Update success message to reference canonical grievance id for SEAH.
- [ ] Remove `SlotSet("seah_public_ref", ...)` dependency after caller paths are updated.
- [ ] Keep `SlotSet("grievance_status", SUBMITTED)` unchanged.

---

## B) `backend/services/database_services/complainant_manager.py`

### 1) `get_complainant_from_grievance_id(grievance_id)`

Current behavior:

- joins `grievances` -> `complainants` by `g.complainant_id`

Required amendment:

- [ ] Prefer primary reporter lookup via `grievance_parties`:
  - `grievance_parties.grievance_id = %s`
  - `is_primary_reporter = TRUE`
  - join to `complainants` on `complainant_id`
- [ ] Handle anonymous SEAH case (`complainant_id IS NULL`) gracefully.

### 2) `get_complainant_id_from_grievance_id(grievance_id)`

Current behavior:

- `SELECT complainant_id FROM grievances`

Required amendment:

- [ ] Source from `grievance_parties` primary reporter rule instead of grievance row.
- [ ] Return `None` for anonymous primary party.

### 3) `merge_complainants_with_same_phone_number(...)`

Current behavior:

- updates `grievances.complainant_id`

Required amendment:

- [ ] Update `grievance_parties.complainant_id` rows instead of direct grievance column replacement.
- [ ] Preserve `is_primary_reporter` and role semantics.

### 4) `check_and_merge_complainants_by_phone_number(...)`

- [ ] Ensure internal merge helper call references existing function names consistently.
- [ ] Verify merge result semantics remain valid after moving linkage updates to `grievance_parties`.

### 5) Create/update complainant whitelist methods

- [ ] Confirm no legacy-only fields are required by submit path.
- [ ] Keep canonical contact/location fields (`contact_id`, `country_code`, `location_code`, `level_*`) supported.

---

## C) `backend/services/database_services/grievance_manager.py`

### 1) `ALLOWED_UPDATE_FIELDS` (module-level)

- [ ] Add/retain canonical phase-2 grievance fields:
  - `case_sensitivity`
  - `vault_payload_ref`
  - `vault_last_updated_at`
- [ ] Remove references that imply legacy SEAH table-only semantics.

### 2) `create_grievance(...)`

- [ ] Ensure canonical grievance create path supports `case_sensitivity`.
- [ ] Ensure raw narrative handling aligns with vault-only rule:
  - either do not write `grievance_description` for SEAH
  - or write safe/empty value and rely on vault payload.

### 3) `update_grievance(...)` and `update_grievance_with_tracking(...)`

- [ ] Update expected/allowed update fields to include canonical sensitivity/vault linkage fields.
- [ ] Ensure updates do not reintroduce raw narrative duplication for SEAH cases.

### 4) `get_grievance_by_id(...)`

Current behavior:

- left joins `grievances` to `complainants` by `g.complainant_id`

Required amendment:

- [ ] Resolve complainant linkage via `grievance_parties` primary reporter.
- [ ] Expose party-role context (at minimum primary role) for policy and UI decisions.
- [ ] Ensure anonymous case support where no complainant row is linked.

### 5) `get_grievance_by_complainant_phone(...)`

Current behavior:

- joins `complainants` to `grievances` by `complainant_id`

Required amendment:

- [ ] Join through `grievance_parties`:
  - `complainants` -> `grievance_parties` -> `grievances`
- [ ] Filter/report primary reporter consistently.
- [ ] Ensure SEAH records remain queryable when role is not victim.

### 6) `is_valid_grievance_id(...)` and `get_grievance_id_by_last_6_characters(...)`

- [ ] Keep canonical `grievance_id` checks only.
- [ ] Remove any legacy dependence on separate SEAH IDs in caller paths.

### 7) Office email lookup helper (`get_office_emails_for_grievance`)

- [ ] Verify municipality source remains valid after party-link refactor.
- [ ] If complainant link becomes nullable for anonymous cases, add null-safe fallback behavior.

---

## D) `backend/services/database_services/postgres_services.py`

### 1) `submit_seah_to_db(data)`

Current behavior:

- creates/updates legacy SEAH tables + stores full `seah_payload`

Required amendment (highest priority):

- [ ] Replace with canonical submit flow:
  1. create/update `complainants` (if identity provided)
  2. create/update `grievances` with `case_sensitivity='seah'`
  3. insert required `grievance_parties` rows:
     - exactly one primary reporter
     - role mapping from chatbot slots
     - allow `complainant_id = NULL` for anonymous route
  4. write original narrative to `grievance_vault_payloads`
  5. do not write `seah_payload` full snapshot
- [ ] Return canonical `grievance_id` as the only external reference.

### 2) Remove legacy helpers and DDL bootstraps

- [ ] Remove/retire `_ensure_seah_tables`.
- [ ] Remove table references to:
  - `complainants_seah`
  - `grievances_seah`
- [ ] Keep `seah_contact_points` only if still explicitly required by product flow; otherwise move to canonical settings/reference model.

### 3) `seah_reporter_category_from_victim_survivor_role(...)`

- [ ] Replace/extend mapping target to canonical `party_role` enum used by `grievance_parties`.

### 4) `submit_grievance_to_db(data)`

- [ ] Ensure standard and SEAH submissions both flow through canonical tables.
- [ ] Ensure creation logging still occurs once per submitted grievance id.

### 5) `update_grievance(...)` and related wrappers

- [ ] Ensure linkage updates use `grievance_parties` where applicable.
- [ ] Ensure no code path assumes `grievances.complainant_id` is always populated.

---

## E) Query inventory requiring explicit review/update

The following SQL statements/targets must be reviewed and amended:

### `complainant_manager.py`

- [ ] `SELECT ... FROM complainants WHERE complainant_phone_hash = %s`
- [ ] `SELECT ... FROM complainants WHERE complainant_id = %s`
- [ ] `SELECT c.* FROM complainants c JOIN grievances g ...`
- [ ] `SELECT complainant_id FROM grievances WHERE grievance_id = %s`
- [ ] `UPDATE grievances SET complainant_id = %s WHERE complainant_id = %s`

### `grievance_manager.py`

- [ ] `SELECT g.*, c.* FROM grievances g LEFT JOIN complainants c ON ...`
- [ ] `UPDATE grievances SET ... WHERE grievance_id = %s`
- [ ] `WITH latest_status ... FROM grievance_status_history ...`
- [ ] `SELECT ... FROM complainants c INNER JOIN grievances g ... WHERE c.complainant_phone_hash = %s`
- [ ] `SELECT complainant_municipality FROM grievances g JOIN complainants c ...`

### `postgres_services.py`

- [ ] Any `CREATE TABLE IF NOT EXISTS complainants_seah ...`
- [ ] Any `CREATE TABLE IF NOT EXISTS grievances_seah ...`
- [ ] Any `INSERT INTO complainants_seah ...`
- [ ] Any `INSERT INTO grievances_seah ...`
- [ ] Any `ALTER TABLE complainants_seah ...`

### `action_submit_grievance.py`

- [ ] `result = self.db_manager.submit_seah_to_db(grievance_data)` call target and response contract
- [ ] SEAH success message that currently references `seah_public_ref`
- [ ] Slot sets for `seah_case_id` / `seah_public_ref`

---

## F) Submit-path acceptance checks (must pass)

1. [ ] `action_submit_grievance` writes canonical grievance + canonical complainant only.
2. [ ] `action_submit_seah` writes canonical grievance + canonical complainant/nullable anonymous + `grievance_parties`.
3. [ ] Exactly one primary reporter row exists per grievance.
4. [ ] No new writes hit legacy SEAH tables.
5. [ ] Original narrative for SEAH is persisted via `grievance_vault_payloads`.
6. [ ] Returned user reference for SEAH is canonical `grievance_id`.

---

## G) Execution order for implementation PR

1. Amend `postgres_services.py` submit functions first (canonical write path).
2. Amend `action_submit_grievance.py` to use new response/ID semantics.
3. Amend `complainant_manager.py` linkage queries to `grievance_parties`.
4. Amend `grievance_manager.py` joins/query surfaces to canonical + party-role model.
5. Run migration + submit-path regression tests (standard + SEAH + anonymous SEAH).
