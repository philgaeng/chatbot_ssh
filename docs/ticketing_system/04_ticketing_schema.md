# Ticketing System – Database Schema (as-built, July 2026)

All tables live in the `ticketing` schema inside `grievance_db`.
No cross-schema FK from `ticketing.*` into `public.*`.
All SQLAlchemy models use `__table_args__ = {"schema": "ticketing"}`.
Migrations managed by Alembic: `ticketing/migrations/alembic.ini`.

**Location codes:** Canonical rules for `location_code` → `LOCATION_CODES.md`.

---

## 1. Design rules

1. No FK from `ticketing.*` into `public.*`.
2. PII (`name`, `phone`, `email`, `address`) never stored in `ticketing.*`.
3. Grievance/complainant referenced by `grievance_id` (String), `complainant_id` (String) only.
4. Every model: `__table_args__ = {"schema": "ticketing"}`.
5. Alembic `include_object` scoped to `ticketing` schema only; `version_table_schema="ticketing"`.

---

## 2. Core tables

### `ticketing.tickets`

```sql
ticket_id                   VARCHAR(36)   PK
grievance_id                VARCHAR(64)   NOT NULL        -- string ref, no FK
complainant_id              VARCHAR(64)
session_id                  VARCHAR(255)                  -- chatbot session for complainant reply
chatbot_id                  VARCHAR(64)   DEFAULT 'nepal_grievance_bot'
grievance_summary           TEXT                          -- non-PII cache
grievance_categories        TEXT
grievance_location          TEXT
country_code                VARCHAR(8)    DEFAULT 'NP'
organization_id             VARCHAR(64)   NOT NULL        -- routing org; resolved from project/package actors on create (see project_routing.py)
location_code               VARCHAR(64)
project_id                  VARCHAR(64)   FK → ticketing.projects (SET NULL)
project_code                VARCHAR(64)                   -- deprecated, kept for compat
package_id                  VARCHAR(36)                   -- soft ref, no FK; set via QR scan
status_code                 VARCHAR(32)   DEFAULT 'OPEN'
current_workflow_id         VARCHAR(36)   FK → ticketing.workflow_definitions
current_step_id             VARCHAR(36)   FK → ticketing.workflow_steps (SET NULL)
priority                    VARCHAR(32)   DEFAULT 'NORMAL'
is_seah                     BOOLEAN       DEFAULT FALSE
intake_route                VARCHAR(64)                   -- chatbot story_main at intake (workflow re-resolution)
intake_fast_path            VARCHAR(64)                   -- deprecated intake signal (compat)
assigned_to_user_id         VARCHAR(128)
assigned_role_id            VARCHAR(36)
complainant_reply_owner_id  VARCHAR(128)                  -- default: L1 Actor
step_started_at             TIMESTAMPTZ
sla_breached                BOOLEAN       DEFAULT FALSE
current_overdue_episode_id  VARCHAR(36)   FK → ticketing.ticket_overdue_episodes (SET NULL)
ai_summary_en               TEXT                          -- LLM findings digest
ai_summary_updated_at       TIMESTAMPTZ
is_archived                 BOOLEAN       DEFAULT FALSE   -- resolved-case archiving
archived_at                 TIMESTAMPTZ
is_deleted                  BOOLEAN       DEFAULT FALSE
created_at                  TIMESTAMPTZ   NOT NULL
created_by_user_id          VARCHAR(128)
updated_at                  TIMESTAMPTZ   NOT NULL
updated_by_user_id          VARCHAR(128)
```

Indexes: `grievance_id`, `(organization_id, location_code, status_code)`, `assigned_to_user_id`, `(current_workflow_id, current_step_id)`, `is_seah`, `(is_archived, status_code)`.

Status codes written by current code: `OPEN`, `IN_PROGRESS`, `ESCALATED`, `GRC_HEARING_SCHEDULED`, `RESOLVED`. (`CLOSED` is accepted read-side for legacy rows but never written since the `CLOSE` action was removed; `PENDING_ESCALATION` no longer exists.)
Priority codes: `NORMAL`, `HIGH`, `SENSITIVE`.

