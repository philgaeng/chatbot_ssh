# Projects and packages

**Status:** Product reference — **reconciled 2026-07-30**: reflects the participants DECISION (2026-07-10, actor-role catalog → implementing agency + donors + staffing) and the staffing/go-live redesign (2026-07-30)  
**UI:** Settings → **Projects & packages**  
**Code:** `ticketing/api/routers/locations.py` (projects/packages), `ticketing/services/project_go_live.py`, `ticketing/services/project_types.py`  
**Related:** [10_settings_overview.md](10_settings_overview.md), [12_workflows_configuration.md](12_workflows_configuration.md), [11_roles_and_permissions.md](11_roles_and_permissions.md), [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md)

This document covers **`ticketing.projects`** and related package/QR configuration. For the chatbot **`public.projects`** catalog (SEAH picker, CSV import), see [features/settings/settings_tab_projects_and_seah_contact_centers.md](features/settings/settings_tab_projects_and_seah_contact_centers.md).

> **⚠ Revised 2026-07-10 — project participants simplified. See [`DECISION-project-participants-and-supervision.md`](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md).** The per-project **actor-role catalog** (`project_actor_roles`, `project_organizations.org_role`, `project_types.actor_roles`, `routing_org_role`, the "+ Add role" action, `GET/PUT /projects/{id}/actor-roles`) is **removed**. A project now carries one defaulted **`implementing_agency_org_id`** (the signing ministry — routing/reporting anchor; `government`/`local_government` only) + optional **`project_donors`** (0..n). **Go-live gates on staffing** — every workflow level has an officer — plus the **donor last-step-informed guardrail** (SEAH-suppressed). Sections below that still describe the actor-role model are **superseded** by the DECISION; the build reconciles them (OC-03 / doc-13 work).
>
> **Build reality, superseded 2026-08-04.** The paragraph below described the actor-role tables as deprecated-but-present. [`DECISION-author-defined-slots`](../sprints/2026-07_org_chart_positions/DECISION-author-defined-slots.md) **reinstates the catalog on the project type**: `project_types.actor_roles` names the organizations, `project_organizations` / `package_organizations` store what fills them. Only **`project_actor_roles`** (the per-project copy) stays dead. Kept for history: the actor-role tables/models were **kept, not dropped** — `project_actor_roles` / `project_organizations` / `package_organizations` are still defined and **still seeded on project create** (`locations.py`), and routing/go-live use `org_role` as a **back-compat fallback**. The new model (`implementing_agency_org_id` + `project_donors` + the staffing go-live gate) is **primary**; the legacy catalog is **deprecated**. Physically dropping it is outstanding cleanup (see followups) — the DECISION's "removed" is intent, not as-built.

---

> **⚠ Reinstated 2026-08-04 — [`DECISION-author-defined-slots.md`](../sprints/2026-07_org_chart_positions/DECISION-author-defined-slots.md).** The organization-role catalog is **primary again**, on the **project type**: `project_types.actor_roles` names the organizations a project must have (label · description · required), and **every one of them sees that project's grievances** in its reports — a lot-level naming reaches that lot only, and a parent organization sees what its children see ([DECISION-organization-membership](../sprints/2026-07_org_chart_positions/DECISION-organization-membership.md), 2026-08-04; the `routing_org_role` anchor is retired). Filled values live in `project_organizations` / `package_organizations`. Still dead: the **per-project** catalog `project_actor_roles` — the catalog is on the type now, not copied per project. `projects.implementing_agency_org_id` + `project_donors` become **legacy reads** and stop being written.


## 1. Purpose

A **project** is the routing hub for a financed infrastructure intervention (e.g. KL Road):

- Which **workflows** handle its grievances — one **default**, plus any others the project needs (§5B)
- Its **implementing agency** (the accountable ministry) and optional **donors**
- Which **locations** and **packages** (lots/segments) exist
- Whether the project is **active** and can **accept tickets**

### Who edits what (admin matrix)

