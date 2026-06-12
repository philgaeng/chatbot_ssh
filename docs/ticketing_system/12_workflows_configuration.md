# Workflows configuration

**Status:** Target architecture (June 2026) — multi-stream per project  
**UI:** Settings → Workflows, roles & permissions → **Workflows**; project links under **Projects & packages → Grievance workflows**  
**Code:** `ticketing/api/routers/workflows.py`, `ticketing/constants/workflow_slots.py`, `ticketing/services/project_workflows.py`, `ticketing/engine/workflow_engine.py`  
**Related:** [11_roles_and_permissions.md](11_roles_and_permissions.md), [13_projects_and_packages.md](13_projects_and_packages.md), [Escalation_rules.md](Escalation_rules.md)

---

## 1. Purpose

Workflows define the **linear escalation chain** for grievances: ordered steps, SLA timers, GRM role per step, and optional stakeholder/action metadata.

A **single project** may attach **N workflow streams** (not just one Standard + one SEAH). Each stream is a **slot** with its own published workflow definition. Different officers handle different steps within each workflow; scoping is unchanged (`officer_scopes` + step `assigned_role_key`).

### Built-in intake streams (minimum on road projects)

| `slot_key` | Label | `workflow_type` | Routed when |
|------------|-------|-----------------|-------------|
| `safeguards` | Safeguards GRM | `standard` | Default grievance intake |
| `hazards` | Road hazards | `standard` | Chatbot `intake_fast_path` = `road_hazard` or `dust` |
| `ca` | Contract administration | `standard` | Explicit `workflow_slot=ca` (or future CA intake) |
| `seah` | SEAH | `seah` | `is_seah=true` or `workflow_slot=seah` |

Admins may add **custom** `slot_key` values (slug) on a project via `PUT /projects/{id}/workflows`.

`workflow_type` (`standard` \| `seah`) still controls **visibility** and the SEAH gate — it is not the routing dimension anymore.

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
| `supervisor_role`, `informed_roles`, `observer_roles` | Tier model (spec 12) |
| `is_deleted` | Soft delete; blocked if active tickets on step |

### `ticketing.project_workflows` (project ↔ stream ↔ workflow)

| Field | Notes |
|-------|-------|
| `project_workflow_id` | UUID PK |
| `project_id` | FK → `ticketing.projects` |
| `slot_key` | e.g. `safeguards`, `hazards`, `ca`, `seah`, or custom slug |
| `workflow_id` | FK → published `workflow_definitions` |
| `label` | Optional display override |
| `sort_order` | UI ordering |

Unique: `(project_id, slot_key)`.

**Legacy columns** on `ticketing.projects` (`standard_workflow_id`, `seah_workflow_id`) are **mirrors** of the `safeguards` and `seah` slots for backward compatibility.

### `ticketing.tickets.workflow_version`

Snapshot of definition `version` at ticket creation.

### Legacy: `ticketing.workflow_assignments`

Maps (org, project_code, location, priority) → workflow. **Not configured in UI.** `resolve_workflow()` falls back only when ticket has no `project_id`. Do not use for new projects.

---

## 3. Who can create workflows and assign them

| Action | `super_admin` | `country_admin` `track=standard` | `country_admin` `track=seah` |
|--------|---------------|----------------------------------|------------------------------|
| Create / edit / publish workflows | ✅ all tracks | ✅ `standard` workflows | ✅ `seah` workflows |
| Assign `safeguards` / `hazards` / `ca` on project | ✅ | ✅ | ❌ |
| Assign `seah` on project | ✅ | ❌ | ✅ |
| Add custom slot on project | ✅ | ✅ (standard track slots) | ✅ (seah slots only) |

`project_admin`: read project workflow links; manage officers for their track ([13_projects_and_packages.md](13_projects_and_packages.md)).

---

## 4. Built-in templates

Returned by `GET /api/v1/workflows/templates` (includes virtual built-ins):