### `ticketing.ticket_events`

Append-only audit log.

```sql
event_id                VARCHAR(36)   PK
ticket_id               VARCHAR(36)   FK → ticketing.tickets (CASCADE)
event_type              VARCHAR(64)   NOT NULL
old_status_code         VARCHAR(32)
new_status_code         VARCHAR(32)
old_assigned_to         VARCHAR(128)
new_assigned_to         VARCHAR(128)
workflow_step_id        VARCHAR(36)        -- step context at event time
note                    TEXT
payload                 JSON               -- LLM note translation lives in payload["translation_en"]
seen                    BOOLEAN       DEFAULT FALSE  -- unseen → officer badge count
assigned_to_user_id     VARCHAR(128)       -- notification target for badge
created_at              TIMESTAMPTZ   NOT NULL
created_by_user_id      VARCHAR(128)
actor_role              VARCHAR(64)        -- role key snapshotted at write time
case_sensitivity        VARCHAR(16)   DEFAULT 'standard'  -- 'standard' | 'seah'
summary_regen_required  BOOLEAN       DEFAULT FALSE  -- LLM summary must regenerate
```

(There is no `note_en` column — per-note EN translation is stored in `payload["translation_en"]` by the `translate_note` Celery task.)

Event types: `CREATED`, `ACKNOWLEDGED`, `ESCALATED`, `RESOLVED`, `NOTE_ADDED`, `FIELD_REPORT`, `COMPLAINANT_MESSAGE`, `REPLY_SENT`, `GRC_CONVENED`, `ASSIGNED`, `REASSIGNMENT_REQUESTED`, `CLASSIFICATION_VALIDATED`, `TIER_CHANGED`, `REPLY_OWNER_CHANGED`, `TASK_ASSIGNED`, `TASK_COMPLETED`, `FILE_UPLOADED`, `FINDINGS_GENERATED`, `REVEAL_ORIGINAL`, `REVEAL_ORIGINAL_CLOSED`, `VIEWER_ADDED`, `VIEWER_REMOVED`, `COMPLAINANT_UPDATED`. `CLOSED` and `GRC_DECIDED` appear only on historical rows (actions removed in v1).

### `ticketing.ticket_overdue_episodes`

One row per overdue stint per step. Source of truth for reports.

```sql
episode_id              VARCHAR(36)   PK
ticket_id               VARCHAR(36)   FK → ticketing.tickets
workflow_step_id        VARCHAR(36)   FK → ticketing.workflow_steps
step_order              INTEGER
assigned_to_user_id     VARCHAR(128)
assigned_role_id        VARCHAR(36)
started_at              TIMESTAMPTZ   NOT NULL
ended_at                TIMESTAMPTZ
end_reason              VARCHAR(64)   -- 'resolved', 'escalated', 'cleared'
triggered_by            VARCHAR(32)   -- 'auto', 'manual'
days_overdue            INTEGER       -- computed at closure
```

### `ticketing.ticket_resolved_summaries`

Structured closure document.

```sql
summary_id          VARCHAR(36)   PK
ticket_id           VARCHAR(36)   FK → ticketing.tickets (UNIQUE)
resolution_category VARCHAR(64)
root_cause          TEXT
actions_taken       TEXT
outcome             TEXT
generated_by        VARCHAR(128)  -- user_id or 'system'
generated_at        TIMESTAMPTZ
```

### `ticketing.ticket_tasks`

Officer action items.

```sql
task_id                 VARCHAR(36)   PK
ticket_id               VARCHAR(36)   FK → ticketing.tickets
title                   VARCHAR(255)  NOT NULL
description             TEXT
status                  VARCHAR(32)   DEFAULT 'open'  -- 'open', 'done'
assigned_to_user_id     VARCHAR(128)
due_date                DATE
created_by_user_id      VARCHAR(128)
created_at              TIMESTAMPTZ
updated_at              TIMESTAMPTZ
```

