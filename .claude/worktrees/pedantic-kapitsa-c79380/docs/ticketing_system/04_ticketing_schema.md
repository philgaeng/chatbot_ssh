# Ticketing System – Postgres Schema (v1)

This spec defines the **concrete Postgres schema** for the ticketing system in **v1**.

- **Database**: reuse the **existing chatbot Postgres database**.
- **Isolation**: keep ticketing data in its **own schema / table group** (no cross-FKs into existing grievance tables).
- **Integration**: relate to grievances and complainants only via IDs (`grievance_id`, `complainant_id`) and the existing **Backend / Messaging / Orchestrator APIs**.

This makes it easy later to:
- Move ticketing to a **separate database** by copying only the ticketing schema and changing the connection string, and
- Keep the chatbot working if ticketing is offline or removed.

---

## 1. Schema and naming

For v1 we recommend:

- Use a **dedicated schema** in the existing DB, e.g. `ticketing`.
- Qualify all tables as `ticketing.*` in SQL and migrations.
- Do **not** add foreign keys from `ticketing.*` into existing tables; use text/UUID fields for references.

Example:

```sql
CREATE SCHEMA IF NOT EXISTS ticketing AUTHORIZATION <app_role>;
```

---

## 2. Core tables

### 2.1 `ticketing.tickets`

Stores ticket metadata and current state. Each ticket corresponds to one grievance (for now).

```sql
CREATE TABLE ticketing.tickets (
    ticket_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Links to chatbot data, via IDs only (no FK)
    grievance_id        VARCHAR(64) NOT NULL,
    complainant_id      VARCHAR(64),
    chatbot_id          VARCHAR(64) NOT NULL,   -- e.g. 'nepal_grievance_bot'

    -- Source / scoping
    country_code        VARCHAR(8)  NOT NULL,   -- e.g. 'NP'
    organization_id     VARCHAR(64) NOT NULL,
    location_code       VARCHAR(64),            -- maps province/district etc.
    project_code        VARCHAR(64),            -- e.g. 'KL_ROAD'

    -- Status & workflow
    status_code         VARCHAR(32) NOT NULL,   -- e.g. 'OPEN','IN_PROGRESS','PENDING_ESCALATION','CLOSED'
    current_workflow_id UUID         NOT NULL,
    current_step_id     UUID,                  -- FK into workflow_steps (within ticketing schema)
    priority            VARCHAR(32),           -- e.g. 'NORMAL','HIGH','SENSITIVE'

    -- Assignment
    assigned_to_user_id VARCHAR(128),          -- AWS Cognito sub or internal user id
    assigned_role_id    UUID,                  -- role at current step (nullable)

    -- Audit
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_by_user_id  VARCHAR(128),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_by_user_id  VARCHAR(128),

    -- Soft delete (if needed later)
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE
);
```

Recommended indexes:

```sql
CREATE INDEX idx_tickets_grievance_id       ON ticketing.tickets (grievance_id);
CREATE INDEX idx_tickets_org_loc_status     ON ticketing.tickets (organization_id, location_code, status_code);
CREATE INDEX idx_tickets_assigned_to        ON ticketing.tickets (assigned_to_user_id);
CREATE INDEX idx_tickets_current_workflow   ON ticketing.tickets (current_workflow_id, current_step_id);
```

---

### 2.2 `ticketing.ticket_events`

Immutable log of all changes (status, assignment, escalation, comments). Used for audit trail and UI “history”.

```sql
CREATE TABLE ticketing.ticket_events (
    event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id           UUID NOT NULL,

    -- Event metadata
    event_type          VARCHAR(64) NOT NULL,   -- e.g. 'CREATED','STATUS_CHANGED','ASSIGNED','ESCALATED','COMMENT_ADDED'
    old_status_code     VARCHAR(32),
    new_status_code     VARCHAR(32),
    old_assigned_to     VARCHAR(128),
    new_assigned_to     VARCHAR(128),
    workflow_step_id    UUID,

    -- Free-form data (for extra fields, JSON payloads, etc.)
    payload             JSONB,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_by_user_id  VARCHAR(128)
);
```

Indexes:

```sql
CREATE INDEX idx_ticket_events_ticket_id    ON ticketing.ticket_events (ticket_id, created_at);
CREATE INDEX idx_ticket_events_event_type   ON ticketing.ticket_events (event_type);
```

---

### 2.3 `ticketing.organizations`

```sql
CREATE TABLE ticketing.organizations (
    organization_id     VARCHAR(64) PRIMARY KEY,
    name                TEXT NOT NULL,
    country_code        VARCHAR(8) NOT NULL,
    -- optional: parent organization, type, etc.
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
```

### 2.4 `ticketing.locations`

We keep it simple and province-oriented to match existing data (can evolve later).

```sql
CREATE TABLE ticketing.locations (
    location_code       VARCHAR(64) PRIMARY KEY,   -- e.g. 'PROVINCE_1', 'KATHMANDU'
    name                TEXT NOT NULL,
    country_code        VARCHAR(8) NOT NULL,
    parent_location     VARCHAR(64),               -- nullable, for hierarchy

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
```

---

### 2.5 `ticketing.roles` and `ticketing.user_roles`

Roles are defined here and mapped to AWS Cognito users (or other IDP) via `user_id`.

```sql
CREATE TABLE ticketing.roles (
    role_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_key            VARCHAR(64) UNIQUE NOT NULL,  -- e.g. 'SITE_SAFEGUARDS_FOCAL_PERSON'
    display_name        TEXT NOT NULL,
    permissions         JSONB NOT NULL,               -- list of permission keys

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
```

