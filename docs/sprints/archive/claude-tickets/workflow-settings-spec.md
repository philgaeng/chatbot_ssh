# GRM Settings, Workflows & Project Routing — Product + Engineering Spec

> **Superseded (June 2026):** Content split into `docs/ticketing_system/10_settings_overview.md` through `14_platform_settings.md`. **Admin ladder locked** in `11_roles_and_permissions.md` (`super_admin` → `country_admin` → `project_admin`). Use those for day-to-day reference; this file is kept for migration notes and historical decisions.

**Status:** ARCHIVED — see `docs/ticketing_system/10–14`  
**Supersedes:** draft dated 2026-04-21 (workflow-only sections retained where still valid)  
**Related:** `docs/ticketing_system/10_settings_overview.md`, `07_officer_management_and_assignment.md`, `docs/claude-tickets/PROGRESS.md`, `CLAUDE.md`

---

## 1. Purpose

Allow GRM administrators to configure the platform **without code**:

1. **Who exists** — organizations (global directory) and officers (GRM roles + jurisdiction).
2. **How cases escalate** — workflow definitions (steps, SLAs, step-level GRM roles).
3. **How a project runs** — per-project workflow choice, commercial actors (org + role), packages, locations, and officer staffing.
4. **Platform reference data** — location tree, reports (placeholder), system templates.

New tickets use the **workflows linked on the project**, resolve **organization** from project/package actors (planned), and assign **officers** whose scopes match.

---

## 2. Settings navigation (four main tabs)

Implemented in `channels/ticketing-ui/app/settings/page.tsx`.

| Main tab | Sub-tabs | What lives here |
| -------- | -------- | ----------------- |
| **Organizations & officers** | Organizations · Officers | Global org registry (identity only). Officer roster, invite, manage scopes. |
| **Workflows, roles & permissions** | Workflows · Roles & permissions | Workflow definitions (Standard / SEAH). GRM role catalog (`site_safeguards_focal_person`, `grc_chair`, …). |
| **Projects & packages** | *(project list → editor)* | Per-project routing hub: metadata, workflows, actor roles, project actors, staffing, locations, packages. |
| **Settings** | Locations · Reports · System config | Country/location import. Reports = placeholder. System config = super-admin JSON (global org-role **template**). |

**Design rule:** Do not mix global directory, geographic data, and per-project routing in one tab. Tab 3 is the single place admins configure “how this project works.”

---

## 3. Two different “role” concepts (do not merge in UI copy)

| Concept | Where configured | Stored in | Example keys |
| ------- | ---------------- | --------- | ------------ |
| **GRM role** | Tab 2 → Roles & permissions; assigned on workflow **steps** and on **officers** | `ticketing.roles`, `workflow_steps.assigned_role_key`, `user_roles`, `officer_scopes.role_key` | `site_safeguards_focal_person`, `seah_national_officer` |
| **Project actor role** | Tab 3 → Actor roles (per project); used when linking **organizations** to project or package | `ticketing.project_actor_roles`, `project_organizations.org_role`, `package_organizations.org_role` | `donor`, `main_contractor`, `supervision_consultant` |

Same organization can be **DOR / implementing_agency** on one project and **main_contractor** on a package. That is not the same as “who handles the ticket in the workflow” (GRM role).

---

## 4. Scope

### In scope (implemented unless noted)

| Area | Status |
| ---- | ------ |
| Workflow create / edit / publish / archive / templates | ✅ |
| Step reorder, add, soft-delete, inline accordion edit | ✅ |
| SLA + GRM role per step | ✅ |
| Notification rules grid (Settings on workflow editor) | ✅ |
| **Project-level** Standard + SEAH workflow selection | ✅ (`projects.standard_workflow_id`, `seah_workflow_id`) |
| Per-project **actor role vocabulary** (editable) | ✅ (`project_actor_roles`) |
| **Project actors** (org + role, project-wide) | ✅ (`project_organizations`) |
| **Package actors** (org + role, per lot) | ✅ (`package_organizations`; replaces `contractor_org_id`) |
| Package ↔ location links, QR tokens | ✅ |
| Project **Staffing** section + warnings | ✅ |
| **Add officer** modal from project actors (org + project locked) | ✅ |
| Officers tab (roster, invite, edit scopes) | ✅ |
| Locations import + tree | ✅ |
| Reports schedule | 🔲 Placeholder only |

