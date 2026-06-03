# May5 SEAH refactor — agent instructions

## Recommended agent count

Use **6 implementation agents + 1 coordinator/reviewer** (7 total participants).

- 6 keeps DB/migration streams separate while adding one dedicated ask-flow UX agent.
- More than 6 implementation agents usually creates merge overhead and conflicting assumptions.

## Mandatory read order (all agents)

1. `docs/Refactor specs/May5_seah/00_overview_and_scope.md`
2. `docs/Refactor specs/May5_seah/01_ticketing_geography_reference_model.md`
3. `docs/Refactor specs/May5_seah/02_public_contact_info_and_party_links.md`
4. `docs/Refactor specs/May5_seah/03_submission_mapping_and_fallback.md`
5. `docs/Refactor specs/May5_seah/04_action_ask_commons_flow_profiles.md`
6. `docs/MIGRATIONS_POLICY.md`
7. `CLAUDE.md` (database architecture + migration traceability sections)
8. `docs/OPERATIONS.md` (runbook expectations)
9. `docs/SETUP.md` (local execution assumptions)

## Global constraints (LOCKED)

- Never mix migration streams:
  - `ticketing.*` -> `ticketing/migrations/alembic.ini`
  - `public.*` -> `migrations/public/alembic.ini`
- No secret changes in repo (`env.local`, credentials, keys).
- Keep backward compatibility during dual-write period.
- Do not remove legacy columns/queries unless explicitly authorized in a later phase.

## Execution order dependency (IMPORTANT)

Because ticketing geography is being finalized on a separate ticketing branch/worktree:

1. Merge ticketing geography work into **integration** first.
2. Sync this branch/worktree from integration (merge or rebase).
3. Only then run agents B/C/D/E against the mirrored ticketing contract.
4. Agent F can run in parallel (it is ask-layer logic, not ticketing-schema coupled).

If step 1 is not complete, agents B/C/D/E should run only in analysis/spec mode (no schema-coupled code changes).

## Agent split

## Agent A — Integration sync and contract verification

**Scope**
- Pull/merge/rebase latest integration changes that contain ticketing geography.
- Verify this worktree mirrors the finalized ticketing schema contract:
  - `ticketing.countries`
  - `ticketing.location_level_defs`
  - `ticketing.locations`
  - `ticketing.location_translations`
- Produce a short compatibility note for agents B/C/D (what is available now).

**Files likely touched**
- Mostly none (or minimal conflict-resolution edits only).
- Optional: docs notes in `docs/Refactor specs/May5_seah/*` if integration contract changed.

**Done criteria**
- Branch/worktree confirmed aligned with integration ticketing schema.
- Single ticketing Alembic head after sync.
- B/C/D agents can proceed without guessing ticketing table shape.

## Agent B — Public contact schema and links

**Scope**
- `public.contact_info` (with `level_1_name..level_6_name`, optional codes, resolution status)
- `resource_persons` (minimal roster table)
- Add `contact_id` + normalized location fields to `complainants` / `complainants_seah` according to phase plan.

**Files likely touched**
- `migrations/public/versions/*`
- `backend/services/database_services/base_manager.py` (fallback table bootstrap only if still required)
- `backend/services/database_services/postgres_services.py` (fallback DDL parity notes)

**Done criteria**
- Single public Alembic head.
- Existing DBs can upgrade without data loss.
- No ticketing schema changes in public migration files.
- Started only after Agent A marks ticketing contract aligned.

## Agent C — Submission & mapping pipeline

**Scope**
- Implement map-first/fallback behavior in submit path:
  - `action_submit_grievance`
  - `action_submit_seah`
- Add shared resolver helper for:
  - `level_n_name`
  - `level_n_code`
  - `location_code`
  - `location_resolution_status`

**Files likely touched**
- `backend/actions/action_submit_grievance.py`
- helper/service module under `backend/services/*` or `backend/shared_functions/*`

**Done criteria**
- Submission never fails due to unmapped location.
- All mapping outcomes covered (`mapped_full`, `mapped_partial`, `free_text_only`).
- Structured logs emitted with resolution status.
- Started only after Agent A marks ticketing contract aligned.

## Agent D — Query compatibility and read paths

**Scope**
- Apply checklist from `03_submission_mapping_and_fallback.md`:
  - `complainant_manager.py`
  - `postgres_services.py`
  - `grievance_manager.py`
  - `gsheet_query_manager.py`
  - `mysql_services.py` (if active)
- Ensure dual-write read precedence (normalized first, legacy fallback where specified).

**Done criteria**
- No silent field drops in create/update/select.
- Existing status-check/report paths still function.
- Merge-by-phone path has explicit `contact_id` winner rule.
- Started only after Agent A marks ticketing contract aligned.

## Agent E — Tests, migration verification, deployment runbook

**Scope**
- Add/update tests for mapping outcomes and DB compatibility.
- Validate both migration streams end-to-end.
- Update operational docs/checklists for upgrade order.

**Files likely touched**
- `tests/**`
- `docs/MIGRATIONS_POLICY.md` (if test commands need clarification)
- `docs/OPERATIONS.md` (migration runbook snippets)

**Done criteria**
- Test coverage includes submission mapping fallbacks.
- Documented command sequence for host and docker environments.
- Explicit rollback notes per stream.
- Runs after B/C/D implementation passes local checks.

## Agent F — `action_ask_commons` flow-profile implementation (Spec 04)

**Scope**
- Implement `docs/Refactor specs/May5_seah/04_action_ask_commons_flow_profiles.md` in one go.
- Add profile-aware ask behavior for:
  - `grievance`
  - `seah-victim`
  - `seah-other`
  - `seah-focal`
- Use derived profile helper strategy (no new `ask_contact_profile` slot in this tranche).
- Respect resolved decisions in spec 04 (e.g., `seah-other` wording, focal email only for affected person stage).

**Files likely touched**
- `backend/actions/action_ask_commons.py`
- `backend/actions/utils/utterance_mapping_rasa.py`
- possibly `tests/*` related to ask actions/mappings

**Done criteria**
- In-scope ask actions in spec 04 are profile-aware with fallback to generic behavior.
- No validation duplication added in ask layer.
- Existing payload/button contracts remain compatible unless explicitly changed by spec.
- Tests cover profile behavior and fallback path.

## Coordinator / Reviewer (human or dedicated agent)

**Responsibilities**
- Own integration branch.
- Sequence merges: Agent A (sync/verify) first; Agent F can merge independently if green; then B, then C + D, then E.
- Resolve cross-agent conflicts on schema contracts.
- Enforce “single head per stream” before merge.
- Final smoke run:
  - `make migrate_ticketing`
  - `make migrate_public`
  - relevant service startup + basic submit scenarios.

## Handoff artifacts required from each agent

- Files changed.
- Migration revisions created (IDs + stream).
- Test commands executed + outputs summarized.
- Risks / TODOs / assumptions.
- Backward-compat notes (what still depends on legacy fields).
