# Ticketing System – v1 Decisions

Snapshot of key **product, architecture, and integration decisions** for v1.  
These decisions are derived from the answered questions in:

- `00_ticketing_overview_and_questions.md`
- `01_ticketing_scope_and_stack.md`
- `02_ticketing_domain_and_settings.md`
- `Escalation_rules.md`

---

## 1. Product and scope

- **Country / project scope (v1)**
  - Nepal only, for **one organization and one project** (KL Road GRM), but the data model is multi-tenant ready (country, chatbot, org, location, project).

- **Primary users**
  - At least three layers of users:
    - ADB (supervisor level),
    - Government of Nepal (main implementer),
    - External partners (contractors at level 1, controllers at level 2).

- **UI requirement**
  - v1 **must include a complete modern web UI** (tiles, usable by Nepali staff).
  - Not API-only: the ticketing service must ship with a usable web interface for agents/admins.

- **Chatbot independence**
  - Ticketing is **optional**: chatbot + grievance backend must be able to run **without** ticketing.
  - Ticketing integrates via APIs only; no hard dependency in chatbot runtime.

---

## 2. Access, tenancy, and identity

- **Access levels / roles**
  - Roles are defined in the **TOR GRMS** and must be **100% configurable** (no hard-coded role names in code).
  - Access is scoped by **organization** and **location**; one user can eventually have different roles in different orgs/locations, but this is not required at launch if it complicates the structure.

- **Organizations and locations**
  - Existing system already has **province**; organizations are **not yet modelled** and must be added in ticketing.
  - Locations start simple (province-based) but support hierarchy (province/district/office) later.

- **User identity**
  - v1 starts with **AWS Cognito** as the identity provider.
  - Ticketing stores only Cognito user IDs and maps them to roles and org/location in its own tables.

---

## 3. Workflows, escalation, and SLA

- **Workflow configuration**
  - All workflows (including approvals and escalation levels) are defined **through settings**, not code.
  - One organization can have **different workflows for one project** (e.g. sensitive vs standard, high priority vs normal).

- **Escalation and SLA**
  - **Escalation is required in v1**.
  - SLA is time-based per level (response time and resolution time). SLA can be defined in settings as well.
  - The **ADB KL Road 4-level workflow** is the reference pattern:
    - Level 1: Site Safeguards Focal Person (1–2 days)
    - Level 2: PD/PIU Safeguards Focal Person (7 days)
    - Level 3: Project Office Safeguards / GRC Secretariat (15 days)
    - Level 4: Legal institutions (no specific timeline)
  - Auto-escalation when resolution time is exceeded; 4th level has no automatic time-based escalation.

---

## 4. Stack and deployment

- **Backend**
  - **Python + FastAPI** for ticketing API and business logic.
  - Background work via **Celery** or FastAPI async tasks (for notifications and escalation).

- **Frontend**
  - **Node.js-based** web frontend for the agent/admin UI (modern UX with tiles, English only for v1).

- **Database**
  - v1 uses the **same Postgres database instance** as the chatbot.
  - Ticketing data is isolated into its **own schema** (e.g. `ticketing`) and has **no foreign keys** into existing grievance tables.
  - This keeps v1 simple and leaves a clean path to move ticketing to a separate DB later.

- **Deployment model**
  - Ticketing runs as a **separate FastAPI process in the same repo** (e.g. `ticketing/main.py`), with its own port and schema.
  - This allows the service to be split into a separate repo/service later without changing API contracts.

---

## 5. Integration and messaging

- **Chatbot ↔ Ticketing**
  - The chatbot backend (or orchestrator) creates tickets via **HTTP API** (no shared tables access).
  - Ticketing references grievances via `grievance_id` and can call the **existing Backend Grievance API** when needed.

- **Conversation history**
  - v1 **does not** need to replay full chatbot conversation history inside tickets.
  - Ticketing stores only what is in the DB (grievance data) and messages sent by officers via the Messaging service.

- **Messaging**
  - Messaging **must be exposed as an API** (not in-process calls) for both chatbot and ticketing.
  - Ticketing uses the **same Messaging API** as the backend for SMS/email notifications (assignment, escalation, status updates).

---

## 6. Out-of-scope for v1

- SSO beyond AWS Cognito and basic JWT/API-key integration.
- Custom report builder (v1 can have fixed reports/exports).
- Mobile app for agents (web-only, responsive UI).
- Multi-language UI (v1 UI is **English only**; chatbot continues to support its own language strategy).

These items can be revisited after v1 based on usage and feedback.