### Out of scope / deprecated

| Item | Notes |
| ---- | ----- |
| **`ticketing.workflow_assignments` for new config** | **Deprecated in UI.** Workflow choice is on the **project** only. Table may remain for legacy fallback in `resolve_workflow()` until removed in code. |
| Conditional / parallel workflow branches | Linear chain only |
| Workflow import/export | Future |
| `resolve_ticket_organization()` from actors | **Next backend step** — see §10 |

---

## 5. GRM admin roles (`admin_seah`, etc.)

Unchanged from original spec:

| Role | Standard workflows | SEAH workflows | Templates |
| ---- | ------------------ | -------------- | --------- |
| `super_admin` | ✅ | ✅ | ✅ all |
| `local_admin` | ✅ | ❌ | ✅ standard |
| `admin_seah` | ❌ | ✅ | ✅ SEAH |

SEAH workflows and SEAH tickets remain hidden from non-SEAH admins (`canSeeSeah`).

---

## 6. Data model

### 6.1 Workflows (unchanged core)

**`ticketing.workflow_definitions`** — `version`, `is_template`, `status`, `workflow_type`, `updated_by_user_id`, etc.

**`ticketing.workflow_steps`** — `assigned_role_key` (GRM role), SLA fields, `stakeholders`, `expected_actions`, `is_deleted`.

**`ticketing.tickets.workflow_version`** — snapshot at creation.

### 6.2 Project workflow links (NEW — primary assignment path)

| Column | Table | Purpose |
| ------ | ----- | ------- |
| `standard_workflow_id` | `ticketing.projects` | Published Standard workflow for grievances on this project |
| `seah_workflow_id` | `ticketing.projects` | Published SEAH workflow when case is SEAH-sensitive |

**Resolution** (`ticketing/engine/workflow_engine.py` → `resolve_workflow()`):

1. If ticket has `project_id` → use project’s `standard_workflow_id` or `seah_workflow_id` by case type.
2. Else legacy fallback → `workflow_assignments` (dev-only path; do not configure in UI).

Migration: `r0s2t4v6_project_workflow_links.py` (KL_ROAD backfill).

### 6.3 Project actor role vocabulary (NEW)

**`ticketing.project_actor_roles`**

| Column | Notes |
| ------ | ----- |
| `project_id` + `role_key` | PK |
| `label`, `description` | Admin-facing |
| `sort_order` | Display order |

- Seeded on **project create** from global `settings.org_roles` JSON (System config tab).
- Editable per project via `GET/PUT /api/v1/projects/{id}/actor-roles`.
- Cannot remove a role key still used on `project_organizations` or `package_organizations`.

Migration: `s1t3u5v7_package_orgs_and_project_actor_roles.py`.

### 6.4 Project & package actors (NEW)

**`ticketing.project_organizations`** — `(project_id, organization_id)` + `org_role` → `project_actor_roles.role_key`.

**`ticketing.package_organizations`** — `(package_id, organization_id, org_role)` PK.

**Override rule (locked, shown in UI):**

> A package-level actor applies only to that lot and **replaces** the project-wide actor with the **same role** on that package only.

Example: CSC A project-wide, CSC B on package 3 → CSC A on all packages except package 3 (CSC B there).

**Removed:** `project_packages.contractor_org_id` — migrated to `package_organizations` with `org_role = main_contractor`.

API:

- `POST/DELETE …/packages/{id}/organizations/{org_id}` body `{ org_role }`
- `DELETE …/organizations/{org_id}/{org_role}`

### 6.5 Officers (unchanged tables, extended UX)

| Layer | Table | Purpose |
| ----- | ----- | ------- |
| Roster | `ticketing.user_roles` | GRM role membership |
| Jurisdiction | `ticketing.officer_scopes` | Auto-assign + reassign (`organization_id`, `project_id` / `project_code`, `package_id`, `location_code`, `includes_children`) |

**Important:** `officer_scopes.organization_id` must align with **`ticket.organization_id`** for auto-assign. Project/package actors define *commercial* parties; they do not automatically set the ticket org field today.

### 6.6 Legacy: `ticketing.workflow_assignments`

Still in DB and API (`/workflows/{id}/assignments`). **Not exposed in Settings UI.** Do not use for new projects. Remove from codebase when fallback is no longer needed.

---

## 7. Project editor (Tab 3) — section order