### `ticketing.ticket_viewers`

Non-Actor participants (Informed / Observer tiers).

```sql
viewer_id           VARCHAR(36)   PK
ticket_id           VARCHAR(36)   FK → ticketing.tickets
user_id             VARCHAR(128)  NOT NULL
tier                VARCHAR(32)   NOT NULL  -- 'INFORMED', 'OBSERVER'
added_at            TIMESTAMPTZ
added_by_user_id    VARCHAR(128)
```

### `ticketing.ticket_files`

Officer-uploaded attachments (complainant files stay in the chatbot upload store).

```sql
file_id             VARCHAR(36)   PK
ticket_id           VARCHAR(36)   NOT NULL (indexed; soft ref)
file_name           VARCHAR(255)  NOT NULL
file_path           VARCHAR(512)  NOT NULL
file_type           VARCHAR(50)
file_size           INTEGER       DEFAULT 0
caption             VARCHAR(500)
uploaded_by_user_id VARCHAR(64)
uploaded_at         TIMESTAMPTZ
```

### `ticketing.ticket_context_cache`

LLM context window (per ticket). Prevents full event history re-fetch on each AI call.

```sql
cache_id        VARCHAR(36)   PK
ticket_id       VARCHAR(36)   FK → ticketing.tickets (UNIQUE)
context_json    JSONB
last_event_id   VARCHAR(36)
updated_at      TIMESTAMPTZ
```

---

## 3. Workflow tables

### `ticketing.workflow_definitions`

```sql
workflow_id         VARCHAR(36)   PK
workflow_key        VARCHAR(64)   UNIQUE NOT NULL   -- slug (auto from name)
display_name        TEXT          NOT NULL
description         TEXT
workflow_type       VARCHAR(32)   DEFAULT 'standard'   -- 'standard' | 'seah' (lowercase since g0h2i4j6)
status              VARCHAR(32)   DEFAULT 'published'  -- 'draft' | 'published' | 'archived'
version             INTEGER       DEFAULT 1            -- incremented on publish
is_template         BOOLEAN       DEFAULT FALSE
template_source_id  VARCHAR(36)                        -- provenance when cloned
updated_by_user_id  VARCHAR(64)
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

### `ticketing.workflow_steps`

```sql
step_id                 VARCHAR(36)   PK
workflow_id             VARCHAR(36)   FK → ticketing.workflow_definitions (CASCADE)
step_order              INTEGER       NOT NULL
step_key                VARCHAR(64)   NOT NULL
display_name            TEXT          NOT NULL
assigned_role_key       VARCHAR(64)   NOT NULL  -- GRM role for the Actor at this step
response_time_hours     INTEGER                 -- NULL = no first-response SLA
resolution_time_days    INTEGER                 -- NULL = no auto-escalation (e.g. L4 legal)
supervisor_role         VARCHAR(64)             -- tier model (spec 12)
informed_roles          JSON          DEFAULT []
observer_roles          JSON          DEFAULT []
informed_pii_access     BOOLEAN       DEFAULT FALSE
stakeholders            JSON                    -- legacy display field (names, not role keys)
expected_actions        JSON
is_deleted              BOOLEAN       DEFAULT FALSE
created_at              TIMESTAMPTZ
updated_at              TIMESTAMPTZ
```

> **Deprecated:** the original `role_required`, `tier_config` (JSONB) and per-step `notification_rules` (JSONB) columns no longer exist. Roles bind via `assigned_role_key` + tier columns; notification rules are the `settings.notification_rules` key.

### `ticketing.project_workflows`

Active project ↔ workflow bindings (N streams per project) — see [12_workflows_configuration.md](12_workflows_configuration.md).

```sql
project_workflow_id VARCHAR(36)   PK
project_id          VARCHAR(64)   FK → ticketing.projects (CASCADE)
workflow_id         VARCHAR(36)   FK → ticketing.workflow_definitions (RESTRICT)
display_label       TEXT          NOT NULL
classifications     JSON          DEFAULT []   -- taxonomy groups for re-route after category edit
intake_route        VARCHAR(64)                -- chatbot story_main (scalar since e7f9a1b3)
is_default          BOOLEAN       DEFAULT FALSE -- catch-all when no rule matches
sort_order          INTEGER       DEFAULT 0
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

