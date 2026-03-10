# Ticketing System – Scope and Stack

## Scope (v1)

- **Ticket = Grievance (from chatbot)**  
  A ticket is created when a grievance is submitted (or when the ticketing system is notified via API). The ticketing system stores ticket metadata, status, assignment, and workflow state; grievance details can be stored in ticketing DB or fetched from the chatbot/backend API when needed.

- **Configurable access levels**  
  Roles such as Viewer, Agent, Approver, Admin (or equivalent) with permissions defined in settings. Access can be scoped by organization and location.

- **Configurable approval workflows**  
  Workflows defined by (access level, organization, location) or similar dimensions in settings (e.g. “Nepal / Org A / high-priority → 2-level approval”). v1 can start with one or two workflow types.

- **Multi-tenant readiness**  
  Data model supports country, chatbot_id, organization_id, location so that multiple countries, chatbots, and orgs can be supported. v1 can ship with one country/one chatbot and still use this model.

- **Integration only via API**  
  No direct DB access to the chatbot’s DB. Ticketing exposes REST APIs for:
  - Chatbot (or backend): create/update ticket, link grievance/session.
  - Optional future UI: list tickets, assign, approve, add comments.
  Messaging (SMS/email) is only via a Messaging API.

---

## Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Ticketing API & business logic** | **Python 3.x + FastAPI** | Aligns with existing orchestrator and backend (FastAPI). Same ecosystem (Pydantic, async), easy to share patterns and possibly auth/middleware. |
| **Background jobs / workers** | **Python (Celery or FastAPI + async tasks)** | Notifications, workflow transitions, scheduled escalation. Reuse Celery if already in use for the chatbot backend, or use async task queue in FastAPI. |
| **Optional UI / real-time** | **Node.js** | If v1 includes a web UI for agents (dashboard, real-time updates), Node.js can serve the frontend and/or WebSocket/SSE. Keeps UI stack separate from core API. Can be deferred if v1 is API-only. |
| **Database** | **PostgreSQL** | Same as current grievance DB; can share instance or use dedicated DB. Strong support for JSON (settings, workflow config), roles, and reporting. |

### Why Python + FastAPI for the core

- Consistency with orchestrator and backend (see [BACKEND.md](../BACKEND.md), [ARCHITECTURE.md](../ARCHITECTURE.md)).
- Single language for API, services, and background jobs simplifies deployment and hiring.
- OpenAPI and Pydantic give clear API contracts for chatbot and future UI clients.

### Why Node.js (optional)

- Useful if the first UI is a real-time dashboard (WebSockets, SSE) or a separate SPA; keeps UI concerns out of the FastAPI app.
- Can be introduced in a later phase if v1 is API-only or a minimal read-only UI.

### Why PostgreSQL

- Already used for grievances; same ops and backup story.
- Can use a dedicated schema or database for ticketing to keep boundaries clear (see [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md)).

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Clients (chatbots, future UI)                          │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ HTTPS
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Ticketing API (FastAPI)                                   │
│  - REST: tickets, assignments, workflow, settings, access                    │
│  - Auth: API keys or JWT (to be defined)                                     │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  PostgreSQL     │     │  Task queue          │     │  External APIs       │
│  (tickets,      │     │  (Celery / async)    │     │  - Chatbot           │
│   users,        │     │  - Notifications     │     │    (POST /message)   │
│   workflows,    │     │  - Workflow steps    │     │  - Messaging API     │
│   settings)     │     │  - Escalation        │     │    (SMS, email)      │
└─────────────────┘     └─────────────────────┘     └─────────────────────┘
```

- **Ticketing API**: single entry point; no direct DB or messaging from clients.
- **PostgreSQL**: source of truth for tickets, users/agents, workflow definitions, and settings.
- **Task queue**: for async work (e.g. send notification after assignment, run escalation rules).
- **External APIs**: chatbot (e.g. send message), Messaging API (SMS/email). All integration is outbound from ticketing via HTTP.

---

## Deployment Options

| Option | Description | When to use |
|--------|-------------|-------------|
| **Same repo, same process** | Ticketing routes mounted in the same FastAPI app as backend/orchestrator. Shared DB or schema. | Fastest path; good if ticketing is always used with this chatbot. |
| **Same repo, separate process** | Ticketing is a separate FastAPI app in the same repo (e.g. `ticketing/main.py`), own port, own DB or schema. | Clear separation, same codebase; deploy separately when needed. |
| **Separate repo, separate service** | Ticketing in its own repo and deployment; talks to chatbot and messaging only via API. | Maximum independence; multiple chatbots or teams owning ticketing. |

Recommendation: start with **same repo, separate process** (and optionally separate DB schema) so that:
- Chatbot and ticketing can be developed and versioned together.
- Ticketing can later be split into its own repo/service without changing the API contract.

---

## Out of Scope for v1 (candidates for later)

- Full-blown agent UI (can start with API + minimal dashboard or read-only view).
- SSO / advanced identity provider integration (can start with API keys or simple JWT).
- Custom report builder; v1 can have a few fixed reports or exports.
- Mobile app for agents.
- Multi-language UI (can follow chatbot language strategy later).

---

## Next

- [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md): tickets, access levels, organizations, locations, workflows, and how they are configured via settings.
