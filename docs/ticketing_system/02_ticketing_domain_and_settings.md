# Ticketing System – Domain Model (as-built, July 2026)

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
| `organization_id` | String(64) | Routing org for auto-assign (e.g. `DOR` = implementing agency on KL Road). Set on create by `resolve_ticket_organization()` when `project_code` / `package_id` present; must match `officer_scopes.organization_id`. |
| `location_code` | String(64) | Canonical location (see `LOCATION_CODES.md`) |
| `project_id` | String(36) | FK → `ticketing.projects` |
| `project_code` | String(64) | Deprecated; kept for backwards compat |
| `package_id` | String(36) | Set via QR scan; NULL for walk-in |
| `status_code` | String(32) | `OPEN`, `IN_PROGRESS`, `ESCALATED`, `GRC_HEARING_SCHEDULED`, `RESOLVED` (`CLOSED` is legacy — read-compat only, never written; `PENDING_ESCALATION` removed) |
| `current_workflow_id` | UUID FK | Active workflow |
| `current_step_id` | UUID FK | Current step within workflow |
| `priority` | String(32) | `NORMAL`, `HIGH`, `SENSITIVE` |
| `is_seah` | Boolean | DB-level filter; SEAH tickets invisible to non-SEAH roles |
| `intake_route` | String(64) | Chatbot `story_main` at intake (e.g. `new_grievance`, `seah_intake`, `road_hazard_grievance`); used for workflow (re-)resolution |
| `intake_fast_path` | String(64) | Deprecated intake signal (kept for compat; `intake_route` is authoritative) |
| `is_archived`, `archived_at` | Boolean / Timestamp | Resolved-case archiving — see `docs/ARCHIVING_AND_RETENTION.md` |
| `assigned_to_user_id` | String(128) | Current Actor |
| `assigned_role_id` | String(36) | Role at current step |
| `complainant_reply_owner_id` | String(128) | Who can reply to complainant (default: L1 Actor) |
| `step_started_at` | Timestamp | SLA timer start |
| `sla_breached` | Boolean | True once step SLA exceeded |
| `current_overdue_episode_id` | UUID FK | Open overdue episode (NULL = on time) |
| `ai_summary_en` | Text | LLM findings digest; role-gated display |

### TicketEvent (`ticketing.ticket_events`)

Append-only audit log for every state change and communication.

Key `event_type` values: `CREATED`, `ACKNOWLEDGED`, `ESCALATED`, `RESOLVED`, `NOTE_ADDED`, `FIELD_REPORT`, `COMPLAINANT_MESSAGE`, `REPLY_SENT`, `GRC_CONVENED`, `ASSIGNED`, `REASSIGNMENT_REQUESTED`, `CLASSIFICATION_VALIDATED`, `TIER_CHANGED`, `TASK_ASSIGNED`/`TASK_COMPLETED`, `FILE_UPLOADED`, `FINDINGS_GENERATED`. (`CLOSED` and `GRC_DECIDED` remain only as historical event types on old rows — the `CLOSE` and `GRC_DECIDE` actions were removed in v1; see `08_ticket_resolution_and_case_summary.md`.)

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

Adjacency-list admin tree per country (province → district → municipality for Nepal).

Fields: `location_code` (PK, canonical mnemonic — see `LOCATION_CODES.md`, e.g. `P1`, `P1_MOR`), `country_code`, `level_number` (matches `location_level_defs`), `parent_location_code` (self-FK), `source_id` (import re-sync), `latitude`/`longitude`, `is_active`. Names are **not** stored on the node — display names live in `ticketing.location_translations` (`location_code` + `lang_code` composite PK). Level semantics per country in `ticketing.location_level_defs`.

Full geography model + submit-time mapping: [18_geography_and_locations.md](18_geography_and_locations.md).

### Project (`ticketing.projects`)

A named infrastructure project (e.g. KL Road). Links org, locations, workflows, and packages.

Fields: `project_id`, `name`, `project_code`, `organization_id`, `country_code`, `chatbot_url` (used in QR redirect).

### Package (`ticketing.packages`)