### `ticketing.workflow_assignments` — legacy

Maps (org, location, project_code, priority) → workflow. **Fallback only**: `resolve_workflow()` consults it when the ticket has no resolvable project. Not managed in the UI.

```sql
assignment_id       VARCHAR(36)   PK
organization_id     VARCHAR(64)   NOT NULL
location_code       VARCHAR(64)
project_code        VARCHAR(64)
priority            VARCHAR(32)
workflow_id         VARCHAR(36)   FK → ticketing.workflow_definitions (CASCADE)
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

---

## 4. Organisation / geography tables

### `ticketing.organizations`

```sql
organization_id     VARCHAR(64)   PK  -- server-generated: initials + country prefix
name                VARCHAR(255)  NOT NULL
country_code        VARCHAR(8)
org_type            VARCHAR(64)
created_at          TIMESTAMPTZ
```

### `ticketing.locations`

Adjacency-list tree; names live in `location_translations`, level semantics in `location_level_defs`. Full model: [18_geography_and_locations.md](18_geography_and_locations.md).

```sql
location_code           VARCHAR(64)   PK   -- canonical mnemonic, e.g. P1, P1_MOR (see LOCATION_CODES.md)
country_code            VARCHAR(8)    FK → ticketing.countries (RESTRICT), NOT NULL
level_number            INTEGER       NOT NULL  -- matches location_level_defs
parent_location_code    VARCHAR(64)   FK → ticketing.locations (SET NULL)
source_id               INTEGER            -- original ID from import dataset (re-sync)
latitude                NUMERIC(9,6)
longitude               NUMERIC(9,6)
is_active               BOOLEAN       DEFAULT TRUE
created_at              TIMESTAMPTZ
updated_at              TIMESTAMPTZ
```

### `ticketing.location_level_defs`

```sql
country_code    VARCHAR(8)    FK → ticketing.countries (CASCADE)
level_number    INTEGER
level_name_en   TEXT          NOT NULL   -- "Province"
level_name_local TEXT                    -- "प्रदेश"
PRIMARY KEY (country_code, level_number)
```

### `ticketing.location_translations`

```sql
location_code   VARCHAR(64)   FK → ticketing.locations (CASCADE)
lang_code       VARCHAR(8)    -- 'en', 'ne', …
name            TEXT          NOT NULL
PRIMARY KEY (location_code, lang_code)
```

### `ticketing.countries`

```sql
country_code    VARCHAR(8)    PK
name            TEXT          NOT NULL
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

### `ticketing.projects`

```sql
project_id          VARCHAR(64)   PK
name                VARCHAR(255)  NOT NULL
project_code        VARCHAR(64)
organization_id     VARCHAR(64)   FK → ticketing.organizations
country_code        VARCHAR(8)
project_type_id     VARCHAR(36)   FK → ticketing.project_types
chatbot_url         VARCHAR(512)  -- used in QR scan redirect
created_at          TIMESTAMPTZ
```

### `ticketing.project_types`

```sql
type_id     VARCHAR(36)   PK
name        VARCHAR(128)  NOT NULL
code        VARCHAR(32)
```

### `ticketing.packages`

Physical assets within a project (e.g. a road segment with a QR sign).

```sql
package_id      VARCHAR(36)   PK
project_id      VARCHAR(64)   FK → ticketing.projects
name            VARCHAR(255)  NOT NULL
location_code   VARCHAR(64)   FK → ticketing.locations
created_at      TIMESTAMPTZ
```

### `ticketing.package_locations`

Many-to-many: package → locations it spans.

