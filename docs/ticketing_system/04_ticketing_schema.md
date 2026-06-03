# Ticketing System – Database Schema (as-built, June 2026)

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
organization_id             VARCHAR(64)   NOT NULL
location_code               VARCHAR(64)
project_id                  VARCHAR(64)   FK → ticketing.projects (SET NULL)
project_code                VARCHAR(64)                   -- deprecated, kept for compat
package_id                  VARCHAR(36)                   -- soft ref, no FK; set via QR scan
status_code                 VARCHAR(32)   DEFAULT 'OPEN'
current_workflow_id         VARCHAR(36)   FK → ticketing.workflow_definitions
current_step_id             VARCHAR(36)   FK → ticketing.workflow_steps (SET NULL)
priority                    VARCHAR(32)   DEFAULT 'NORMAL'
is_seah                     BOOLEAN       DEFAULT FALSE
assigned_to_user_id         VARCHAR(128)
assigned_role_id            VARCHAR(36)
complainant_reply_owner_id  VARCHAR(128)                  -- default: L1 Actor
step_started_at             TIMESTAMPTZ
sla_breached                BOOLEAN       DEFAULT FALSE
current_overdue_episode_id  VARCHAR(36)   FK → ticketing.ticket_overdue_episodes (SET NULL)
ai_summary_en               TEXT                          -- LLM findings digest
ai_summary_updated_at       TIMESTAMPTZ
is_deleted                  BOOLEAN       DEFAULT FALSE
created_at                  TIMESTAMPTZ   NOT NULL
created_by_user_id          VARCHAR(128)
updated_at                  TIMESTAMPTZ   NOT NULL
updated_by_user_id          VARCHAR(128)
```

Indexes: `grievance_id`, `(organization_id, location_code, status_code)`, `assigned_to_user_id`, `(current_workflow_id, current_step_id)`, `is_seah`.

Status codes: `OPEN`, `IN_PROGRESS`, `PENDING_ESCALATION`, `ESCALATED`, `RESOLVED`, `CLOSED`.
Priority codes: `NORMAL`, `HIGH`, `SENSITIVE`.

### `ticketing.ticket_events`

Append-only audit log.

```sql
event_id            VARCHAR(36)   PK
ticket_id           VARCHAR(36)   FK → ticketing.tickets
event_type          VARCHAR(64)   NOT NULL
actor_user_id       VARCHAR(128)
actor_role          VARCHAR(64)
note                TEXT
note_en             TEXT                -- LLM translation of note
payload             JSONB
step_id             VARCHAR(36)        -- step context at event time
created_at          TIMESTAMPTZ   NOT NULL
```

Event types: `CREATED`, `ACKNOWLEDGED`, `ESCALATED`, `RESOLVED`, `CLOSED`, `NOTE_ADDED`, `FIELD_REPORT`, `COMPLAINANT_MESSAGE`, `REPLY_SENT`, `GRC_CONVENED`, `GRC_DECIDED`, `TIER_CHANGED`, `TASK_ADDED`, `FILE_UPLOADED`, `FINDINGS_GENERATED`, `ASSIGN`, `REVEAL_CONTACT`.

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
name                VARCHAR(128)  NOT NULL
description         TEXT
workflow_scope      VARCHAR(32)   DEFAULT 'standard'  -- 'standard', 'seah'
is_active           BOOLEAN       DEFAULT TRUE
created_at          TIMESTAMPTZ
```

### `ticketing.workflow_steps`

```sql
step_id                 VARCHAR(36)   PK
workflow_id             VARCHAR(36)   FK → ticketing.workflow_definitions
step_order              INTEGER       NOT NULL
name                    VARCHAR(128)  NOT NULL
role_required           VARCHAR(64)
response_time_hours     INTEGER
resolution_time_days    INTEGER
tier_config             JSONB         -- per-tier actor/supervisor/informed assignment rules
notification_rules      JSONB         -- event × tier × channel matrix
```

### `ticketing.workflow_assignments`

Maps (org, project, location, priority) → workflow.

```sql
assignment_id       VARCHAR(36)   PK
workflow_id         VARCHAR(36)   FK → ticketing.workflow_definitions
organization_id     VARCHAR(64)
project_id          VARCHAR(64)
location_code       VARCHAR(64)
priority            VARCHAR(32)
is_default          BOOLEAN       DEFAULT FALSE
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

```sql
location_code   VARCHAR(64)   PK   -- canonical mnemonic (see LOCATION_CODES.md)
name            VARCHAR(255)  NOT NULL
name_ne         VARCHAR(255)       -- Nepali name
parent_code     VARCHAR(64)        -- FK to self
level           VARCHAR(32)        -- 'province', 'district', 'municipality'
country_code    VARCHAR(8)
```

### `ticketing.location_translations`

```sql
id              INTEGER       PK (autoincrement)
location_code   VARCHAR(64)   FK → ticketing.locations
lang            VARCHAR(8)    -- 'en', 'ne'
name            VARCHAR(255)
```

### `ticketing.countries`

```sql
country_code    VARCHAR(8)    PK
name            VARCHAR(128)
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
role_code           VARCHAR(64)   UNIQUE NOT NULL
name                VARCHAR(128)
description         TEXT
workflow_scope      VARCHAR(32)   -- 'standard', 'seah', 'both'
jurisdiction_mode   VARCHAR(32)   -- e.g. 'local', 'national', 'global'
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

Managed by Alembic (`ticketing/migrations/`). Key migrations in order:

| Migration ID | Description |
|---|---|
| `a1b2c3...` | Initial schema: tickets, ticket_events, workflow_*, organizations, locations, roles, user_roles, settings |
| `b2c3d4...` | officer_scopes |
| `c1d5f8a2e047` | LLM findings: `ai_summary_en`, `ai_summary_updated_at` on tickets; `note_en` on ticket_events |
| `e8d4b6a0f291` | Projects, packages, package_locations, officer scopes redesign |
| `f1a3e9c72b05` | Countries, location redesign, location_translations |
| `f2b4d6e8a0c3` | ticket_tasks |
| `g4d6f8b0c2e5` | ticket_viewers |
| `h5e7g9i1k3m5` | `chatbot_url` on projects |
| `i6j8l0n2p4` | ticket_context_cache |
| `j8l0n2p4r6` | workflow_step tier model (`tier_config`, `notification_rules`) |
| `k0l2n4p6r8` | `tier` on ticket_viewers; `complainant_reply_owner_id` on tickets |
| `l2m4o6q8s0` | qr_tokens; `package_id` on tickets |
| `n4p6r8t0` | `description`, `workflow_scope` on roles |
| `o5p7q9r1` | officer_onboarding; backfill existing users as active |
| `p6q8s0t2` | admin_audit_log |
| `q9r7s1u3` | Canonical Nepal location codes seeded |
| `r0s2t4v6` | project_workflow_links |
| `s1t3u5v7` | package_organizations; `actor_roles` on projects |
| `u3v5w7x9` | project_types |
| `v5x7y9z1` | `jurisdiction_mode` on roles |
| `w8x0y2z4` | ticket_resolved_summaries |
| `x9y1z3a5` | ticket_overdue_episodes; `current_overdue_episode_id` on tickets |
