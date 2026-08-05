# Platform settings (locations, reports, types, system JSON)

**Status:** Product reference (June 2026). **Access:** `super_admin` only for this entire main tab — see [11_roles_and_permissions.md](11_roles_and_permissions.md) §2.  
**UI:** Settings → **Settings** (platform tab)  
**Related:** [10_settings_overview.md](10_settings_overview.md), [11_roles_and_permissions.md](11_roles_and_permissions.md), [09_reports_and_report_builder.md](09_reports_and_report_builder.md), [LOCATION_CODES.md](LOCATION_CODES.md), [18_geography_and_locations.md](18_geography_and_locations.md), [docs/ARCHIVING_AND_RETENTION.md](../ARCHIVING_AND_RETENTION.md)

The fourth main Settings tab holds **platform-wide** configuration: national reference data, project archetypes, system JSON, and **admin role assignment**. `org_admin` and `project_admin` **cannot** open this tab. Per-project routing stays in [13_projects_and_packages.md](13_projects_and_packages.md).

---

> **⚠ Reinstated 2026-08-04 — [`DECISION-author-defined-slots.md`](../sprints/2026-07_org_chart_positions/DECISION-author-defined-slots.md).** The organization-role catalog is **primary again**, on the **project type**: `project_types.actor_roles` names the organizations a project must have (label · description · required), and `routing_org_role` names which of them a ticket is stamped with — so nothing is hardcoded as "the implementing agency". Filled values live in `project_organizations` / `package_organizations`. Still dead: the **per-project** catalog `project_actor_roles` — the catalog is on the type now, not copied per project. `projects.implementing_agency_org_id` + `project_donors` become **legacy reads** and stop being written.


## 1. Sub-tabs and access

| Sub-tab | `super_admin` | `org_admin` | `project_admin` |
|---------|---------------|-----------------|-----------------|
| **Locations** | ✅ import + tree | ❌ (tab hidden) | ❌ |
| **Quarterly reports** | ✅ | ❌ | ❌ |
| **Advanced (JSON)** | ✅ | ❌ | ❌ |
| **Admin access** *(planned)* | ✅ | ❌ | ❌ |

**Note:** `org_admin` manages workflows, **project types**, orgs, projects, and packages via the **other three** main Settings tabs (country scope) — project types under Workflows ([12 §6.00](12_workflows_configuration.md)). Quarterly report *planning* for local ops may move to a country-scoped surface later; v1 platform tab owns the library.

---

## 2. Locations

**Purpose:** Canonical geography tree for ticket `location_code`, officer scopes, and project location links.

### Data

- `ticketing.locations` — `location_code`, `country_code`, `level_number`, `parent_location_code`, `source_id`, `latitude`/`longitude`, `is_active` (names live in translations)
- `ticketing.location_translations` — per-language display names (`location_code`, `lang_code`, `name`)
- `ticketing.location_level_defs` — level semantics per country (Province / District / Municipality)
- `ticketing.countries` — country lookup

Codes follow [LOCATION_CODES.md](LOCATION_CODES.md) (e.g. province `P1` = Koshi, district `P1_MOR` = Morang, `P1_JHA` = Jhapa). Full model: [18_geography_and_locations.md](18_geography_and_locations.md).

### UI (`LocationsSection`)

- Browse tree: country → province → district → municipality
- **Import:** CSV or JSON upload via `POST /api/v1/locations/import`
- Template downloads: `GET /api/v1/locations/template.csv`, `template.json`

