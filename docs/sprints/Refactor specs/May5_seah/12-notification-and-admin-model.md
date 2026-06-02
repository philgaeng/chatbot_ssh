# Spec 12 — Notification model, tier-based permissions, and admin role split

> **Status:** Locked for implementation  
> **Scope:** `ticketing.*` schema + `channels/ticketing-ui/` only  
> **Depends on:** Spec 01 (geography), existing `WorkflowStep`, `OfficerScope`, `WorkflowAssignment` models  
> **Does NOT touch:** `public.*`, chatbot, Rasa, orchestrator

---

## Context

This spec was derived from a design review (2026-05-05) covering:
- How notifications should be structured across workflow steps
- Why a flat "Stakeholders notified" field is insufficient
- How to avoid a per-role × per-step × per-channel complexity explosion
- How admin scope should be split to keep local management tractable

---

## 1. Four-tier permission model

Permissions on a ticket are **not** derived from a user's named role. They are derived from
the user's **tier on that ticket**, which is assigned dynamically based on workflow state.

### Tier definitions

| Tier | Assignment | Actions available |
|---|---|---|
| **Actor** | Explicitly assigned to the current workflow step | Acknowledge, escalate, resolve, assign tasks, assign complainant-reply responsibility, add notes, add docs, message internally |
| **Supervisor** | Declared in the step template (`supervisor_role`) | Same as Actor + override actor, reassign ticket |
| **Informed** | Previous step actors (auto) + manually added (with gate) + role-based (e.g. GRC members) | Add notes, add docs, message internally, execute assigned tasks (mark done), **no** workflow actions |
| **Observer** | Derived from org-wide scope assignment | Read ticket only — no notifications, no actions, no notes |

### Key rules

**Actor is step-scoped, task execution is not.**
Being assigned a task does not change your tier. An Informed officer executes their
assigned task (adds a report, marks it done) without gaining Actor-level workflow rights.
The Actor at the current step retains exclusive control of escalate / resolve / assign.

**Complainant reply is a distinct capability.**
It is not a tier right. It defaults to whoever was Actor at Step 1 (L1 officer) and
persists even as the ticket escalates. Any Actor above L1 can explicitly reassign this
capability to another person (via a task or explicit assignment UI). This ensures the
complainant always has one known contact.

**GRC members are Informed, not a 5th tier.**
The GRC Chair is Actor at L3. GRC members participate as Informed: they can add notes,
attach documents, and message internally. Their hearing notification is just the standard
Informed notification for the `grc_convened` event.

**SEAH add-to-Informed requires supervisor approval.**
On standard tickets, any Actor can add someone to Informed. On SEAH tickets, the
Supervisor must approve before the addition is committed. This protects SEAH
confidentiality without removing the feature.

**PII visibility by tier.**
By default, Informed users do not see complainant PII (name, phone, address).
This is a workflow-level configuration flag (`informed_pii_access: false` default).
Actors and Supervisors always see PII (subject to reveal-on-demand for phone/address
per existing vault design).

---

## 2. Tier lifecycle on a ticket

```
Ticket created at Step 1
  → Step 1 actor_role becomes Actor
  → Step 1 supervisor_role becomes Supervisor
  → Step 1 observer_roles become Observers (auto-added as viewers, no notifications)
  → Complainant-reply assigned to Step 1 Actor

Ticket escalated to Step 2
  → Previous Step 1 Actor moves to Informed (auto, logged as TIER_CHANGED event)
  → Step 2 actor_role becomes Actor
  → Step 2 supervisor_role becomes Supervisor
  → local_admin / project_admin notified if supervisor changed due to template update

Officer manually added to ticket
  → Added as Informed (standard)
  → Added as Informed pending supervisor approval (SEAH)

Task assigned to Informed officer
  → They execute task (add doc, add note, mark done)
  → Tier remains Informed — no workflow rights gained

Task completed / closed
  → No tier change — Informed stays Informed

Ticket resolved
  → All tiers receive closure notification per workflow notification rules
  → Complainant notified via chatbot / SMS fallback
```

---

## 3. Workflow step model changes

### Current `WorkflowStep` fields (relevant subset)
```
step_key, display_name, assigned_role, response_hours, resolution_days,
stakeholders_notified (JSON array), expected_actions (JSON array), metadata (JSON)
```

### Required additions
```
supervisor_role:    str | null   — role key for the supervisor at this step
observer_roles:     str[]        — roles auto-added as Observers (no notifications)
informed_pii_access: bool        — default false; if true, Informed see complainant PII
```

