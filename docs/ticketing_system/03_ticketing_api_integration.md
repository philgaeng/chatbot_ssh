# Ticketing System – API Reference (as-built, June 2026)

All integration with the ticketing system is API-only. This document covers:
1. **Inbound** — chatbot/backend calls ticketing
2. **Outbound** — ticketing calls chatbot, messaging, grievance API
3. **Full endpoint reference** — all implemented ticketing API routes

---

## 1. Chatbot → Ticketing (Inbound)

### 1.1 Create ticket from grievance submission

Called by `backend/actions/utils/ticketing_dispatch.py` (fire-and-forget Celery task) after OTP verification and DB persistence.

```
POST /api/v1/tickets
Headers: X-Ticketing-Secret: {TICKETING_SECRET_KEY}
Body:
{
  "grievance_id": "GRV-2025-001",
  "complainant_id": "...",
  "session_id": "...",
  "chatbot_id": "nepal_grievance_bot",
  "country_code": "NP",
  "organization_id": "DOR",
  "location_code": "NP_P1_MOR",
  "project_code": "KL_ROAD",        // deprecated, use project_id
  "project_id": "...",              // optional, from QR scan
  "package_id": "...",             // optional, from QR scan
  "priority": "NORMAL",
  "is_seah": false,
  "grievance_summary": "...",
  "grievance_categories": "...",
  "grievance_location": "Morang District, Koshi Province"
}
Response: { "ticket_id": "...", "status_code": "OPEN", "created_at": "..." }
```

### 1.2 QR token scan (chatbot pre-fill)

Called by chatbot `ActionIntroduce` when URL parameter `t` is present.

```
GET /api/v1/scan/{token}
Response: {
  "token": "a1b2c3d4",
  "package_id": "...",
  "package_label": "KL Road — Km 45 Sign",
  "location_code": "NP_P1_MOR",
  "project_code": "KL_ROAD",
  "chatbot_url": "https://grm.facets-ai.com/chat"
}
404 / 410 / 422 all treated as "no token" by chatbot — graceful fallback.
```

---

## 2. Ticketing → Chatbot (Outbound)

### 2.1 Reply to complainant

```
POST {ORCHESTRATOR_BASE_URL}/message
Body: { "user_id": session_id, "text": "...", "channel": "ticketing" }
```

Called when officer clicks Reply in ticket detail, or automatically on RESOLVE/ESCALATE events via `notify_complainant.delay()`.

### 2.2 SMS fallback (session expired)

```
POST {BACKEND_API_BASE_URL}/api/messaging/send-sms
Headers: x-api-key: {MESSAGING_API_KEY}
Body: { "phone": "...", "message": "..." }
```

---

## 3. Ticketing → Grievance API (Outbound)

```
GET {BACKEND_GRIEVANCE_BASE_URL}/api/grievance/{grievance_id}
```

Called from ticket detail view to fetch PII (name, phone) on-demand. Never cached in `ticketing.*`.

---

## 4. Full API Endpoint Reference

All routes prefixed with `/api/v1` unless noted.

### Tickets

| Method | Path | Description |
|---|---|---|
| `POST` | `/tickets` | Create ticket (chatbot webhook) |
| `GET` | `/tickets` | List tickets (role-filtered, paginated) |
| `GET` | `/tickets/{id}` | Ticket detail + event history |
| `PATCH` | `/tickets/{id}` | Update ticket metadata |
| `PATCH` | `/tickets/{id}/complainant` | Update complainant data |
| `POST` | `/tickets/{id}/actions` | Perform workflow action (see below) |
| `POST` | `/tickets/{id}/reply` | Reply to complainant via orchestrator |
| `POST` | `/tickets/{id}/inbound-message` | Record inbound complainant message |
| `GET` | `/tickets/{id}/sla` | SLA countdown data |
| `GET` | `/tickets/{id}/teammates` | Assignable teammates for this ticket |
| `POST` | `/tickets/{id}/seen` | Mark events as seen (badge clear) |
| `POST` | `/tickets/{id}/informed` | Add user to Informed tier |
| `PUT` | `/tickets/{id}/complainant-reply-owner` | Set complainant reply owner |
| `GET` | `/tickets/{id}/files` | List complainant-uploaded files |
| `GET` | `/tickets/{id}/files/{file_id}` | Download complainant file |
| `POST` | `/tickets/{id}/attachments` | Upload officer attachment |
| `GET` | `/tickets/{id}/attachments` | List officer attachments |
| `GET` | `/tickets/{id}/attachments/{file_id}` | Download officer attachment |
| `GET` | `/tickets/{id}/pii` | Fetch PII from grievance API (logged) |
| `GET` | `/tickets/{id}/resolved-summary` | Get resolved case summary |
| `POST` | `/tickets/{id}/resolved-summary` | Generate resolved summary (LLM) |
| `POST` | `/tickets/{id}/findings` | Generate AI findings digest (LLM) |
| `POST` | `/tickets/{id}/reveal-contact/begin` | Begin PII reveal (logged) |
| `POST` | `/tickets/{id}/reveal-contact/close` | Close PII reveal session |

### Ticket actions (`POST /tickets/{id}/actions`)

