# Ticketing System – Decisions (as-built, June 2026)

This file records **settled product, architecture, and integration decisions** for the GRM ticketing system.
It reflects what has actually been built. Questions that drove these decisions are in `00_ticketing_overview_and_questions.md`.

---

## 1. Product and scope

- **Country / project scope (v1):** Nepal, KL Road GRM (ADB Loan 52097-003). Data model is multi-tenant ready: `country`, `organization_id`, `project_id`, `location_code`.
- **Primary users:** Three tiers — ADB (supervisor/observer), Government of Nepal / DOR (implementing officers), external partners (contractors L1, controllers L2).
- **UI requirement:** Full modern web UI (Next.js 16, Tailwind v4) shipped as part of the system. Not API-only.
- **Chatbot independence:** Ticketing is optional — chatbot + grievance backend run without ticketing. Integration is API-only, fire-and-forget webhook from chatbot to `POST /api/v1/tickets`.

---

## 2. Architecture

- **Same Postgres instance (`grievance_db`), separate `ticketing.*` schema.**
- No cross-schema FK from `ticketing.*` into `public.*`. All cross-service data via APIs.
- PII never stored in `ticketing.*`. Officer detail view fetches PII fresh via `GET /api/grievance/{id}`.
- Ticketing FastAPI service on port 5002 (standard) / 5003 (auth-mode).
- Auth: Keycloak OIDC in production; `NEXT_PUBLIC_BYPASS_AUTH=true` bypass mode for local dev.
- Background workers: dedicated Celery app (`grm_ticketing`) — SLA watchdog, LLM tasks, notification dispatch, report emails.

---

## 3. Data model decisions

| Decision | Detail |
|---|---|
| `grievance_id` | String ref (no FK). Ticket created from grievance at submission time via chatbot webhook. |
| `session_id` | Stored on ticket at creation — used for complainant notifications via orchestrator `POST /message`. |
| Non-PII cache | `grievance_summary`, `grievance_categories`, `grievance_location`, `priority` cached at creation. PII never cached. |
| `project_id` | FK to `ticketing.projects` (replaced legacy `project_code` string). |
| `package_id` | Set when ticket created via QR token scan; NULL for walk-in / phone intake. Soft ref (no FK) so non-QR tickets are always valid. |
| `is_seah` | Boolean flag; DB-level filter ensures SEAH tickets are invisible to non-SEAH roles. |
| `complainant_reply_owner_id` | User who holds the "reply to complainant" capability. Defaults to L1 Actor; reassignable by any Actor above L1. |
| `current_overdue_episode_id` | FK to `ticket_overdue_episodes`. NULL = not overdue. One row per overdue stint per step. |
| `ai_summary_en` | LLM findings digest (GPT-4, Celery task). Role-gated: hidden from L1/L2 field officers. |

---

## 4. Workflow and escalation

- **Two workflows:** Standard GRM (4 levels) and SEAH (dedicated officers, invisible to standard roles).
- One grievance → one ticket → one workflow. Never both.
- **Escalation triggers:** automatic (Celery SLA watchdog, every 15 min) + manual (officer button).
- **Auto-assign on escalation:** `auto_assign_officer()` called inside `escalate_ticket()`; notification fires after reassign.
- **Complainant notification on RESOLVE / ESCALATE:** automatic via `notify_complainant.delay()` — tries orchestrator `POST /message` first, falls back to `POST /api/messaging/send-sms`.
- **GRC (L3):** Two-step: Convene (schedules hearing, notifies all GRC members) → Decide (records resolution).

---

## 5. Permission / tier model

Four-tier model per ticket step:

| Tier | Who | Permissions |
|---|---|---|
| **Actor** | Officer assigned to current step | Can perform step actions (acknowledge, escalate, resolve, etc.) |
| **Supervisor** | Manager of current Actor | Can read, assign, manually escalate |
| **Informed** | Previous Actors (auto-moved on escalation) | Read + comment |
| **Observer** | ADB, senior oversight roles | Read-only; no action |

