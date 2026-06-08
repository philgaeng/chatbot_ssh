# Agent prompt — Roles, permissions & admin matrix

You are implementing the **admin matrix**, **scoped country/project admins**, **custom operational roles**, and **Settings UI** changes for the GRM ticketing portal.

---

## Read first (in order)

1. **`docs/ticketing_system/11_roles_and_permissions.md`** — locked product spec (source of truth)
2. **`docs/sprints/June5/05-roles-permissions-spec.md`** — implementation tickets RP-01 … RP-11
3. **`docs/ticketing_system/10_settings_overview.md`** — Settings tab map
4. **`docs/ticketing_system/12_workflows_configuration.md`** §5.1 — workflows-first role binding
5. **`docs/ticketing_system/14_platform_settings.md`** — platform tab + Admin access
6. **`docs/ticketing_system/07_officer_management_and_assignment.md`** — officer scopes (operational; separate from admin scopes)

---

## Mission

Implement tickets **RP-01 through RP-11** in spec order unless blocked.

| Phase | IDs | Outcome |
|-------|-----|---------|
| Backend foundation | RP-01, RP-02 | `admin_scopes` table, `role_kind`/`role_origin`, `CurrentUser` + `admin_access.py` |
| APIs | RP-03, RP-04, RP-05 | Roles CRUD, admin appointment, matrix guards on routers |
| Frontend | RP-06 … RP-09 | Settings tabs, Roles wizard, workflow inline create, Admin access tab |
| Data & quality | RP-10, RP-11 | Seed migration off `local_admin`, tests |

---

## Locked rules (do not reinterpret)

1. **Three admin keys only:** `super_admin`, `country_admin`, `project_admin`.
2. **Standard vs SEAH** = `workflow_track` on **`ticketing.admin_scopes`** assignment (`standard` \| `seah`), not separate role names like `seah_admin`.
3. **Deprecated:** `local_admin` → migrate to scoped `country_admin` / `project_admin`; do not add new features for `local_admin`.
4. **Operational roles:** seed TOR catalog + **`country_admin` may create custom** roles via archetype templates; `project_admin` assigns only.
5. **Workflows-first:** primary role binding is workflow **step editor** dropdown; optional **+ Create role…** inline.
6. **Party types** (`donor`, `contractor`, …) live in **Projects & packages** — out of scope.
7. **Platform Settings tab** (`Locations`, `Project types`, `Advanced JSON`, **Admin access**) = **`super_admin` only**.
8. **Standard-track `country_admin` only** may create projects, orgs, locations. SEAH-track cannot.

---

## Primary paths

**Backend**

- `ticketing/api/dependencies.py` — replace `is_admin` / `local_admin` gates
- `ticketing/services/admin_access.py` — **new** permission matrix
- `ticketing/constants/role_archetypes.py` — **new** archetype → permissions map
- `ticketing/constants/grm_role_catalog.py` — add `country_admin`, `project_admin`
- `ticketing/models/admin_scope.py` — **new**
- `ticketing/api/routers/users.py` — roles CRUD + admin scopes
- `ticketing/api/routers/workflows.py`, `locations.py`, `settings.py` — guards
- `ticketing/migrations/versions/` — Alembic only for `ticketing.*`

**Frontend**

- `channels/ticketing-ui/app/settings/page.tsx` — tabs, RolesTab, WorkflowsTab, AdminAccessTab
- `channels/ticketing-ui/app/providers/AuthProvider.tsx` — admin scope context
- `channels/ticketing-ui/lib/api.ts` — new endpoints

**Tests**

- `tests/ticketing/test_admin_access.py`
- `tests/ticketing/test_roles_crud.py`

---

## Implementation order (detail)

### RP-01 — Migration + models

Create `ticketing.admin_scopes` per spec. Add `role_kind`, `role_origin` to `ticketing.roles`. Backfill existing rows.

### RP-02 — `admin_access.py`

