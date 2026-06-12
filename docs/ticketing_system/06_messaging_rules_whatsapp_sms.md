# Messaging Rules – WhatsApp and SMS (Staff Notifications)

**Status (June 2026):** Active policy + **project-level officer SMS** (implemented — see agent runbook).  
**Related:** [../services/05_messaging_service.md](../services/05_messaging_service.md), [03_ticketing_api_integration.md](03_ticketing_api_integration.md), [13_projects_and_packages.md](13_projects_and_packages.md), [Escalation_rules.md](Escalation_rules.md)  
**Implementation:** [`agents/officer_sms_project_messaging.md`](agents/officer_sms_project_messaging.md)

---

## 1. Scope

This document covers **staff-facing notifications** (assignment alerts and ticket links).

| In scope | Out of scope |
|----------|--------------|
| Officer SMS when assigned at L1–Ln | Complainant closure / status message content |
| Project-level enablement by country admin | Global `notification_rules` SMS for officers (not used; see §5.4) |
| Future WhatsApp 1:1 per level (config shape reserved) | WhatsApp group automation |

---

## 2. Locked rules

### 2.1 No PII in staff notifications

- Do not include complainant name, phone, email, or address in SMS/WhatsApp staff alerts.
- Allowed payload: grievance reference, short category/location text, status, and ticket link.

Examples:

```
New case: GRV-2025-001 (Road safety, Morang). Open: https://grm.facets-ai.com/tickets/{ticket_id}
```

```
Escalation: GRV-2025-001 (Road safety, Morang). Open: https://grm.facets-ai.com/tickets/{ticket_id}
```

### 2.2 WhatsApp channel constraints

- System messages are **1:1 only** when using official WhatsApp APIs.
- Group posting is not supported by official APIs; do not use unofficial automation.
- If groups are required operationally, use a **human bridge** who forwards link-only summaries.

### 2.3 Group hygiene: links-only

- In WhatsApp groups, do not post screenshots/files directly.
- Upload evidence to managed storage and share links.
- Keeps auditability and access control outside chat history.

### 2.4 SMS is default/fallback

- Use SMS as primary channel for officer assignment alerts (reliability, approval simplicity).
- WhatsApp 1:1 may be enabled per level in a later phase where business verification/templates exist.

### 2.5 Ticket link format

Officer SMS links use the officer case view:

```
{TICKETING_PUBLIC_BASE_URL}/tickets/{ticket_id}
```

- `TICKETING_PUBLIC_BASE_URL` → `ticketing.config.settings.TicketingSettings.ticketing_public_base_url` (env: `TICKETING_PUBLIC_BASE_URL`).
- Auth middleware handles login redirect when the officer opens the link on a new device.

---

## 3. Operational model

| Actor | Channel | Rule |
|---|---|---|
| System → Officers (assignment) | SMS (v1); WhatsApp 1:1 (future) | Link-only, no PII; gated by project Messaging config |
| Bridge person | WhatsApp groups | Forward summary + link only |
| Managers / Boss | 1:1 digest or group | No attachments, links only |

---

## 4. Compliance

- Notification sends and contact reveal actions are auditable (`TicketEvent` rows).
- Staff training includes: no PII in messages, no file uploads in group chats, links only.

---

## 5. Project-level officer messaging (LOCKED — June 2026)

Country managers configure officer SMS **per project** under Settings → **Projects & packages** → project editor → **Messaging**.

### 5.1 Who configures

| Action | `super_admin` | `country_admin` | `project_admin` |
|--------|---------------|-----------------|-----------------|
| View Messaging section | ✅ | ✅ | ✅ read-only |
| Edit Messaging | ✅ | ✅ (country scope) | ❌ |

Same edit gate as project metadata / workflows — not delegated to `project_admin`.

### 5.2 UI — Project editor section order

Insert **Messaging** after **Grievance workflows** and before **Actor roles** (see [13_projects_and_packages.md](13_projects_and_packages.md) §5).

| Control | Behaviour |
|---------|-----------|
| **Master: Officer SMS enabled** | Off → no officer SMS for this project |
| **Per-level checkboxes L1…Ln** | When master is on, country admin picks which levels send SMS |
| **Dynamic level count (n)** | `n` = max `step_order` across all published workflows linked on the project (`project_workflows` slots). SEAH projects with 2-step workflows show L1–L2 only. |
| **WhatsApp (future)** | Disabled placeholders per level; same JSON shape as SMS |

Copy hint: *“Officers receive a link-only SMS when assigned at checked levels. No complainant details are included.”*

### 5.3 Granularity

- **One config block per project** — same L1–Ln toggles apply to **all** workflow streams on that project (safeguards, hazards, CA, SEAH, custom slots).
- Not per-slot and not on the workflow definition template.

### 5.4 Relationship to global `notification_rules`

- `ticketing.settings.notification_rules` (Settings → Workflows notification matrix) remains for **app / email** tiers and complainant-related platform defaults.
- **Officer SMS is not gated by global rules.** Project Messaging is the sole gate for officer assignment SMS.
- `should_notify(..., channel="sms")` must not be required for officer assignment SMS.

### 5.5 Triggers

Send officer SMS **only on assignment** — when `assigned_to_user_id` is set or changes to a new officer at the current step:

