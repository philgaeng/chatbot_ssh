# Roles, permissions & admin matrix — implementation spec

**Sprint:** June5 (add-on)  
**Audience:** Ticketing UI + `ticketing/` API agent  
**Product spec (locked):** [`docs/ticketing_system/11_roles_and_permissions.md`](../../ticketing_system/11_roles_and_permissions.md)  
**Related:** [`10_settings_overview.md`](../../ticketing_system/10_settings_overview.md), [`12_workflows_configuration.md`](../../ticketing_system/12_workflows_configuration.md), [`14_platform_settings.md`](../../ticketing_system/14_platform_settings.md), [`07_officer_management_and_assignment.md`](../../ticketing_system/07_officer_management_and_assignment.md)

---

## Summary (locked product decisions)

| Topic | Decision |
|-------|----------|
| Admin role keys | **`super_admin`**, **`country_admin`**, **`project_admin`** only |
| Standard vs SEAH | **`workflow_track`** on **assignment scope** (`standard` \| `seah`), not separate admin role names |
| Deprecated | `local_admin`, `seah_admin`, `seah_project_admin` → migrate to scoped assignments |
| Operational roles | Seed TOR catalog + **`country_admin` can create custom** roles (archetype wizard) |
| Workflows vs roles | **Workflows-first** — bind roles on step editor; optional inline “+ Create role” |
| Party types | Stay in **Projects & packages** (`project_actor_roles`) — out of scope here |
| `project_admin` | Assigns officers; does **not** create operational role catalog |

---

## Tickets

Implement in order unless blocked.

| ID | Phase | Summary |
|----|-------|---------|
| **RP-01** | Data model | `admin_scopes` (or scoped extension), `role_kind`, `role_origin`, Alembic + models |
| **RP-02** | Auth core | `CurrentUser` admin context, replace `local_admin`/`is_admin` with matrix checks |
| **RP-03** | Roles API | `GET /roles?kind=`, `POST /roles`, archetypes, usage counts, delete guards |
| **RP-04** | Admin API | Appoint `country_admin` / `project_admin`; platform Admin access endpoints |
| **RP-05** | Route guards | Settings/workflows/projects/users routers enforce tier + `workflow_track` |
| **RP-06** | Settings UI — access | Tab visibility matrix; platform tab `super_admin` only; deprecate broad `local_admin` UX |
| **RP-07** | Settings UI — roles | Operational Roles tab only; create wizard; usage columns; track filter |
| **RP-08** | Settings UI — workflows | Step role dropdown groups; inline create role; publish guard if step missing role |
| **RP-09** | Settings UI — admin access | New platform sub-tab: list/appoint scoped admins |
| **RP-10** | Seed & migration | Demo officers, `local_admin` → matrix; update `grm_role_catalog` |
| **RP-11** | Tests | API + permission service unit tests |

---

## RP-01 — Data model

### New table: `ticketing.admin_scopes`

Prefer a **dedicated table** over overloading `officer_scopes` (clearer queries, no collision with operational `role_key`).

```sql
admin_scope_id      VARCHAR(36) PK
user_id             VARCHAR(128) NOT NULL
role_key            VARCHAR(64) NOT NULL   -- country_admin | project_admin
country_code        VARCHAR(8)             -- required for country_admin
project_id          VARCHAR(64) NULL       -- required for project_admin
organization_id     VARCHAR(64) NULL
package_id          VARCHAR(64) NULL
workflow_track      VARCHAR(16) NOT NULL   -- 'standard' | 'seah'
created_at          TIMESTAMPTZ
created_by_user_id  VARCHAR(128) NULL
```

**Rules:**

- `country_admin` row: `country_code` + `workflow_track`; `project_id` NULL.
- `project_admin` row: `project_id` + `workflow_track`; optional `organization_id` / `package_id`.
- One user may have **multiple rows** (e.g. NP+standard and NP+seah country admin).
- Index: `(user_id)`, `(project_id)`, `(country_code, workflow_track)`.

### Extend `ticketing.roles`

| Column | Type | Notes |
|--------|------|-------|
| `role_kind` | `VARCHAR(16)` | `admin` \| `operational` — backfill from allowlist |
| `role_origin` | `VARCHAR(16)` | `system` \| `custom` — default `system` for seed |

Backfill `role_kind`:

- `admin`: `super_admin`, `country_admin`, `project_admin`
- `operational`: all others in catalog

Add `country_admin` and ensure `project_admin` in `grm_role_catalog.py` with correct permissions JSON.

### Migration header

```python
# Safe to run: only creates/modifies ticketing.* tables
```

Alembic: `ticketing/migrations/alembic.ini` only.

---

## RP-02 — Auth core

**Files:** `ticketing/api/dependencies.py`, new `ticketing/services/admin_access.py`

### `CurrentUser` extensions

Load from DB on each request (or cache in JWT claims post-Keycloak sync):