`action_type` values:

| Action | Who | Effect |
|---|---|---|
| `ACKNOWLEDGE` | Actor at current step | Moves status to IN_PROGRESS |
| `ESCALATE` | Actor or Supervisor | Advances to next step, auto-assigns, notifies |
| `RESOLVE` | Actor (with resolution record) | Closes workflow, notifies complainant |
| `CLOSE` | Super admin | Hard close |
| `NOTE_ADDED` | Any officer with access | Adds internal note to timeline |
| `FIELD_REPORT` | Actor | Adds field report bubble to timeline |
| `GRC_CONVENE` | GRC chair | Schedules hearing, notifies GRC members |
| `GRC_DECIDE` | GRC chair | Records GRC resolution |
| `ASSIGN` | Actor or Supervisor | Reassign to another officer |

### Workflows

| Method | Path | Description |
|---|---|---|
| `GET` | `/workflows` | List all workflow definitions |
| `GET` | `/workflows/{id}` | Workflow detail + steps |
| `POST` | `/workflows` | Create workflow |
| `PATCH` | `/workflows/{id}` | Update workflow |
| `POST` | `/workflows/{id}/steps` | Add step |
| `PATCH` | `/workflows/{id}/steps/{step_id}` | Update step |
| `DELETE` | `/workflows/{id}/steps/{step_id}` | Delete step |

### Users / Officers

| Method | Path | Description |
|---|---|---|
| `GET` | `/users/roster` | List all officers (for bypass switcher + Settings) |
| `POST` | `/users/invite` | Invite officer (creates UserRole + OfficerOnboarding) |
| `GET` | `/users/{id}` | Officer detail |
| `PATCH` | `/users/{id}` | Update officer |
| `GET` | `/roles` | List roles catalog |
| `PATCH` | `/roles/{id}` | Update role definition |

### Settings

| Method | Path | Description |
|---|---|---|
| `GET` | `/settings` | Get all settings (key/value) |
| `PATCH` | `/settings/{key}` | Update a setting |

### Organizations / Locations / Projects

| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/organizations` | List / create orgs |
| `GET/PATCH` | `/organizations/{id}` | Get / update org |
| `GET/POST` | `/locations` | List / create locations |
| `GET/PATCH` | `/locations/{id}` | Get / update location |
| `GET/POST` | `/projects` | List / create projects |
| `GET/PATCH` | `/projects/{id}` | Get / update project |
| `GET/POST` | `/projects/{id}/packages` | List / create packages |
| `GET/PATCH/DELETE` | `/projects/{id}/packages/{pkg_id}` | Package CRUD |

### QR Tokens

| Method | Path | Description |
|---|---|---|
| `GET` | `/scan/{token}` | Public scan — no auth; returns package context |
| `GET` | `/qr-tokens` | Admin: list tokens (with scan_url) |
| `POST` | `/qr-tokens` | Admin: create token for a package |
| `DELETE` | `/qr-tokens/{token}` | Admin: revoke token |

### Reports

| Method | Path | Description |
|---|---|---|
| `GET` | `/reports/overview` | Filtered overview (Resolved/High/Overdue/Others) |
| `GET` | `/reports/pivot` | Pivot crosstab query |
| `POST` | `/reports/export` | XLSX export (rate-limited) |
| `GET` | `/reports/quarterly-plan` | Current quarter assignments |
| `PUT` | `/reports/quarterly-plan/{role}` | Update role's report assignment |
| `POST` | `/reports/quarterly-library` | Save named report to library |
| `GET` | `/reports/quarterly-library` | List library |
| `DELETE` | `/reports/quarterly-library/{id}` | Remove from library |
| `PATCH` | `/reports/limits` | Update per-role caps (super_admin) |
| `GET` | `/reports/limits` | Get current caps |

### Viewers / Tasks

| Method | Path | Description |
|---|---|---|
| `GET` | `/tickets/{id}/viewers` | List viewers (Informed + Observer) |
| `POST` | `/tickets/{id}/viewers` | Add viewer |
| `DELETE` | `/tickets/{id}/viewers/{user_id}` | Remove viewer |
| `GET` | `/tickets/{id}/tasks` | List tasks |
| `POST` | `/tickets/{id}/tasks` | Create task |
| `PATCH` | `/tickets/{id}/tasks/{task_id}` | Update task |
| `DELETE` | `/tickets/{id}/tasks/{task_id}` | Delete task |

### Webhooks

| Method | Path | Description |
|---|---|---|
| `POST` | `/webhooks/keycloak` | Keycloak event webhook (invite accepted → activate officer) |

---

## 5. Authentication

| Mode | Mechanism |
|---|---|
| Production | Keycloak OIDC JWT bearer token. `ticketing_api_auth` container validates tokens. |
| Local/demo | `NEXT_PUBLIC_BYPASS_AUTH=true` — `grm_bypass_user` cookie; officer identity from roster. |
| Chatbot webhook | `X-Ticketing-Secret` header = `TICKETING_SECRET_KEY` env var. |
| Keycloak webhook | `X-Keycloak-Webhook-Secret` header = `KEYCLOAK_WEBHOOK_SECRET` env var. |