A physical asset within a project (e.g. a road segment). Each package can have multiple QR tokens.

Fields: `package_id`, `project_id`, `name`, `location_code`.

`ticketing.package_locations` — many-to-many join: one package can span multiple locations.
`ticketing.package_organizations` — package → allowed organizations. **Deprecated** (legacy, still present; DECISION 2026-07-10) — per-lot variation is now staffing override ([13 §5A](13_projects_and_packages.md)).

### ProjectType (`ticketing.project_types`)

Lookup: type of infrastructure project (road, bridge, etc.).

### Country (`ticketing.countries`)

Lookup table for multi-country support.

---

## Workflow and roles

### WorkflowDefinition (`ticketing.workflow_definitions`)

Named, versioned workflow (e.g. Default GRM 4-level, Default SEAH). Fields: `workflow_key` (unique slug), `display_name`, `description`, `workflow_type` (`standard`/`seah` — visibility / SEAH gate), `status` (`draft`/`published`/`archived`), `version` (incremented on publish), `is_template`, `template_source_id`.

Full lifecycle (draft → publish → archive), templates, and admin UI: [12_workflows_configuration.md](12_workflows_configuration.md).

### WorkflowStep (`ticketing.workflow_steps`)

One row per level. Fields: `step_order`, `step_key`, `display_name`, `assigned_role_key` (GRM role for the Actor at this step), `response_time_hours`, `resolution_time_days` (NULL = no auto-escalation), plus tier-model fields `supervisor_role`, `informed_roles` (JSON), `observer_roles` (JSON), `informed_pii_access`, and display metadata `stakeholders` / `expected_actions` (JSON). `is_deleted` soft delete.

> **Deprecated shape:** the original columns `role_required`, `tier_config` (JSONB) and per-step `notification_rules` (JSONB) no longer exist — replaced by `assigned_role_key` + the tier fields above; notification rules moved to the `settings.notification_rules` key.

### ProjectWorkflow (`ticketing.project_workflows`)

Active project ↔ workflow binding ("slots"): a project can attach N workflow streams. Fields: `project_id`, `workflow_id` (FK → published definition), `display_label`, `classifications` (JSON — taxonomy groups for re-route after category edit), `intake_route` (chatbot `story_main`: `new_grievance`, `seah_intake`, `road_hazard_grievance`; scalar since migration `e7f9a1b3`), `is_default` (catch-all), `sort_order`.

`resolve_workflow()` picks the ticket's workflow from these bindings (classification/intake-route match → default), falling back to legacy `projects.standard_workflow_id`/`seah_workflow_id`, then legacy `workflow_assignments`.

### WorkflowAssignment (`ticketing.workflow_assignments`) — legacy

Maps (organization, location, project_code, priority) to a workflow. **Legacy fallback only** — used by `resolve_workflow()` when the ticket has no resolvable project. Not configured in the UI; do not use for new projects.

### Role (`ticketing.roles`)

Named GRM role. Fields: `role_key` (unique), `display_name`, `description`, `workflow_scope` (`standard`/`seah`/`both`), `jurisdiction_mode` (`field`/`country`/`global`), `permissions` (JSON), `role_kind` (`operational`/`admin`), `role_origin` (`system`/`custom`).

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

**Full admin UI specs:** [10_settings_overview.md](10_settings_overview.md) (index) → [11](11_roles_and_permissions.md)–[14](14_platform_settings.md).

Key settings:
- `chatbot_webchat_url` — base URL for QR code scan redirect
- `notification_rules` — per-event, per-tier notification channel matrix
- `report_limits` — per-role quarterly email assignment caps (super_admin JSON)
- `archiving_policy` — resolved-case archiving schedule and attachment tiering (super_admin JSON) — see [`docs/ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md)
- Workflow step SLA overrides

---

## AdminAuditLog (`ticketing.admin_audit_log`)

Append-only log of all admin actions (settings changes, user invites, role modifications).

Fields: `log_id`, `actor_user_id`, `action_type`, `target_entity`, `target_id`, `payload` (JSONB), `created_at`.