### Field rename
`stakeholders_notified` → `informed_roles` (same semantics, clearer name)

These roles are added as Informed when the ticket first enters this step (in addition
to auto-promotion of previous Actors).

### Migration
One Alembic revision adding three columns to `ticketing.workflow_steps`.
`informed_pii_access` defaults to `false`. `supervisor_role` and `observer_roles`
default to null / empty array. Existing seed data populated in the same revision.

---

## 4. Notification rules — per workflow, derived from tier

Notifications are configured **once per workflow** (not per step). The tier determines
which channel fires. Stored as `settings["notification_rules"]` JSON:

```json
{
  "standard": {
    "ticket_created":    { "actor": ["app","email"], "supervisor": ["app","email"], "informed": [],        "observer": [] },
    "ticket_escalated":  { "actor": ["app","email"], "supervisor": ["app","email"], "informed": ["email"], "observer": [] },
    "ticket_resolved":   { "actor": ["app","email"], "supervisor": ["app"],         "informed": [],        "observer": [] },
    "sla_breach":        { "actor": ["app","email"], "supervisor": ["app","email"], "informed": ["email"], "observer": [] },
    "grc_convened":      { "actor": ["app","email"], "supervisor": ["app"],         "informed": ["app"],   "observer": [] },
    "assignment":        { "actor": ["sms","app"],   "supervisor": [],              "informed": [],        "observer": [] },
    "quarterly_report":  { "actor": [],              "supervisor": ["email"],       "informed": ["email"], "observer": [] }
  },
  "seah": {
    "ticket_created":    { "actor": ["app","email"], "supervisor": ["app","email"], "informed": [],        "observer": [] },
    "ticket_escalated":  { "actor": ["app"],         "supervisor": ["app"],         "informed": [],        "observer": [] },
    "ticket_resolved":   { "actor": ["app"],         "supervisor": ["app"],         "informed": [],        "observer": [] },
    "sla_breach":        { "actor": ["app","email"], "supervisor": ["app","email"], "informed": [],        "observer": [] },
    "assignment":        { "actor": ["app"],         "supervisor": [],              "informed": [],        "observer": [] }
  }
}
```

SEAH defaults are intentionally more restrictive (no email trails by default).

### Complainant notifications (separate from officer tiers)

| Event | Channel |
|---|---|
| Ticket created | Chatbot message (primary) / SMS fallback |
| Ticket acknowledged | Chatbot / SMS |
| Ticket resolved | Chatbot / SMS |
| Reply from officer | Chatbot / SMS |

Complainant channel is configured separately in `settings["complainant_notifications"]`.

---

## 5. Admin role split

The current `local_admin` role is too broad. It conflates country-level structure
management with project-level personnel management. Replace with two scoped roles:

### `country_admin` (new — replaces local_admin for structural work)

**Scope:** One country  
**Manages:**
- Create / edit workflow templates (or delegates to super_admin)
- Create projects and location hierarchy (country → province → district → municipality)
- Assign workflow templates to projects
- Create and manage project_admins for their country
- View all tickets in country (read-only)

