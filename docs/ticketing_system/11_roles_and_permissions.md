# Roles and permissions

**Status:** Locked product spec (June 2026). **Implementation:** partial — admin ladder not fully wired in API/UI; see §8.  
**Related:** [10_settings_overview.md](10_settings_overview.md), [12_workflows_configuration.md](12_workflows_configuration.md), [14_platform_settings.md](14_platform_settings.md), [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md), [13_projects_and_packages.md](13_projects_and_packages.md)

This document covers **`ticketing.roles`** — both the **admin ladder** (who configures the system) and **operational GRM roles** (who handles grievances). It does **not** cover **project actor roles** (`donor`, `contractor`, …) in `ticketing.project_actor_roles`; those are configured per project in [13_projects_and_packages.md](13_projects_and_packages.md).

---

## 1. Two kinds of row in `ticketing.roles`

| Kind | `role_kind` (conceptual) | Question it answers | UI surface |
|------|--------------------------|---------------------|------------|
| **Admin roles** | `admin` | Who can configure the platform and delegate to others? | Settings → **Settings** (platform) → **Admin access** — `super_admin` only |
| **Operational roles** | `operational` | Who acts on grievance tickets in the workflow? | Settings → **Workflows, roles & permissions** → **Roles & permissions** — catalog managed by scoped `country_admin`; used by `project_admin` when inviting |

**Party types** (`implementing_agency`, `main_contractor`, …) are **not** in `ticketing.roles`. They live in `project_actor_roles` on each project.

**Delegation model (locked):** Three admin **`role_key`s** only (`super_admin`, `country_admin`, `project_admin`). **Tier** is the role; **workflow track** (`standard` \| `seah`) is on the **assignment scope** at country and project tiers — not a separate role name.

---

## 2. Admin matrix — LOCKED

Admins are defined on **two dimensions**:

| Dimension | Values |
|-----------|--------|
| **Tier** | Platform → Country → Project |
| **Workflow track** | **Standard** GRM \| **SEAH** |

Same tier + same *kind* of responsibility; **SEAH roles mirror Standard roles** with SEAH-scoped data and `canSeeSeah`. Not a separate permission mini-language.

```
                    │  Standard track              │  SEAH track
────────────────────┼──────────────────────────────┼────────────────────────────
Platform (global)   │  super_admin (both tracks)   │  super_admin
Country             │  country_admin + track=standard│  country_admin + track=seah
Project             │  project_admin + track=standard│  project_admin + track=seah
```

**Three admin keys, scope carries the track.** No `seah_admin`, `seah_project_admin`, or `local_admin`. Reusable for future tracks by extending `workflow_track`, not the role catalog.

### Admin scope shape (implementation)

| Field | Country tier | Project tier |
|-------|--------------|--------------|
| `country_code` | Required | From project |
| `project_id` | — | Required |
| `organization_id` | — | Optional |
| **`workflow_track`** | `standard` \| `seah` | `standard` \| `seah` |

One person may hold **two** assignments (e.g. `country_admin` NP + `standard` and `country_admin` NP + `seah`) — two scope rows, not two role keys.

### 2.1 `super_admin`

- Full access including **Settings → Settings** (platform): locations import, project types, system JSON (`org_roles`, `report_limits`, `archiving_policy`).
- Creates and manages scoped `country_admin` and `project_admin` accounts (sets `workflow_track` on each assignment).
- Break-glass, migrations, env-level config.
- Does **not** need to perform day-to-day officer assignment unless supporting ops.

### 2.2 `country_admin` — country tier (scoped by `workflow_track`) — LOCKED

One **`role_key`** for all country-tier admins. **`workflow_track` on the assignment scope** selects Standard vs SEAH behaviour (same pattern as `project_admin`).

| Capability | `workflow_track: standard` | `workflow_track: seah` |
|------------|---------------------------|------------------------|
| Settings (no platform tab) | ✅ country | ✅ country |
| Create / edit **projects** | ✅ country | ✅ country |
| Create / edit **packages**, **orgs**, **locations** | ✅ | ❌ — detail structure owned by **standard** track |
| Create / edit **workflows** | ✅ standard templates | ✅ SEAH templates only |
| Create **custom operational roles** (§3) | ✅ standard track | ✅ SEAH track only |
| Appoint **`project_admin`** (same track on child scope) | ✅ `track=standard` | ✅ `track=seah` |
| Invite **country-wide** operational officers | ✅ standard roles | ✅ SEAH roles only |
| Read tickets in country | ✅ standard | ✅ SEAH only (`is_seah`) |
| Manage other track | ❌ | ❌ |

