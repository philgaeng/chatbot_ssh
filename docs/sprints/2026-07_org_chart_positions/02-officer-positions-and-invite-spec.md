# OC-03 — Officer positions + invite pre-fill + supervisor resolver

> Workstream: backend-positions (part 1) · Branch `orgchart/oc-03-04-positions` · Depends on OC-01 + OC-02 tables.
> Feature source: [`docs/ticketing_system/16_org_chart_and_positions.md`](../../ticketing_system/16_org_chart_and_positions.md) §3.3, §4, §9, §5 (resolver). Re-locate line numbers first.
> **This is the correctness-critical ticket:** it *generates* `user_roles` + `officer_scopes` — the enforcement truth — from descriptive positions. A wrong scope row here is a real access-control defect, not a cosmetic one.

---

## 1. Data model — `ticketing.officer_positions`

Migration (chained after OC-02) creates `ticketing.officer_positions` (doc 16 §3.3):

| Column | Notes |
|---|---|
| `officer_position_id` | UUID PK |
| `user_id` | Officer (string ref, matches existing user id convention) |
| `position_type_id` | FK → `position_types` |
| `organization_id` | FK → `organizations` — the unit where the position is held |
| `reports_to_user_id` | **Override**, nullable — deputation / acting |
| `is_active` | Boolean; transfers end the old row (`is_active=false`) and add a new one |
| `created_at` / `updated_at` | UTC tz-aware |

Multiple active positions per officer allowed (dual-hat — doc 16 §3.3). Model at `ticketing/models/officer_position.py`, `__table_args__ = {"schema": "ticketing"}`, safety-headed migration with real `downgrade()`.

## 2. Invite pre-fill — the integration seam

### Where it plugs in (verified)

Officer invite: `POST /users/invite` → `ticketing/api/routers/users.py:1249-1317`, which already calls `upsert_user_role_row` (`users.py:1289` → `services/officer_admin.py:145`, builds `UserRole` at :163) and `create_scope_row` (`users.py:1290` → `officer_admin.py:97`, builds `OfficerScope` at :103). **This is the only place that should mint enforcement rows** — the position flow *feeds* it, never bypasses it.

### Behavior (doc 16 §4 — default, overridable)

1. The invite request may carry a `position` selection: `{ organization_id, position_type_id }` (and optional `reports_to_user_id`).
2. When present, the server **pre-fills** from the matrix and tree — but the admin's explicit fields in the request always win:
   - role ← `position_type.default_role_key` (unless the request overrides `role_key`)
   - organization ← the position's `organization_id`
   - location scope ← the org unit's `territory_location_code` / `territory_includes_children` (unless the request overrides scope)
3. Saving then goes through the **existing** `upsert_user_role_row` + `create_scope_row` — same rows, same validation (`validate_jurisdiction` at `officer_admin.py:37` still runs). Additionally insert the `officer_positions` row.
4. **Editing a position type's `default_role_key` does not re-sync existing holders** (doc 16 §4). The API stores the new default; a "review holders" prompt is OC-05 UI. Transfers likewise prompt (UI), never silently re-scope.
5. **Override visibility**: when the saved `role_key` differs from the position type's current `default_role_key`, that's surfaced as an informational badge on the Manage modal (OC-05) — the backend just needs to expose both values on the officer-position read.

### Endpoints (doc 16 §9)

- `GET /api/v1/users/{id}/positions` — list an officer's positions (active + historical), with the matrix default vs actual role for the override badge.
- `POST /api/v1/users/{id}/positions` — add a position (also generates/refreshes role+scope through the existing helpers, honoring overrides).
- `DELETE /api/v1/users/{id}/positions/{opid}` — end a position (`is_active=false`); does **not** auto-delete the `user_roles`/`officer_scopes` (prompt to refresh is UI — a dangling role after a transfer is an admin decision, doc 16 §4).

## 3. Supervisor resolver

`GET /api/v1/users/{id}/supervisor` — resolution order (doc 16 §3.3, §5.5), first match wins:

1. `officer_positions.reports_to_user_id` **override** (if set and the target is active).
2. **Derived**: the active holder of `reports_to_position_key` at the same unit if `reports_to_locus = same_unit`, else at the `parent_organization_id` unit. If multiple holders, document the tie-break (lowest `created_at`) and log it.
3. **Fallback**: none at the person level — callers fall back to the workflow step's `supervisor_role` tier (this resolver returns `null` and the caller uses the role pool). Do **not** invent a supervisor.

Implement as a pure service function (`resolve_supervisor(user_id, position_context) -> user_id | None`) reused by OC-04's escalation-notify and visibility — one resolver, no duplication.

## Constraints

- **Never bypass `upsert_user_role_row` / `create_scope_row`.** The position flow pre-fills their inputs and adds an `officer_positions` row; it does not write `user_roles`/`officer_scopes` directly. This keeps `validate_jurisdiction` and the existing invariants in one place.
- Positions are additive to the enforcement model — `user_roles` + `officer_scopes` remain the truth (doc 16 §2). No query anywhere should read `officer_positions` to make an **access-control** decision (only display, routing preference, and the notify/visibility features in OC-04).
- No change to Keycloak user creation (`officer_admin.py:604`) or the invite email flow.
- Migration: ticketing stream only, chained after OC-02.

## Tests (acceptance)

`tests/ticketing/test_officer_positions.py`:
- [ ] Invite with a position selection generates the expected `user_roles` (role = matrix default) + `officer_scopes` (org + territory scope) **through the existing helpers** (assert the helpers were the writer — no direct inserts).
- [ ] Explicit `role_key`/scope override in the request beats the matrix default; the resulting `officer_positions` row records the position, and the read exposes default-vs-actual for the badge.
- [ ] Dual-hat: two active positions for one officer produce two scope sets; both enforce.
- [ ] `default_role_key` edit does not mutate existing holders' `user_roles` (re-assert from OC-02, now with a real holder).
- [ ] Transfer: ending a position sets `is_active=false`, adds the new one; **existing `user_roles`/`officer_scopes` are untouched until an explicit refresh** (assert no silent re-scope).
- [ ] Supervisor resolver: override wins; derived (same_unit + parent_unit) resolves the right holder; no holder → `null` (caller falls back to `supervisor_role`); tie-break deterministic.
- [ ] **Authz matrix**: `POST/DELETE /users/{id}/positions` — `project_admin` ✅ within own scope only, `org_admin` ✅, `super_admin` ✅, cross-scope `project_admin` ❌, operational roles ❌, unauthenticated ❌.
- [ ] `validate_jurisdiction` still rejects an out-of-jurisdiction position assignment (the guard wasn't bypassed).

## Manual verification
- [ ] On the seeded DB: invite an officer by picking Division Office → "SDE"; confirm the created role/scope match the matrix and the officer can act on the right tickets. Override the role on a second invite; confirm the badge data is exposed.
- [ ] Resolver: set an override, hit `GET /users/{id}/supervisor`, confirm the override person; clear it, confirm the derived holder.

## Done means
OC-03 checklist ticked in [`PROGRESS.md`](PROGRESS.md); test file + authz matrix green in the full ticketing suite; migration round-trip verified; the resolver is the single shared function OC-04 imports.