**Cannot:**
- Assign individual officers to steps (that's project_admin)
- Access other countries' data

### `project_admin` (new — replaces local_admin for day-to-day ops)

**Scope:** One or more projects within one country  
**Manages:**
- Officer assignments: who fills each role at each location within their project(s)
- Notification rule overrides per workflow instance (within defaults set by country_admin)
- Step-level personnel changes (e.g. replacing the L1 officer for a location)
- Receives template-change notifications for their in-flight tickets

**Cannot:**
- Create or modify workflow templates
- Create new locations or projects
- Access other projects' tickets (unless explicitly granted)

### `local_admin` disposition

Existing `local_admin` users should be migrated to `project_admin` by default.
`country_admin` is a new designation requiring explicit assignment by `super_admin`.

### Summary of all admin roles

| Role | Creates | Assigns people | Sees tickets |
|---|---|---|---|
| `super_admin` | Everything | Yes | All |
| `country_admin` | Projects, locations, templates | project_admins only | All in country (read) |
| `project_admin` | Nothing | Officers to roles/locations | Own project(s) only |

---

## 6. Scope matrix

Access to tickets is always bound by **project + location + role**. This is enforced
at the DB query level (existing `OfficerScope` model).

```
country_admin assigns:
  project_admin → project X

project_admin assigns:
  site_safeguards_focal_person → project X, location: JHAPA
  pd_piu_safeguards_focal      → project X, location: all (provincial level)
  grc_chair                    → project X, location: all

ADB oversight roles (adb_hq_safeguards, adb_national_project_director, etc.)
  → assigned by country_admin at country scope
  → become Observers on all tickets in that country automatically
  → no notifications by default
```

The project_admin UI surface for managing their matrix is:
**location × role → officer** for their project only. With 10 locations and 4 actor
roles per step, that's ~40 cells — manageable in a simple assignment table.

---

## 7. UI changes required

### Settings — Roles & Permissions tab
- Add `country_admin` and `project_admin` rows to the role table
- Mark `local_admin` as deprecated with migration note
- Replace free-form permission tags with tier-per-step table (read-only, derived from
  workflow template): Role → Workflow → L1 tier / L2 tier / L3 tier / L4 tier

### Settings — Workflows tab (step editor)
- Add `Supervisor` field (single role dropdown) to step editor
- Rename `Stakeholders notified` → `Informed roles` (same component, label change)
- Add `Observers (access only)` field (multi-role, no notifications)
- Add `PII visible to Informed` toggle (default off)

### Settings — Workflows tab (workflow-level Notifications section)
- New collapsible section at the bottom of each workflow editor (below Assignments)
- 4-column toggle grid: Actor / Supervisor / Informed / Observer × app / SMS / email
- One row per event type (7 rows for standard, 5 for SEAH)
- Separate row for Complainant (chatbot-first / SMS fallback toggles)

### Settings — new Project Admin tab (or sub-section under Organizations & Locations)
- project_admin sees: their project(s) only
- Table: Location | Role | Assigned officer | Actions
- Inline edit: click officer name → dropdown of available officers for that role
- "Change officer" triggers notification to the new officer (app + email)

### Ticket detail (thread)
- Tier badge next to officer name in events: `Actor` `Supervisor` `Informed` `Observer`
- "Add to informed" button (Actor only; requires supervisor approval on SEAH)
- Complainant reply button visible only to: officer holding reply capability

---

## 8. Backend changes required

### `ticketing/models/workflow.py`
- Add `supervisor_role`, `observer_roles`, `informed_pii_access` to `WorkflowStep`

### `ticketing/engine/workflow_engine.py`
- On ticket creation: resolve tier for all roles in scope → create viewer records with tier
- On escalation: auto-move previous Actor to Informed (log TIER_CHANGED event)
- On template supervisor_role change: notify affected project_admins for in-flight tickets

### `ticketing/engine/escalation.py`
- After escalation: add `TIER_CHANGED` event for previous Actor → Informed

### `ticketing/api/routers/tickets.py`
- `POST /tickets/{id}/informed` — add officer to Informed (permission check: SEAH requires supervisor)
- `PUT /tickets/{id}/complainant-reply-owner` — reassign reply capability

### `ticketing/tasks/notifications.py`
- `should_notify(workflow_slug, event, tier, channel)` — reads `notification_rules` settings key
- All notification dispatch goes through this gate before firing

### `ticketing/models/user.py` / seed
- Add `country_admin` and `project_admin` roles to seed data
- `local_admin` kept for backward compat, flagged deprecated in display

### Alembic migration (one revision)
```
# Safe to run: only creates/modifies ticketing.* tables
# Adds supervisor_role, observer_roles, informed_pii_access to workflow_steps
# Does NOT touch: public.* tables
```

---

## 9. What is explicitly out of scope for this sprint

- Message template customisation by language (v2 — documented in TODO)
- SSE real-time push for officer notifications (v2 — currently badge-on-poll)
- SEAH add-to-Informed supervisor approval UI (v2 — permission check returns 403 with message for now)
- Quarterly report scheduling UI (already exists under Report Schedule tab)
- `country_admin` creating workflow templates in UI (super_admin does this for demo; UI shell only for country_admin)

---

## 10. Implementation order

1. **Alembic migration** — `WorkflowStep` new columns
2. **Backend model + engine** — tier derivation, TIER_CHANGED event, `should_notify` gate
3. **API endpoints** — add-to-informed, complainant-reply-owner
4. **Settings UI** — step editor fields + Workflow Notifications section
5. **Project admin UI** — location × role × officer assignment table
6. **Roles & Permissions tab** — new roles + tier table
7. **Ticket thread** — tier badges + add-to-informed button
8. **Seed data** — update KL Road Standard + SEAH workflow with supervisor_role + observer_roles
