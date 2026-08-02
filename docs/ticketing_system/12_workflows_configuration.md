# Workflows configuration

**Status:** As-built — **reconciled 2026-08-02**: a project links **N named workflows**; the fixed `slot_key` vocabulary was **dropped** by migration `c5e7f9a1_workflow_classifications`  
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

`workflow_type` (`standard` \| `seah`) still controls **visibility** and the SEAH gate — it is not the routing dimension.

---

## 2. Data model

### `ticketing.workflow_definitions`

| Field | Notes |
|-------|-------|
| `workflow_id` | UUID PK |
| `workflow_key` | Slug (auto from name) |
| `display_name` | Admin-facing name |
| `description` | Optional |
| `workflow_type` | `standard` \| `seah` (visibility / SEAH gate) |
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
| `tier_labels` | Per-step, per-tier **display name + description** — each **defaults from the tier type** (e.g. supervisor → "oversees; can reassign") and is **editable by the author in the Workflows step editor**. Shown **read-only** on staffing / case UI instead of generic tier words. See §6.2 |
| `required_tiers` | JSON list ⊆ {`supervisor`, `informed`, `observer`} — the non-actor tiers the author marks **mandatory** on this step. The **actor tier is always required**. Drives the project staffing go-live gate ([13 §5A.5 / §7 A4](13_projects_and_packages.md)). See §6.2 |
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

- List active workflows + templates; **Clone** creates a draft.
- Step editor: role dropdown, SLAs, tier fields.
- Footer: *Put a workflow on a project under Settings → Projects & packages → Grievance workflows.*

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

**Effect on project go-live (staffing gate):** a project blocks activation if any step has a **required** tier with no officer staffed for it ([13 §5A.5 / §7 A4](13_projects_and_packages.md)). The supervisor's default (next-step handler pool, [DECISION §5](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md)) satisfies a mandatory supervisor **except on the top step**, where an explicit one is required. Requiredness is a **workflow** property, so it is consistent across every project that uses the workflow.

**UI (wireframe):** the step-cast editor — bind a role, name each tier + add a description, mark required — is mocked at [`ui/06_workflows_step_cast_editor.html`](ui/06_workflows_step_cast_editor.html). The author-set names + required flags then drive the **read-only** Staffing screen ([13 §5A](13_projects_and_packages.md); mockup [`ui/04`](ui/04_projects_packages_redesign.html)).

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

Officers on the same project can hold **different roles on different steps** across the linked workflows — e.g. an L1 safeguards focal on the default, a contractor liaison on a CA workflow, a rapid-response role on road hazards. Staffing is **position-first** ([13 §5A](13_projects_and_packages.md)): fill each level's cast under **Project-wide staffing**, with per-lot overrides in **Packages**.

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
| `GET` | `/workflows` | List workflows |
| `GET` | `/workflows/routing-options` | Category classifications + chatbot menu paths for the project editor |
| `GET` | `/workflows/templates` | Templates only |
| `GET` | `/workflows/{id}` | Detail + steps |
| `POST` | `/workflows` | Create |
| `PATCH` | `/workflows/{id}` | Metadata |
| `POST` | `/workflows/{id}/publish` | Publish |
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
