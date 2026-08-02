# Ticketing System – API Reference (as-built, July 2026)

Integration with the ticketing system is API-first. This document covers:
1. **Inbound** — chatbot/backend calls ticketing
2. **Outbound** — ticketing calls chatbot, messaging, grievance API
3. **Direct `public.*` access** — the enumerated exception to "API-only" (§3b)
4. **Full endpoint reference** — all implemented ticketing API routes

> **"API-only" was never true and is no longer claimed** (amended 2026-07-15). Ticketing reads
> and writes a closed set of `public.*` tables directly — see **§3b** for the contract, and
> CLAUDE.md §Data rules rule 1. Complainant PII *is* API-only; grievance content is not.

---

## 1. Chatbot → Ticketing (Inbound)

### 1.1 Create ticket from grievance submission (primary path)

Called by `backend/actions/utils/ticketing_dispatch.py` after the grievance row is saved — **synchronous HTTP POST**, fire-and-forget (failures are logged; grievance submit never blocks).

**Call sites (all intake paths):**

| Path | Module | When |
|------|--------|------|
| Standard submit | `backend/actions/action_submit_grievance.py` (`BaseActionSubmit`) | After DB save |
| SEAH submit | `backend/actions/action_submit_grievance.py` (`ActionSubmitSeah`) | After DB save |
| Road-hazard fast path | `backend/actions/forms/intake_submit.py` (`complete_road_hazard_intake_submit`) | After DB save |

