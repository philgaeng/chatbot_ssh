# Settings — overview and documentation index

**Status:** Product reference (June 2026). Admin ladder locked in [11_roles_and_permissions.md](11_roles_and_permissions.md); partial implementation — see §8 there.  
**Last updated:** 2026-09-07 — §2.1 added: search and filters on the organisation tree (`GRM-086`), including why a match keeps its ancestors and why the server's `q` cannot serve this screen. Earlier the same day, `GRM-085`: the main tab order is now **Projects & packages · Organizations & officers · Workflows · Settings**, reordered in the three tables that list it (§1, §2, §8) and given its reason in §2. Earlier: sprint citations folded — reasons kept inline, forks recorded in `DECISIONS.md` (lifecycle §10) · ⚠ header date backfilled; content not re-verified against the code
**UI:** `channels/ticketing-ui/app/settings/page.tsx`  
**Related:** [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md), [03_ticketing_api_integration.md](03_ticketing_api_integration.md)

This document is the **entry point** for all GRM admin configuration. Detailed specs live in numbered docs **10–14** (this file plus focused children).

---

> **⚠ Reinstated 2026-08-04 — [D-005](../DECISIONS.md#d-005--the-project-type-is-the-template-a-typed-project-cannot-deviate-from-it).** The organization-role catalog is **primary again**, on the **project type**: `project_types.actor_roles` names the organizations a project must have (label · description · required), and **every one of them sees that project's grievances** in its reports — a package-level naming reaches that package only, and a parent organization sees what its children see ([D-006](../DECISIONS.md#d-006--an-organizations-grievances-are-its-projects-grievances), 2026-08-04; the `routing_org_role` anchor is retired). Filled values live in `project_organizations` / `package_organizations`. Still dead: the **per-project** catalog `project_actor_roles` — the catalog is on the type now, not copied per project. `projects.implementing_agency_org_id` + `project_donors` become **legacy reads** and stop being written.

## 1. What Settings configures

| Area | Question it answers |
|------|---------------------|
| **Projects & packages** | How does a specific road/bridge project route tickets, link orgs, and go live? |
| **Organizations & officers** | Who are the commercial parties and operational officers? |
| **Workflows & GRM roles** | How do cases escalate and which officer role acts at each level? |
| **Platform** | Where are locations, report schedules, project archetypes, and system JSON keys? |

New tickets use **workflows linked on the project**, resolve context from **package → project + location → location only**, and assign officers whose **OfficerScope** matches (see [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md)).

---

## 2. Settings UI navigation (four main tabs)

| Main tab | Sub-tabs | Spec |
|----------|----------|------|
| **Projects & packages** | List → project editor | [13_projects_and_packages.md](13_projects_and_packages.md) |
| **Organizations & officers** | Organizations · Officers | Orgs: this doc §3; Officers: [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md) |
| **Workflows** | Workflows · **Project types** | [12_workflows_configuration.md](12_workflows_configuration.md) §6/§6.00 · model in [14 §4](14_platform_settings.md) · [11_roles_and_permissions.md](11_roles_and_permissions.md) |
| **Settings** (platform) | Locations · Quarterly reports · Advanced (JSON) · Admin access | [14_platform_settings.md](14_platform_settings.md) |

> **The order of the strip is a decision, not an accident (2026-09-07, `GRM-085`).** It is
> **outcome-first**: Projects leads because it is what the admin came to do, and because the page has
> defaulted to it since the go-live tab was removed — until the reorder, Settings opened with its
> active underline on the *third* tab. ⚠ **It is deliberately the reverse of the build order** —
> staffing needs officers, who need organizations; levels need workflows. That is safe here and only
> here, because the project console sequences those dependencies itself (Identity → Grievance
> workflows → Packages → Organizations → Staffing) and the go-live panel blocks on what is missing.
> **If the project console ever stops sequencing setup, this ordering loses its justification.**

### 2.1 Finding an organisation in the tree (`GRM-086`, 2026-09-07)

The organisation surface is a **forest** — the government reporting line plus independent roots —
and until this item it carried **no search and no filter at all**.

**Search filters in place, and a match keeps its ancestors.** A hit deep in the forest is not an
answer on its own: *"Division Office"* means nothing, *"DOR → Provincial Office 1 → Division
Office"* is the answer. Ancestors render as **context** — present, de-emphasised — and are **not
counted**, so five rows on screen read honestly as *"2 organisations match. 3 more shown to place
them."*

| Control | Reads | Note |
|---|---|---|
| Search | name · Nepali name · id | |
| **Type** | `unit_type` | ⚠ **Not `org_category`** — category is root-only and inherited, so filtering on it silently drops every child whose column is null. The two groups already express category |
| **Area** | `territory_location_code` | Options are the codes present on real organisations, not a location hierarchy — so it stays correct outside Nepal. ⚠ A level-grouped picker needs `location_level_defs` and is **not built** |

**No parent-organisation filter**, though it was asked for: the tree *is* the parent relationship,
so the control duplicates clicking a parent node while training the admin not to read the structure
the screen exists to show (Q-02).

⭐ **All of it is client-side, and the server's `q` parameter is deliberately unused here.**
`GET /api/v1/organizations?q=` returns a **flat filtered set**, so an organisation whose parent does
not match comes back *without its parent* and the forest cannot be rebuilt — a structural limit, not
a missing feature. `OrgTree` already fetches the whole forest in one call with every filter field on
each node. The predicate is
[`orgFilter.ts`](../../channels/ticketing-ui/components/settings/org/orgFilter.ts), pure and
unit-tested; the wireframe it was built from is
[`ui/07_org_directory_filters.html`](ui/07_org_directory_filters.html).

**Two empty states**, as on the officer directory: *"No organisation units yet"* offers Add; *"No
organisations match …"* names the term and offers **Clear the filters**. A filtered tree is forced
open, and **clearing the filter restores the default expansion** — otherwise the forest is left
half-collapsed and the filter appears to have broken it.

**Design rule:** Global directory, geographic reference data, and per-project routing stay in separate tabs. Tab 3 is the single place admins configure *how this project works*.

---

## 3. Access control — admin ladder (LOCKED)

**Admin matrix** (tier × workflow track): see [11_roles_and_permissions.md](11_roles_and_permissions.md) §2.

| Role | Tier | Track | Settings access |
|------|------|-------|-----------------|
| **`super_admin`** | Platform | Both | All tabs + **Settings → Settings** (platform) |
| **`org_admin`** | Country | **`workflow_track` on scope** (`standard` \| `seah`) | Country admin; standard track owns structure, SEAH track owns SEAH ops |
| **`project_admin`** | Project | **`workflow_track` on scope** (`standard` \| `seah`) | Project delegate; track set at appointment |
| **Operational officers** | — | — | No Settings |

`local_admin` / `seah_admin` are **deprecated** → scoped `org_admin` or `project_admin` + `workflow_track`.

### Settings UI matrix (target)

| Main tab | `super_admin` | `org_admin` | `project_admin` |
|----------|---------------|-----------------|-----------------|
| Projects & packages | ✅ | ✅ | ✅ assigned project(s) |
| Organizations & officers | ✅ | ✅ country | ✅ scoped |
| Workflows, roles & permissions | ✅ | ✅ | ✅ (roles catalog read) |
| **Settings** (platform) | ✅ | ❌ | ❌ |

Additional gates:

- **SEAH workflows:** `canSeeSeah` — SEAH operational roles + `super_admin` + `adb_hq_exec`; country/project admin SEAH powers TBD.
- **Platform sub-tab** (`super_admin` only): Locations import, Quarterly reports config, Advanced JSON, Admin access. **Project types moved to the Workflows tab 2026-08-04** — a type is mostly a bundle of workflows ([12 §6.00](12_workflows_configuration.md)); `org_admin` authors them for its own subtree.
- **Implementation note:** API/UI today still treat `local_admin` as `is_admin`; three-tier enforcement is not yet wired.

---

## 4. Role concepts in the product (three tables, three UI places)

| Concept | Where configured | Stored in | Example keys |
|---------|------------------|-----------|--------------|
| **Admin roles** | Settings → Settings → **Admin access** (`super_admin`) | `ticketing.roles` + scoped assignments | `super_admin`, `org_admin`, `project_admin` (+ `workflow_track` on scope) |
| **Operational GRM roles** | Workflows → **Roles & permissions** | `ticketing.roles`, `workflow_steps`, `user_roles`, `officer_scopes` | `site_safeguards_focal_person`, `grc_chair` |
| **Project participants** | Projects & packages → Partner organizations | The **project type's `actor_roles`** catalog, filled into `project_organizations` (reinstated 2026-08-04). `implementing_agency_org_id` + `project_donors` are legacy reads | implementing agency (1) + donors (0..n) |

No confusion between operational roles and project participants: different tabs, different tables. Admin roles are not mixed into the operational Roles tab.

Global party-role vocabulary (`settings.org_roles`) is **deprecated** (DECISION 2026-07-10) — the per-project actor-role catalog it seeds is legacy/back-compat, superseded by one **implementing agency** + optional **donors**. See [13_projects_and_packages.md](13_projects_and_packages.md).

---

## 5. Two different “project” tables (do not confuse)

| Table / concept | Owner | Spec |
|-----------------|-------|------|
| **`ticketing.projects`** | GRM ticketing | [13_projects_and_packages.md](13_projects_and_packages.md) — workflows, packages, QR, go-live |
| **`public.projects`** | Chatbot / SEAH catalog | [features/settings/settings_tab_projects_and_seah_contact_centers.md](features/settings/settings_tab_projects_and_seah_contact_centers.md) — `project_uuid`, CSV import, SEAH contact centers |

These share Postgres but serve different apps. Ticketing project `short_code` (e.g. `KL_ROAD`) is not the same as chatbot catalog `project_uuid`.

---

## 6. Settings key/value store (`ticketing.settings`)

JSON keys managed via API `GET/PUT /api/v1/settings/{key}` and parts of the UI:

| Key | UI surface | Who can write | Spec |
|-----|------------|---------------|------|
| `notification_rules` | Workflow editor panel | `org_admin`+ | [12_workflows_configuration.md](12_workflows_configuration.md) |
| `complainant_notifications` | Seeded; no dedicated UI yet | Admin | [06_messaging_rules_whatsapp_sms.md](06_messaging_rules_whatsapp_sms.md) |
| `org_roles` | Advanced (JSON) | `super_admin` only | **Deprecated** — a *global* role vocabulary is the wrong shape now that each **project type** carries its own `actor_roles` ([14 §4](14_platform_settings.md)). Originally DECISION 2026-07-10 — legacy party-role vocabulary; still seeds the deprecated actor-role catalog on project create |
| `report_limits` | Advanced (JSON) | `super_admin` only | [09_reports_and_report_builder.md](09_reports_and_report_builder.md) |
| `archiving_policy` | Advanced (JSON) | `super_admin` only | [docs/ARCHIVING_AND_RETENTION.md](../ARCHIVING_AND_RETENTION.md) |

`chatbot_webchat_url` is env-driven (`ticketing/config/settings.py`, `CHATBOT_WEBCHAT_URL`) — used for QR scan redirects, not the key/value table.

---

## 7. Child specification documents

| Doc | Contents |
|-----|----------|
| [11_roles_and_permissions.md](11_roles_and_permissions.md) | Admin ladder (3 levels) + operational GRM roles, UI placement |
| [12_workflows_configuration.md](12_workflows_configuration.md) | Workflow definitions, steps, SLAs, templates, notification matrix |
| [13_projects_and_packages.md](13_projects_and_packages.md) | Project editor, partner orgs (implementing agency + donors), staffing, packages, go-live, QR |
| [14_platform_settings.md](14_platform_settings.md) | Locations, quarterly report settings, project types, system JSON |
| [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md) | Officer invite, scopes, auto-assign |
| [06_messaging_rules_whatsapp_sms.md](06_messaging_rules_whatsapp_sms.md) | Staff WhatsApp/SMS policy |
| [16_org_chart_and_positions.md](16_org_chart_and_positions.md) | Org unit tree, position types, position→role matrix |
| [Escalation_rules.md](Escalation_rules.md) | SLA breach behaviour (runtime; configured via workflows) |

**Historical:** `docs/sprints/archive/claude-tickets/workflow-settings-spec.md` was the working draft for tabs 2–3; content is split into docs 10–14 above.

---

## 8. Open gaps (tracked)

| Gap | Notes |
|-----|-------|
| `workflow_assignments` table | Legacy fallback in `resolve_workflow()`; not exposed in UI; remove when safe |
| Chatbot `public.projects` Settings tab | Spec written; implementation in ticketing UI TBD — see features doc |
| Dedicated UI for `complainant_notifications` | Key seeded; officer channel matrix is in workflow editor |
| Admin scope `workflow_track` enforcement | Spec locked; code still uses legacy `local_admin` |
