# Ticketing System – Domain Model (as-built, June 2026)

Full schema DDL → `04_ticketing_schema.md`. API contracts → `03_ticketing_api_integration.md`.

---

## Core entities

### Ticket (`ticketing.tickets`)

The central entity. One ticket per grievance submission.

| Field | Type | Notes |
|---|---|---|
| `ticket_id` | UUID | PK |
| `grievance_id` | String(64) | String ref to `public.grievances`; no FK |
| `complainant_id` | String(64) | String ref; no FK |
| `session_id` | String(255) | Chatbot session; used for complainant reply via orchestrator |
| `chatbot_id` | String(64) | e.g. `nepal_grievance_bot` |
| `grievance_summary` | Text | Non-PII cache from submission |
| `grievance_categories` | Text | Non-PII cache |
| `grievance_location` | Text | Non-PII cache (district/municipality text) |
| `country_code` | String(8) | e.g. `NP` |
| `organization_id` | String(64) | Executing agency (e.g. `DOR`) |
| `location_code` | String(64) | Canonical location (see `LOCATION_CODES.md`) |
| `project_id` | String(36) | FK → `ticketing.projects` |
| `project_code` | String(64) | Deprecated; kept for backwards compat |
| `package_id` | String(36) | Set via QR scan; NULL for walk-in |
| `status_code` | String(32) | `OPEN`, `IN_PROGRESS`, `PENDING_ESCALATION`, `ESCALATED`, `RESOLVED`, `CLOSED` |
| `current_workflow_id` | UUID FK | Active workflow |
| `current_step_id` | UUID FK | Current step within workflow |
| `priority` | String(32) | `NORMAL`, `HIGH`, `SENSITIVE` |
| `is_seah` | Boolean | DB-level filter; SEAH tickets invisible to non-SEAH roles |
| `assigned_to_user_id` | String(128) | Current Actor |
| `assigned_role_id` | String(36) | Role at current step |
| `complainant_reply_owner_id` | String(128) | Who can reply to complainant (default: L1 Actor) |
| `step_started_at` | Timestamp | SLA timer start |
| `sla_breached` | Boolean | True once step SLA exceeded |
| `current_overdue_episode_id` | UUID FK | Open overdue episode (NULL = on time) |
| `ai_summary_en` | Text | LLM findings digest; role-gated display |

### TicketEvent (`ticketing.ticket_events`)

Append-only audit log for every state change and communication.

Key `event_type` values: `CREATED`, `ACKNOWLEDGED`, `ESCALATED`, `RESOLVED`, `CLOSED`, `NOTE_ADDED`, `FIELD_REPORT`, `COMPLAINANT_MESSAGE`, `REPLY_SENT`, `GRC_CONVENED`, `GRC_DECIDED`, `TIER_CHANGED`, `TASK_ADDED`, `FILE_UPLOADED`, `FINDINGS_GENERATED`.

Each event carries: `ticket_id`, `event_type`, `actor_user_id`, `note` (text), `payload` (JSONB), `created_at`.

### TicketTask (`ticketing.ticket_tasks`)

Officer action items attached to a ticket. Fields: `title`, `description`, `status` (`open`/`done`), `assigned_to_user_id`, `due_date`.

### TicketViewer (`ticketing.ticket_viewers`)

Non-Actor participants on a ticket with a `tier` column:
- `INFORMED` — previous Actors; auto-added on escalation
- `OBSERVER` — ADB/senior oversight; added explicitly

### TicketOverdueEpisode (`ticketing.ticket_overdue_episodes`)

One row per overdue stint at a workflow step. Source of truth for reports and Summary tab.

| Field | Notes |
|---|---|
| `episode_id` | PK |
| `ticket_id` | FK |
| `workflow_step_id`, `step_order` | Step context at breach |
| `assigned_to_user_id`, `assigned_role_id` | Officer at breach |
| `started_at` | When SLA was breached |
| `ended_at`, `end_reason` | When overdue period closed (resolved / escalated / manually cleared) |
| `triggered_by` | `auto` (Celery) or `manual` |

### TicketResolvedSummary (`ticketing.ticket_resolved_summaries`)

Structured closure document generated when a ticket is resolved. For supervisors, GRC, ADB, and quarterly reporting. Fields include: `resolution_category`, `root_cause`, `actions_taken`, `outcome`, `generated_by`.