| Action | `org_admin` `track=standard` | `org_admin` `track=seah` | `project_admin` |
|--------|-------------------------------|------------------------------|-----------------|
| Create **project** | ✅ country | ✅ country | ❌ |
| Create **package** | ✅ country | ❌ | ❌ |
| Edit **safeguards / hazards / CA** workflows on project | ✅ | ✅ `track=standard` | ❌ |
| Edit **SEAH** workflow / SEAH staffing | ✅ | ✅ `track=seah` | ✅ if scope `track=seah` |
| Set **implementing agency** / add **donors** | ✅ | ❌ | ✅ on assigned project (standard track) |
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
| `implementing_agency_org_id` | **Legacy read.** Was the one accountable org (signing ministry; `government`/`local_government` only). Reporting is membership now — [DECISION-organization-membership](../sprints/2026-07_org_chart_positions/DECISION-organization-membership.md) — and this is kept only so pre-types projects still pass go-live B1 and still stamp a ticket |
| `officer_messaging` | JSON: `sms_enabled`, `sms_levels[]`, `whatsapp_levels[]` — see [06_messaging_rules_whatsapp_sms.md](06_messaging_rules_whatsapp_sms.md) §6 |
| `standard_workflow_id` | Legacy mirror of `safeguards` slot |
| `seah_workflow_id` | Legacy mirror of `seah` slot |

### `ticketing.project_workflows`

