# Workflows configuration

**Status:** As-built reference (June 2026)  
**UI:** Settings → Workflows, roles & permissions → **Workflows**  
**Code:** `ticketing/api/routers/workflows.py`, `ticketing/engine/workflow_engine.py`, `ticketing/tasks/escalation.py`  
**Related:** [11_roles_and_permissions.md](11_roles_and_permissions.md), [13_projects_and_packages.md](13_projects_and_packages.md), [Escalation_rules.md](Escalation_rules.md)

---

## 1. Purpose

Workflows define the **linear escalation chain** for grievances: ordered steps, SLA timers, GRM role per step, and optional stakeholder/action metadata. Two workflow **types** exist:

| `workflow_type` | Used when |
|-----------------|-----------|
| `standard` | Normal GRM cases (`is_seah = false`) |
| `seah` | SEAH-sensitive cases (`is_seah = true`) |

Workflows are **linked on projects** (`projects.standard_workflow_id`, `projects.seah_workflow_id`), not via the legacy `workflow_assignments` UI.

---

## 2. Data model

### `ticketing.workflow_definitions`

| Field | Notes |
|-------|-------|
| `workflow_id` | UUID PK |
| `workflow_key` | Slug (auto from name) |
| `display_name` | Admin-facing name |
| `description` | Optional |
| `workflow_type` | `standard` \| `seah` |
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
| `resolution_time_days` | Escalation trigger; `NULL` = no auto-escalation (e.g. L4 legal) |
| `stakeholders` | JSON array — descriptive |
| `expected_actions` | JSON array — descriptive |
| `is_deleted` | Soft delete; blocked if active tickets on step |

### `ticketing.tickets.workflow_version`

Snapshot of definition `version` at ticket creation.

### Legacy: `ticketing.workflow_assignments`

Maps (org, project_code, location, priority) → workflow. **Not configured in UI.** `resolve_workflow()` falls back only when ticket has no `project_id`. Do not use for new projects.

---

## 3. Built-in templates

Returned by `GET /api/v1/workflows/templates` (includes virtual built-ins):

| Template | Type | Steps |
|----------|------|-------|
| **Default GRM** | `standard` | L1 Site (2d) → L2 PIU (7d) → L3 GRC (21d) → L4 Legal (no SLA) |
| **Default SEAH** | `seah` | L1 National (7d) → L2 HQ (14d) |

Admin flow: clone template → edit → publish → link on project.

---

## 4. Workflow lifecycle

```
draft → publish → (in use on projects) → archive
                ↘ delete (draft only, no active tickets)
```

| Action | API | Rules |
|--------|-----|-------|
| Create | `POST /workflows` | Optional `clone_from_id` |
| Edit metadata | `PATCH /workflows/{id}` | Draft or published |
| Add/edit/reorder steps | `POST/PATCH/DELETE/POST reorder` | Delete blocked if tickets on step |
| Publish | `POST /workflows/{id}/publish` | Increments version |
| Save as template | `POST /workflows/{id}/save-as-template` | Copies steps |
| Archive | `POST /workflows/{id}/archive` | Published only; unlinks from new tickets |
| Delete | `DELETE /workflows/{id}` | Draft only |

**SEAH gate:** mutating SEAH workflows requires `canSeeSeah`.

---

## 5. Settings UI — Workflows tab

### List view

- Active workflows (non-template) with type badge, step count, version, status.
- Templates section: built-in + admin-created; **Clone** creates a new draft workflow.
- SEAH rows hidden when `!canSeeSeah`.
- No "assigned to org/project" column (assignments deprecated).

### Editor

- Vertical step list with up/down reorder.
- Inline accordion per step: display name, **assigned role** (`assigned_role_key`), response/resolution SLA, stakeholders, actions.
- Footer: *Assign this workflow on a project under Settings → Projects & packages.*
- **Notification rules** collapsible panel (per workflow type slug) — see §6.

### 5.1 Role picker on each step (workflows-first)

Admins edit workflows **more often** than they create roles. The step editor is the **primary** place where roles meet escalation paths.