| Template | Type | Steps |
|----------|------|-------|
| **Default GRM** | `standard` | L1 Site (2d) → L2 PIU (7d) → L3 GRC (21d) → L4 Legal (no SLA) |
| **Default SEAH** | `seah` | L1 National (7d) → L2 HQ (14d) |

Admin flow: clone template → edit steps / roles → publish → link on project per slot.

Slot catalog: `GET /api/v1/workflows/slots`.

---

## 5. Workflow lifecycle

```
draft → publish → (in use on projects) → archive
                ↘ delete (draft only, no active tickets)
```

| Action | API | Rules |
|--------|-----|-------|
| Create | `POST /workflows` | Optional `clone_from_id`; `super_admin` or `country_admin` (matching track) |
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
- Footer: *Assign streams on a project under Settings → Projects & packages → Grievance workflows.*

### 6.1 Role picker on each step

Admins edit workflows **more often** than they create roles. The step editor is the **primary** place where roles meet escalation paths.

| Control | Behaviour |
|---------|-----------|
| **Role dropdown** | Operational roles for this workflow's track (Standard / SEAH) |
| **+ Create role…** | Role archetype wizard; returns with new `role_key` selected |
| **Step without role** | Block publish until every step has `assigned_role_key` |

---

## 7. Settings UI — Project grievance workflows

Section lists **all built-in slots** (safeguards, hazards, CA, SEAH) plus any custom slots already on the project.

| Control | Behaviour |
|---------|-----------|
| Per-slot workflow picker | Published workflows filtered by `workflow_type` |
| **+ Create new workflow…** | Opens clone modal; on save, assigns to that slot |
| Save | `PUT /api/v1/projects/{id}/workflows` |

Officers for the same project can hold **different roles on different steps** across streams — e.g. L1 safeguards focal on `safeguards`, a contractor liaison on `ca`, a rapid-response role on `hazards`. Staffing is configured under **Project actors** and **Staffing** ([07_officer_management_and_assignment.md](07_officer_management_and_assignment.md)).

---

## 8. Workflow resolution at ticket creation

```
if ticket.project_id / project_code:
    slot = workflow_slot
        ?? (is_seah → seah)
        ?? (intake_fast_path → hazards | ca)
        ?? safeguards
    workflow_id = project_workflows[slot]
    fallback: projects.standard_workflow_id | seah_workflow_id
else:
    legacy workflow_assignments
```

Implemented in `ticketing/engine/workflow_engine.py` → `resolve_workflow()`.

**Webhook fields** (`POST /api/v1/tickets`):

| Field | Purpose |
|-------|---------|
| `workflow_slot` | Explicit stream (overrides inference) |
| `intake_fast_path` | `road_hazard`, `dust`, `ca`, … |
| `is_seah` | Maps to `seah` when `workflow_slot` omitted |

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
| `GET` | `/workflows/slots` | Built-in slot catalog |
| `GET` | `/workflows/templates` | Templates only |
| `GET` | `/workflows/{id}` | Detail + steps |
| `POST` | `/workflows` | Create |
| `PATCH` | `/workflows/{id}` | Metadata |
| `POST` | `/workflows/{id}/publish` | Publish |
| `GET` | `/projects/{id}/workflows` | Slots on project |
| `PUT` | `/projects/{id}/workflows` | Replace all slot assignments |
| `PATCH` | `/projects/{id}` | Legacy `standard_workflow_id` / `seah_workflow_id` (syncs slots) |

---

## 12. Acceptance criteria

1. `super_admin` and scoped `country_admin` can create, publish, and assign workflows on their track.
2. A project can link **at least three** standard streams (safeguards, hazards, CA) plus SEAH.
3. Each step binds exactly one `assigned_role_key`; different streams may use different roles on the same project.
4. Ticket intake selects the correct workflow from slot inference or explicit `workflow_slot`.
5. Published workflow version is snapshotted on the ticket; publishing does not rewrite open tickets.
6. Auto-escalation respects `resolution_time_days` on the current step.