### TicketContextCache (`ticketing.ticket_context_cache`)

LLM context window cache (per ticket) for findings generation. Avoids re-fetching full event history on each AI call.

---

## Organisation and geography

### Organization (`ticketing.organizations`)

Logical tenant (e.g. DOR, ADB). Scopes which tickets a user can see.

Fields: `organization_id` (server-generated from name initials + country prefix), `name`, `country_code`, `org_type`.

### Location (`ticketing.locations`)

Location tree: country → province → district → municipality.

Fields: `location_code` (canonical mnemonic, see `LOCATION_CODES.md`), `name`, `name_ne`, `parent_code`, `level` (`province`/`district`/`municipality`), `country_code`.

Also: `ticketing.location_translations` (EN/NE display names for codes).

### Project (`ticketing.projects`)

A named infrastructure project (e.g. KL Road). Links org, locations, workflows, and packages.

Fields: `project_id`, `name`, `project_code`, `organization_id`, `country_code`, `chatbot_url` (used in QR redirect).

### Package (`ticketing.packages`)

A physical asset within a project (e.g. a road segment). Each package can have multiple QR tokens.

Fields: `package_id`, `project_id`, `name`, `location_code`.

`ticketing.package_locations` — many-to-many join: one package can span multiple locations.
`ticketing.package_organizations` — package → allowed organizations.

### ProjectType (`ticketing.project_types`)

Lookup: type of infrastructure project (road, bridge, etc.).

### Country (`ticketing.countries`)

Lookup table for multi-country support.

---

## Workflow and roles

### WorkflowDefinition (`ticketing.workflow_definitions`)

Named workflow (e.g. `KL_ROAD_4_LEVEL`, `KL_ROAD_SEAH`). Fields: `name`, `description`, `workflow_scope` (`standard`/`seah`).

### WorkflowStep (`ticketing.workflow_steps`)

One row per level. Fields: `step_order`, `name`, `role_required`, `response_time_hours`, `resolution_time_days`, `tier_config` (JSONB), `notification_rules` (JSONB).

### WorkflowAssignment (`ticketing.workflow_assignments`)

Maps (organization, project, location, priority) to a `workflow_definition`. Engine uses this to pick the right workflow at ticket creation.

### Role (`ticketing.roles`)

Named GRM role. Fields: `role_code`, `name`, `description`, `workflow_scope` (`standard`/`seah`/`both`), `jurisdiction_mode`.

9 seeded GRM roles (from `grm_role_catalog.py`): `site_safeguards_focal_person`, `pd_piu_safeguards_focal`, `grc_chair`, `grc_member`, `seah_national_officer`, `seah_hq_officer`, `adb_national_project_director`, `adb_hq_safeguards`, `super_admin`.

### UserRole (`ticketing.user_roles`)

Maps a user (Keycloak sub or bypass ID) to a role + org + location scope.

### OfficerScope (`ticketing.officer_scopes`)

Fine-grained: which org + location combination a user can act on. Used to filter ticket queries.

### OfficerOnboarding (`ticketing.officer_onboarding`)

Lifecycle: `invited` → `active`. Created by Keycloak webhook on invite; updated on first login.

---

## QR tokens

### QrToken (`ticketing.qr_tokens`)

| Field | Notes |
|---|---|
| `token` | Opaque 8-char hex, PK |
| `package_id` | FK to `ticketing.packages` |
| `is_active` | Revocable |
| `expires_at` | Optional |
| `scan_url` | Full URL returned to UI for QR image generation |

Public endpoint: `GET /api/v1/scan/{token}` — returns package label, location_code, project_code. Used by chatbot `ActionIntroduce` to pre-fill slots.

---

## Settings (`ticketing.settings`)

Key/value JSON store for system-wide configuration. Managed via Settings UI.

Key settings:
- `chatbot_webchat_url` — base URL for QR code scan redirect
- `notification_rules` — per-event, per-tier notification channel matrix
- `report_limits` — per-role quarterly email assignment caps (super_admin JSON)
- Workflow step SLA overrides

---

## AdminAuditLog (`ticketing.admin_audit_log`)

Append-only log of all admin actions (settings changes, user invites, role modifications).

Fields: `log_id`, `actor_user_id`, `action_type`, `target_entity`, `target_id`, `payload` (JSONB), `created_at`.