| Control | Behaviour |
|---------|-------------|
| **Role dropdown** | Lists operational roles for this workflow’s track (Standard / SEAH); group *System* vs *Custom* |
| **+ Create role…** | Opens role archetype wizard ([11_roles_and_permissions.md](11_roles_and_permissions.md) §3.4); on save, returns to step with new `role_key` selected |
| **Step without role** | Block publish until every step has `assigned_role_key` |

**Typical flow:** Clone **Default GRM** template → tweak SLAs / step labels → change assigned role on one step if a custom position is needed → publish → link on project.

New roles are **not** created inside “New workflow” step 1 — only on demand from the step dropdown or from the Roles tab.

### Removed from editor

- **Assigned to** panel (`workflow_assignments`) — use project workflow pickers instead.

---

## 6. Notification rules (`settings.notification_rules`)

JSON shape:

```json
{
  "standard": {
    "ticket_created": { "actor": ["app"], "supervisor": ["app"], "informed": [], "observer": [] },
    "sla_breach": { "actor": ["app", "email"], ... }
  },
  "seah": { ... }
}
```

| Dimension | Values |
|-----------|--------|
| **Events** | `ticket_created`, `ticket_escalated`, `ticket_resolved`, `sla_breach`, `grc_convened`, `assignment`, `quarterly_report` |
| **Tiers** | `actor`, `supervisor`, `informed`, `observer` |
| **Channels** | `app` (in-app badge), `email`, `sms` |

SEAH panel omits `grc_convened` and `quarterly_report`.

**Runtime:** `ticketing/tasks/notifications.py` → `should_notify(workflow_slug, event, tier, channel)`.

**UI:** Workflow editor → Notification rules — expand, toggle matrix, save → `PUT /api/v1/settings/notification_rules`.

**Proto note:** Officer notifications are in-app first; email/SMS columns exist for future use.

---

## 7. Workflow resolution at ticket creation

```
if ticket.project_id:
    use project.standard_workflow_id  (or seah_workflow_id if is_seah)
else:
    legacy fallback → workflow_assignments table
```

Implemented in `ticketing/engine/workflow_engine.py` → `resolve_workflow()`.

---

## 8. SLA and escalation (runtime)

Configured per step; behaviour specified in [Escalation_rules.md](Escalation_rules.md):

- Timer starts at `ticket.step_started_at` when step is entered.
- Celery Beat every 15 min checks `resolution_time_days`.
- On breach: auto-escalate, open `ticket_overdue_episodes` row, `notify_complainant` on escalate.
- GRC L3: `GRC_CONVENE` → `GRC_DECIDE` two-step actions.
- L4: no `resolution_time_days` → manual only.

---

## 9. API summary

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/workflows` | List workflows (`?include_templates=`) |
| `GET` | `/workflows/templates` | Templates only |
| `GET` | `/workflows/{id}` | Detail + steps + assignments |
| `POST` | `/workflows` | Create (`clone_from_id`, `is_template`) |
| `PATCH` | `/workflows/{id}` | Metadata |
| `POST` | `/workflows/{id}/publish` | Publish |
| `POST` | `/workflows/{id}/archive` | Archive |
| `POST` | `/workflows/{id}/save-as-template` | Clone as template |
| `DELETE` | `/workflows/{id}` | Draft delete |
| `POST/PATCH/DELETE` | `/workflows/{id}/steps/...` | Step CRUD + reorder |
| `GET/POST/DELETE` | `/workflows/{id}/assignments` | **Legacy** — avoid |

---

## 10. Acceptance criteria

1. Admin can create, edit, publish, and archive Standard workflows; SEAH admins can manage SEAH workflows.
2. Each step binds exactly one `assigned_role_key` from the GRM catalog.
3. Published workflow can be selected on a project's Grievance workflows section.
4. Notification rules save per `standard` / `seah` slug without overwriting the other.
5. Active tickets retain `workflow_version` at creation; publishing does not rewrite open ticket step graphs.
6. Auto-escalation respects `resolution_time_days` on the current step.
