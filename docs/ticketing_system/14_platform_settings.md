# Platform settings (locations, reports, types, system JSON)

**Status:** Product reference (June 2026). **Access:** `super_admin` only for this entire main tab — see [11_roles_and_permissions.md](11_roles_and_permissions.md) §2.  
**UI:** Settings → **Settings** (platform tab)  
**Related:** [10_settings_overview.md](10_settings_overview.md), [11_roles_and_permissions.md](11_roles_and_permissions.md), [09_reports_and_report_builder.md](09_reports_and_report_builder.md), [LOCATION_CODES.md](LOCATION_CODES.md), [docs/ARCHIVING_AND_RETENTION.md](../ARCHIVING_AND_RETENTION.md)

The fourth main Settings tab holds **platform-wide** configuration: national reference data, project archetypes, system JSON, and **admin role assignment**. `country_admin` and `project_admin` **cannot** open this tab. Per-project routing stays in [13_projects_and_packages.md](13_projects_and_packages.md).

---

## 1. Sub-tabs and access

| Sub-tab | `super_admin` | `country_admin` | `project_admin` |
|---------|---------------|-----------------|-----------------|
| **Locations** | ✅ import + tree | ❌ (tab hidden) | ❌ |
| **Quarterly reports** | ✅ | ❌ | ❌ |
| **Project types** | ✅ | ❌ | ❌ |
| **Advanced (JSON)** | ✅ | ❌ | ❌ |
| **Admin access** *(planned)* | ✅ | ❌ | ❌ |

**Note:** `country_admin` manages workflows, orgs, projects, and packages via the **other three** main Settings tabs (country scope). Quarterly report *planning* for local ops may move to a country-scoped surface later; v1 platform tab owns the library.

---

## 2. Locations

**Purpose:** Canonical geography tree for ticket `location_code`, officer scopes, and project location links.

### Data

- `ticketing.locations` — `location_code`, `name`, `name_ne`, `parent_code`, `level`, `country_code`
- `ticketing.location_translations` — EN/NE display names
- `ticketing.countries` — country lookup

Codes follow [LOCATION_CODES.md](LOCATION_CODES.md) (e.g. province `NP-KO`, district `NP-KO-JH`).

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

## 4. Project types (archetypes)

**Purpose:** `super_admin` defines reusable project templates (`construction_road`, …).

**Component:** `channels/ticketing-ui/components/settings/ProjectTypesTab.tsx`  
**API:** `ticketing/api/routers/project_types.py`

| Field on type | Copied to new project |
|---------------|----------------------|
| `type_key`, `label` | `project.project_type_key` |
| `standard_workflow_id`, `seah_workflow_id` | Project workflow links |
| Required actor role keys | `project_actor_roles` rows |
| `routing_org_role` | Go-live implementing-agency check |

`country_admin` and `project_admin` **cannot** edit type definitions or actor role keys on instantiated projects.

See [13_projects_and_packages.md](13_projects_and_packages.md) §3.

---

## 5. Admin access *(planned sub-tab)*

**Purpose:** Assign the **admin ladder** — who holds `country_admin` and scoped `project_admin` roles. Operational officer assignment stays under **Organizations & officers** / **Project staffing**.

| Action | Who performs |
|--------|----------------|
| Create `country_admin` | `super_admin` |
| Create `country_admin` (`country_code` + `workflow_track`) | `super_admin` |
| Create `project_admin` (project + optional org + `workflow_track`) | `country_admin` with **matching** track, or `super_admin` |
| Revoke admin access | Same as creator tier or `super_admin` |

**Not in this tab:** Operational GRM roles (`site_safeguards_focal_person`, …) — those are defined in **Roles & permissions** and assigned by `project_admin` / `country_admin` via Officers.

Full role semantics: [11_roles_and_permissions.md](11_roles_and_permissions.md) §2.

---

## 6. Advanced (JSON) — system configuration

**Component:** `SystemConfigTab` in `settings/page.tsx`  
**Access:** `super_admin` only

Three JSON editors:

### 6.1 `org_roles` (organization role vocabulary)

**Key:** `settings.org_roles`  
**Shape:** JSON array:

```json
[
  { "key": "donor", "label": "Donor", "description": "Financing institution" },
  { "key": "implementing_agency", "label": "Implementing Agency", "description": "..." }
]
```

**Usage:** Template when **creating** a new project — copied into `project_actor_roles`. Editing this key does **not** retroactively change existing projects.

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

**Other keys** (e.g. `notification_rules`) are writable by `country_admin`+ and edited from the workflow UI — see [12_workflows_configuration.md](12_workflows_configuration.md).

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
2. Super admin can import location tree, CRUD project types, edit Advanced JSON, and assign `country_admin`.
3. `country_admin` and `project_admin` are blocked from platform tab (API + UI).
4. `org_roles` JSON validates (array of `{key, label}`) before save.
5. `report_limits` and `archiving_policy` reject invalid shapes with 422.
6. Admin access sub-tab lists admin role holders; does not list operational officers.
