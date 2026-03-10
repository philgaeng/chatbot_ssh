# Ticketing System – Domain Model and Settings

## Core Entities

### Ticket

- Represents a **grievance** (or future request types) in the ticketing system.
- **Key attributes** (conceptual):
  - `ticket_id` (PK, e.g. UUID)
  - `grievance_id` (FK or reference to chatbot/backend grievance)
  - `source`: country, chatbot_id, organization_id, location (for routing and workflow)
  - Status (e.g. open, in_progress, pending_approval, approved, closed)
  - Assignment (assigned_to, assigned_at)
  - Workflow state (current step, approval history)
  - Created_at, updated_at, and optionally conversation/session reference for “show in chat”

Tickets are created when the chatbot (or backend) notifies the ticketing system via API (e.g. “grievance submitted” → create ticket).

### Access Level (Role)

- Named role that defines what a user can do (e.g. **Viewer**, **Agent**, **Approver**, **Admin**).
- **Configurable**: list of roles and their permissions are defined in settings, not hard-coded.
- Permissions can include: view_ticket, edit_ticket, assign_ticket, approve_ticket, manage_workflow, manage_settings, manage_users, etc.
- Access can be **scoped** by organization and/or location (e.g. “Approver in Org A, Viewer in Org B”).

### Organization

- Logical tenant (e.g. government body, department, partner org).
- Used to scope:
  - Which tickets a user can see or act on.
  - Which workflow and approval rules apply.
- Identified by `organization_id` (and optionally country/region).

### Location

- Geographic or logical place (district, office, region).
- Used together with organization to scope access and workflows (e.g. “Nepal / Kathmandu / Org A”).
- Can be hierarchical (e.g. country → region → district) if needed; v1 can be flat.

### Workflow

- Defines the **approval path** for a ticket (e.g. Agent → Approver 1 → Approver 2 → Closed), including **escalation levels** with SLAs (response time, resolution time per level).
- **Configurable** by:
  - Access level (e.g. high-priority tickets need Approver role)
  - Organization, location, project, ticket type (e.g. sensitive vs standard)
- Each step can define: assigned role, stakeholders, resolution timeline, and expected actions. See [Escalation_rules.md](Escalation_rules.md) for the ADB KL Road 4-level example and configurable model.
- Stored as workflow definitions (steps, transitions, who can approve at each step, SLA per step). Exact schema TBD (e.g. JSON config or normalized tables).

### User / Agent

- Identity that performs actions (view, assign, approve). May come from an existing user store (SSO, internal DB) or be defined inside the ticketing system.
- Linked to one or more **access levels** per (organization, location).

---

## Settings (Configurable)

All of the following should be **manageable through settings** (API and/or admin UI), not only via code or DB migrations.

| Setting area | What is configured | Example |
|--------------|--------------------|---------|
| **Access levels** | Role names and permissions | Viewer: [view_ticket]; Agent: [view_ticket, edit_ticket, assign_ticket]; Approver: [view_ticket, approve_ticket]; Admin: all |
| **Organizations** | List of organizations, optional parent/country | Nepal / Ministry X, Nepal / Office Y |
| **Locations** | List of locations, optional hierarchy | Kathmandu, Lalitpur, … |
| **User–role mapping** | Which user has which role in which org/location | user_123 → Approver in Org A, Viewer in Org B |
| **Workflow definitions** | Steps, transitions, conditions | “default”: [submit → assign → approve → close]; “high_priority”: [submit → assign → approve_1 → approve_2 → close] |
| **Workflow assignment** | Which workflow applies to which (org, location, ticket type/priority) | Org A + Kathmandu + high_priority → workflow “high_priority” |
| **SLA and escalation** | Response/resolution times per level; auto-escalate when exceeded | See [Escalation_rules.md](Escalation_rules.md) |
| **Integrations** | Chatbot base URL, Messaging API URL, API keys (secrets in env or vault) | TICKETING_CHATBOT_ORCHESTRATOR_URL, TICKETING_MESSAGING_API_URL |

Settings can live in:
- **PostgreSQL**: dedicated `settings` or `config` table(s) (JSON or key-value), or normalized tables for roles/workflows.
- **Environment / config files**: for URLs and secrets; for small deployments, minimal workflow config can also be in config.

---

## Multi-Country, Multi-Chatbot, Multi-Organization

- **Country**: optional dimension on ticket and on org/location; used for filtering and reporting.
- **Chatbot**: each ticket is tied to a `chatbot_id` (or source identifier) so that:
  - “Send message to user” calls the correct orchestrator/backend for that chatbot.
  - Lists and filters can be per chatbot.
- **Organization / Location**: as above; workflows and access are defined per (org, location) (and optionally country).

The ticketing system does **not** contain the chatbot logic; it only holds references (chatbot_id, grievance_id, session_id) and uses the API to interact with the right chatbot and messaging service.

---

## Data Model (Conceptual)

```
Ticket
  - ticket_id, grievance_id, chatbot_id, source (country, org, location)
  - status, assigned_to, workflow_state, created_at, updated_at
  - optional: session_id, conversation_id (for “show in chat”)

User / Agent
  - user_id, display_name, ...
  - (user_id, organization_id, location_id, access_level_id) for scoped roles

Access_level
  - access_level_id, name, permissions (list or JSON)

Organization
  - organization_id, name, country (optional)

Location
  - location_id, name, parent_id (optional)

Workflow_definition
  - workflow_id, name, steps (JSON or normalized)

Workflow_assignment
  - (organization_id, location_id, ticket_type/priority) → workflow_id

Settings
  - key-value or JSON for integration URLs, feature flags, etc.
```

Exact schema (tables, indexes, constraints) to be defined in a later technical spec.

---

## Next

- [03_ticketing_api_integration.md](03_ticketing_api_integration.md): API contracts between ticketing ↔ chatbot and ticketing ↔ messaging.