```python
# Example checks — implement fully from doc 11 §2
def can_manage_structure(user, *, track: str) -> bool: ...
def can_create_operational_role(user, *, track: str) -> bool: ...
def require_track_for_mutation(user, required_track: str) -> None: ...
```

Extend `CurrentUser` with `admin_scopes: list[AdminScope]`. Load scopes in `get_current_user` from DB (join `user_roles` + `admin_scopes`).

### RP-03 — Roles API

- `GET /roles?kind=operational|admin&workflow_track=`
- `POST /roles` with archetype
- Usage counts on list
- Delete guards

### RP-04 — Admin scopes API

- `GET/POST/DELETE /api/v1/admin-scopes`
- `super_admin` appoints `country_admin` (country + track)
- `country_admin` appoints `project_admin` (project + track, matching appointee track)

### RP-05 — Router guards

Replace bare `require_admin` / `current_user.is_admin` with matrix-aware dependencies on every Settings-related mutating route. Document each change in PR notes.

### RP-06 — Settings tab gating

Update `MAIN_TABS` / `mainTabs` useMemo in `settings/page.tsx`:

- `project_admin`: Projects (+ Officers/Staffing); no platform tab
- `country_admin`: tabs per track (standard gets structure; seah gets SEAH workflows/officers)
- `super_admin`: all tabs

Update `AuthProvider` — remove `local_admin` from `ADMIN_ROLES` set; use API-fed admin scopes or parse from roster in bypass mode.

### RP-07 — Roles tab

- Fetch `kind=operational` only
- **+ New role** wizard: display name, slug, archetype, jurisdiction, track
- Show `Used on N steps · M officers`
- `project_admin`: read/use only (invite dropdown), no create

### RP-08 — Workflow step dropdown

- Group system vs custom roles
- Filter by `workflow_type`
- **+ Create role…** opens same wizard; on success set step `assigned_role_key`
- Block publish if any step missing role

### RP-09 — Admin access sub-tab

Under platform Settings, `super_admin` only: list admin assignments, appoint country/project admins.

### RP-10 — Seed

- Demo officers for standard + SEAH country admin and project_admin on KL_ROAD
- Migrate `local_admin` seed row

### RP-11 — Tests

Minimum tests listed in `05-roles-permissions-spec.md`.

---

## Do not edit

- `backend/orchestrator/`, `backend/actions/`, `rasa_chatbot/`
- `channels/REST_webchat/`
- `docker-compose.yml`, `.env`, `requirements.txt` (use `requirements.grm.txt` if deps needed)
- `project_actor_roles` / party-type UI (already on Projects tab)

---

## Bypass-auth testing

With `NEXT_PUBLIC_BYPASS_AUTH=true`:

1. Extend roster / seed so header switcher includes:
   - `super_admin`
   - `country_admin` (NP, standard)
   - `country_admin` (NP, seah)
   - `project_admin` (KL_ROAD, standard)
2. Verify Settings tabs match matrix for each.

---

## Progress protocol

Update **`docs/sprints/June5/PROGRESS.md`** → section **Agent: Roles & permissions** per ticket (RP-01 … RP-11).

When complete, update **`docs/ticketing_system/11_roles_and_permissions.md`** §8 implementation status table.

Log deviations in **`05-roles-permissions-spec.md`** deviations log.

---

## Definition of done

- [ ] RP-01 … RP-11 marked `done` in PROGRESS.md
- [ ] §8 in `11_roles_and_permissions.md` reflects shipped state
- [ ] Manual smoke: three admin types + custom role + workflow step bind + inline create
- [ ] `pytest tests/ticketing/test_admin_access.py tests/ticketing/test_roles_crud.py` pass
- [ ] No new reliance on `local_admin` for authorization (migration mapping only)

**Do not commit unless the user asks.**

---

## Report back

1. Migration revision id(s) and new columns/tables
2. List of routers updated with new guards
3. Screenshots or steps: Roles wizard, workflow inline create, Admin access tab
4. Demo officer emails/ids for each matrix cell
5. Any spec ambiguities requiring product decision
