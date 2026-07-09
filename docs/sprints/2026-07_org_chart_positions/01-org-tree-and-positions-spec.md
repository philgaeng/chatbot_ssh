# OC-01 / OC-02 — Org tree + position types & matrix

> Workstream: backend-org-tree · Branch `orgchart/oc-01-02-tree` · Additive (no behavior change to existing orgs).
> Feature source: [`docs/ticketing_system/16_org_chart_and_positions.md`](../../ticketing_system/16_org_chart_and_positions.md) §3.1, §3.2, §9. Re-locate all line numbers with grep before editing.
> **Migration coordination:** both tickets add a ticketing revision. Chain them in order (OC-01 then OC-02) on the live `alembic heads`, *after* hardening HR-03 if it has landed. See sprint README § Parallel-safety.

---

## 1. OC-01 — Org tree on `ticketing.organizations`

### Current state (verified)

`Organization` model at `ticketing/models/organization.py:20-44` (table `ticketing.organizations`), columns today: `organization_id` (String(64) PK), `name`, `country_code` (nullable FK→`ticketing.countries`), `is_active`, `default_language`, `created_at`, `updated_at`. Existing flat orgs must keep working — they simply become tree roots.

Router lives in `ticketing/api/routers/locations.py` (there is **no** `organizations.py`): `GET /organizations` (:252-264), `POST` (:267-304), `PATCH /organizations/{id}` (:307-330), `DELETE` (:333-364, already guards ticket + user_role references). M2M link models to keep tree-aware: `ProjectOrganization` (`models/project.py:120-144`), `PackageOrganization` (`models/package.py:72-91`).

### Change

1. **Migration** (ticketing stream, safety header, real `downgrade()`) adds to `ticketing.organizations`:
   - `parent_organization_id` — String(64), nullable, **self-FK** to `organizations.organization_id`. Existing rows stay NULL (roots).
   - `unit_type` — String, nullable→backfill `company`/`development_partner` for existing rows; allowed values `ministry | department | directorate | provincial_office | division_office | company | development_partner` (enforce in the app layer / a CHECK, not a PG enum — keep it migratable).
   - `territory_location_code` — String, nullable, string ref into the location reference (no cross-schema FK; mirror the `officer_scopes.location_code` convention).
   - `territory_includes_children` — Boolean, default false (same semantics as `officer_scopes.includes_children`).
   - `display_name_ne` — Text, nullable. **Nepali is translator-gated** — the column ships now (doc 16 §10: "cheap now, painful later"); values come later via the review sheet. Add `display_name_ne` in the same migration to avoid a second one.
   - Index `parent_organization_id` for subtree walks.
2. **Model** (`organization.py`): add the columns + the self-referential relationship (`children`/`parent`). Keep `__table_args__ = {"schema": "ticketing"}`.
3. **Subtree helper** in a service (not the router): `descendant_org_ids(root_id) -> set[str]` via a recursive CTE (bounded depth guard against cycles — reject a `parent` that is a descendant on save). "Officer belongs to DoR" = membership in DoR's subtree.
4. **Router extension** (`locations.py`): `GET /organizations` returns the new fields and supports a `tree=true` shape (nested by parent) and a `?root_id=` subtree filter; `POST`/`PATCH` accept and validate the new fields (reject a parent that would create a cycle; validate `unit_type`; validate `territory_location_code` against the location reference). Keep the existing `require_admin` gate but tighten per §7 (org-tree edits are **`org_admin` standard-track / `super_admin`** — not `project_admin`). Reuse `admin_access` helpers; do not invent a new permission check.
5. **CSV import** `POST /organizations/import` (doc 16 §9): `org_admin` standard. Accepts a CSV of org units (columns: `organization_id?`, `name`, `name_ne?`, `unit_type`, `parent_organization_id?` or `parent_name?`, `territory_location_code?`, `territory_includes_children?`). Two-phase: validate the whole file (row-level errors returned as a list, nothing written on any error), then insert in a single transaction. Mirror the CSV pattern from `features/settings/settings_tab_projects_and_seah_contact_centers.md`. Idempotent on re-import by `organization_id` (upsert), safe on `parent_name` resolution order (topological or two-pass).

### Tests (acceptance)

