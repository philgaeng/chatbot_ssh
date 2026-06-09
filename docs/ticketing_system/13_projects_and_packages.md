# Projects and packages

**Status:** As-built reference (June 2026)  
**UI:** Settings → **Projects & packages**  
**Code:** `ticketing/api/routers/locations.py` (projects/packages), `ticketing/services/project_go_live.py`, `ticketing/services/project_types.py`  
**Related:** [10_settings_overview.md](10_settings_overview.md), [12_workflows_configuration.md](12_workflows_configuration.md), [11_roles_and_permissions.md](11_roles_and_permissions.md), [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md)

This document covers **`ticketing.projects`** and related package/QR configuration. For the chatbot **`public.projects`** catalog (SEAH picker, CSV import), see [features/settings/settings_tab_projects_and_seah_contact_centers.md](features/settings/settings_tab_projects_and_seah_contact_centers.md).

---

## 1. Purpose

A **project** is the routing hub for a financed infrastructure intervention (e.g. KL Road):

- Which **workflows** apply (Standard + SEAH)
- Which **organizations** play commercial **actor roles**
- Which **locations** and **packages** (lots/segments) exist
- Whether the project is **active** and can **accept tickets**

### Who edits what (admin matrix)

| Action | `country_admin` `track=standard` | `country_admin` `track=seah` | `project_admin` |
|--------|-------------------------------|------------------------------|-----------------|
| Create project / package | ✅ country | ❌ | ❌ |
| Edit **standard** workflow on project | ✅ | ❌ | ❌ (read) |
| Edit **SEAH** workflow / SEAH staffing | ❌ | ✅ country | ✅ if scope `track=seah` |
| Link orgs to **party roles** | ✅ | ❌ | ✅ on assigned project (standard track) |
| Invite **standard** officers (Staffing) | ✅ | ❌ | ✅ scoped, `track=standard` |
| Invite **SEAH** officers | ❌ | ✅ | ✅ scoped, `track=seah` |
| Platform **Settings → Settings** tab | ❌ | ❌ | ❌ |

See [11_roles_and_permissions.md](11_roles_and_permissions.md) §2.

---

## 2. Data model

### `ticketing.projects`

| Field | Notes |
|-------|-------|
| `project_id` | UUID PK |
| `name`, `short_code` | `short_code` unique (e.g. `KL_ROAD`) |
| `country_code` | e.g. `NP` |
| `description` | Optional |
| `project_type_key` | FK → `ticketing.project_types` (archetype) |
| `is_active` | Gated by go-live checks |
| `standard_workflow_id` | Published Standard workflow |
| `seah_workflow_id` | Published SEAH workflow |
| `chatbot_url` | Optional override for QR redirect |

### `ticketing.project_organizations`

Project-wide commercial actors: `(project_id, organization_id)` + `org_role` → `project_actor_roles.role_key`.

### `ticketing.project_actor_roles`

Per-project vocabulary of actor role keys (labels, sort order). Seeded from `settings.org_roles` on create; keys **locked** for `local_admin` when type defines them.

### `ticketing.packages` (`project_packages`)

Physical lots within a project. Fields: `package_id`, `project_id`, `name`, `is_active`.

### `ticketing.package_organizations`

Package-level actor override: `(package_id, organization_id, org_role)`.

**Override rule:** A package-level actor replaces the project-wide actor with the **same `org_role`** on that package only.

### `ticketing.package_locations`

Many-to-many: package ↔ `location_code`.

### `ticketing.qr_tokens`

Opaque token → `package_id`; public scan URL. See [10_settings_overview.md](10_settings_overview.md) §6 and `GET /api/v1/scan/{token}`.

---

## 3. Project types (archetypes)

Defined by `super_admin` under Settings → Project types. See [14_platform_settings.md](14_platform_settings.md).

First type: **`construction_road`**

- Bundles Standard + SEAH workflow IDs from the type
- Defines required actor role keys (e.g. `implementing_agency`, `donor`)
- On **New project**, local admin picks type → system copies actor vocabulary and workflow links
- Project starts **`is_active = false`** until go-live passes

---

## 4. Settings UI — project list

| Viewer | Behaviour |
|--------|-----------|
| `super_admin` | List all projects; create, edit, remove |
| `project_admin` | Usually one project — lands directly in editor ("Set up") |

List columns: name, short code, actor org summary, location count.

---

## 5. Project editor — section order