When editing a project (`ProjectsSection` → `ProjectEditor`):

| # | Section | Purpose |
| - | ------- | ------- |
| 1 | Description | Name, short code (metadata) |
| 2 | Grievance workflows | Pick Standard + SEAH workflow definitions |
| 3 | Actor roles | Per-project vocabulary (donor, CSC, contractor, …) |
| 4 | Project actors | Org + role for whole project; **Add officer** per row |
| 5 | Staffing | Officers scoped to this project/packages; gaps warned |
| 6 | Linked locations | Province / district / municipality coverage |
| 7 | Packages | Lots: metadata, **package actors** table, locations, QR tokens |

### 7.1 Add officer modal (from project actors or staffing)

- **Invite new** or add scope to **existing** officer (same organization).
- Organization + project **locked** to current project context.
- GRM role + at least one of package / location required (`OfficerJurisdictionFields`).
- Component: `ProjectOfficerModal.tsx`.

### 7.2 Staffing section

- Lists roster entries whose scopes touch this project (`project_codes` or `package_ids` on project).
- Amber warnings when a **project actor** organization has **no** officer scoped on this project.
- **Manage** → full `EditOfficerModal`; **+ Add officer** when at least one project actor exists.

---

## 8. Workflows tab (Tab 2) — UI

### 8.1 List view

- Workflows + templates; Standard / SEAH badges; version / status.
- **No** “assigned to org/project” line (legacy assignments removed from list).
- SEAH rows hidden per role.

### 8.2 Editor

- Vertical step list, up/down reorder, inline accordion edit, publish / archive.
- Footer note: assign workflows under **Settings → Projects & packages**.
- Notification rules panel (event × tier × channel) unchanged.

### 8.3 Removed from editor

- **Assigned to** panel (`workflow_assignments` rows) — **removed.**

---

## 9. Workflow templates (seed)

Built-in templates unchanged:

- **Default GRM** — 4 levels (L1 site → L4 legal).
- **Default SEAH** — 2 levels (national → HQ).

Admin can clone, save-as-template, publish. Templates are not assigned directly; clone then link on project.

---

## 10. Ticket routing & assignment (target behaviour)

### 10.1 Workflow selection

```
ticket.project_id (+ is_seah) → projects.standard_workflow_id | seah_workflow_id
```

### 10.2 Context priority (intake)

1. **Package** — QR `package_id` or location → package via `package_locations`
2. **Project + location**
3. **Location only** (province fallback for assignment — implemented for scopes)

### 10.3 Organization on ticket (GAP — implement next)

**Planned:** `resolve_ticket_organization(project_id, package_id?, location_code?)`

1. If `package_id` → look up `package_organizations` for relevant role (e.g. implementing agency / contractor per product rules).
2. Else → `project_organizations` for project-wide actor by role.
3. Set `ticket.organization_id` **before** `auto_assign_officer()`.

Until then, mismatches can occur (e.g. ticket `organization_id = DOR` but officer scoped to `NP_DC1`).

### 10.4 Officer assignment

`auto_assign_officer(step_role, organization_id, location_code, project_code, package_id)`:

- Match `officer_scopes` to ticket fields + step `assigned_role_key`.
- Package-first when `ticket.package_id` set (see `07_officer_management_and_assignment.md`).
- Least-loaded among candidates.

---

## 11. API summary

### Workflows

| Method | Path | Notes |
| ------ | ---- | ----- |
| GET/POST/PATCH | `/workflows`, `/workflows/{id}/steps`, publish, archive, clone | Unchanged |
| GET/POST/DELETE | `/workflows/{id}/assignments` | Legacy; avoid in UI |

### Projects, actors, packages

| Method | Path | Notes |
| ------ | ---- | ----- |
| GET/PUT | `/projects/{id}/actor-roles` | Per-project role vocabulary |
| GET/POST/PATCH/DELETE | `/projects/{id}/organizations/{org_id}` | Project actors |
| GET/POST/PATCH | `/projects/{id}/packages` | Includes `organizations[]` in response |
| POST | `/projects/{id}/packages/{pkg_id}/organizations/{org_id}` | Package actor |
| DELETE | `…/organizations/{org_id}/{org_role}` | Remove package actor |

### Officers