`tests/ticketing/test_org_tree.py`:
- [ ] Migration round-trip: `upgrade` adds columns with correct nullability/defaults; existing rows get a sensible `unit_type` backfill and NULL parent; `downgrade` drops cleanly.
- [ ] Self-FK: create ministry → department → division; `descendant_org_ids(ministry)` returns all three; cycle attempt (`PATCH` a parent to its own descendant) → 400.
- [ ] Territory: `territory_location_code` persists; `territory_includes_children` defaults false.
- [ ] **Authz matrix**: org-tree `POST/PATCH/DELETE/import` — `super_admin` ✅, `org_admin` standard ✅, `org_admin` seah ❌, `project_admin` ❌, operational roles ❌, unauthenticated ❌.
- [ ] CSV import: valid file inserts a subtree; a file with one bad row writes **nothing** and returns the row error; re-import upserts (no duplicates).

### Manual verification
- [ ] `alembic upgrade head` → `downgrade -1` → `upgrade head` clean on seeded dev DB; existing seeded orgs still list and still resolve on tickets.

---

## 2. OC-02 — `position_types` + position→role matrix

### Design (doc 16 §2, §3.2, §4)

Positions are **descriptive**; roles remain the **enforcement truth**. A position type carries the title, the org levels it exists at, its reporting rule, and — the matrix — a `default_role_key` that pre-fills the role at invite time. ~20–50 rows expected; this is not an HRIS.

### Change

1. **Migration** (chained after OC-01) creates `ticketing.position_types`:
   - `position_type_id` UUID PK, `position_key` (slug, immutable after save — enforce in service), `display_name`, `display_name_ne` (translator-gated), `allowed_unit_types` (JSON list of org-unit levels), `reports_to_position_key` (nullable), `reports_to_locus` (`same_unit | parent_unit`), **`default_role_key`** (FK-by-key into `ticketing.roles` — string ref matching `Role` key convention, validated at write, no hard FK needed but validate existence), `visibility_mode` (`none | direct_reports | subtree`), `workflow_track` (`standard | seah | both`). Safety header, real `downgrade()`.
2. **Model** `ticketing/models/position_type.py` (`__table_args__ = {"schema": "ticketing"}`).
3. **Router** `/api/v1/position-types` — `GET` (list, filterable by `workflow_track`), `POST`, `PATCH`, `DELETE` (guard: block delete when any `officer_positions` row references the type — mirror the org DELETE guard at `locations.py:333-364`). Access: `org_admin` standard / `super_admin` per §7; SEAH-track type authoring is an **open question** (doc 16 §10) — for v1, only standard-track admins author types; a `workflow_track=seah` type is allowed but flag the "who authors SEAH types" decision in PROGRESS and default to standard-admin-owned.
4. **Matrix validation**: on save, `default_role_key` must resolve to an existing role in `grm_role_catalog`; `allowed_unit_types` values must be valid `unit_type`s; `reports_to_position_key` (if set) must reference an existing position_key. Editing `default_role_key` does **not** re-sync existing holders (doc 16 §4) — that's a UI "review holders" prompt handled in OC-05; the API just stores the new default.

### Tests (acceptance)

`tests/ticketing/test_position_types.py`:
- [ ] CRUD happy path; `position_key` immutable after create (PATCH attempt to change it → 400).
- [ ] Matrix validation: bad `default_role_key` → 400; bad `allowed_unit_types` value → 400; dangling `reports_to_position_key` → 400.
- [ ] Delete guard: type in use by an `officer_positions` row → 409/400, not deleted.
- [ ] **Authz matrix**: `POST/PATCH/DELETE` — `super_admin` ✅, `org_admin` standard ✅, `project_admin` ❌, `org_admin` seah ❌ (log the open question), operational roles ❌, unauthenticated ❌.
- [ ] Editing `default_role_key` does not mutate any existing `user_roles` (assert no side effect).

### Manual verification
- [ ] Seed ~5 position types matching real DoR titles (SDE, Divisional Engineer, PD, etc.) pointing at catalog role keys; confirm they list and filter by track.

---

## Constraints (both tickets)

- **Additive only.** No changes to `tickets`, `user_roles`, `officer_scopes`, or the assignment engine here — those are OC-03/OC-04. `tickets.organization_id` and `officer_scopes` FKs stay exactly as they are (doc 16 §3.1).
- Every new endpoint is gated at the **country tier** (§7) — reuse `ticketing/services/admin_access.py`; do not write a new ad-hoc permission check.
- Migrations touch `ticketing.*` only (three-stream rule, `docs/deployment/07_migrations_policy.md`). Coordinate the head with HR-03.
- `# INTEGRATION POINT:` any place OC-03 will plug into (invite pre-fill reads these tables).

## Done means

OC-01 + OC-02 checklists ticked in [`PROGRESS.md`](PROGRESS.md); both test files + authz matrices green in the full ticketing suite; migration round-trips verified on the seeded DB; seed data for position types committed.
