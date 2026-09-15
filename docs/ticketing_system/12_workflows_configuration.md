# Workflows configuration

**Status:** As-built — **reconciled 2026-08-02**: a project links **N named workflows**; the fixed `slot_key` vocabulary was **dropped** by migration `c5e7f9a1_workflow_classifications`  
**Last updated:** 2026-09-15 — §2 gains *The resolution panel* (`GRM-119`: one panel per workflow, up to 8, no owner field, who may do what; API rows). Earlier the same day: §2 gains *A workflow's organization* (`GRM-122`: chosen on create, shown and changed in the editor, refused while the list would strand an action; API table). Earlier the same day: §2 gains *Resolution actions*: every workflow and template belongs to an organization, lists hold at most 8 and are copied not inherited, publishing requires one, a sensitive workflow never has one (`GRM-116`).  
**UI:** Settings → Workflows, roles & permissions → **Workflows**; project links under **Projects & packages → Grievance workflows**  
**Code:** `ticketing/api/routers/workflows.py`, `ticketing/constants/workflow_routing.py`, `ticketing/services/project_workflows.py`, `ticketing/services/workflow_routing.py`, `ticketing/engine/workflow_engine.py`  
**Related:** [11_roles_and_permissions.md](11_roles_and_permissions.md), [13_projects_and_packages.md](13_projects_and_packages.md), [Escalation_rules.md](Escalation_rules.md)

---

## 1. Purpose

Workflows define the **linear escalation chain** for grievances: ordered steps, SLA timers, GRM role per step, and optional stakeholder/action metadata.

A **single project** may link **N workflows** (not just one Standard + one SEAH). Each link carries a **name the admin chooses** (`display_label`), the **published workflow** it uses (`workflow_id`), and the rules that send grievances to it — the **chatbot menu path** the complainant took (`intake_route`) and/or the grievance **categories** (`classifications`). Exactly one link is the **default** (`is_default`): it takes every grievance nothing else matches. Different officers handle different steps within each workflow; scoping is unchanged (`officer_scopes` + step `assigned_role_key`).

> **⚠ Vocabulary + model correction (2026-08-02).** The fixed-slot model (`slot_key` ∈ `safeguards` / `hazards` / `ca` / `seah`, unique per project) **no longer exists** — migration `c5e7f9a1_workflow_classifications` dropped the column and moved to `display_label` + `intake_route` + `classifications` + `is_default`. The project name is therefore **independent of the workflow's own name**: two projects may bind the same published workflow under different names. **"Stream" and "slot" are dead words** — never in UI copy, where the on-screen word is **workflow** ([ui/05 §4](ui/05_ui_copy_style.md)).

### Links seeded on a new road project (all renamable/removable)

| Name (`display_label`) | Published workflow type | Chatbot menu (`intake_route`) | Categories | Default? |
|---|---|---|---|---|
| Safeguards GRM | `standard` | `new_grievance` | — (catch-all) | ✅ |
| Road hazard | `standard` | `road_hazard_grievance` | Road Hazard | — |
| SEAH | `seah` | `seah_intake` | Gender · Gender, Social · Malicious Behavior · Malicious Behavior, Environmental | — |

Seeds: `ticketing/constants/workflow_routing.py` + `ticketing/services/project_types.py`. Admins add, rename, or remove links via `PUT /projects/{id}/workflows`.