**Appointment:** `super_admin` only (sets `country_code` + `workflow_track`).

**Isolation:** API filters every mutation by scope `workflow_track`. Standard and SEAH country admins are different **assignments**, not different role keys.

### 2.3 `project_admin` — project tier (scoped by `workflow_track`) — LOCKED

One **`role_key`** for all project-tier delegates. **Track** (Standard vs SEAH) is on the **admin assignment scope**, not a separate role name — reproducible for future cases without new admin keys.

| Scope field | Values | Set by |
|-------------|--------|--------|
| `project_id` (+ optional `organization_id`, `package_id`) | Assigned project(s) | `country_admin` **with matching `workflow_track`** |
| **`workflow_track`** | `standard` \| `seah` | Must match appointing country admin’s track |

| `workflow_track` on scope | Appointed by | Can do (within project scope) |
|---------------------------|--------------|-------------------------------|
| **`standard`** | `country_admin` (`track=standard`) | Standard officers, party orgs, staffing, go-live data entry |
| **`seah`** | `country_admin` (`track=seah`) | SEAH officers, SEAH staffing fields; **no** standard L1/L2/GRC officer management |

Shared rules (both tracks):

- **Cannot** create projects, country location tree, or workflow templates.
- **Cannot** appoint other `project_admin` or `country_admin` users.
- **Cannot** access platform **Settings → Settings** tab.
- **Cannot** create operational roles in catalog (country-tier admin only).

**Rationale for org management (standard track):** Subcontractors join mid-project; standard `project_admin` links orgs to party roles without waiting for `country_admin`.

**Implementation:** extend admin scope model (reuse `officer_scopes` pattern or `admin_scopes` table) with `workflow_track` column; API enforces track on every Settings mutation.

### 2.4 Deprecated admin keys

| `role_key` | Migration |
|------------|-----------|
| **`local_admin`** | → `country_admin` or `project_admin` + appropriate `workflow_track` |
| **`seah_admin`** *(if seeded)* | → `country_admin` + `workflow_track: seah` |
| **`seah_project_admin`** | Never shipped — use `project_admin` + `workflow_track: seah` |

**Code gap:** Today `local_admin` maps to generic `is_admin`; implement scope `workflow_track` enforcement in §8.

---

## 3. Operational GRM roles — LOCKED placement

These rows stay in **Settings → Workflows, roles & permissions → Roles & permissions**. They are **not** admin roles.

| Bucket | `role_key` examples |
|--------|---------------------|
| L1 / L2 / L3 handlers | `site_safeguards_focal_person`, `pd_piu_safeguards_focal`, `grc_chair`, `grc_member` |
| SEAH handlers | `seah_national_officer`, `seah_hq_officer` |
| Observers | `adb_national_project_director`, `adb_hq_safeguards`, `adb_hq_project`, `adb_hq_exec` |
| System fallback | `country_l1_fallback` — hidden from routine invite UI; `country_admin` / `super_admin` only |

### 3.1 Seeded roles vs custom roles — LOCKED

Deployments start from a **TOR-aligned seed catalog** (`grm_role_catalog.py`). That is a **starter kit**, not a hard ceiling.

| `role_origin` | Examples | Who can create | Who can delete |
|---------------|----------|----------------|----------------|
| **`system`** | `site_safeguards_focal_person`, `grc_chair`, `seah_national_officer` | Seed / `super_admin` | `super_admin` only, if unused |
| **`custom`** | `supervision_consultant_field`, `dor_provincial_oversight` | Scoped `country_admin`, `super_admin` | Creator tier, if unused |

**Why custom roles:** On-the-ground titles and responsibility lines differ by project (supervisory consultants country-wide vs package-scoped, extra L2 variants, etc.). Renaming `display_name` on a single global row is **not enough** when two positions need **different permissions** or **different workflow step bindings**.

### 3.2 Country-wide vs project-scoped — two knobs (do not conflate)

| Knob | Where it lives | What it means |
|------|----------------|---------------|
| **Default jurisdiction** (`jurisdiction_mode` on role) | Role edit modal (see screenshot) | **UX default** when inviting: `country` = suggest country-wide scope; `field` = require project/package/location on scope |
| **Actual assignment scope** | `officer_scopes` on each officer | **Enforcement** — country-wide supervisor vs project-only supervisor is set **per person**, not only per role |

Example: one custom role `supervision_consultant_oversight` with default `field`; Officer A scoped to **project KL_ROAD**; Officer B scoped **country NP** with `includes_children`. Same role key, different scopes.