| Method | Path | Notes |
| ------ | ---- | ----- |
| GET | `/users/roster` | Includes `project_codes`, `package_ids` |
| POST | `/users/invite` | Requires jurisdiction |
| GET/POST/DELETE | `/users/{id}/scopes` | |

### Settings

| Method | Path | Notes |
| ------ | ---- | ----- |
| GET/PUT | `/settings/org_roles` | Global template for **new** projects only |

---

## 12. Migrations (ticketing Alembic)

| Revision | What |
| -------- | ---- |
| `c4e7d2b91f35`+ | Workflow editor columns |
| `r0s2t4v6` | `projects.standard_workflow_id`, `seah_workflow_id` |
| `s1t3u5v7` | `project_actor_roles`, `package_organizations`; drop `contractor_org_id` |
| `q9r7s1u3` | Nepal canonical location codes (related) |

Run: `alembic -c ticketing/migrations/alembic.ini upgrade head` (see `docs/claude-tickets/DOCKER.md`).

---

## 13. In-flight ticket versioning

**Adopted:** `workflow_version` on ticket at creation; publish increments definition version; existing tickets keep their snapshot. UI may warn active ticket count on publish.

For demo with seeded tickets only, edits to published workflows affect **new** tickets via project workflow IDs, not retroactively changing old step graphs on open tickets.

---

## 14. Resolved open questions (2026-04 draft)

| # | Question | Decision |
| - | -------- | -------- |
| Q-A | `is_default` on workflow_assignments? | Irrelevant for new config; project links used instead |
| Q-B | Version snapshot vs immediate? | Snapshot on ticket; project picks current published workflow ID |
| Q-C | Assignment conflict detector? | N/A at project level: one Standard + one SEAH per project |
| Q-D | Step key editable? | Auto-generated, then editable |
| Q-E | Delete step in use? | Block |
| Q-F | Who can create templates? | `local_admin` can |
| Q-G | Publish without assignment? | Workflows publish without project link; project editor enforces workflow pick for routing |

### New decisions (2026-05)

| Topic | Decision |
| ----- | -------- |
| Officer scopes on project tab? | **B** — Staffing editable on project; Add officer modal on project actors |
| Global `org_roles` in System config? | Template for **new** projects only; each project owns `project_actor_roles` |
| Legacy `workflow_assignments`? | Not configured in UI; remove from code when safe |
| Reports | Placeholder under Settings tab |
| Project archetypes (`project_types`)? | **Planned** — see §17; first type `construction_road` |
| Who defines project types? | **`super_admin` only** |
| Actor role keys on instantiated projects? | **Locked** — super-admin defines on type; local admin fills orgs only |
| SEAH on construction type? | **Always bundled** on archetype |

---

## 15. Build / verification checklist

- [x] Project workflow fields + `resolve_workflow()` project-first
- [x] `project_actor_roles` + API + UI editor
- [x] `package_organizations` + migration from contractor
- [x] Four-tab Settings shell
- [x] Project Staffing + `ProjectOfficerModal`
- [x] Remove workflow assignment panel from workflow editor
- [ ] `resolve_ticket_organization()` + set `ticket.organization_id` on create
- [ ] Show resolved org on ticket “Area covered” / detail
- [ ] Reports schedule implementation
- [ ] Drop `workflow_assignments` fallback and table (optional cleanup)
- [x] `project_types` table + super-admin studio UI
- [x] Project create: pick type → instantiate `construction_road`
- [x] Go-live checklist panel on project editor (§17)
- [x] Gate `is_active` / ticket create per §17 demo rules

---

## 16. File index (implementation)

| Area | Path |
| ---- | ---- |
| Settings UI | `channels/ticketing-ui/app/settings/page.tsx` |
| Project officer modal | `channels/ticketing-ui/components/settings/ProjectOfficerModal.tsx` |
| Project staffing | `channels/ticketing-ui/components/settings/ProjectStaffingSection.tsx` |
| Officers tab | `channels/ticketing-ui/components/settings/OfficersTab.tsx` |
| Jurisdiction form | `channels/ticketing-ui/components/settings/OfficerJurisdictionForm.tsx` |
| Project/location API | `ticketing/api/routers/locations.py` |
| Workflow resolve | `ticketing/engine/workflow_engine.py` |
| Actor role service | `ticketing/services/project_actor_roles.py` |
| Officer assignment spec | `docs/ticketing_system/07_officer_management_and_assignment.md` |

---

## 17. Project archetypes & go-live checklist (locked 2026-05-16)