```sql
package_id      VARCHAR(36)   FK → ticketing.packages
location_code   VARCHAR(64)   FK → ticketing.locations
PRIMARY KEY (package_id, location_code)
```

### `ticketing.package_organizations`

Many-to-many: package → allowed organizations.

```sql
package_id          VARCHAR(36)   FK → ticketing.packages
organization_id     VARCHAR(64)   FK → ticketing.organizations
PRIMARY KEY (package_id, organization_id)
```

---

## 5. User / role tables

### `ticketing.roles`

```sql
role_id             VARCHAR(36)   PK
role_key            VARCHAR(64)   UNIQUE NOT NULL
display_name        TEXT          NOT NULL
description         TEXT
workflow_scope      VARCHAR(32)   -- 'standard', 'seah', 'both'
jurisdiction_mode   VARCHAR(16)   -- 'field', 'country', 'global'
permissions         JSON          DEFAULT []
role_kind           VARCHAR(16)   DEFAULT 'operational'  -- 'operational' | 'admin'
role_origin         VARCHAR(16)   DEFAULT 'system'       -- 'system' | 'custom'
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

### `ticketing.user_roles`

```sql
user_role_id        VARCHAR(36)   PK
user_id             VARCHAR(128)  NOT NULL  -- Keycloak sub or bypass ID
role_id             VARCHAR(36)   FK → ticketing.roles
organization_id     VARCHAR(64)
location_code       VARCHAR(64)
is_active           BOOLEAN       DEFAULT TRUE
created_at          TIMESTAMPTZ
```

### `ticketing.officer_scopes`

Fine-grained ticket visibility: which org + location scope a user can act on.

```sql
scope_id            VARCHAR(36)   PK
user_id             VARCHAR(128)  NOT NULL
organization_id     VARCHAR(64)
location_code       VARCHAR(64)
role_code           VARCHAR(64)
```

### `ticketing.officer_onboarding`

Lifecycle tracking for invited officers.

```sql
onboarding_id       VARCHAR(36)   PK
user_id             VARCHAR(128)  NOT NULL UNIQUE
email               VARCHAR(255)
status              VARCHAR(32)   DEFAULT 'invited'  -- 'invited', 'active'
invited_at          TIMESTAMPTZ
activated_at        TIMESTAMPTZ
invited_by_user_id  VARCHAR(128)
```

---

## 6. QR tokens

### `ticketing.qr_tokens`

```sql
token           VARCHAR(16)   PK   -- opaque 8-char hex
package_id      VARCHAR(36)   FK → ticketing.packages (CASCADE)
is_active       BOOLEAN       DEFAULT TRUE
expires_at      TIMESTAMPTZ        -- optional
scan_url        TEXT               -- full URL for QR image
created_at      TIMESTAMPTZ
```

---

## 7. Settings

### `ticketing.settings`

```sql
key         VARCHAR(128)  PK
value       JSONB         NOT NULL
updated_at  TIMESTAMPTZ
updated_by  VARCHAR(128)
```

Key settings stored here:
- `chatbot_webchat_url`
- `notification_rules` (event × tier × channel matrix)
- `report_limits` (per-role quarterly email assignment caps)

---

## 8. Admin audit log

### `ticketing.admin_audit_log`

```sql
log_id          VARCHAR(36)   PK
actor_user_id   VARCHAR(128)
action_type     VARCHAR(64)   NOT NULL
target_entity   VARCHAR(64)        -- e.g. 'workflow', 'user', 'setting'
target_id       VARCHAR(128)
payload         JSONB
created_at      TIMESTAMPTZ   NOT NULL
```

---

## 9. Migration history

Managed by Alembic (`ticketing/migrations/`). Full chain (38 revisions, head `g0h2i4j6`), in `down_revision` order:

| # | Migration ID | Description |
|---|---|---|
| 1 | `e3ca0a118dbf` | Initial schema: tickets, ticket_events, workflow_definitions/steps/assignments, organizations, locations, roles, user_roles, settings |
| 2 | `b2f1a9c34d87` | `ticket_files` (officer attachments) |
| 3 | `c4e7d2b91f35` | Workflow editor columns: `status`, `version`, `is_template`, `is_deleted` |
| 4 | `d5f3e1a09c28` | `officer_scopes` |
| 5 | `f1a3e9c72b05` | Geography redesign: `countries`, `location_level_defs`, locations tree, `location_translations`, org country FK |
| 6 | `e8d4b6a0f291` | `projects`, `project_organizations`, `project_locations`, scope `includes_children`, `tickets.project_id` |
| 7 | `a9c3e5f1d720` | `org_role` on project_organizations + seed default org roles in settings |
| 8 | `b8c2d4e6f1a3` | `project_packages`, `package_locations`, `officer_scopes.package_id` + seed KL Road lots |
| 9 | `c1d5f8a2e047` | LLM findings: `ai_summary_en`, `ai_summary_updated_at` on tickets |
| 10 | `d2e8f4a1b093` | `default_language` on organizations + `preferred_language` on user_roles |
| 11 | `e5a7b2c089d1` | Event audit fields: `actor_role`, `case_sensitivity`, `summary_regen_required` on ticket_events (SEAH privacy handoff) |
| 12 | `f2b4d6e8a0c3` | `ticket_tasks` |
| 13 | `g4d6f8b0c2e5` | `ticket_viewers` |
| 14 | `h5e7g9i1k3m5` | `chatbot_base_url` on projects |
| 15 | `i6j8l0n2p4` | `ticket_context_cache` |
| 16 | `j8l0n2p4r6` | Workflow step tier model: `supervisor_role`, `informed_roles`, `observer_roles`, `informed_pii_access` |
| 17 | `k0l2n4p6r8` | `tier` on ticket_viewers; `complainant_reply_owner_id` on tickets |
| 18 | `l2m4o6q8s0` | `qr_tokens`; `package_id` on tickets |
| 19 | `n4p6r8t0` | `description`, `workflow_scope` on roles |
| 20 | `o5p7q9r1` | `officer_onboarding` (invited vs active, Keycloak webhook) |
| 21 | `p6q8s0t2` | `admin_audit_log` |
| 22 | `q9r7s1u3` | Rewrite Nepal location PKs from legacy `NP_*` to canonical `P1` / `P1_*` (LOCATION_CODES.md) |
| 23 | `r0s2t4v6` | Legacy `standard_workflow_id` / `seah_workflow_id` links on projects |
| 24 | `s1t3u5v7` | `package_organizations`, `project_actor_roles`; drop `contractor_org_id` |
| 25 | `u3v5w7x9` | `project_types` archetypes; `projects.project_type_key`; seed `construction_road` |
| 26 | `v5x7y9z1` | `roles.jurisdiction_mode` (field \| country \| global) |
| 27 | `w8x0y2z4` | `ticket_resolved_summaries` |
| 28 | `x9y1z3a5` | `ticket_overdue_episodes`; `current_overdue_episode_id` on tickets |
| 29 | `y0z2a4b6` | `latitude`/`longitude` on locations + seed NP district centroids |
| 30 | `z1a3b5c7` | `is_archived`, `archived_at` on tickets |
| 31 | `a2b4c6d8` | `admin_scopes` table; `role_kind`, `role_origin` on roles |
| 32 | `b3c5d7e9` | `project_workflows` — N workflow slots per project |
| 33 | `c4d6e8f0` | `officer_messaging` JSON on projects |
| 34 | `c5e7f9a1` | Dynamic project workflows: `classifications`, intake routes, `is_default` flag |
| 35 | `d6f8a0b2` | Normalize `project_workflows.intake_routes` to active catalog keys |
| 36 | `e7f9a1b3` | Replace `intake_routes[]` with scalar `intake_route` (story_main) |
| 37 | `f8a0b2c4` | Shorten `package_code` values; migrate KL Road lot ids to 01–05 |
| 38 | `g0h2i4j6` | Normalize `workflow_definitions.workflow_type` to lowercase |
