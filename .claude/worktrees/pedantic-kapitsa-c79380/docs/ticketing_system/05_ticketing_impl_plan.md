# Ticketing System – v1 Implementation Plan

High-level sequence to implement the v1 ticketing system based on the decisions, schema, and API specs.

---

## Phase 0 – Foundations and wiring

- **P0.1 – Create ticketing FastAPI service**
  - New app entrypoint, e.g. `ticketing/main.py`, running on its own port.
  - Reuse existing DB config module (`DB_CONFIG`), but use the **`ticketing` schema** for all tables.
  - Add basic health endpoint (`GET /health`).

- **P0.2 – Messaging API on backend**
  - In the existing backend FastAPI app, implement:
    - `POST /api/messaging/send-sms`
    - `POST /api/messaging/send-email`
  - Use the existing `messaging_service` implementation under the hood, but expose it via HTTP so both chatbot and ticketing can call it.

---

## Phase 1 – Database schema and migrations

- **P1.1 – Create ticketing schema and tables**
  - Implement migrations (e.g. raw SQL or Alembic) for all tables in `04_ticketing_schema.md`:
    - `ticketing.tickets`
    - `ticketing.ticket_events`
    - `ticketing.organizations`
    - `ticketing.locations`
    - `ticketing.roles`
    - `ticketing.user_roles`
    - `ticketing.workflow_definitions`
    - `ticketing.workflow_steps`
    - `ticketing.workflow_assignments`
    - `ticketing.settings`

- **P1.2 – Seed initial data (KL Road workflow)**
  - Insert at least:
    - One `organization` and locations for the KL Road project.
    - Role entries for the safeguards focal persons and legal institutions.
    - A `workflow_definitions` row for `KL_ROAD_4_LEVEL`.
    - Four `workflow_steps` implementing the SLA and actions from `Escalation_rules.md`.
    - A `workflow_assignments` row mapping (org, project, priority) to that workflow.

---

## Phase 2 – Core ticketing API and domain logic

- **P2.1 – Ticket creation endpoint**
  - Implement `POST /api/v1/tickets` in the ticketing FastAPI app.
  - Responsibilities:
    - Validate payload (`grievance_id`, `complainant_id`, `chatbot_id`, org, location, project, priority).
    - Look up the applicable workflow (`workflow_assignments`).
    - Create a `tickets` record with `status_code='OPEN'`, `current_workflow_id`, and initial step.
    - Create a `ticket_events` record for creation.
    - Return the response shape documented in `03_ticketing_api_integration.md`.

- **P2.2 – Link conversation endpoint**
  - Implement `POST /api/v1/tickets/{ticket_id}/link-conversation`.
  - Store `session_id` and `chatbot_id` on the ticket so later outbound messages can use the orchestrator `POST /message`.

- **P2.3 – Basic ticket queries for UI**
  - Implement:
    - `GET /api/v1/tickets` – list tickets for the current user (filter by org/location/role).
    - `GET /api/v1/tickets/{ticket_id}` – ticket detail with status, current step, history (from `ticket_events`).

---

## Phase 3 – Workflow engine and escalation

- **P3.1 – In-process workflow engine**
  - Implement a small service that:
    - Reads `workflow_steps` for a workflow.
    - Determines the **current step** and its SLA (resolution time).
    - Knows how to advance to the next step (escalation).

- **P3.2 – SLA check / auto-escalation worker**
  - Add a periodic job (Celery or async task) that:
    - Scans open tickets where the current step SLA is exceeded.
    - Moves them to the next step:
      - Update `tickets.current_step_id`, `status_code` if needed.
      - Reassign to users with the role required at the next level.
      - Write `ticket_events` entry of type `ESCALATED`.
    - Triggers notifications via the Messaging API (assignee and stakeholders).

---

## Phase 4 – Integration with chatbot and backend

- **P4.1 – Chatbot/backend → ticketing hook**
  - In the grievance submission flow (backend/orchestrator), after the grievance is stored:
    - Call `POST /api/v1/tickets` with the required fields.
    - Optionally call `link-conversation` if a `session_id` is available.

- **P4.2 – Ticketing → Backend (grievance details)**
  - Implement a simple HTTP client in the ticketing service to:
    - Call `GET /api/grievance/{grievance_id}` when detailed data is needed for the UI.
  - Keep this behind an interface so it’s easy to stub in tests.

- **P4.3 – Ticketing → Orchestrator (reply in chat)**
  - Implement a client for orchestrator `POST /message`.
  - Attach this to a UI/action endpoint like `POST /api/v1/tickets/{ticket_id}/reply` which:
    - Uses stored `session_id` and `chatbot_id` to send the message.
    - Logs a `ticket_events` entry for the outgoing message.

---

## Phase 5 – Node.js UI (agent/admin)

- **P5.1 – Basic layout and auth integration**
  - Node.js app with:
    - Login via AWS Cognito (or use existing login shell if available).
    - Basic layout with tiles for “My tickets”, “All tickets (by role)”, “Escalated tickets”.

- **P5.2 – Ticket list and detail**
  - Use the ticketing API to:
    - List tickets with filters (org, location, status, priority).
    - Show ticket details, workflow step, SLA countdown, and event history.

- **P5.3 – Actions**
  - From the UI, call ticketing endpoints for:
    - Assign / reassign (updates ticket + sends notifications).
    - Manual escalate to next level (if allowed by role).
    - Reply to complainant (triggers orchestrator `POST /message`).

---

## Phase 6 – Hardening and v1 launch

- **P6.1 – Permissions and role checks**
  - Enforce role-based access (from `ticketing.user_roles`) on all ticketing endpoints.
  - Ensure only permitted users (by role/org/location) can assign, escalate, or close tickets.

- **P6.2 – Monitoring and logging**
  - Add structured logging around:
    - Ticket creation.
    - Escalation decisions.
    - Messaging API calls (success/failure).
  - Add basic metrics (counts of tickets per level, SLA breaches).

- **P6.3 – Migration path notes**
  - Confirm that:
    - No FKs from ticketing tables into existing chatbot tables.
    - All integrations use HTTP APIs (Backend, Orchestrator, Messaging).
  - Document the steps to move ticketing to a separate DB later if needed (copy `ticketing` schema + change connection string).