### 17.1 Admin tiers

| Tier | Who | Configures |
| ---- | --- | ---------- |
| **Platform** | `super_admin` | Project **types** (archetypes), workflow templates, GRM role catalog, global location import, routing rules on the type |
| **Project** | `local_admin` | Pick type on create → fill **who / what / where** (orgs in actor slots, packages, locations, officers in orgs). Cannot edit actor **role keys** or workflow step graphs |

`admin_seah` does **not** create project types (SEAH workflow is bundled on types that include it; SEAH workflow editing remains role-gated as today).

### 17.2 First archetype: `construction_road`

| Field | Value |
| ----- | ----- |
| `type_key` | `construction_road` |
| Standard workflow | Published Standard workflow (e.g. KL 4-level) — set on type |
| SEAH workflow | **Always bundled** — published SEAH workflow set on type |
| Actor role keys | Defined on type; copied to `project_actor_roles` on instantiate; **keys locked** for local admin |
| Ticket org resolver (target) | `implementing_agency` at project level; package override for same **role** on package (e.g. `main_contractor`) when `package_id` present — see §10 |

**Required actor slots on type:**

| Scope | `role_key` | Required when |
| ----- | ---------- | ------------- |
| Project | `implementing_agency` | Always |
| Project | `donor` | Always |
| Project | `supervision_consultant`, `main_contractor` | Optional (shown; not blocking in demo) |
| Package | `main_contractor` | Each **active** package, unless same role filled project-wide |

### 17.3 Instantiate flow (target)

1. Local admin: **New project** → choose `construction_road`.
2. System copies actor vocabulary + sets `standard_workflow_id` / `seah_workflow_id` from type.
3. Local admin completes checklist sections (actors, locations, packages, staffing).
4. **Go-live** panel shows status; demo rules in §17.4.

Replaces ad-hoc per-project workflow pick and editable actor-role dictionary for local admins.

### 17.4 Go-live checklist

**Goal:** Can we create a ticket and assign L1 to the right operational officer?

**Severity:**

| Level | Meaning |
| ----- | ------- |
| **Block** | Cannot set project `active`, and/or ticket create rejected / misconfiguration queue |
| **Warn** | Project may be active; amber banner on project + admin visibility |
| **Info** | Best practice only |

#### Demo (proto)

| ID | Check | Severity |
| -- | ----- | -------- |
| A1 | `standard_workflow_id` → published Standard workflow | Warn (auto from type; warn if cleared/archived) |
| A2 | `seah_workflow_id` → published SEAH workflow | Warn (bundled on type) |
| A3 | Project actor `implementing_agency` has an org | **Block** for `active` |
| B1 | All type-**required** actor slots filled at project level | Warn |
| B2 | Each active package has ≥1 location link | Warn |
| B3 | Each active package: required package roles filled (or project-wide override) | Warn |
| C1 | ≥1 **active** officer: GRM role = Standard workflow **step 1** `assigned_role_key`, scoped to **implementing agency org** + this project | Warn on project; **Block ticket create** if fail |
| C2 | Officer `organization_id` matches implementing-agency org | Warn |
| C3 | Per-package L1 when package has distinct `main_contractor` org | Warn |
| C4 | ≥1 officer with SEAH step-1 GRM role scoped to project | Warn |
| D1 | ≥1 project location linked | Warn |
| D2 | Package QR token present | Info |
| E1 | Name + short code set | Warn |

**Demo blocks:** A3 for activation; C1 for ticket intake (no silent assign to admins).

#### Production (later)

Promote A1, A2, B1, B2, B4, C1, C2, C4, D1, E1 to **Block** when `resolve_ticket_organization()` and package-first auto-assign are verified. Add **A4**: simulated ticket resolves `organization_id` and C1 uses that org.

### 17.5 UI (target)

- **Project editor header:** “Go-live status” with grouped checks (Routing · Commercial · Officers · Geography); green / amber / red; links jump to section.
- **Super-admin:** CRUD `project_types`, required slots, workflow IDs, routing slot mapping.
- **Local admin:** checklist read-only except data entry in sections.

### 17.6 Implementation note

Built 2026-05-16: migration `u3v5w7x9`, API `/project-types`, `/projects/{id}/go-live`, create-from-type, activation + ticket intake gates. Legacy projects without `project_type_key` keep prior behaviour.