```sql
CREATE TABLE ticketing.user_roles (
    user_role_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             VARCHAR(128) NOT NULL,        -- Cognito sub or internal id
    role_id             UUID NOT NULL,
    organization_id     VARCHAR(64) NOT NULL,
    location_code       VARCHAR(64),

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_user_roles_user_org_loc ON ticketing.user_roles (user_id, organization_id, location_code);
```

---

## 3. Workflow & escalation tables

### 3.1 `ticketing.workflow_definitions`

Top-level named workflows (e.g. “KL_ROAD_STANDARD”, “KL_ROAD_SENSITIVE”).

```sql
CREATE TABLE ticketing.workflow_definitions (
    workflow_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_key        VARCHAR(64) UNIQUE NOT NULL,  -- e.g. 'KL_ROAD_4_LEVEL'
    display_name        TEXT NOT NULL,
    description         TEXT,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
```

### 3.2 `ticketing.workflow_steps`

Ordered steps within a workflow, each with SLA and escalation config (based on `Escalation_rules.md`).

```sql
CREATE TABLE ticketing.workflow_steps (
    step_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID NOT NULL,
    step_order          INTEGER NOT NULL,          -- 1,2,3,4...

    step_key            VARCHAR(64) NOT NULL,      -- e.g. 'LEVEL_1_SITE', 'LEVEL_2_PIU'
    display_name        TEXT NOT NULL,            -- e.g. 'First level – Site'

    assigned_role_key   VARCHAR(64) NOT NULL,     -- matches ticketing.roles.role_key
    stakeholders        JSONB,                    -- list of stakeholder labels

    -- SLA
    response_time_hours INTEGER,                  -- e.g. 24 (global) or per-level
    resolution_time_days INTEGER,                 -- e.g. 2, 7, 15; NULL = no timeline

    expected_actions    JSONB,                    -- list of action descriptions

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_workflow_steps_workflow_order ON ticketing.workflow_steps (workflow_id, step_order);
```

### 3.3 `ticketing.workflow_assignments`

Maps (organization, location, project, priority/sensitive flag) to a workflow.

```sql
CREATE TABLE ticketing.workflow_assignments (
    assignment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     VARCHAR(64) NOT NULL,
    location_code       VARCHAR(64),
    project_code        VARCHAR(64),
    priority            VARCHAR(32),          -- e.g. 'NORMAL','HIGH','SENSITIVE'

    workflow_id         UUID NOT NULL,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_workflow_assign_org_loc_pri
    ON ticketing.workflow_assignments (organization_id, location_code, project_code, priority);
```

---

## 4. Settings table

For simple key/value or JSON config, including integration URLs, feature flags, etc.

```sql
CREATE TABLE ticketing.settings (
    key                 VARCHAR(128) PRIMARY KEY,
    value               JSONB NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_by_user_id  VARCHAR(128)
);
```

Examples:

- `('messaging_api_base_url', '{"url": "https://backend/api/messaging"}')`
- `('orchestrator_base_url', '{"chatbot_id": "nepal_grievance_bot", "url": "https://..."}')`

---

## 5. Sample data: KL Road 4‑level workflow

Illustrative seed data for the **ADB KL Road** example from `Escalation_rules.md`.

### 5.1 Workflow definition

```sql
INSERT INTO ticketing.workflow_definitions (workflow_id, workflow_key, display_name, description)
VALUES (
    gen_random_uuid(),
    'KL_ROAD_4_LEVEL',
    'KL Road – 4-level safeguards workflow',
    'Site → PIU → GRC → Legal, with time-based escalation'
);
```

### 5.2 Workflow steps (pseudo-SQL)

```sql
-- Level 1 – Site Safeguards Focal Person
INSERT INTO ticketing.workflow_steps (
    workflow_id, step_order, step_key, display_name,
    assigned_role_key, stakeholders,
    response_time_hours, resolution_time_days,
    expected_actions
) VALUES (
    (SELECT workflow_id FROM ticketing.workflow_definitions WHERE workflow_key = 'KL_ROAD_4_LEVEL'),
    1,
    'LEVEL_1_SITE',
    'First level – Site',
    'SITE_SAFEGUARDS_FOCAL_PERSON',
    '["Contractor","CSC","Site Project Office"]'::jsonb,
    24,
    2,
    '["Initial assessment","Basic resolution attempt","Documentation of actions taken"]'::jsonb
);

-- Level 2 – PD/PIU Safeguards Focal Person
-- resolution_time_days = 7, stakeholders PD + PIU, actions review/coordination/investigation/proposal

-- Level 3 – Project Office Safeguards (GRC Secretariat)
-- resolution_time_days = 15, stakeholders GRC + PIU + Site Office + Affected Persons

-- Level 4 – Legal Institutions
-- resolution_time_days = NULL (no specific timeline), stakeholders = all previous, actions = legal review/process
```

You can seed the remaining levels similarly using the descriptions from `Escalation_rules.md`.

---

## 6. Notes for future DB split

Because **all ticketing objects live under the `ticketing` schema and have no foreign keys into existing tables**:

- To move ticketing to a **separate database** later, you can:
  - Create the same schema via migrations in a new DB,
  - `COPY` / dump+restore only `ticketing.*` tables,
  - Point the ticketing FastAPI service at the new DB via environment/config.
- The chatbot backend stays on the original DB and continues to expose its **HTTP APIs** that ticketing already uses.

This preserves the clean separation you want while keeping v1 operationally simple.