```python
admin_scopes: list[AdminScope]  # dataclass rows from admin_scopes table
```

Properties / helpers:

| Helper | Behaviour |
|--------|-----------|
| `is_super_admin` | `super_admin` in `role_keys` |
| `is_country_admin(track?)` | Has `admin_scopes` row `role_key=country_admin`; optional track filter |
| `is_project_admin(project_id?, track?)` | Has matching `project_admin` scope |
| `admin_workflow_tracks()` | Set of tracks user may administer |
| `can_access_platform_settings` | `is_super_admin` only |
| `can_manage_structure` | `super_admin` OR `country_admin` with `track=standard` |
| `can_manage_seah_settings` | `super_admin` OR `country_admin` with `track=seah` |
| `can_see_seah` | Extend: include `country_admin`/`project_admin` scopes with `track=seah` |

**Replace:**

- `is_admin` → do not use as blanket gate; use specific helpers per endpoint.
- Transitional: `is_admin` = `is_super_admin` OR any `admin_scopes` row (for minimal diff during migration).
- `can_view_archived` → `super_admin` OR any country/project admin scope.

### Dependencies

```python
def require_super_admin(current_user: CurrentUser) -> CurrentUser: ...
def require_country_admin(track: Literal["standard", "seah"] | None = None): ...
def require_project_admin(project_id: str | None = None, track: ...): ...
def require_settings_write(action: SettingsAction): ...  # maps to matrix in doc 11 §2
```

---

## RP-03 — Roles API

**Files:** `ticketing/api/routers/users.py`, `ticketing/constants/role_archetypes.py` (new), schemas

### `GET /api/v1/roles`

Query params:

- `kind=operational` | `admin` (default `operational` for Settings Roles tab)
- `workflow_track=standard` | `seah` (filter operational by `workflow_scope`)

Exclude admin keys from operational list.

### `POST /api/v1/roles`

Body: `display_name`, `role_key?`, `workflow_scope`, `jurisdiction_mode`, `archetype`, `permissions?`, `description?`

- Set `role_origin=custom`, `role_kind=operational`
- Validate `role_key` slug; unique
- Apply archetype template from `role_archetypes.py`
- Reject admin-only permissions on operational roles
- Access: `country_admin` (own track) or `super_admin`

### `PATCH /api/v1/roles/{id}`

- System roles: `display_name`/`description` by track-scoped country admin; **permissions** only `super_admin`
- Custom roles: full edit by track-scoped country admin

### `DELETE /api/v1/roles/{id}`

- Block if referenced by `workflow_steps.assigned_role_key` or `user_roles` / `officer_scopes`
- System roles: `super_admin` only
- Return usage counts in 409 body

### List enrichment

Each role: `steps_count`, `officers_count` (for UI warnings).

---

## RP-04 — Admin assignment API

**Files:** `ticketing/api/routers/users.py` or new `ticketing/api/routers/admin_access.py`

| Method | Path | Access |
|--------|------|--------|
| `GET` | `/api/v1/admin-scopes` | `super_admin` (all) or self |
| `POST` | `/api/v1/admin-scopes` | `super_admin` appoints `country_admin`; `country_admin` appoints `project_admin` (matching track) |
| `DELETE` | `/api/v1/admin-scopes/{id}` | Appointer or `super_admin` |

On appoint:

- Upsert `user_roles` row linking `role_id` for `country_admin` / `project_admin`
- Insert `admin_scopes` row with `workflow_track`
- Keycloak sync stub (auth stack) — follow existing `officer_admin.py` patterns

---

## RP-05 — Route guards (matrix enforcement)

Apply `admin_access.py` to mutating routes:

| Router | Standard country admin | SEAH country admin | Project admin |
|--------|------------------------|------------------|---------------|
| `workflows.py` | CRUD standard workflows | CRUD SEAH workflows only | Read |
| `locations.py` projects/orgs/packages | CRUD | Read; SEAH workflow fields on project only | Scoped project |
| `users.py` invite | Standard officers | SEAH officers | Scoped officers |
| `settings.py` | `notification_rules` etc. | SEAH subset | No platform keys |
| `settings.py` super_admin keys | ❌ | ❌ | ❌ |

**Standard-track `country_admin` only:** create project, org directory, location import.

Log 403 with clear message: `requires country_admin track=standard`.

---

## RP-06 — Settings UI access matrix

**File:** `channels/ticketing-ui/app/settings/page.tsx`, `app/providers/AuthProvider.tsx`

### AuthProvider

Expose from API or derive:

- `isSuperAdmin`, `isCountryAdmin`, `isProjectAdmin`
- `adminWorkflowTracks: ('standard'|'seah')[]`
- `adminProjectIds: string[]`
- `adminCountryCode: string | null`

Replace `isAdmin` / `local_admin` checks.

### Main tabs visibility