| Event | Fire SMS? |
|-------|-----------|
| Ticket created + L1 auto-assigned | ✅ if L1 enabled |
| Auto-escalation to next step + new assignee | ✅ if that step's level enabled |
| Manual escalate to next step + new assignee | ✅ |
| Manual reassign (`assign_to_user_id`) at same step | ✅ if that step's level enabled |
| SLA breach without reassignment | ❌ |
| Ticket created with no assignee | ❌ (nothing to send) |
| Resolved / closed | ❌ |

### 5.6 Recipients

- **Assigned officer only** (`assigned_to_user_id` at time of assignment).
- Do not SMS supervisor, informed, or observer tiers for this feature.

### 5.7 Phone source

- Officer mobile: Keycloak user attribute `phone_number` (same as officer profile / invite onboarding).
- Lookup by `assigned_to_user_id` (email / username in Keycloak).
- If SMS is enabled for the level but assignee has **no phone**: skip send, log audit event, no retry storm.

### 5.8 Go-live

Add check **`F1`** (severity **warn**, group **officers**, section **messaging**):

> For each level with SMS enabled: at least one officer scoped to this project with the step's `assigned_role_key` must have a phone in Keycloak.

- Does **not** block activation or ticket create (warn only).
- Jump target: Messaging section in go-live panel.

---

## 6. Data model

### 6.1 Storage

Add JSON column on `ticketing.projects`:

| Column | Type | Default |
|--------|------|---------|
| `officer_messaging` | `JSONB` / JSON | see below |

Default (all off):

```json
{
  "sms_enabled": false,
  "sms_levels": [],
  "whatsapp_levels": []
}
```

When master on and levels selected:

```json
{
  "sms_enabled": true,
  "sms_levels": [1, 2, 3, 4],
  "whatsapp_levels": []
}
```

- `sms_levels`: list of integers — 1-based `step_order` values.
- `whatsapp_levels`: reserved for future 1:1 WhatsApp; ignored at runtime in v1.

### 6.2 Audit events

Log on `ticketing.ticket_events`:

| `event_type` | When |
|--------------|------|
| `OFFICER_SMS_SENT` | SMS accepted by messaging API |
| `OFFICER_SMS_SKIPPED` | Config off, level off, no phone, or API failure |
| `ASSIGNMENT_NOTIFICATION` | Unchanged — in-app badge (existing) |

`OFFICER_SMS_*` payload (no PII): `{ "channel": "sms", "level": 1, "reason": "..." }`.

---

## 7. Runtime

### 7.1 Service flow

```
assignment committed (ticket_id, assigned_to_user_id, step_id)
  → resolve project from ticket.project_code / project_id
  → load project.officer_messaging
  → if not sms_enabled: return
  → resolve step_order for current step
  → if step_order not in sms_levels: return
  → fetch phone from Keycloak for assigned_to_user_id
  → if no phone: log OFFICER_SMS_SKIPPED; return
  → build message (grievance_id, categories/location snippet, ticket URL)
  → ticketing.clients.messaging_api.send_sms(phone, body)
  → log OFFICER_SMS_SENT or OFFICER_SMS_SKIPPED
  → always enqueue/create ASSIGNMENT_NOTIFICATION (in-app badge)
```

Implement as `ticketing.services.officer_messaging` + Celery task `notify_officer_assignment` (extend existing `notify_assignment` or call from it).

### 7.2 Call sites (must wire)

| Location | When |
|----------|------|
| `ticketing/services/ticket_intake.py` | After create + auto-assign |
| `ticketing/engine/escalation.py` | After escalate + new `assigned_to_user_id` |
| `ticketing/api/routers/tickets.py` | Manual reassign / escalate actions that change assignee |

Use `notify_officer_assignment.delay(...)` after DB commit.

### 7.3 Messaging API

- `POST /api/messaging/send-sms` via `ticketing/clients/messaging_api.py`
- Auth: `x-api-key` / shared secret per [../services/05_messaging_service.md](../services/05_messaging_service.md)
- Best-effort: assignment must not fail if SMS fails.

---

## 8. API

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/projects/{id}/messaging` | Return `officer_messaging` + computed `max_levels` |
| `PATCH` | `/api/v1/projects/{id}/messaging` | `country_admin` / `super_admin`; validate levels ⊆ 1…max_levels |

Optional: include `officer_messaging` on `GET /projects/{id}` response for fewer round-trips.

`max_levels` = `MAX(step_order)` across workflows linked in `project_workflows` for this project (non-deleted steps only).

---

## 9. Acceptance criteria

1. Country admin can enable master SMS and select individual levels L1–Ln on a project; `project_admin` sees but cannot edit.
2. Level count in UI matches longest assigned workflow on the project.
3. Assignee receives link-only SMS when assigned at an enabled level and has a phone in Keycloak.
4. No SMS when master off, level unchecked, no assignee, or no phone (skipped + audit).
5. No complainant PII in message body or event payload.
6. Go-live shows **F1** warn when SMS enabled but scoped officers lack phones.
7. Assignment SMS works on create, auto-escalation, manual escalation, and manual reassign.
8. In-app `ASSIGNMENT_NOTIFICATION` badge behaviour unchanged.
9. `whatsapp_levels` stored but not sent in v1.

---

## 10. Out of scope (v1)

- WhatsApp 1:1 delivery
- SMS to supervisor / informed / observer tiers
- Per workflow-stream overrides on the same project
- SLA-breach SMS without reassignment
- Complainant SMS (separate path — orchestrator + `complainant_notifications` settings)
