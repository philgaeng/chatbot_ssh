# Claude Handoff — Phase 2 Public Canonical Implementation

## Scope

Implement `docs/Refactor specs/May5_seah/08_phase2_query_and_submit_amendments.md` in the backend worktree.

Target files:

- `backend/actions/action_submit_grievance.py`
- `backend/services/database_services/complainant_manager.py`
- `backend/services/database_services/grievance_manager.py`
- `backend/services/database_services/postgres_services.py`

## Non-negotiable outcomes

1. Canonical tables only for new writes:
   - `grievances`
   - `complainants`
   - `grievance_parties`
   - `grievance_vault_payloads`
2. No new writes to `grievances_seah` / `complainants_seah`.
3. SEAH confirmation uses canonical `grievance_id`.
4. Exactly one `is_primary_reporter = true` party row per grievance.
5. Anonymous SEAH allowed (`grievance_parties.complainant_id` may be null).

## Ordered implementation plan

### 1) `postgres_services.py` (do this first)

#### A. Replace `submit_seah_to_db(data)` internals

- Stop calling `_ensure_seah_tables()`.
- Generate/require canonical `grievance_id`.
- Upsert complainant to `complainants` only when identity/contact exists.
- Create/update grievance in `grievances` with:
  - `case_sensitivity = 'seah'`
  - no raw duplication strategy (narrative goes to vault)
- Insert one primary reporter row in `grievance_parties`:
  - map roles:
    - `victim_survivor` -> `victim_survivor`
    - `not_victim_survivor` -> `relative_or_representative`
    - `focal_point` -> `seah_focal_point`
    - fallback -> `victim_survivor`
  - `is_primary_reporter = true`
  - `complainant_id = null` when anonymous and no identity captured
- Insert original narrative payload into `grievance_vault_payloads` (`payload_type='original_grievance'`).
- Return contract:
  - `{ "ok": true, "grievance_id": <canonical_id>, "complainant_id": ... }`
- Remove legacy keys in return (`seah_case_id`, `seah_public_ref`).

#### B. Retire legacy helpers

- Delete or no-op `_ensure_seah_tables()` usage in submit path.
- Do not create/alter legacy SEAH tables at runtime.

### 2) `action_submit_grievance.py`

#### A. `ActionSubmitSeah.execute_action(...)`

- Keep slot collection and shared data gathering.
- Expect canonical response from `submit_seah_to_db`.
- Confirmation message should reference canonical `grievance_id` only.
- Replace slot sets:
  - keep `SlotSet("grievance_status", SUBMITTED)`
  - set `SlotSet("grievance_id", result["grievance_id"])`
  - remove `seah_public_ref` dependency.

#### B. Keep standard submit path unchanged unless needed

- `ActionSubmitGrievance` continues via canonical `submit_grievance_to_db`.

### 3) `complainant_manager.py`

#### A. Update linkage queries to `grievance_parties`

- `get_complainant_from_grievance_id`:
  - resolve primary reporter from `grievance_parties` then join `complainants`.
- `get_complainant_id_from_grievance_id`:
  - read from `grievance_parties` where `is_primary_reporter=true`.
  - return null-safe for anonymous.

#### B. Merge behavior

- `merge_complainants_with_same_phone_number`:
  - update `grievance_parties.complainant_id` instead of `grievances.complainant_id`.
  - preserve role rows and primary reporter flags.

### 4) `grievance_manager.py`

#### A. Add canonical fields to allowed updates

- Include:
  - `case_sensitivity`
  - `vault_payload_ref`
  - `vault_last_updated_at`

#### B. Update queries that assume direct grievance->complainant linkage

- `get_grievance_by_id`:
  - join through `grievance_parties` (`is_primary_reporter=true`).
- `get_grievance_by_complainant_phone`:
  - `complainants -> grievance_parties -> grievances`.
- Null-safe behavior for anonymous grievance parties.

## Minimal SQL templates (for manager methods)

### Primary reporter lookup

```sql
SELECT gp.complainant_id
FROM grievance_parties gp
WHERE gp.grievance_id = %s
  AND gp.is_primary_reporter = TRUE
LIMIT 1;
```

### Complainant join via party link

```sql
SELECT c.*
FROM grievance_parties gp
JOIN complainants c ON c.complainant_id = gp.complainant_id
WHERE gp.grievance_id = %s
  AND gp.is_primary_reporter = TRUE
LIMIT 1;
```

## Test checklist (must pass)

1. Standard submit writes canonical grievance + complainant + default primary party.
2. SEAH submit writes canonical grievance (`case_sensitivity='seah'`) and primary party.
3. Anonymous SEAH submit succeeds with `grievance_parties.complainant_id IS NULL`.
4. No inserts occur in `grievances_seah` / `complainants_seah`.
5. `grievance_vault_payloads` row exists for original narrative.
6. Confirmation message exposes canonical `grievance_id`.
7. Status check flows still resolve complainant/grievance via updated joins.

## Suggested commit split

1. `fix(db): canonicalize seah submit to grievances + grievance_parties + vault`
2. `fix(actions): switch seah submit response and confirmation to grievance_id`
3. `fix(db-queries): route complainant and grievance lookups through grievance_parties`
4. `test: add phase2 canonical submit and anonymous seah coverage`