> **⚠ Superseded 2026-08-02 — [D-007](../DECISIONS.md#d-007--seah-is-a-property-of-a-workflow-not-a-concept-in-the-system).** `workflow_type ∈ {standard, seah}` becomes a single boolean **`is_sensitive`** set by the workflow author. **SEAH is not a mode — it is the name of a workflow.** A sensitive workflow's grievances are visible **only to officers cast on its steps** (no admin, no oversight role, not `super_admin`), and their PII is vault-gated to that same cast. Sensitive workflows are **optional** on a project and **may not be the default**. Sections below still written in track terms are superseded by the DECISION; code change is outstanding (DECISION §7).

`workflow_type` (`standard` \| `seah`) still controls **visibility** as-built — it is not the routing dimension.

---

## 2. Data model

### `ticketing.workflow_definitions`

| Field | Notes |
|-------|-------|
| `workflow_id` | UUID PK |
| `workflow_key` | Slug (auto from name) |
| `display_name` | Admin-facing name |
| `description` | Optional |
| `workflow_type` | `standard` \| `seah` (visibility gate) — **being replaced by `is_sensitive` (bool)**, [D-007](../DECISIONS.md#d-007--seah-is-a-property-of-a-workflow-not-a-concept-in-the-system) §6 |
| `status` | `draft` \| `published` \| `archived` |
| `version` | Incremented on publish |
| `is_template` | Reusable blueprint; not assigned to tickets directly |
| `template_source_id` | Provenance when cloned |

### `ticketing.workflow_steps`

| Field | Notes |
|-------|-------|
| `step_order` | 1-based sequence |
| `step_key` | Stable key (auto-generated from display name, editable) |
| `display_name` | e.g. "Level 1 — Site Safeguards" |
| `assigned_role_key` | GRM role from [11_roles_and_permissions.md](11_roles_and_permissions.md) |
| `response_time_hours` | First-response SLA (optional) |
| `resolution_time_days` | Escalation trigger; `NULL` = no auto-escalation |
| `supervisor_role`, `informed_roles`, `observer_roles` | Tier model (spec 12) — the step **cast** (actor = `assigned_role_key`) |
| `tier_labels` | **Built 2026-08-04** (`j6l8n0p2`). Per-step, per-tier **display name + description** — each **defaults from the tier type** (e.g. supervisor → "oversees; can reassign") and is **editable by the author in the Workflows step editor**. Shown **read-only** on staffing / case UI instead of generic tier words. See §6.2 |
| `required_tiers` | **Built 2026-08-04** (`j6l8n0p2`). JSON list ⊆ {`supervisor`, `informed`, `observer`} — the non-actor tiers the author marks **mandatory** on this step. The **actor tier is always required**, so the API **rejects `actor`** (422) rather than accepting a silent no-op. Drives the project staffing go-live gate ([13 §5A.5 / §7 A4](13_projects_and_packages.md)). See §6.2 |
| `staff_per_package` | **Built 2026-08-04** (`p2r4t6v8`). Is this level staffed **package by package** (`true`) or **once for the project** (`false`, the default and what every step did before)? Typically the lower levels are per package and the upper ladder project-wide. The **workflow author** sets it, so a project built from a type inherits it and has no switch of its own. Drives the Staffing screen's shape and the go-live staffing gate ([13 §5A/§7](13_projects_and_packages.md)) |
| `is_deleted` | Soft delete; blocked if active tickets on step |

### `ticketing.project_workflows` (project ↔ named link ↔ workflow)

| Field | Notes |
|-------|-------|
| `project_workflow_id` | UUID PK |
| `project_id` | FK → `ticketing.projects` |
| `workflow_id` | FK → published `workflow_definitions` |
| `display_label` | **Required** — the name the admin gives this workflow **on this project** (independent of `workflow_definitions.display_name`) |
| `intake_route` | Chatbot `story_main`: `new_grievance` \| `road_hazard_grievance` \| `seah_intake`. **Required on non-default links**, `NULL` on the default |
| `classifications` | JSON list of category classifications routed here (also used to re-route when an officer changes the category) |
| `is_default` | Exactly one per project — takes everything nothing else matches |
| `sort_order` | UI ordering |

No `slot_key` (dropped 2026-07 by `c5e7f9a1_workflow_classifications`), so no `(project_id, slot_key)` uniqueness; the invariant is **exactly one `is_default` row per project**, enforced in `ticketing/services/project_workflows.py`.

**Legacy columns** on `ticketing.projects` (`standard_workflow_id`, `seah_workflow_id`) are **mirrors** of the default standard link and the SEAH link, kept for backward compatibility.

### `ticketing.tickets.workflow_version`

Snapshot of definition `version` at ticket creation.

### Resolution actions — what the workflow's officers can record as done (`GRM-116`)

Each workflow holds an **ordered list of at most 8** actions from the resolution-action catalog
(`ticketing.workflow_resolution_actions` → `ticketing.resolution_actions`). A case offers its
workflow's list when an officer resolves it. The catalog — owned by organizations, never global, with
local actions counting as a ministry's shared ones — is specified in
[08 §2.2](08_ticket_resolution_and_case_summary.md). What matters here:

**A workflow's organization decides what it can list.** An action is usable when it belongs to the
workflow's organization or one above it, so **every workflow and template belongs to an
organization** (`owner_organization_id`). How it is set and changed is the next section.

| How the workflow came to exist | Lists |
| --- | --- |
| Created from scratch, or from a built-in template | **nothing** — built-in templates belong to no organization and carry no list |
| Cloned, created from a database template, or saved as a template | a **copy** of the source's list — refused (422) if the new organization cannot use one of its actions |
| Existing before migration `b3d5f7h9` | sensitive → none · bound to the road-hazard menu on any project → the road-works five · otherwise the general five |

**Copied, never inherited**: a later change to the source does not reach the copy.

**Publishing requires an action.** `POST /workflows/{id}/publish` refuses a non-sensitive workflow
with no active action: *"Add at least one resolution action before publishing."* A published one
cannot be emptied. Only published workflows bind to projects, so a case meets an empty list only in a
sensitive workflow.

**A sensitive workflow never lists an action** — its cases record neither what was done nor who did
it. `workflow_type` cannot change after creation, so the rule is decided once. Every path above goes
through `resolution_catalog.set_workflow_actions`, the only writer.

### The resolution panel — where the list is managed (`GRM-119`)

**One place:** a panel in the workflow editor, below *Notifications*, on workflows **and** templates —
*What officers can choose when closing a case*, with **n of 8**. The owner's review of the first design
(a panel *and* a catalog screen, ownership choices, retire and merge) found it too complex for the admins
who will run it; this is what remained.

- One row per action, in order: **▲▼**, the name, **Edit** where the viewer may edit that action,
  **Remove**. A local action shows *counts as <shared action>* under its name.
- **+ Add an action** searches the actions **this workflow can use** that it does not already offer;
  typed text that matches nothing offers **+ Create "…"**.
- **Every change saves at once** and applies to the next case closed. The list is read live — it is
  **not** versioned by *Publish*.
- **Full (8 of 8):** *Add* disabled — *"A workflow can offer at most 8 actions. Remove one to add
  another."* **Empty:** *"Add at least one action before publishing."*, and *Publish* is disabled (the
  server refuses it too). **Last action of a published workflow:** *Remove* disabled. **Sensitive:** one
  line — *"SEAH workflows do not record a resolution action."* — no controls.

**Create and edit — one dialog.** *Action* · *Default text for the officer* · and, when the workflow does
**not** belong to a ministry itself, **In national reports, count this as** — required, one of the
ministry's active shared actions. An admin who manages the ministry also sees **A new national action**
first in that list. **There is no owner field:** a new action belongs to the workflow's organization, or
to its ministry when *A new national action* is chosen, and is appended to the list in the same request.
Editing a shared action warns *"Used by N workflows — the change applies to all of them."*

**Who may do what** — enforced in `services/resolution_authoring.py`; the panel renders the flags the
server returns. *Reach* is the organizations an admin administers on the standard track; a platform admin
reaches everything.

| Action | Allowed when |
| --- | --- |
| Change a workflow's list (add, remove, reorder, create into it) | the workflow's organization is in reach · not sensitive · ≤ 8 |
| Create *A new national action* | as above, and the workflow's ministry is in reach |
| Edit an action (label, default text, what it counts as) | the action's organization is in reach |
| Pick an action | it is active and usable by the workflow (its organization or one above) |

⚠ **The track check alone is not enough.** Workflow writes elsewhere check only the track
(`can_mutate_workflow`), so any standard-track `org_admin` passes it; the panel's endpoints check reach on
the workflow's organization after it. `project_admin`, `officer_admin` and officers author nothing.

A create refused at 8 — or for any other reason — is refused **before** the action row is written: actions
are never deleted, so a refusal must not leave one behind.

✅ **Verified in a browser, local stack, 2026-09-15** — `e2e/flows/settings-resolution-panel.spec.ts`: an
empty draft blocks Publish; add, reorder and remove save at once; 8 of 8 refuses a ninth; the create dialog
opens (with no *counts as* on DOR's own workflow) and is cancelled. ⚠ **Pinned only at the API level**
(`tests/ticketing/test_resolution_authoring.py`): **creating and editing** an action — an action is never
deleted, so each e2e run would add a permanent one to DOR's catalog, and a local action needs an
organization below DOR that e2e must not create (`GRM-092`) — and the **sensitive** panel state, which no
seeded user can open in the browser (`GRM-125`).

### A workflow's organization — *Belongs to* (`GRM-122`)

**Why it matters.** It decides which resolution actions the workflow can offer (above), and it is what
an organization's admin needs in reach to manage the workflow. The migration gave every existing
workflow and template **its projects' ministry** — the only safe automatic answer — but the right
owner is often lower down: the KL Road workflows are PD-ADB's, not all of DOR's. So admins move them.

| Where | What |
| --- | --- |
| **New workflow / New template** | **Belongs to** is required. A platform admin chooses; an `org_admin` finds its organization filled in (the top of its reach, as `catalog_owner_for`) and may pick any organization it manages. The template list then shows **only templates of that organization or one above it**, so everything a template copies is usable |
| **Workflow editor** | *Belongs to: Department of Roads · Change* beside *Type* and *Key*, on workflows and templates. *Belongs to: — · Choose* when it has none |
| **Change** | Organizations the admin manages (a platform admin: all), and, for information, the projects using the workflow. **Refused, dialog kept open, one line per action**, while the list holds an action the new organization could not use: *"Remove 'Culvert cleared' first — it belongs to PD-ADB."* Moving **down** (DOR → PD-ADB) never hits this; sideways, up or to another ministry can. Local actions do not move with the workflow |
| **Workflow list** | Each workflow and template shows *For <organization>* under its name |
| **Save as template** | The template takes the workflow's organization |

**Who.** Moving needs reach on **both** the current and the new organization; a sensitive workflow
additionally needs the sensitive-configuration capability (`_load_workflow`). Every move is written to
`admin_audit_log` (`workflow_organization_changed`, with both organizations).

**Deliberately not checked:** whether the projects using a workflow sit under its new organization —
no catalog enforces that today, and the dialog shows the projects so the admin can see it (`GRM-120`).
✅ **Verified in a browser, local stack, 2026-09-15** — `e2e/flows/settings-workflow-organization.spec.ts`
creates a draft that must be given an organization and moves it (DOR → ADB, two top organizations: a
fresh seed has nothing below DOR). ⚠ **Two cases are pinned only by API tests**
(`tests/ticketing/test_workflow_organization.py`): moving **down** to a sub-organization, and the
**refused** move — the latter was driven in a browser once that day but is not in the committed spec,
because the only workflow that can carry actions today has steps and cannot be cleaned up (`GRM-124`).

### Legacy: `ticketing.workflow_assignments`

Maps (org, project_code, location, priority) → workflow. **Not configured in UI.** `resolve_workflow()` falls back only when ticket has no `project_id`. Do not use for new projects.

---

## 3. Who can create workflows and assign them

| Action | `super_admin` | `org_admin` `track=standard` | `org_admin` `track=seah` |
|--------|---------------|----------------------------------|------------------------------|
| Create / edit / publish workflows | ✅ all tracks | ✅ `standard` workflows | ✅ `seah` workflows |
| Link a `standard` workflow on a project | ✅ | ✅ | ❌ |
| Link a `seah` workflow on a project | ✅ | ❌ | ✅ |
| Add / rename / remove a link on a project | ✅ | ✅ (standard links) | ✅ (SEAH link only) |

`project_admin`: read project workflow links; manage officers for their track ([13_projects_and_packages.md](13_projects_and_packages.md)).

---

## 4. Built-in templates

Returned by `GET /api/v1/workflows/templates` (includes virtual built-ins):

| Template | Type | Steps |
|----------|------|-------|
| **Default GRM** | `standard` | L1 Site (2d) → L2 PIU (7d) → L3 GRC (21d) → L4 Legal (no SLA) |
| **Default SEAH** | `seah` | L1 National (7d) → L2 HQ (14d) |

Admin flow: clone template → edit steps / roles → publish → link on a project under a name the admin chooses.

Routing options for the project editor (category classifications + chatbot menu paths): `GET /api/v1/workflows/routing-options`.

---

## 5. Workflow lifecycle

```
draft → publish → (in use on projects) → archive
                ↘ delete (draft only, no active tickets)
```

| Action | API | Rules |
|--------|-----|-------|
| Create | `POST /workflows` | Optional `clone_from_id`; `super_admin` or `org_admin` (matching track) |
| Edit metadata | `PATCH /workflows/{id}` | Draft or published |
| Add/edit/reorder steps | `POST/PATCH/DELETE/POST reorder` | Delete blocked if tickets on step |
| Publish | `POST /workflows/{id}/publish` | Increments version; every step needs `assigned_role_key` |
| Save as template | `POST /workflows/{id}/save-as-template` | Copies steps |
| Archive | `POST /workflows/{id}/archive` | Published only |
| Delete | `DELETE /workflows/{id}` | Draft only |

**SEAH gate:** mutating SEAH workflows requires `canSeeSeah`.

---

## 6. Settings UI — Workflows tab

**Two sub-tabs: Workflows · Project types.** They live together because a project type is
mostly a bundle of workflows — see §6.00. (Project types sat under Settings → platform data
until 2026-08-04, where nobody looking at a workflow would find them.)

- List active workflows + templates; **Clone** creates a draft.
- Step editor: role dropdown, SLAs, tier fields.
- **Sensitive workflow** checkbox — see §6.0.
- Footer: *Put a workflow on a project under Settings → Projects & packages → Grievance workflows.*

### 6.00 Project types sub-tab — where a workflow becomes a project's workflow

A workflow on its own runs nothing. A **project type** binds one or more of them (name, default,
chatbot menu, categories) and names the organizations a project of that kind must have. Creating
a project is: **organization → one of its types → name it.** A typed project cannot deviate from its type, so this sub-tab is where a
project's workflow set is actually changed — the project screen shows it read-only and links
here.

- **Component:** `ProjectTypesTab.tsx`. Its workflow cards are the project screen's own
  (`<WorkflowBindingCards>`, shared), so the two cannot drift.
- **Who:** `super_admin` anywhere, `org_admin` within its own subtree — the same gate as
  authoring a workflow. A `project_admin` does not see the sub-tab.
- **Model, freeze rules and validation:** [14 §4](14_platform_settings.md) — one description,
  referenced from everywhere.

### 6.0 The **Sensitive** checkbox — the one place the property is set

A workflow-level property (`is_sensitive`; as-built `workflow_type == 'seah'`), edited **here and nowhere else**. Wireframe: [`ui/06`](ui/06_workflows_step_cast_editor.html), the strip under the workflow title.

On-screen copy (LOCKED — [ui/05](ui/05_ui_copy_style.md)):

> ☐ **Sensitive workflow**
> Only officers staffed on this workflow can see these grievances. Contact details stay hidden until an officer opens them, and every time is recorded. **A sensitive workflow can't be a project's default.**

What ticking it does — the whole contract, in one place ([DECISION §2](../DECISIONS.md#d-007--seah-is-a-property-of-a-workflow-not-a-concept-in-the-system)):

| | |
|---|---|
| **Access** | Grievances on this workflow are visible **only to officers cast on its steps** — not to admins, oversight roles, or `super_admin`. They do not appear in anyone else's queue, counts, notifications, or reports. |
| **PII** | Complainant contact is masked in the case view and readable only through a **logged vault reveal**, by that same cast. |
| **Routing** | The workflow can still be linked to any project, but **never as the default** (422). |
| **Authoring** | Only an admin with the configure capability sees or edits it; a standard-scoped role cannot be cast on its steps (`validate_step_roles`). |

Everywhere else the property is **read-only and derived**: the project screen's 🔒 Sensitive badge reflects the bound workflow ([13 §5B.2](13_projects_and_packages.md)), and a ticket's sensitivity is copied from the workflow it resolves to at intake (`ticket.is_seah = workflow_is_seah(workflow)`) — never set by hand.

### 6.1 Role picker on each step

Admins edit workflows **more often** than they create roles. The step editor is the **primary** place where roles meet escalation paths.

| Control | Behaviour |
|---------|-----------|
| **Role dropdown** | Operational roles for this workflow's track (Standard / SEAH) |
| **+ Create role…** | Role archetype wizard; returns with new `role_key` selected |
| **Step without role** | Block publish until every step has `assigned_role_key` |

### 6.2 Step cast — tiers, names, and required flags

A step is a **cast**, not one role ([13 §5A.1](13_projects_and_packages.md)): **actor** (`assigned_role_key`) · **supervisor** (`supervisor_role`) · **participant / informed** (`informed_roles[]`) · **observer** (`observer_roles[]`). In the step editor the workflow author controls two things per tier:

- **Name + description** (`tier_labels`) — each tier starts from a **default** (from its type — e.g. supervisor → "oversees; can reassign") that the author can **edit per step, here in the Workflows tab**; e.g. L1 actor named "Safeguard Officer", L3 actor "GRC Chairman". These (default or edited) labels — never generic words like "Handles it" — are what the staffing and case UI display (**read-only there; edited only here**).
- **Mandatory or not** (`required_tiers`) — the **actor is always required**; the author decides, **per step**, whether **supervisor / participant / observer** are mandatory. A tier not marked mandatory is optional and never blocks go-live.

**Effect on project go-live (staffing gate):** a project blocks activation if any step has a **required** tier with no officer staffed for it ([13 §5A.5 / §7 A4](13_projects_and_packages.md)). The supervisor's default (next-step handler pool, [DECISION §5](../DECISIONS.md#d-004--a-projects-participants-are-typed-fields-staffing-decides-who-acts)) satisfies a mandatory supervisor **except on the top step**, where an explicit one is required. Requiredness is a **workflow** property, so it is consistent across every project that uses the workflow.

**UI (wireframe):** the step-cast editor — bind a role, name each tier + add a description, mark required — is mocked at [`ui/06_workflows_step_cast_editor.html`](ui/06_workflows_step_cast_editor.html). The author-set names + required flags then drive the **read-only** Staffing screen ([13 §5A](13_projects_and_packages.md); mockup [`ui/04`](ui/04_projects_packages_redesign.html)).

#### As built, and closed 2026-08-04

The model and the editor shipped in `f0e6f844` (migration `j6l8n0p2`), but **nothing was ever authored** — every seeded step had `tier_labels = {}` — so every screen fell through to a second choice: the **display name of the role** bound to the job. The words were right by accident and the workflow screen looked ignored, which is exactly what this section says must not happen ("never generic words", "edited only here"). Three changes close it:

1. **`r4t6v8x0` back-fills** each job's name with what its screen was already showing, so nothing is blank. Nothing changed visually; the words are now *owned* by the workflow instead of borrowed from the role catalog.
2. **A name is required to save.** A level with an enabled job and no name is refused (422, naming the jobs in the editor's own words), and **publish refuses** a workflow with any unnamed job — a project cannot supply the name, so it has to exist before the workflow is usable. `services/role_scope.py`: `unnamed_jobs` / `require_named_jobs`.
3. **The role-name fallback is deleted**, in the staffing screen and in go-live's gap message. With no blanks and no fallback, the workflow is the only place a job's name can come from — the claim is structural, not conventional. (A last-resort generic word remains for a level that somehow has none; the role **key** can no longer reach a screen — it is a slug, ui/05 §2.5.)

**Descriptions stay optional** and fall back to the job's default text ("alerted on escalation; can reassign"), which is what makes a short authored description worth writing rather than mandatory.

The **seeds author names too** (`kl_road_standard.py`, `kl_road_seah.py`) — a fresh deployment must be able to publish the workflow it ships with.

---

## 7. Settings UI — Project grievance workflows

One card per linked workflow — the **default first**, then the others. Routing (chatbot menu + categories) sits **on the same card**, so a project's whole routing picture is one screen. Spec + wireframe: [13 §5B](13_projects_and_packages.md#5b-grievance-workflows--the-project-editor-screen) / [`ui/04`](ui/04_projects_packages_redesign.html).

| Control | Behaviour |
|---------|-----------|
| **Name** | `display_label` — free text, the project's own name for this workflow |
| **Workflow** picker | Published workflows filtered by `workflow_type` (SEAH hidden without `canSeeSeah`) |
| **+ Create a new workflow…** | Opens the clone modal; on save, binds the new workflow to this card |
| **Default** | Exactly one card; the default takes no routing rules |
| **Chatbot menu** / **Categories** | `intake_route` (required on non-default) + `classifications` |
| Save | `PUT /api/v1/projects/{id}/workflows` (replaces all links) |

Officers on the same project can hold **different roles on different steps** across the linked workflows — e.g. an L1 safeguards focal on the default, a contractor liaison on a CA workflow, a rapid-response role on road hazards. Staffing is **position-first** ([13 §5A](13_projects_and_packages.md)): fill each level's cast under **Project-wide staffing**, with per-package overrides in **Packages**.

---

## 8. Workflow resolution at ticket creation

```
if ticket.project_id / project_code:
    route = intake_route (story_main)  ?? (is_seah → seah_intake)
    link  = 1. non-default link whose intake_route == route
            2. (re-route only) non-default link whose classifications match the categories
            3. the default link (is_default = true)
    workflow_id = link.workflow_id
    fallback: projects.seah_workflow_id | standard_workflow_id (track-aware)
else:
    legacy workflow_assignments
```

Implemented in `ticketing/services/workflow_routing.py` → `pick_project_workflow_binding()` / `resolve_project_workflow()`, called from `ticketing/engine/workflow_engine.py` → `resolve_workflow()`.

**Re-classification.** When an officer changes a grievance's categories, `ticketing/services/ticket_workflow_reroute.py` re-derives the route — but **only from the safeguards menu path** (`new_grievance`). A grievance that came in on the SEAH or road-hazard menu stays on it.

**Webhook fields** (`POST /api/v1/tickets`):

| Field | Purpose |
|-------|---------|
| `intake_route` | Chatbot `story_main` — the menu path the complainant took |
| `is_seah` | Legacy — maps to `seah_intake` when `intake_route` is omitted |
| `intake_fast_path` | **Deprecated** — legacy aliases (`dust`, `road_hazard`, …) normalized to `intake_route` |

---

## 9. Notification rules (`settings.notification_rules`)

Still keyed by workflow **track slug** `standard` / `seah` (not per slot). SEAH panel omits `grc_convened` and `quarterly_report`.

**Runtime:** `ticketing/tasks/notifications.py` → `should_notify(workflow_slug, event, tier, channel)` for **app / email** tiers.

**Officer assignment SMS** is **not** controlled here — it is configured per project under **Messaging** ([06_messaging_rules_whatsapp_sms.md](06_messaging_rules_whatsapp_sms.md) §5).

---

## 10. SLA and escalation (runtime)

Unchanged per step — [Escalation_rules.md](Escalation_rules.md). Each ticket follows **one** workflow graph for its lifetime.

---

## 11. API summary

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/workflows` | List workflows — each with `owner_organization_id` and `owner_name`; `?for_organization_id=` lists those owned by that organization **or one above it** (the new-workflow template picker; must be in reach) |
| `GET` | `/workflows/routing-options` | Category classifications + chatbot menu paths for the project editor |
| `GET` | `/workflows/templates` | Templates only |
| `GET` | `/workflows/{id}` | Detail + steps + `used_by_projects` (names) |
| `POST` | `/workflows` | Create — `owner_organization_id` required from a platform admin, defaulted for an `org_admin` (must be in reach) |
| `PATCH` | `/workflows/{id}` | Metadata |
| `POST` | `/workflows/{id}/publish` | Publish — refused for a non-sensitive workflow with no resolution action |
| `GET` | `/workflows/{id}/resolution-actions` | The panel: `actions [{code, label, default_wording, counts_as_label, can_edit, used_by_count}]`, `can_change`, `max`, `national_choices`, `can_create_national`, `is_sensitive`, `owner_is_ministry` (`GRM-119`) |
| `GET` | `/workflows/{id}/resolution-actions/available?q=` | Actions the workflow can use and does not offer |
| `PUT` | `/workflows/{id}/resolution-actions` | `{codes}` — replace the list, order included |
| `POST` | `/workflows/{id}/resolution-actions/new` | `{label, default_wording, counts_as_code?, national?}` — create and append; code generated server-side |
| `PATCH` | `/resolution-actions/{code}` | `{label?, default_wording?, counts_as_code?}` — edit; applies to every workflow using it |
| `PATCH` | `/workflows/{id}/organization` | `{organization_id}` — move it (`GRM-122`); 403 without reach on both organizations, 422 naming each action the new one cannot use |
| `GET` | `/projects/{id}/workflows` | Workflow links on the project |
| `PUT` | `/projects/{id}/workflows` | Replace all links (name + workflow + routing + default) |
| `PATCH` | `/projects/{id}` | Legacy `standard_workflow_id` / `seah_workflow_id` (syncs links) |

---

## 12. Acceptance criteria

1. `super_admin` and scoped `org_admin` can create, publish, and assign workflows on their track.
2. A project can link **N named workflows** — the admin names each one and picks the published workflow it uses; exactly one is the default.
3. Each step binds exactly one `assigned_role_key`; different links may use different roles on the same project.
4. Ticket intake selects the link by `intake_route`, then by categories on re-classification, then the default.
5. Published workflow version is snapshotted on the ticket; publishing does not rewrite open tickets.
6. Auto-escalation respects `resolution_time_days` on the current step.
7. The step editor lets the author name each cast tier and mark **supervisor / participant / observer** mandatory (`required_tiers`); actor is always required. Only required tiers gate project go-live ([13 §5A.5](13_projects_and_packages.md)).