Workflow steps reference **`role_key`** only. Custom roles must be **assigned to a workflow step** before auto-assign can use them.

### 3.2.1 Organization on invite vs ticket routing — as-built

For **`jurisdiction_mode=field`** officers scoped to a project or package:

- **UI** defaults `organization_id` to the project’s **implementing agency** (routing role).
- **API** (`POST /users/invite`, `POST /users/{id}/scopes`) overrides a mismatched org via `resolve_ticket_organization()` so `officer_scopes.organization_id` matches `tickets.organization_id` on create.

**`jurisdiction_mode=country`** observers (e.g. `adb_national_project_director`) keep the selected org (e.g. ADB). Details: [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md) §4.1, [13_projects_and_packages.md](13_projects_and_packages.md) §6.

### 3.3 Who manages the operational catalog — LOCKED

| Action | `project_admin` | `country_admin` (by scope track) | `super_admin` |
|--------|-----------------|----------------------------------|---------------|
| List / use roles in invite | ✅ own track | ✅ own track | ✅ |
| Edit `display_name`, `description` | ✅ | ✅ own track | ✅ |
| Edit `workflow_scope`, `jurisdiction_mode`, **permissions** | ❌ | ✅ own track | ✅ |
| **Create role** | ❌ | ✅ own track | ✅ |
| **Delete role** | ❌ | ✅ custom unused, own track | ✅ all unused |

`project_admin` **assigns** roles to officers within scope; **does not** define the catalog (avoids N contractors inventing N incompatible role keys).

### 3.4 Smart permission allocation (UX) — LOCKED approach

**Problem:** Letting admins tick 20 raw permission strings is error-prone. **Solution:** **role archetype template** + grouped overrides + workflow linkage warnings.

#### Step 1 — Create role wizard

| Field | Rules |
|-------|--------|
| **Display name** | Required (e.g. “Construction Supervision Consultant — Field”) |
| **`role_key`** | Auto-slug from name; editable once; `[a-z][a-z0-9_]{0,63}`; unique |
| **Workflow track** | Standard \| SEAH (defaults to assigner’s `workflow_track`) |
| **Archetype** *(permission template)* | Pick one — see table below |
| **Default jurisdiction** | `field` \| `country` \| `global` |
| **Description** | Optional |

#### Step 2 — Archetypes (pre-fill `permissions` JSON)

| Archetype | Pre-filled capabilities | Typical use |
|-----------|-------------------------|-------------|
| **Field actor** | `tickets:read`, `acknowledge`, `note`, `resolve` | L1-style case handler |
| **Supervisor** | Field actor + `escalate`, manual reassign | L2 / oversight with escalation |
| **GRC committee** | Supervisor + `grc:convene`, `grc:decide` | L3 chair |
| **GRC member** | `read`, `note` | L3 participant |
| **Informed** | `read`, `note` | Informed tier — contractors, copied team members, oversight with notes |
| **Observer** | `tickets:read`, `reports:read` | ADB / donor read-only |
| **SEAH handler** | Field actor + `seah:access`, `escalate` | SEAH track |
| **Custom** | None — show grouped picker | Expert / `super_admin` only |

#### Step 3 — Grouped permission picker (optional tweak)

Show checkboxes in **plain-language groups**, not a flat dev list:

| Group | Capabilities |
|-------|----------------|
| **Cases** | View, Acknowledge, Add notes, Escalate, Resolve |
| **GRC** | Convene hearing, Record decision |
| **SEAH** | Access SEAH cases |
| **Reports** | View reports / export |

**Rules:**

- Archetype sets defaults; admin may add/remove within groups (`country_admin` / `super_admin`).
- **`country_admin`** with `workflow_track: seah` cannot grant permissions outside SEAH track (no `grc:*` unless `super_admin`).
- **Dangerous caps:** `users:invite`, `settings:write`, `projects:manage` only on **admin matrix roles**, never on operational archetypes.

#### Step 4 — Workflow linkage (guard rails)

Roles list shows: **“Used on N workflow steps · M officers”**.

- **0 steps, 0 officers** → soft warning on role row (orphan catalog entry — OK if preparing ahead)
- **0 steps, M officers** → stronger warning (officers hold a role not on any workflow — auto-assign may fail)
- Delete blocked if **any** workflow step or officer references the role

**Clone from existing role:** `country_admin` can duplicate a system or custom role as starting point.

### 3.5 Workflows-first binding (LOCKED — primary UX path)