- `ticket_viewers` table stores all non-Actor participants with a `tier` column.
- `notification_rules` in settings JSON controls which tiers receive which notification events.
- Role-based filters enforced at every API endpoint (`OfficerScope`).

---

## 6. QR token feature

- QR tokens link a physical location / project package to the chatbot intake URL.
- One QR code per package (e.g. a road segment sign). Revocable; expiry optional.
- When a complainant scans, the chatbot pre-fills `project_code`, `location_code`, `package_id` and displays the package label in the greeting.
- `ticketing.qr_tokens` table + `GET /api/v1/scan/{token}` public endpoint.
- QR image generated client-side via qrserver.com API (no server-side image lib needed).

---

## 7. Reports

- **Overview tab:** Filtered ticket lists (Resolved / High / Overdue / Others).
- **Pivot tab:** Excel-style crosstab builder (any dimension × any metric).
- **Quarterly email tab:** Named report library + role assignments (max 3 per role per quarter); Celery dispatches email per assignment.
- **Summary tab (§12):** Quarterly matrix + charts for ADB Project Director — **specified, not yet built**.
- **Export:** XLSX via openpyxl. Rate-limited per user (config in `report_limits` settings JSON).
- **Overdue episodes (`ticket_overdue_episodes`):** Source of truth for "SLA breached Y/N per level" in reports and Summary tab.

---

## 8. LLM / AI features

- **Per-note translation to English:** Celery task using GPT-4 — field officers write in Nepali; supervisors read translated notes.
- **Findings digest (`ai_summary_en`):** Generated by `POST /tickets/{id}/findings`. Role-gated display.
- **Model:** GPT-4 via OpenAI. Tasks in `ticketing/tasks/` (separate Celery app from chatbot LLM queue).

---

## 9. Notifications

| Channel | Who | Trigger |
|---|---|---|
| In-app badge | Officers | Badge count refreshes on navigation |
| Chatbot message | Complainant | RESOLVE, ESCALATE → `POST /message` to orchestrator |
| SMS fallback | Complainant | When session expired → `POST /api/messaging/send-sms` |
| Email | Quarterly report recipients (by role) | Celery quarterly dispatch |
| In-app (GRC) | All GRC members for project | On GRC_CONVENE action |

---

## 10. Auth and officer management

- **Production:** Keycloak OIDC. Webhook (`POST /api/v1/webhooks/keycloak`) creates `UserRole` + `OfficerOnboarding` on invite acceptance.
- **Local/demo:** `NEXT_PUBLIC_BYPASS_AUTH=true` — header role-switcher lists officers from `GET /api/v1/users/roster`.
- **Officer lifecycle:** `officer_onboarding` table — states: `invited` → `active`.
- **Admin model (locked):** three keys (`super_admin`, `country_admin`, `project_admin`); **`workflow_track`** (`standard` \| `seah`) on country and project **assignment scope** — no `seah_admin` / `seah_project_admin` / `local_admin`. Details: [11_roles_and_permissions.md](11_roles_and_permissions.md).
- **Operational roles:** `ticketing.roles` — GRM case handlers and observers; configured in Roles & permissions tab, assigned by `project_admin` / `country_admin`.
- **OfficerScope:** Org + project + package + location scope; enforced on ticket queries and auto-assign.

---

## 11. Settings

All configurable via Settings UI (`/settings` — role-gated; see [10_settings_overview.md](10_settings_overview.md)):

- Workflows (steps, SLA per step, tier config, notification rules) — [12_workflows_configuration.md](12_workflows_configuration.md)
- GRM roles catalog — [11_roles_and_permissions.md](11_roles_and_permissions.md)
- Organizations, officers — [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md)
- Projects, packages, go-live — [13_projects_and_packages.md](13_projects_and_packages.md)
- Locations, project types, quarterly report plan, system JSON — [14_platform_settings.md](14_platform_settings.md)
- QR tokens (per package) — [13_projects_and_packages.md](13_projects_and_packages.md)
- Report limits (max assignments per quarter) — [09_reports_and_report_builder.md](09_reports_and_report_builder.md)
- `chatbot_webchat_url` (env; used in QR scan redirect) — [14_platform_settings.md](14_platform_settings.md)