| Tab | super_admin | country_admin | project_admin |
|-----|-------------|---------------|---------------|
| Organizations & officers | ✅ | ✅ | ✅ (scoped) |
| Workflows, roles & permissions | ✅ | ✅ | ✅ (limited) |
| Projects & packages | ✅ | ✅ standard: all country; seah: read+SEAH fields | ✅ assigned |
| Settings (platform) | ✅ | ❌ | ❌ |

`local_admin` bypass roster: map demo users to new scopes in seed.

---

## RP-07 — Roles tab UI

**Files:** `settings/page.tsx` (`RolesTab`, `RoleEditModal`, new `RoleCreateModal`)

- List **operational** roles only (`GET /roles?kind=operational`)
- Filter toggle Standard / SEAH
- Columns: display name, key, workflow scope, **steps · officers** counts
- **+ New role** → archetype wizard (country admin + super admin only)
- Edit: keep existing modal; add permissions read-only for project_admin; country admin can edit own track
- **Clone role** action
- Remove admin rows (`super_admin`, `country_admin`, `project_admin`) from this tab

---

## RP-08 — Workflows-first UI

**Files:** `settings/page.tsx` (`WorkflowEditor`, step accordion)

- Role dropdown: group **System (TOR)** / **Custom**; filter by workflow type
- **+ Create role…** at bottom of dropdown → modal → on save select new key on step
- Publish workflow: validate every step has `assigned_role_key`
- Footer note unchanged (assign workflow on project)

Spec: [`12_workflows_configuration.md`](../../ticketing_system/12_workflows_configuration.md) §5.1

---

## RP-09 — Admin access sub-tab

**File:** `settings/page.tsx` — new `AdminAccessTab` under platform `Settings`

`super_admin` only:

- Table: user, role (`country_admin` / `project_admin`), country, project, **track**
- **+ Appoint country admin** (country + track)
- **+ Appoint project admin** (project + org optional + track) — or delegate to country admin API only from their session

---

## RP-10 — Seed & demo migration

**Files:** `ticketing/seed/grm_roles.py`, `grm_role_catalog.py`, `mock_tickets.py`, `ticketing/constants/demo_officers.py`

1. Add `country_admin`, `project_admin` to catalog with `role_kind=admin`.
2. Mark seed operational roles `role_origin=system`.
3. Migrate demo `local_admin` user → `country_admin` + `admin_scopes` (`NP`, `standard`) OR `project_admin` as appropriate.
4. Optional: second demo user `country_admin` + `track=seah` for SEAH settings testing.
5. Document bypass header roles in `DOCKER.md` / `PROGRESS.md`.

---

## RP-11 — Tests

**Path:** `tests/ticketing/test_admin_access.py`, `test_roles_crud.py`

| Test | Assert |
|------|--------|
| SEAH country admin cannot POST project | 403 |
| Standard country admin can POST project | 201 |
| Project admin cannot POST `/roles` | 403 |
| Country admin creates custom role | 201, `role_origin=custom` |
| Delete role on workflow step | 409 |
| Archetype rejects `settings:write` on operational role | 422 |
| `GET /roles?kind=operational` excludes admin keys | |

---

## Touch map

### May edit

- `ticketing/migrations/versions/*.py`
- `ticketing/models/user.py`, new `ticketing/models/admin_scope.py`
- `ticketing/api/dependencies.py`
- `ticketing/services/admin_access.py` (new)
- `ticketing/constants/role_archetypes.py` (new)
- `ticketing/constants/grm_role_catalog.py`
- `ticketing/api/routers/users.py`, `workflows.py`, `locations.py`, `settings.py`
- `ticketing/api/schemas/user.py`
- `channels/ticketing-ui/app/settings/page.tsx`
- `channels/ticketing-ui/app/providers/AuthProvider.tsx`
- `channels/ticketing-ui/lib/api.ts`
- `tests/ticketing/test_admin_access.py`, `test_roles_crud.py`
- `docs/ticketing_system/11_roles_and_permissions.md` §8 implementation status only

### Do not edit

- `backend/orchestrator/`, `backend/actions/`, `rasa_chatbot/`
- `project_actor_roles` party-type model (separate spec)
- `docker-compose.yml`, `.env`
- Cross-schema SQL joins `ticketing.*` → `public.*`

---

## Definition of done

- [ ] All RP-01 … RP-11 `done` in [`PROGRESS.md`](PROGRESS.md)
- [ ] `11_roles_and_permissions.md` §8 gaps marked implemented
- [ ] Demo: bypass as `country_admin` NP standard + project_admin on KL_ROAD
- [ ] Demo: bypass as `country_admin` NP seah sees SEAH workflows, cannot create project
- [ ] Roles tab shows no admin keys; + New role works with archetype
- [ ] Workflow step inline create role works
- [ ] No remaining production dependency on `local_admin` as sole admin gate (transitional alias OK in seed migration only)

---

## Deviations log

Record any spec change here and in `11_roles_and_permissions.md` §8:

| Date | Ticket | Deviation |
|------|--------|-----------|
| | | |