N rows per project — each one a **named link**: `display_label` (the project's own name for it) + `workflow_id` + routing (`intake_route`, `classifications`) + `is_default`. **No `slot_key`** — dropped 2026-07 by `c5e7f9a1_workflow_classifications`. See [12_workflows_configuration.md](12_workflows_configuration.md) §2.

(The stray `chatbot_url` row that used to sit here belongs to `ticketing.projects` and is called **`chatbot_base_url`** as built — optional override for the QR redirect, `ticketing/models/project.py`.)

### `ticketing.project_donors`

`(project_id, organization_id)` — **0..n** donor orgs (category `donor`). Drives the donor last-step-informed guardrail (§7 A5). [DECISION §3](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md).

### `ticketing.project_organizations` — primary again · `ticketing.project_actor_roles` — dead

**Amended 2026-08-04** ([DECISION-author-defined-slots](../sprints/2026-07_org_chart_positions/DECISION-author-defined-slots.md)). The two tables part company:

- **`project_organizations` (`organization_id`, `org_role`) is the store for filled organization slots.** `org_role` holds a `key` from the project type's `actor_roles` catalog. Primary, not legacy.
- **`project_actor_roles` stays dead.** The catalog lives on the **type** now — one per archetype — not copied per project. That is the half of the July decision that survives: no per-project role vocabulary, because that is how vocabularies drift.

`implementing_agency_org_id` + `project_donors` become **legacy reads** for projects created before the change, and stop being written.

### `ticketing.packages` (`project_packages`)

Physical lots within a project. Fields: `package_id`, `project_id`, `name`, `is_active`.

### `ticketing.package_organizations` — the per-lot half of the catalog

Holds organization slots filled **for one lot** — the catalog entries the type marks `required_package` / `scope: package` (e.g. a different contractor on lot 3). Reinstated with the catalog 2026-08-04.

Per-lot variation in **people** is a different thing and remains a **staffing override** (position-first, §5A): a package can override a workflow level's staffing, otherwise it inherits the project-wide staffing.

### `ticketing.package_locations`

Many-to-many: package ↔ `location_code`.

### `ticketing.qr_tokens`

Opaque token → `package_id`; public scan URL. See [10_settings_overview.md](10_settings_overview.md) §6 and `GET /api/v1/scan/{token}`.

---

## 3. Project types (archetypes)

Authored by `super_admin` (anywhere) or `org_admin` (its own subtree) under **Settings → Settings tab → Project types** (`ProjectTypesTab`). See [14_platform_settings.md](14_platform_settings.md) §4.

**A project may change type while it is not accepting grievances** (2026-08-04): `PATCH /projects/{id}` with `project_type_key` re-applies the new type's workflow links and **removes** organizations named against roles the new type does not have. On a **live** project it is refused with **409** — deactivate, change, reactivate (which re-runs go-live). See [DECISION-author-defined-slots §8](../sprints/2026-07_org_chart_positions/DECISION-author-defined-slots.md), revisited.

**A typed project's Grievance workflows section is read-only** (§8 of the decision, as built 2026-08-04) — for **everyone**, `super_admin` included. It shows the **project type picker** plus a read-only list of the workflows that type brings (name · workflow · which is the catch-all · chatbot menu · categories) — `ProjectWorkflowsSummary`. The previous screen rendered the full editor with every control disabled, which is a form that lies about being a form. `PUT /projects/{id}/workflows` returns **409** on a typed project, so the rule is enforced server-side rather than by a disabled form. Only a legacy untyped project still edits its workflows inline. The project header shows the type's **name** (not its key) and links to it.

- Bundles the workflows a project runs (`workflow_bindings`) — name, workflow, default, chatbot menu, categories
- Carries the **organization catalog** (`actor_roles`) the project must fill. **Primary again 2026-08-04.** No entry is privileged: every organization named on a project sees its grievances ([DECISION-organization-membership](../sprints/2026-07_org_chart_positions/DECISION-organization-membership.md))
- On **New project** (as built 2026-08-04, `ProjectCreateModal`): pick the **organization** → only its types (its own, its parents', plus the global ones — `GET /project-types?owner_organization_id=…`) → the project inherits the type's workflow links, and the chosen organization is written straight into the type's **first required** organization role as a `project_organizations` row
- **A type is required.** `POST /projects` without `project_type_key` returns 422: without one there is no catalog for go-live's B1 to check, and a project could activate with no accountable organization at all
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

> **Redesigned 2026-07-30 (target — see mockup [`ui/04`](ui/04_projects_packages_redesign.html)).** Two-pane console: a sticky go-live rail + one section at a time. This order supersedes the old actor-role sections.
>
> **Amended 2026-08-02:** **Classifications is no longer its own section** — category routing moved onto the workflow card it belongs to, so all of a project's routing is one screen (§5B).

| # | Section | Purpose |
|---|---------|---------|
| 1 | **Identity** | Name, short code, description |
| 2 | **Overview & go-live** | Binary readiness checks (§7) + Activate / Deactivate |
| 3 | **Grievance workflows** | Name each workflow, bind it to a published one, set the **default**, and say which chatbot menu + categories come to it (§5B) |
| 4 | **Officer messaging** | Optional officer assignment SMS — see [06_messaging_rules_whatsapp_sms.md](06_messaging_rules_whatsapp_sms.md) §5 |
| 5 | **Partner organizations** | Implementing agency + optional donors *(no actor-role catalog — DECISION 2026-07-10)* |
| 6 | **Project-wide staffing** | Fill each workflow level's cast — position-first (§5A) |
| 7 | **Linked locations** | Province / district / municipality coverage |
| 8 | **Packages** | Lots: metadata, locations, QR, per-lot **staffing override** (§5A) |

Current as-built components: `ProjectGoLivePanel`, `ProjectStaffingSection`, `ProjectOfficerModal` (the redesign replaces the old `ProjectActorAddRow` + actor sections).

**Staffing & officer assignment** are specified authoritatively in **[§5A](#5a-staffing--position-first-officer-assignment)** (position-first). Coverage gaps show inline per workflow level and in the go-live rail (§7).

---

## 5A. Staffing — position-first officer assignment

**Status: authoritative (2026-07-30).** Specifies **how an admin fills a staffing slot** on a project or a package. Supersedes the "Add officer modal" / "Staffing section" notes in §5 for the assignment flow. **No backend contract changes:** the engine still assigns per ticket from **role + `officer_scopes`** pools ([07](07_officer_management_and_assignment.md), [DECISION §5–7](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md)); **positions** (`officer_positions` / `position_types`, [16](16_org_chart_and_positions.md)) are the human-facing handle the UI leads with. The build must follow this section exactly.

### 5A.1 What a slot is
Each **workflow level** exposes the **cast tiers its step declares** (actor / supervisor / participant / observer). Each tier carries a **name and a short description** that both start from a **sensible default** (from the tier type — e.g. a supervisor defaults to *"oversees; can reassign"*) and are **editable by the workflow author in the Workflows tab** ([12 §6.2](12_workflows_configuration.md)) — e.g. L1 actor named "Safeguard Officer", L3 actor "GRC Chairman". The label is a **workflow property**: set once in the Workflows tab, then shown **read-only** wherever the tier appears (staffing, case view). The staffing screen shows those (default or author-edited) labels; it never shows generic tier words ("Handles it", "owns the case", etc.).

### 5A.2 The two-step fill (LOCKED)
Filling a slot is always **position first, then person** — never a free officer search:

1. **Choose the position** (a seat = **position type @ org unit**).
   - **This step is where the position is linked to the workflow role** — the admin picks which position plays this role. Candidates = positions held by officers **within the slot's location scope** (§5A.3); the position→role matrix ([16 §4](16_org_chart_and_positions.md)) surfaces the sensible default first but does **not** hard-restrict the choice. (So a position does not "already carry" the role — the link is made here.)
   - **If the position does not exist → create it inline** (position type + org unit; the position→role matrix pre-fills the role, [16 §4](16_org_chart_and_positions.md)) and continue to step 2 — *create-and-assign in one action*.
2. **Choose the officer who holds that position.**
   - Pick from the holders within scope → assigned. This ensures the officer's `officer_scopes(project, location, role)` row for the level.
   - **If no one holds it (vacant) → invite an officer into the position** — the invite-as-result flow ([16 §5.2](16_org_chart_and_positions.md); `channels/ticketing-ui/components/settings/officers-v2/InviteOfficer.tsx`): the position pre-fills **role + org + scope**; admin enters **name + email**; Keycloak sends a set-password invite; the pending officer is assigned.

**Exactly one flow, two steps, two escape hatches** (create position · invite officer). No parallel "reuse / anchor / search" columns, no competing primary buttons.

### 5A.3 Location scope — who is eligible
Eligible positions/officers are those whose **territory covers the slot's location _or any ancestor_ of it** — a package in a **municipality** may be staffed by officers at that municipality **and** its **district** and **province** (higher offices legitimately cover lower areas). Territory model: [16 §3.1](16_org_chart_and_positions.md) (`territory_location_code`, `includes_children`) + `officer_scopes.location`; ranking prefers own-office then least-loaded ([16 §5.4](16_org_chart_and_positions.md)).

- **Slot location** = the **package's location** for package staffing; the **project's linked locations** for project-wide staffing.
- **Scope — progressive, narrow-first (LOCKED).** The picker **starts at the slot's own level** (e.g. the package's **municipality**) and shows only officers located **there**. **If that level has no officers, it climbs to the next ancestor** — municipality → district → province → national — and **stops at the first level that has candidates**. The admin may then **widen** further (pull in higher levels) or **narrow** back. Default = the *nearest* level that actually has officers, most-local first — so local staff are preferred and higher offices are only pulled in when the local level is empty.

### 5A.4 After assignment — continuity
The slot records the **anchored seat** (position @ org unit) **and** the assigned **officer**. On transfer the seat persists; the admin **reassigns** the new holder in one step. The anchor is a staffing-side hint; the engine still resolves the person from the role + scope pool.

### 5A.5 Tier specifics (which tiers must be staffed)
- **Required tiers are decided by the workflow author, per step** ([12 §6.2](12_workflows_configuration.md)). The **actor tier is always required**; the author additionally marks whether **supervisor / participant / observer** are mandatory. Go-live **blocks** on any **required** tier that is unstaffed; the **L1 actor unstaffed also blocks intake** ([DECISION §7](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md)). Tiers the workflow leaves optional never block.
- **Supervisor** defaults to the **next level's handler pool** (shown with provenance), overridable to a position + person. When a step marks supervisor mandatory, that default satisfies it — **except the top step**, which has no default and **requires an explicit** one ([DECISION §5](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md)).
- **Participant / observer** may be role pools rather than a single seat. The **donor guardrail** auto-adds ≥1 donor role to the **last standard step's** informed tier and blocks go-live if absent (SEAH-suppressed, [DECISION §3](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md)) — this is independent of the author's `required_tiers`.

### 5A.6 UI reference
Position-first picker mockup: [`ui/04_projects_packages_redesign.html`](ui/04_projects_packages_redesign.html) (Staffing pane). Reuses `officers-v2/InviteOfficer` (invite escape hatch) and the org-tree / position-type pickers ([16 §9](16_org_chart_and_positions.md)) (create-position escape hatch).

---

## 5B. Grievance workflows — the project editor screen

**Status: authoritative (2026-08-02).** Replaces the old "one row per stream" layout **and** the separate **Classifications** section — category routing now sits on the workflow card it belongs to, so a project's whole routing picture is one screen. Wireframe: [`ui/04`](ui/04_projects_packages_redesign.html) (Grievance workflows pane). Data model + resolution order: [12 §2 / §8](12_workflows_configuration.md). **No backend change** — the screen edits the as-built `project_workflows` columns.

### 5B.1 What the admin does, in order
1. **Choose the default workflow** — name it, then bind it to a published workflow. It is used **when nothing else matches**. Until it is set the project cannot go live (§7 A1).
2. **Add more workflows only if some grievances need a different one** — same two fields, plus the rules that send grievances there.
3. There is **no third step**: categories are set on the card, not in a separate section.

### 5B.2 The card — one per link
| Field | Column | Notes |
|---|---|---|
| **Name** | `display_label` | The project's own name for this workflow, **independent of the workflow's own name** — the same published workflow can appear under different names on different projects. Required. |
| **Workflow** | `workflow_id` | Published workflows only. Sensitive ones are listed only for an admin with the **configure** capability (`can_configure_sensitive`) — *not* `can_see_seah`, which is case access ([DECISION §3](../sprints/2026-07_org_chart_positions/DECISION-sensitive-workflows.md)). **+ Create a new workflow…** opens the clone modal; **Edit steps ↗** deep-links to the step-cast editor ([12 §6.2](12_workflows_configuration.md), [`ui/06`](ui/06_workflows_step_cast_editor.html)). |
| **🔒 Sensitive** badge | `is_sensitive` **on the bound workflow** (as-built: `workflow_definitions.workflow_type == 'seah'`) | **Derived and read-only here.** It is not a property of the card or of the project — the card *reflects* the workflow it points at, so the badge appears, disappears, and re-styles the card **when the Workflow picker changes**. It is set in one place only: the **Sensitive workflow** checkbox in the workflow editor ([12 §6.2](12_workflows_configuration.md), [`ui/06`](ui/06_workflows_step_cast_editor.html)). Never editable from the project screen — a project cannot make someone else's workflow sensitive, or stop it being so. |
| **Default** | `is_default` | Exactly one per project. The default carries **no** routing rules — that is what makes it the catch-all. **A sensitive workflow cannot be the default**, so the default card's picker does not offer them (server: 422, §5B.3). |
| **Chatbot menu** | `intake_route` | Non-default cards only, and **required** there (`new_grievance` · `road_hazard_grievance` · `seah_intake`). |
| **Categories** | `classifications` | Chips. Applied at intake and when an officer changes the category — the re-route only moves grievances that came in on the safeguards menu ([12 §8](12_workflows_configuration.md)). A category belongs to **one** card. |
| **Remove** | — | On every card except the default. A sensitive card is removable like any other. |

### 5B.3 Sensitive workflows (SEAH)
**Governed by [`DECISION-sensitive-workflows.md`](../sprints/2026-07_org_chart_positions/DECISION-sensitive-workflows.md) (2026-08-02).** SEAH is **not a mode** — it is the name someone gave a workflow. The one thing that makes it different is the workflow's **sensitive** property.

**On this screen there is no special SEAH card.** A sensitive card is renamable, removable and optional exactly like the others; a project may have none. Three things follow from the *bound workflow*, not from the card:

| | |
|---|---|
| **The 🔒 Sensitive badge** | Derived from the bound workflow, read-only here (§5B.2). Change the Workflow picker and the badge follows. |
| **It cannot be the default** | The default takes every grievance matching nothing else; if it were sensitive those would land where only its cast can see them. Enforced server-side — **422**, `services/project_workflows.py` (built 2026-08-02, pinned by `tests/ticketing/test_sensitive_workflow_access.py`). The default card's picker therefore does not list sensitive workflows. |
| **Who can see the grievances** | **Only officers cast on that workflow's steps.** Not admins, not oversight roles, not `super_admin` — configuring a sensitive workflow (authoring, staffing, inviting) grants no case or PII access (DECISION §3, built). A `super_admin` who needs a case staffs themselves onto the workflow: an audited assignment. ADB safeguards staff get access the same way — cast on the workflow, observer tier is enough. |

Also as-built: `validate_step_roles` forbids a standard-scoped role on a sensitive step, and only an admin with the configure capability may edit a sensitive workflow ([11_roles_and_permissions.md](11_roles_and_permissions.md) §2). Go-live check **A2** ("SEAH workflow configured") is **removed** — §7.

> **Correction kept for the record.** An earlier draft of this section claimed the SEAH card "cannot be removed" and "cannot be made the default". The first was never true and is not true now; the second was aspiration — `project_workflows.py` had **no** SEAH special-casing until the 422 above was built.

> **Naming lag.** The code still says `workflow_type == 'seah'` / `is_seah` / `workflow_track`; the *behaviour* above is as-built. The rename to `is_sensitive` follows with its migration ([DECISION §6–7](../sprints/2026-07_org_chart_positions/DECISION-sensitive-workflows.md)).

### 5B.4 Copy (LOCKED)
**"Stream" and "slot" never appear on screen** — the word is **workflow** ([ui/05 §4](ui/05_ui_copy_style.md)). The default is explained as *"used when nothing else matches"*, never "catch-all", "fallback", or "binding". The chatbot-menu options are complainant-facing menu names, so they follow the same guide — the current `INTAKE_ROUTE_CATALOG` labels still carry jargon ("safeguards GRM", "fast path") and are logged for cleanup ([followup](../sprints/2026-07_org_chart_positions/followups/workflow-stream-vocabulary-and-intake-route-labels.md)).

---

## 6. Ticket routing (uses project config)

### Workflow selection

```
ticket.project_id + intake_route (story_main) | is_seah
  → project_workflows: intake_route match → (re-classify) category match → default
     (fallback: standard_workflow_id | seah_workflow_id)
```

See [12_workflows_configuration.md](12_workflows_configuration.md) §8.

### Context priority (intake)

1. **Package** — QR `package_id`
2. **Project + location**
3. **Location only**

### Organization on ticket

**Implemented:** `ticketing.services.project_routing.resolve_ticket_organization()`.

`resolve_ticket_organization()` sets `tickets.organization_id`, a **descriptive stamp** since 2026-08-04. Order: the **lot's** first organization (a lot is more specific) → the organization filling the project type's **first required** role → `implementing_agency_org_id` → any organization named on the project.

> **Superseded 2026-08-04 — [DECISION-organization-membership](../sprints/2026-07_org_chart_positions/DECISION-organization-membership.md).** The stamp no longer decides who sees a grievance, so nothing about it is authored any more. **Which organizations see a project's grievances** is answered by membership — `services/org_reach.py`, §6.1 below. The stamp survives because `tickets.organization_id` is NOT NULL and rides along in a few payloads. Pinned by `test_project_type_freeze.py::test_stamp_follows_the_first_required_role`.

### 6.1 Which grievances belong to an organization

**`ticketing/services/org_reach.py`** — the one answer, used by `GET /tickets?organization_id=`,
the report query and the XLSX export:

> Every organization named on a project sees that project's grievances. An organization named on
> **one lot** sees that lot only. A **parent** organization sees everything its children see.

Same shape as the location filter (`_location_codes_with_descendants`), applied to the org tree
via `descendant_org_ids`. An organization named nowhere matches **nothing** — not everything.
The export's column is **"Organizations"** (plural) and lists them all: a grievance belongs to
several, so one id was one true name and several missing ones.

**Call sites:**

- `create_ticket_from_intake()` — sets `ticket.organization_id` before workflow + `auto_assign_for_workflow_step()` (webhook and sync backfill).
- `validate_jurisdiction()` — field operational roles with project/package scope; overrides invite/add-scope org to match routing (observers with `jurisdiction_mode=country` unchanged).

Chatbot may still send `organization_id: "DOR"` in the webhook body; ticketing resolves from project config when `project_code` / `package_id` is set.

**UI (invite):** Settings → Officers pre-selects the same org when a project is chosen — see [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md) §4.1.

### Officer assignment

`auto_assign_officer()` matches step `assigned_role_key` + `officer_scopes` to ticket fields. Package-first when `package_id` set.

---

### 5A.6 Staffing, as built 2026-08-04

**One screen, `ProjectCastSection`.** Per-lot staffing left the Packages section: a lot is where
you say *where* the work is and *which organizations* do it; *who works each level* is one place,
so you can see at a glance where a lot differs instead of opening each lot in turn.

- **One tab per workflow.** Each has its own levels, and staffing them is a separate job. (A
  dropdown hid the fact that a second workflow existed.)
- **Levels run last → first** (L4 → L1), the reverse of how a grievance travels. The upper ladder
  is the stable part you settle once; the lower levels are the ones that vary by lot, so the
  screen gets more specific as you work down.
- **A level staffed per lot asks for an officer on each lot, inline** — read from
  `workflow_steps.staff_per_package` ([12 §2](12_workflows_configuration.md)). The project has no
  say: the workflow author decided, and a typed project cannot deviate from its type.

The **go-live gate follows the same flag** and stops guessing (§7 C1/C5): a per-lot level needs an
officer on **every active lot** — a project-wide officer does not answer it, and neither does the
country L1 fallback, which is an assignment safety net rather than a staffing plan. A project-wide
level needs one project-wide officer and is never asked about lots.

---

## 7. Go-live checklist

**API:** `GET /api/v1/projects/{id}/go-live`  
**Service:** `ticketing/services/project_go_live.py`

**Goal:** Can we activate the project and create a ticket assigned to the right L1 officer?

**Binary (2026-07-30, Q-GL-1/2):** every check is either a **Blocker** (must pass to Activate) or **Optional** (never blocks). No "warning" tier. A blocked check states the one thing to fix.

> **As-built since 2026-08-04.** Binary is now real: `_ACTIVATION_BLOCK_IDS = {A1, B1, C1, C4, C5, D1, E1, R1}` — exactly the Blockers below. **A1 (default workflow), D1 (locations), E1 (name + code) and C4 (sensitive workflow staffing) were promoted from warnings**, so a project with no default workflow and no linked locations can no longer be activated. Everything else carries `severity="info"` and never blocks; the UI shows it as **optional**, not amber ([`ui/04`](ui/04_projects_packages_redesign.html), `ProjectConsoleRail`). Projects activated **before** this change keep `is_active = true` until someone deactivates them — the gate is on activation, not a sweep.
>
> **A3 and A5 were deleted the same day** ([DECISION-author-defined-slots](../sprints/2026-07_org_chart_positions/DECISION-author-defined-slots.md) §7). Both hardcoded the two organizations the platform happened to know about — an implementing agency and a donor. **B1 asks the same question in the author's own words**, against whatever organizations the project's *type* names, and is now a Blocker. The donor guardrail is expressible in that model: mark the donor slot required, put its role in the last level's kept-informed job, and C5 enforces it like any other required job. Legacy reads keep old projects passing — B1 accepts `implementing_agency_org_id` for an `implementing_agency` slot and `project_donors` for a `donor` slot.

### Blockers (must pass to activate)

| ID | Check | Notes |
|----|-------|-------|
| B1 | **Every required organization is named** | The **type's** catalog (`actor_roles[].required`); the message names the gap in the author's words ("Name the organization for: Ward Office"). Replaced A3 + A5 on 2026-08-04 |
| A1 | **A default workflow is chosen** | Routing has nowhere to fall back without it (§5B.1) |
| A4 | **Every step's required cast tiers staffed** | Actor always; plus supervisor / participant / observer the workflow marks mandatory (`required_tiers`, [12 §6.2](12_workflows_configuration.md)) |
| C1 | **L1 actor staffed** | Also **gates ticket intake** — fail ⇒ create rejected |
| D1 | **≥1 project location linked** | Routing needs it |
| ~~A2~~ / C4 | **Sensitive workflow L1 staffed** | **A2 removed 2026-08-02** — a project needs no sensitive workflow ([DECISION](../sprints/2026-07_org_chart_positions/DECISION-sensitive-workflows.md) §1.3). C4 still applies **if** one is linked: its levels are staffed like any other workflow's (A4) |
| E1 | **Name + short code set** | — |

### Optional (never blocks activation)

| Check | Notes |
|-------|-------|
| ~~A3 Implementing agency~~ · ~~A5 Donor kept informed~~ | **Deleted 2026-08-04** — both are B1 now (see the note above). `donor_informed_ok()` survives as the predicate that pre-fills the last level's kept-informed cast when a donor is added; it no longer gates activation on its own. |
| B1 on an **untyped** project | Reports `info`, not a blocker: a legacy project created before types existed has no catalog to check. New projects cannot be untyped — `POST /projects` requires `project_type_key` (422 otherwise) |
| ~~Classification coverage~~ | **Deleted 2026-08-02** (with `workflow_routing.uncovered_classifications`). A category no card claims goes to the default — that is what the default is for (§5B.2) — so it was never a finding, only noise on any project that doesn't enumerate the whole catalog. It also shipped as id **`A4`**, colliding with this doc's `A4` (required cast tiers); that collision is gone. |
| Package QR tokens | Generate anytime from the main QR menu |
| Officer-SMS phone coverage | Only relevant if officer SMS is on ([06_messaging_rules_whatsapp_sms.md](06_messaging_rules_whatsapp_sms.md) §5.8) |

Activation (`PATCH` with `is_active: true`) returns 422 if `can_activate` is false.

---

## 8. API summary

| Method | Path | Notes |
|--------|------|-------|
| `GET/POST` | `/projects` | List / create (admin) |
| `GET/PATCH/DELETE` | `/projects/{id}` | CRUD; activation gated |
| `GET/PUT` | `/projects/{id}/workflows` | Workflow links — name + workflow + routing + default (§5B) |
| `GET/PATCH` | `/projects/{id}/messaging` | Officer assignment SMS config — [06_messaging_rules_whatsapp_sms.md](06_messaging_rules_whatsapp_sms.md) |
| `GET` | `/projects/{id}/go-live` | Checklist report |
| `GET/PUT` | `/projects/{id}/implementing-agency` | Set the one accountable org (`government`/`local_government`) — [DECISION §2](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md) |
| `GET/POST/DELETE` | `/projects/{id}/donors` | Optional donor participants (0..n); drives the last-step-informed guardrail |
| `GET/POST` | `/projects/{id}/locations/{code}` | Location links |
| `GET/POST/PATCH` | `/projects/{id}/packages` | Package CRUD |
| `/projects/{id}/packages/{pkg}/organizations` | POST/DELETE | Per-lot organization slots — the catalog entries scoped to a package (§2). Reinstated 2026-08-04 |
| `POST/DELETE` | `/projects/{id}/packages/{pkg}/locations/...` | Package locations |
| `GET/POST/DELETE` | `/qr-tokens` (via scan router) | QR management |

---

## 9. Acceptance criteria

1. Super admin can create a typed project, link workflows, orgs, locations, and packages.
2. `org_admin` can complete go-live data entry (workflows, staffing, locations, packages) — there is no actor-role catalog to edit.
3. Project cannot activate until implementing agency actor is set (demo block A3).
4. Ticket create blocked when L1 officer scope missing (demo block C1).
5. A package can **override a workflow level's staffing** (position-first, §5A); otherwise it inherits the project-wide staffing.
6. QR scan returns package + location context for chatbot pre-fill.