**Observation:** Admins create and edit **workflows more often than roles**. The catalog is relatively stable (seed + occasional custom role); **workflow steps are where roles are consumed**.

| Activity | Primary surface | Secondary / escape hatch |
|----------|-----------------|---------------------------|
| Define escalation path, SLAs, **which role owns each step** | **Workflows tab** → step editor → `assigned_role_key` dropdown | — |
| Add a **new** position type to the catalog | **Roles tab** → + New role (archetype wizard) | **Inline** “+ Create role…” on workflow step dropdown (opens same wizard, returns to step) |
| Reuse same role across workflows | Pick existing `role_key` on each step | — |
| Per-project workflow choice | **Projects & packages** → link `standard_workflow_id` / `seah_workflow_id` | Clone workflow from template |

**Do not** require role creation inside the main “New workflow” flow. Typical path:

1. Clone workflow from template (steps already reference seed `role_key`s).
2. Adjust step names / SLAs; change **assigned role** on a step via dropdown.
3. Only if the needed role is missing → **+ Create role** from dropdown or Roles tab first.

**Workflow step dropdown** should group roles: *System (TOR)* · *Custom* · filter by workflow track (Standard / SEAH).

**Roles tab** remains the place for permission archetypes, jurisdiction defaults, and catalog hygiene — not the daily editing surface.

See [12_workflows_configuration.md](12_workflows_configuration.md) §5.1.

### 3.6 Create role API (target)

`POST /api/v1/roles` body: `display_name`, `role_key?`, `workflow_scope`, `jurisdiction_mode`, `permissions[]`, `archetype?`, `role_origin: custom`.

`PATCH` may update permissions for custom roles; **system** roles: permissions change `super_admin` only (protect TOR defaults).

---

## 4. Settings UI — access matrix (target)

| Main tab | `super_admin` | `country_admin` | `project_admin` |
|----------|---------------|-----------------|-----------------|
| Organizations & officers | ✅ | ✅ per scope track | ✅ per scope track, project |
| Workflows, roles & permissions | ✅ | ✅ per scope track | ✅ invite only |
| Projects & packages | ✅ | ✅ create projects (both tracks); standard: packages/orgs/locations; SEAH: SEAH fields | ✅ assigned project(s) |
| **Settings** (platform) | ✅ | ❌ | ❌ |

### Platform sub-tabs (`super_admin` only)

| Sub-tab | Purpose |
|---------|---------|
| Locations | National tree import (platform) |
| Quarterly reports | Report library + role assignments |
| Project types | Archetype studio |
| Advanced (JSON) | `org_roles`, `report_limits`, `archiving_policy` |
| **Admin access** *(new)* | Assign `country_admin` / `project_admin`; list admin role holders |

---

## 5. Data model (`ticketing.roles`)

| Column | Notes |
|--------|-------|
| `role_id` | UUID PK |
| `role_key` | Stable machine key — set at create; **immutable after save** |
| `role_origin` | `system` \| `custom` *(implementation)* |
| `display_name` | Admin-editable label |
| `description` | Admin-editable |
| `workflow_scope` | `Standard` \| `SEAH` \| `Both` — operational roles; admin roles may use `Both` or null |
| `jurisdiction_mode` | `global` \| `country` \| `field` — default scope shape for invites |
| `permissions` | JSON capability strings; `["*"]` for `super_admin` |

*Future implementation:* optional `role_kind` column (`admin` \| `operational`) or allowlist in code to split API list endpoints.

### Admin scope (assignment, not a column on `roles`)

Stored on **`user_roles`** + admin scope rows *(reuse `officer_scopes` with `scope_kind: admin` or dedicated `admin_scopes` — TBD)*:

| Admin role | Typical scope fields |
|------------|---------------------|
| `country_admin` | `country_code` + **`workflow_track`** (`standard` \| `seah`) |
| `project_admin` | `project_id`, optional `organization_id` / `package_id`, **`workflow_track`** (must match appointing country admin) |

**Design rule:** prefer **scope dimensions** over new `role_key`s when the job shape is the same but the data boundary differs (SEAH vs Standard today; other tracks later).

---

## 6. System seed catalog (starter roles)

Shipped from `ticketing/constants/grm_role_catalog.py` as **`role_origin: system`**. Admins may add **custom** rows alongside these.