Shared helper: `dispatch_grievance_from_tracker()` builds the payload from tracker slots (+ optional grievance dict), then `dispatch_ticket()` POSTs to ticketing.

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
  "organization_id": "DOR",         // hint only when project_code/package_id set — server resolves (§1.3)
  "location_code": "P1_MOR",
  "project_code": "KL_ROAD",
  "package_id": "...",              // optional, from QR scan
  "priority": "NORMAL",
  "is_seah": false,
  "grievance_summary": "...",
  "grievance_categories": "...",
  "grievance_location": "Morang District, Koshi Province"
}
Response: { "ticket_id": "...", "status_code": "OPEN", "created_at": "..." }
```

**Server-side intake** (`ticketing/services/ticket_intake.py` → `create_ticket_from_intake()`):

- Resolves workflow, auto-assigns L1, creates `CREATED` event.
- When `project_code` or `package_id` is present, **`organization_id` is overwritten** by `resolve_ticket_organization()` (see [13_projects_and_packages.md](13_projects_and_packages.md) §6) before workflow lookup and auto-assign.
- Duplicate `grievance_id` → **409** (sync backfill skips quietly).

Env (orchestrator / backend): `TICKETING_API_URL`, `TICKETING_SECRET_KEY`.

### 1.2 Grievance sync (safety net — secondary path)

Celery Beat task `ticketing.tasks.grievance_sync.sync_grievances` every **2 minutes** (`grm_celery_beat`).

**Option A behaviour (does not race the webhook):**

| Case | Action |
|------|--------|
| Ticket exists | **UPDATE** cached fields only (`grievance_summary`, `grievance_categories`, `grievance_location`) |
| No ticket, grievance age &lt; grace | **Skip** create (`pending_webhook` in task result) |
| No ticket, age ≥ grace (default **180s**) | **Backfill CREATE** via same `create_ticket_from_intake()` as §1.1 |

Grace period: `ticketing_sync_backfill_grace_seconds` in settings, env `TICKETING_SYNC_BACKFILL_GRACE_SECONDS` (minimum 60).

Backfill payload is best-effort from `public.grievances` (+ complainant `location_code` join); **`package_id` is usually NULL** — QR/webhook path remains authoritative for package-scoped assign.

Policy helpers (no DB): `ticketing/services/grievance_sync_policy.py`.

### 1.3 Ticket routing organization

`ticketing/services/project_routing.py` → `resolve_ticket_organization(db, project_code=…, package_id=…)`:

1. **Prefer** the project's `implementing_agency_org_id` ([DECISION §2](../sprints/2026-07_org_chart_positions/DECISION-project-participants-and-supervision.md)).
2. **Legacy fallback** (projects predating that field): `package_organizations` (if `package_id`) then `project_organizations` for the routing role (default `implementing_agency`) — deprecated.

Used on **ticket create** and on **field-officer invite / add scope** (`validate_jurisdiction` overrides wrong org, e.g. contractor vs DOR). Country/global observer roles (`jurisdiction_mode=country`) keep the submitted org (e.g. ADB).

### 1.4 QR token scan (chatbot pre-fill)

Called by chatbot `ActionIntroduce` when URL parameter `t` is present.

```
GET /api/v1/scan/{token}
Response: {
  "token": "a1b2c3d4",
  "package_id": "...",
  "package_label": "KL Road — Km 45 Sign",
  "location_code": "P1_MOR",
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
GET  {BACKEND_GRIEVANCE_BASE_URL}/api/grievance/{grievance_id}          → x-api-key
POST {BACKEND_GRIEVANCE_BASE_URL}/api/grievance/{grievance_id}/status   → x-api-key
```

Called from ticket detail view to fetch **complainant PII** (name, phone) on-demand. Never cached in `ticketing.*`. Both endpoints require `x-api-key: $TICKETING_SECRET_KEY` as of T3-06; every call funnels through `ticketing/clients/grievance_api.py`.

**Grievance *state* changes go over this API, never over SQL.** That is a real invariant — keep it.

> ⚠️ The GET does **not** decrypt PII today; it returns pgcrypto hex ciphertext, which `ticketing/services/pii_vault.py` decrypts client-side. T3-04 fixes this at the backend. See CLAUDE.md §APIs to call.

---

## 3b. Ticketing → `public.*` direct access (NOT via the API)

**Ticketing reads — and in three places writes — a closed, enumerated set of `public.*` tables through its own SQLAlchemy session.** This is **deliberate and documented as of 2026-07-15**, not a violation and not tech debt to pay down. The full decision and evidence: [`../sprints/archive/2026-08_tier3_structural/00-reassessment.md`](../sprints/archive/2026-08_tier3_structural/00-reassessment.md) §6.

Measured surface — **11 statements, 5 tables, 3 writes**:

| `public.*` table | Access | Callers |
| --- | --- | --- |
| `grievances` | read | `services/grievance_content.py` (9 cols incl. `grievance_description`), `tasks/grievance_sync.py` (10 cols) |
| `file_attachments` | read + **`UPDATE`** (archive tier) | `api/ticket_access.py`, `api/routers/tickets/files.py`, `engine/ticket_actions.py`, `services/archiving.py` |
| `grievance_classification_taxonomy` | read + **`DELETE`+`INSERT`** (catalog resync) | `services/grievance_categories_catalog.py`, `seed/kl_road_standard.py` |
| `complainants` | read — join-only, **non-PII** (`location_code`) | `tasks/grievance_sync.py` |
| `grievance_parties` | read — join-only | `tasks/grievance_sync.py` |

**The contract is enforced, not aspirational.** `tests/ticketing/test_boundary_policy.py` fails when the code and this list disagree, in both directions, and when a column ticketing names disappears from the `public.*` schema baseline.

**Why not route these through the grievance API?** Because it would be a **security downgrade**. The direct read is behind a Keycloak JWT and `assert_ticket_visibility`'s SEAH + jurisdiction gate; `GET /api/grievance/{id}` has **no authz** even after T3-06 hardened it (D-38) — an `x-api-key` says *"this is ticketing"*, not *"this is officer X in district Y"*. Routing would also turn a PII-free query into a PII-bearing one, and `grievance_sync.py` pages 500 rows every 2 minutes against an API with no bulk endpoint. **Do not cite T3-06 as having made this viable** — it made the API a credible *authn + audit* boundary, not an *authorization* one.

**Two rules still hold and are pinned by the same test:** no cross-schema FK, and no complainant PII columns in `ticketing.*`.

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
| `PATCH` | `/tickets/{id}/classification` | Officer validates/edits summary + categories → `officer_confirmed` (see [17_classification_status.md](17_classification_status.md)) |
| `GET` | `/reference/grievance-categories` | Category options from classification taxonomy (TP-14) |
| `POST` | `/tickets/{id}/reply` | Reply to complainant via orchestrator |
| `POST` | `/tickets/{id}/inbound` | Record inbound complainant message |
| `GET` | `/tickets/{id}/sla` | SLA countdown data |
| `GET` | `/tickets/{id}/teammates` | Assignable teammates for this ticket |
| `POST` | `/tickets/{id}/seen` | Mark events as seen (badge clear) |
| `POST` | `/tickets/{id}/informed` | Add user to Informed tier |
| `PUT` | `/tickets/{id}/complainant-reply-owner` | Set complainant reply owner |
| `GET` | `/tickets/{id}/files` | List complainant-uploaded files |
| `GET` | `/files/{file_id}` | Download complainant file |
| `POST` | `/tickets/{id}/attachments` | Upload officer attachment |
| `GET` | `/tickets/{id}/attachments` | List officer attachments |
| `GET` | `/attachments/{file_id}` | Download officer attachment |
| `GET` | `/tickets/{id}/pii` | Fetch PII from grievance API (logged) |
| `GET` | `/tickets/{id}/resolved-summary` | Get resolved case summary |
| `POST` | `/tickets/{id}/resolved-summary` | Generate resolved summary (LLM) |
| `POST` | `/tickets/{id}/findings` | Generate AI findings digest (LLM) |
| `POST` | `/tickets/{id}/reveal` | Begin PII reveal session (logged) |
| `POST` | `/tickets/{id}/reveal/close` | Close PII reveal session |

### Ticket actions (`POST /tickets/{id}/actions`)

`action_type` values (`VALID_ACTIONS` in `ticketing/api/routers/tickets.py`):

| Action | Who | Effect |
|---|---|---|
| `ACKNOWLEDGE` | Assigned officer (or admin) | Moves status to IN_PROGRESS, starts SLA clock. **Blocked (422)** until classification is validated — see [17_classification_status.md](17_classification_status.md) |
| `ESCALATE` | Assigned officer / Supervisor / admin | Advances to next step, auto-assigns, notifies |
| `RESOLVE` | Assigned officer, admin, or `supervisor_role` match (with resolution record) | **Only terminal action** — resolves the case, notifies complainant. See `08_ticket_resolution_and_case_summary.md` §2 |
| `NOTE` | Any officer with access | Adds internal note to timeline (LLM EN translation async) |
| `FIELD_REPORT` | Assigned officer | Adds field report bubble to timeline |
| `GRC_CONVENE` | GRC chair | Sets `GRC_HEARING_SCHEDULED`, notifies all GRC members |
| `REASSIGNMENT_REQUESTED` | Assigned officer / admin | Requests (or performs) reassignment to another officer |

> **Removed in v1:** `CLOSE` and `GRC_DECIDE`. The only way to end a case is `RESOLVE` with a resolution record; GRC chairs use `GRC_CONVENE` then `RESOLVE` (or `ESCALATE` to legal) like any assigned officer. Direct reassignment by an admin also happens via `PATCH /tickets/{id}` (`assigned_to` → `ASSIGNED` event); there is no `ASSIGN` action.

### Auth (`ticketing/api/routers/auth.py`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Sign in with email + password (Keycloak direct grant) |
| `POST` | `/auth/forgot-password` | Request password reset |
| `POST` | `/auth/request-invite-link` | Re-request invite/setup link |
| `POST` | `/auth/reset-password` | Complete password reset |

### Workflows

Full contract in [12_workflows_configuration.md](12_workflows_configuration.md) §11. Highlights:

| Method | Path | Description |
|---|---|---|
| `GET` | `/workflows`, `/workflows/{id}` | List / detail + steps |
| `GET` | `/workflows/templates`, `/workflows/routing-options` | Templates; classifications + intake routes for the project workflow editor |
| `POST/PATCH/DELETE` | `/workflows`, `/workflows/{id}` | Create (optional clone) / metadata / delete (draft only) |
| `POST` | `/workflows/{id}/publish`, `/{id}/archive`, `/{id}/save-as-template` | Lifecycle |
| `POST/PATCH/DELETE` | `/workflows/{id}/steps…`, `POST …/steps/reorder` | Step editor |
| `GET/POST/DELETE` | `/workflows/{id}/assignments…` | **Legacy** workflow_assignments rows (fallback routing only) |
| `GET/PUT` | `/projects/{id}/workflows` | Project workflow bindings (slots) |

### Users / Roles / Admin scopes

| Method | Path | Description |
|---|---|---|
| `GET` | `/users/roster`, `/users/officers` | Officer lists (bypass switcher, Settings, staffing) |
| `GET` | `/users/invite/preflight` | Validate invite before creating |
| `POST` | `/users/invite` | Invite officer (`user_roles` + `officer_scopes`; field roles: org resolved from project — §1.3) |
| `POST` | `/users/{id}/resend-invite` | Re-send Keycloak setup link |
| `PATCH/DELETE` | `/users/{id}` | Update officer (org, roles, Keycloak sync) / deactivate |
| `GET/POST/DELETE` | `/users/{id}/roles…` | Role assignments |
| `GET/POST/DELETE` | `/users/{id}/scopes…` | Officer jurisdiction rows |
| `GET/PATCH` | `/users/me/preferences`, `/users/me/profile` | Own preferences / profile |
| `GET` | `/users/me/session`, `/users/me/admin-context`, `/users/me/badge`, `/users/me/notifications`, `/users/me/tasks` | Session, admin ladder context, badge count, notifications, own tasks |
| `GET/POST/PATCH/DELETE` | `/roles…` | Roles catalog CRUD; `GET /roles/archetypes` for the role wizard |
| `GET/POST/DELETE` | `/admin-scopes…` | Admin ladder (`org_admin` / `project_admin`); `POST /admin-scopes/{id}/send-invite` |

### Settings

| Method | Path | Description |
|---|---|---|
| `GET` | `/settings`, `/settings/{key}` | List / get settings (key/value JSON) |
| `PUT` | `/settings/{key}` | Update a setting (super-admin gate on sensitive keys — see `14_platform_settings.md` §7) |
| `DELETE` | `/settings/{key}` | Delete a setting |

### Organizations / Locations / Projects / Packages

| Method | Path | Description |
|---|---|---|
| `GET/POST/PATCH/DELETE` | `/organizations…` | Org CRUD |
| `GET` | `/countries` | Country list |
| `GET` | `/locations`, `/locations/{code}` | Location tree query / node |
| `POST` | `/locations/import` (+ `GET /locations/import/template.{csv,json}`) | Bulk location import |
| `GET/POST/PATCH/DELETE` | `/projects…` | Project CRUD |
| `GET` | `/projects/{id}/go-live` | Go-live readiness check |
| `GET/PATCH` | `/projects/{id}/messaging` | Project officer SMS/WhatsApp config |
| `GET/PUT` | `/projects/{id}/workflows` | Workflow slot bindings |
| ~~`/projects/{id}/organizations…`, `…/actor-roles`~~ | **deprecated** — legacy project actors / actor-role links (superseded by implementing agency + donors + staffing, [13](13_projects_and_packages.md)); still present |
| `GET/POST/DELETE` | `/projects/{id}/locations…` | Project location links |
| `GET/POST/PATCH` | `/projects/{id}/packages…` | Package CRUD |
| `POST/DELETE` | `/projects/{id}/packages/{pkg}/locations/{code}`, `…/organizations/{org}` | Package location + org links |

### Project types

| Method | Path | Description |
|---|---|---|
| `GET/POST/PATCH` | `/project-types…` | Project archetype CRUD (`14_platform_settings.md` §4) |

### QR Tokens

| Method | Path | Description |
|---|---|---|
| `GET` | `/scan/{token}` | Public scan — no auth; returns package context |
| `GET` | `/my-packages/qr` | Packages + QR tokens in the caller's scope |
| `GET/POST` | `/packages/{package_id}/qr-tokens` | List / create tokens for a package |
| `DELETE` | `/qr-tokens/{token}` | Revoke token |

### Reports

Full behaviour: `09_reports_and_report_builder.md`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/reports/query` | Operational report — four sections (Resolved/High/Overdue/Others) with filters |
| `GET` | `/reports/summary`, `/reports/summary/export` | Summary tab (quarterly matrix) + XLSX export |
| `POST` | `/reports/build` | Pivot/report builder query |
| `GET` | `/reports/export`, `/reports/export-all` | XLSX export (rate-limited) |
| `POST` | `/reports/share` | Create public share link (`GET /reports/share/{token}`) |
| `GET` | `/reports/fields` | Available report fields |
| `GET/PUT/POST/PATCH/DELETE` | `/reports/quarterly-plan`, `…/quarterly-schedule`, `…/quarterly-assignments…`, `…/quarterly-library…` | Quarterly email plan, schedule, role assignments, report library |

### Viewers / Tasks

| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/tickets/{id}/viewers` | List / add viewers (Informed + Observer) |
| `DELETE` | `/tickets/{id}/viewers/{user_id}` | Remove viewer |
| `GET/POST` | `/tickets/{id}/tasks` | List / create tasks |
| `POST` | `/tickets/{id}/tasks/{task_id}/complete` | Complete task |
| `GET` | `/users/me/tasks` | Own open tasks across tickets |

### Public (no officer auth)

| Method | Path | Description |
|---|---|---|
| `GET` | `/public/closure/{token}` (+ `/pdf`) | Complainant-facing closure document + PDF |
| `GET` | `/public/report/{token}`, `/reports/share/{token}` | Shared report views |
| `GET` | `/scan/{token}` | QR scan (above) |

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