| # | Section | Purpose |
|---|---------|---------|
| 1 | **Metadata** | Name, short code, description, active toggle |
| 2 | **Go-live panel** | Readiness checks with pass/warn/fail — see §7 |
| 3 | **Grievance workflows** | Pick published Standard + SEAH workflows |
| 4 | **Actor roles** | Per-project commercial role labels (keys locked on typed projects) |
| 5 | **Project actors** | Org + role for whole project; **Add officer** per row |
| 6 | **Staffing** | Officers scoped to this project; gap warnings |
| 7 | **Linked locations** | Province / district / municipality coverage |
| 8 | **Packages** | Lots: metadata, package actors, locations, QR tokens |

Components: `ProjectGoLivePanel`, `ProjectStaffingSection`, `ProjectOfficerModal`, `ProjectActorAddRow`.

### Add officer modal (from project context)

- Organization + project **locked** to current project.
- GRM role + at least one of package / location required.
- Creates invite or adds `officer_scopes` row — see [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md).

### Staffing section

- Lists roster entries with scopes on this project.
- Amber warning when a **project actor org** has no officer scoped on the project.

---

## 6. Ticket routing (uses project config)

### Workflow selection

```
ticket.project_id + is_seah → projects.standard_workflow_id | seah_workflow_id
```

### Context priority (intake)

1. **Package** — QR `package_id`
2. **Project + location**
3. **Location only**

### Organization on ticket (gap)

**Planned:** `resolve_ticket_organization(project_id, package_id?, location_code?)` from actors before `auto_assign_officer()`. Until implemented, `ticket.organization_id` may not match commercial actors.

### Officer assignment

`auto_assign_officer()` matches step `assigned_role_key` + `officer_scopes` to ticket fields. Package-first when `package_id` set.

---

## 7. Go-live checklist

**API:** `GET /api/v1/projects/{id}/go-live`  
**Service:** `ticketing/services/project_go_live.py`

**Goal:** Can we activate the project and create a ticket assigned to the right L1 officer?

| Severity | Meaning |
|----------|---------|
| **Block** | Cannot set `is_active` and/or ticket create rejected |
| **Warn** | May activate; amber banner |
| **Info** | Best practice |

### Demo (proto) checks

| ID | Check | Severity |
|----|-------|----------|
| A1 | `standard_workflow_id` → published workflow | Warn |
| A2 | `seah_workflow_id` → published SEAH workflow | Warn |
| A3 | Project actor `implementing_agency` has an org | **Block** for activation |
| B1 | Required actor slots filled | Warn |
| B2 | Each active package has ≥1 location | Warn |
| B3 | Package required roles filled | Warn |
| C1 | L1 GRM officer scoped to implementing agency + project | Warn on project; **Block ticket create** if fail |
| C2 | Officer org matches implementing agency | Warn |
| C4 | SEAH L1 officer scoped to project | Warn |
| D1 | ≥1 project location linked | Warn |
| D2 | Package QR token present | Info |
| E1 | Name + short code set | Warn |

Activation (`PATCH` with `is_active: true`) returns 422 if `can_activate` is false.

---

## 8. API summary

| Method | Path | Notes |
|--------|------|-------|
| `GET/POST` | `/projects` | List / create (admin) |
| `GET/PATCH/DELETE` | `/projects/{id}` | CRUD; activation gated |
| `GET` | `/projects/{id}/go-live` | Checklist report |
| `GET/PUT` | `/projects/{id}/actor-roles` | Commercial role vocabulary |
| `GET/POST/PATCH/DELETE` | `/projects/{id}/organizations/...` | Project actors |
| `GET/POST` | `/projects/{id}/locations/{code}` | Location links |
| `GET/POST/PATCH` | `/projects/{id}/packages` | Package CRUD |
| `POST/DELETE` | `/projects/{id}/packages/{pkg}/organizations/...` | Package actors |
| `POST/DELETE` | `/projects/{id}/packages/{pkg}/locations/...` | Package locations |
| `GET/POST/DELETE` | `/qr-tokens` (via scan router) | QR management |

---

## 9. Acceptance criteria

1. Super admin can create a typed project, link workflows, orgs, locations, and packages.
2. Local admin can complete go-live data entry without editing locked actor role keys.
3. Project cannot activate until implementing agency actor is set (demo block A3).
4. Ticket create blocked when L1 officer scope missing (demo block C1).
5. Package actor override replaces project-wide actor for same role on that package only.
6. QR scan returns package + location context for chatbot pre-fill.