| `role_key` | Workflow scope | TOR level (reference) |
|------------|----------------|------------------------|
| `site_safeguards_focal_person` | Standard | L1 |
| `country_l1_fallback` | Standard | L1 fallback |
| `pd_piu_safeguards_focal` | Standard | L2 |
| `grc_chair` | Standard | L3 |
| `grc_member` | Standard | L3 |
| `adb_national_project_director` | Standard | Observer |
| `adb_hq_safeguards` | Standard | Observer / L4 |
| `adb_hq_project` | Standard | Observer |
| `seah_national_officer` | SEAH | SEAH L1 |
| `seah_hq_officer` | SEAH | SEAH L2 |
| `adb_hq_exec` | Both | Senior oversight |

Admin keys (`super_admin`, `country_admin`, `project_admin`) live in `ticketing.roles` for JWT consistency but appear only in platform **Admin access**, not the operational Roles tab.

---

## 7. Permissions (capability strings)

Fixed per `role_key` in seed — **not** editable via custom admin role factory in v1.

| Permission | Typical holders |
|------------|-----------------|
| `*` | `super_admin` |
| `projects:create`, `projects:manage` | `country_admin` (either track, country scope) |
| `settings:write`, `locations:manage`, `workflows:manage` | `country_admin` (standard track) |
| SEAH workflow / officer settings (no packages/orgs/locations) | `country_admin` + `workflow_track: seah` |
| `users:invite`, `users:manage`, `settings:project` | `project_admin` |
| `tickets:*`, `grc:*` | Operational roles |

---

## 8. Implementation status (gap vs spec)

| Item | Status |
|------|--------|
| Admin matrix in docs | ✅ Locked — 3 keys; `workflow_track` on country + project scope |
| `workflow_track` on admin scope + API enforcement | ✅ Migration `a2b4c6d8`; `admin_access.py` + router guards |
| `POST /roles` create + archetype permissions UI | ✅ API + Roles tab wizard |
| Filter operational vs admin in Roles API/UI | ✅ `GET /roles?kind=operational` |
| `role_origin` column + system role delete guard | ✅ Column + delete rules |
| Platform **Admin access** sub-tab | ✅ `super_admin` only |
| `local_admin` → matrix migration | ✅ Seed: `country-admin@grm.local` + scopes |
| `project_admin` + `workflow_track` on admin scope | ✅ `project-admin@grm.local` KL_ROAD standard |

---

## 9. SEAH visibility (operational roles)

| Role type | Standard tickets | SEAH tickets |
|-----------|------------------|--------------|
| Standard operational | Yes | No |
| SEAH operational | No | Yes |
| `super_admin`, `adb_hq_exec` | Yes | Yes |

SEAH workflow/officer management: **`country_admin`** with **`workflow_track: seah`**. **Any** scoped `country_admin` may **create projects** in their country; standard track additionally owns packages, orgs, and locations. SEAH workflow link may come from project type template or SEAH-track country admin edit on the project.

---

## 10. API (target)

| Method | Path | Access |
|--------|------|--------|
| `GET` | `/api/v1/roles?kind=operational` | Authenticated |
| `POST` | `/api/v1/roles` | Scoped `country_admin` / `super_admin` |
| `GET` | `/api/v1/roles?kind=admin` | `super_admin` (platform Admin access tab) |
| `PATCH` | `/api/v1/roles/{id}` | Track-scoped admin; permissions on system roles: `super_admin` only |
| `DELETE` | `/api/v1/roles/{id}` | If unused; system roles: `super_admin` only |

Officer assignment: [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md).

---

## 11. Acceptance criteria

1. Admin keys: **`super_admin`**, **`country_admin`**, **`project_admin`** only; track on scope, not extra role names.
2. **`workflow_track`** (`standard` \| `seah`) on country and project admin assignments; API enforces on every mutation.
3. `local_admin`, `seah_admin` deprecated → scoped `country_admin` / `project_admin`.
4. Operational Roles tab lists operational keys only; admin assignments in platform **Admin access**.
5. Scoped `country_admin` may **create projects** (either track); standard-track owns packages/orgs/locations; SEAH-track cannot create packages/orgs/locations.
6. Scoped `country_admin` can **create** custom operational roles (own track); `project_admin` cannot.
7. Country-wide vs project-scoped officers: **default jurisdiction on role** + **officer_scopes** at assignment.
8. Permissions allocated via **archetype templates** + grouped overrides; admin caps cannot leak onto operational roles.
9. **Workflows-first:** step editor binds roles; role wizard does not require picking a workflow. Optional inline create from step dropdown.
10. Roles list shows step + officer usage counts; delete guarded.
11. Party types remain in **Projects & packages**, not this tab.