### API

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/countries` | Country list |
| `GET` | `/locations` | Filter by `country_code`, `parent_code`, `level` |
| `GET` | `/locations/{code}` | Single node |
| `POST` | `/locations/import` | Bulk upsert (admin) |

**Rule:** Nepal deployments should keep codes aligned with chatbot location JSON where both are used.

---

## 3. Quarterly reports (Settings sub-tab)

**Purpose:** Configure the **Quarterly email** plan on the Reports page — not the operational Overview/Pivot tabs.

**Component:** `channels/ticketing-ui/components/settings/QuarterlyReportSettings.tsx`

| Feature | Detail |
|---------|--------|
| Report library | Named XLSX report definitions |
| Role assignments | Which roles receive which report each quarter |
| Caps | `settings.report_limits` — max assignments per role per quarter |

Full behaviour: [09_reports_and_report_builder.md](09_reports_and_report_builder.md) §4.

**API:** `ticketing/api/routers/reports.py` — library CRUD, assignments, Celery dispatch.

---

## 4. Project types (archetypes) — *the model; the screen lives under Workflows*

> **This is not a platform sub-tab.** Project types are authored under **Settings → Workflows →
> Project types** ([12 §6.00](12_workflows_configuration.md)) — a type is mostly a bundle of
> workflows, so it belongs beside them. **Moved 2026-08-04**; it shipped under platform data,
> where nobody looking at a workflow would find it. The model, the freeze rules and the
> validation stay documented here because every other doc already points at "14 §4".

**Purpose:** a project type is the **binding template** for a project — the workflows it runs, the organizations it must name, and how categories route ([DECISION-author-defined-slots](../sprints/2026-07_org_chart_positions/DECISION-author-defined-slots.md)). Creating a project is: pick the organization → pick one of its types → allocate the remaining organizations.

**Component:** `channels/ticketing-ui/components/settings/ProjectTypesTab.tsx` — built 2026-08-04: one card per type, and an editor for the workflows, the organization catalog, the routing anchor and the owner. The workflow cards are the project screen's own (`<WorkflowBindingCards>`, shared) — a type is mostly a bundle of workflows, so authoring one looks like editing one.
**API:** `ticketing/api/routers/project_types.py`

**Who:** `super_admin` anywhere; `org_admin` within its own subtree — the same gate as authoring a workflow. A `project_admin` does not see the sub-tab.

**Organization keys are never typed or shown.** The author writes the label ("Ward Office"); the key is derived from it once and then never changes, because filled organizations point at it. Renaming a role therefore never orphans anything.

| Field on type | What it gives the project |
|---------------|----------------------|
| `type_key`, `label` | `project.project_type_key`. **`label` is always editable**, even with live projects — a name is not configuration |
| `owner_organization_id` | The top-level organization this template belongs to (`l8n0p2r4`). **NULL = global.** New project offers the chosen organization's types + global ones |
| `workflow_bindings` | The project's workflow links — name, workflow, default, `intake_route`, `classifications` |
| `actor_roles` | **The organization catalog** (primary again): `{key, label, description, required, required_package, scope}`. The author's words — "Executing Agency", "Ward Office", "Concessionaire" |
| `routing_org_role` | **Which** of those roles a ticket is stamped with. An author-chosen key, so nothing is hardcoded as "the implementing agency" |
| `standard_workflow_id`, `seah_workflow_id` | Legacy mirrors of the bindings |

### 4.1 A type with a live project is frozen

Once **any active project** runs on a type, its **configuration** cannot change — `PATCH` returns **409** naming how many projects are at stake and both ways out. Enforced server-side, not by disabling the form.

| | |
|---|---|
| **Frozen** | workflows, `actor_roles`, `routing_org_role`, `owner_organization_id`, category routing |
| **Always editable** | `label`, `description` (a name is not configuration) · `is_active`, `sort_order` (availability — retiring a type from the New-project list changes nothing about projects using it) |
| **Two ways out** | **Use as template** — `POST /project-types/{key}/duplicate` copies everything into a new key, `is_active=false` so an unfinished edit is never offered · or **deactivate the project**, fix the type, reactivate (which re-runs go-live) |

`active_project_count` on the type response drives the UI's frozen state.

**Back-filled 2026-08-04** (`n0p2r4t6`): every previously-untyped project got a type derived from the workflows it already ran, named "Type 1", "Type 2" — rename them. Only the routing anchor is marked required, so no project was blocked by its own migration.

`org_admin` authors types **within its own org subtree**; `super_admin` anywhere. Neither `org_admin` nor `project_admin` can edit a type's definition through a project — a typed project cannot deviate from its type. A **global** type (owner NULL) is offered to everyone, so only `super_admin` may change it; an `org_admin` copies it instead (403 names that way out).

**Checked on every write** (`_validate_config`, 422 in plain language):

- `routing_org_role` must be one of the type's **own** organization roles — a type can never name an anchor it doesn't have
- role names are unique and non-empty
- the workflow set has **exactly one** default, the default is never a sensitive workflow, every non-default names a chatbot menu, and a category belongs to one workflow only

`standard_workflow_id` / `seah_workflow_id` are derived from the bindings on save, so the legacy mirrors cannot drift from what the type actually runs.

See [13_projects_and_packages.md](13_projects_and_packages.md) §3.

---

## 5. Admin access *(planned sub-tab)*

**Purpose:** Assign the **admin ladder** — who holds `org_admin` and scoped `project_admin` roles. Operational officer assignment stays under **Organizations & officers** / **Project staffing**.

| Action | Who performs |
|--------|----------------|
| Create `org_admin` | `super_admin` |
| Create `org_admin` (`country_code` + `workflow_track`) | `super_admin` |
| Create `project_admin` (project + optional org + `workflow_track`) | `org_admin` with **matching** track, or `super_admin` |
| Revoke admin access | Same as creator tier or `super_admin` |

**Not in this tab:** Operational GRM roles (`site_safeguards_focal_person`, …) — those are defined in **Roles & permissions** and assigned by `project_admin` / `org_admin` via Officers.

Full role semantics: [11_roles_and_permissions.md](11_roles_and_permissions.md) §2.

---

## 6. Advanced (JSON) — system configuration

**Component:** `SystemConfigTab` in `settings/page.tsx`  
**Access:** `super_admin` only

Three JSON editors:

### 6.1 `org_roles` (organization role vocabulary) — deprecated

**Key:** `settings.org_roles`  
**Shape:** JSON array:

```json
[
  { "key": "donor", "label": "Donor", "description": "Financing institution" },
  { "key": "implementing_agency", "label": "Implementing Agency", "description": "..." }
]
```

**Usage (still deprecated, for a new reason):** a **global** role vocabulary is the wrong shape — since 2026-08-04 each **project type** carries its own `actor_roles` so a client can use the words on their contract. This key is legacy; it is still copied into `project_actor_roles` on project create, and that per-project catalog is **dead** (DECISION 2026-07-10; superseded by the implementing agency + donors). Editing this key does **not** retroactively change existing projects.

Default keys include: `donor`, `executing_agency`, `implementing_agency`, `main_contractor`, `subcontractor_t1`, `subcontractor_t2`, `supervision_consultant`, `specialized_consultant`.

### 6.2 `report_limits`

**Key:** `settings.report_limits`  
**Writer:** `ticketing/services/report_limits.py` — validates and merges on save.

Default caps (per role per quarter):

```json
{
  "max_assignments_per_role_per_quarter": 3,
  "export_rate_limit_per_user_per_hour": 10
}
```

See [09_reports_and_report_builder.md](09_reports_and_report_builder.md).

### 6.3 `archiving_policy`

**Key:** `settings.archiving_policy`  
**Writer:** `ticketing/services/archiving_policy.py`

Controls resolved-case archiving schedule and attachment tiering. Documented in [docs/ARCHIVING_AND_RETENTION.md](../ARCHIVING_AND_RETENTION.md).

---

## 7. Settings API (`ticketing/api/routers/settings.py`)

| Method | Path | Access |
|--------|------|--------|
| `GET` | `/settings` | Authenticated — list all keys |
| `GET` | `/settings/{key}` | Authenticated |
| `PUT` | `/settings/{key}` | Admin; `org_roles`, `report_limits`, `archiving_policy` require `super_admin` |
| `DELETE` | `/settings/{key}` | Admin (same super-admin gate) |

**Other keys** (e.g. `notification_rules`) are writable by `org_admin`+ and edited from the workflow UI — see [12_workflows_configuration.md](12_workflows_configuration.md).

---

## 8. Environment (not in key/value table)

| Setting | Source | Used for |
|---------|--------|----------|
| `CHATBOT_WEBCHAT_URL` | `ticketing/config/settings.py` | QR scan redirect base URL |
| `TICKETING_SECRET_KEY` | env | Chatbot → `POST /api/v1/tickets` auth |
| Keycloak / bypass auth | env | Officer login |

---

## 9. Organizations (related — tab 1)

Global org directory is under **Organizations & officers → Organizations**, not the platform tab.

| API | Purpose |
|-----|---------|
| `GET/POST/PATCH/DELETE /organizations` | Org CRUD |
| `organization_id` | Server-generated from name initials + country |

Orgs are linked to projects via project actors, not as a standalone platform setting.

---

## 10. Acceptance criteria

1. Only `super_admin` can open the **Settings → Settings** (platform) main tab.
2. Super admin can import location tree, CRUD project types, edit Advanced JSON, and assign `org_admin`.
3. `org_admin` and `project_admin` are blocked from platform tab (API + UI).
4. `org_roles` JSON validates (array of `{key, label}`) before save.
5. `report_limits` and `archiving_policy` reject invalid shapes with 422.
6. Admin access sub-tab lists admin role holders; does not list operational officers.
