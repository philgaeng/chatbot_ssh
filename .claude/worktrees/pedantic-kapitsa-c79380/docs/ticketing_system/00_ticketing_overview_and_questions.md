# Ticketing System – Overview and First Questions

## Vision

A **ticketing system** that manages all grievances produced by one or more chatbots, across countries, organizations, and locations. It is **independent** of any specific chatbot: it is API-only, so each chatbot can choose to integrate with it or not.

## Goals

- **Manage all grievances** as tickets: view, assign, route, approve, and track status.
- **Configurable access control**: define different access levels (e.g. viewer, agent, approver, admin) and scope them by organization and location.
- **Configurable approval workflows**: define workflows by access level, organization, and location (e.g. “Nepal / Org A / high-priority → 2-level approval”).
- **Multi-tenant and multi-bot**: support different countries, different chatbots, different organizations, and different workflows; all driven by **settings**, not hard-coded logic.
- **Integration only via API**: the ticketing system talks to the chatbot(s) and to messaging (SMS/email) only through APIs. No direct DB or in-process coupling.

## Principles

| Principle | Meaning |
|-----------|--------|
| **Ticketing is independent** | Deployable and usable without any chatbot. Chatbots opt in by calling the ticketing API (e.g. to create/update tickets from grievances). |
| **API-only integration** | Chatbot → Ticketing: e.g. “create ticket from grievance”, “link conversation”. Ticketing → Chatbot: e.g. “send message to user” via Orchestrator `POST /message`. Messaging (SMS/email) via a dedicated Messaging API. |
| **Settings-driven** | Access levels, organizations, locations, and approval workflows are defined in configuration/settings (DB or config service), not in code. |
| **Same messaging service** | Notifications (SMS, email) used by the ticketing system go through the same Messaging API used by the chatbot backend, so one place to manage templates and delivery. |

## High-Level Integration Picture

```
┌─────────────────┐     API      ┌─────────────────────┐     API      ┌──────────────────┐
│  Chatbot(s)     │ ────────────►│  Ticketing System   │◄────────────►│  Messaging API   │
│  (Orchestrator  │  create/     │  (Python/FastAPI +  │  send SMS/   │  (Backend or     │
│   + backend)    │  link ticket │   Node.js + PG)    │  email       │   dedicated)     │
└─────────────────┘              └──────────┬─────────┘              └──────────────────┘
        ▲                                    │
        │ API (e.g. send message to user)    │ API (grievance/ticket data)
        └────────────────────────────────────┘
```

- **Chatbot → Ticketing**: Create/update tickets from submitted grievances; optionally link conversation/session.
- **Ticketing → Chatbot**: When agents need to “reply in chat”, ticketing calls Orchestrator `POST /message` (or equivalent).
- **Ticketing → Messaging**: All SMS/email (e.g. assignee notifications, status updates to complainant) via Messaging API.

## Specs in This Folder

| Doc | Purpose |
|-----|--------|
| [00_ticketing_overview_and_questions.md](00_ticketing_overview_and_questions.md) | This file: vision, principles, first questions (answered) |
| [01_ticketing_scope_and_stack.md](01_ticketing_scope_and_stack.md) | Scope, stack (Python, FastAPI, Node.js, Postgres), architecture |
| [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md) | Domain model: tickets, access levels, orgs, locations, workflows; settings |
| [03_ticketing_api_integration.md](03_ticketing_api_integration.md) | API contracts: ticketing ↔ chatbot, ticketing ↔ messaging |
| [Escalation_rules.md](Escalation_rules.md) | SLA and escalation rules (configurable); example: ADB KL Road 4-level workflow and roles |
| [06_flicket_gap_assessment.md](06_flicket_gap_assessment.md) | Gap assessment: what Flicket provides vs. our specs; effort and approach |

---

## First Questions to Answer

Use these to narrow scope and make early decisions before detailed design.

### 1. Product and scope

- **Q1.1** Who is the primary user of the ticketing system? (e.g. internal staff only, or also external partners?)  At least 3 layers (ADB (supervisor), Nepal Gvt (main implementer), external partners of different level (contractors who are at level 1 of operation and controller who is at level 2))
- **Q1.2** Is the first version “single country / single chatbot” (e.g. Nepal only) with the data model ready for multi-country/multi-bot later, or do we need multi-country/multi-bot from day one? Nepal only for only one organization and one project for now
- **Q1.3** Do we need a dedicated UI for the ticketing system in v1 (web app for agents/admins), or is “API-only + optional minimal UI (e.g. read-only dashboard)” enough for the first release? We need a complete modern UX/UI with tiles so that it can be used by Nepalis.

### 2. Access and tenancy

- **Q2.1** What are the concrete access levels we need at launch? (e.g. Viewer, Agent, Approver, Admin – or different names/roles?) describe in TOR GRSM - this needs to be 100 % configurable
- **Q2.2** How do we identify “organization” and “location” in the current system? (Do we already have `organization_id` / `location` on grievances or only in external systems?) - we already have the province in the current system - but we dont have organizations
- **Q2.3** Should one user have different roles in different organizations/locations (e.g. Approver in Org A, Viewer in Org B)? This can happen but we dont need to implement this at launch if it is not someting that completely changes the structure

### 3. Workflows

- **Q3.1** What is the minimum approval workflow we need for v1? (e.g. “single approver”, “two-level approval”, “no approval – auto-close”?) - configurable through settings
- **Q3.2** Are workflows defined per (country, chatbot, organization, location) or per (organization, location) only? - everything through settings. One organization can even have different workflows for one projetc as we will have a different workflow for sensiitive issues or high priority
- **Q3.3** Do we need to support “escalation” (e.g. auto-escalate if not approved in N hours)? Yes

### 4. Integration

- **Q4.1** When a grievance is submitted by the chatbot, who creates the ticket? (Chatbot backend calling Ticketing API, or Ticketing system polling/consuming from a queue or shared DB?) - ideally we have separate dbs and work through API so the ticketing system is optionnal
- **Q4.2** Does the ticketing system need to “replay” or “show” conversation history (from the chatbot) inside a ticket? If yes, does that require a new API from the chatbot (e.g. “get conversation for session_id”) or is storing a link/session_id enough for now? No - we will store only what is in the db as well as the messages that the officer may send through the messaging service (eg custom message sent by agent not chatbot)
- **Q4.3** Is the Messaging API already planned (as in BACKEND.md)? Should the ticketing system depend on it from day one, or can it call the current in-process messaging service via an adapter in v1? I think the messaging should already be an API

### 5. Stack and deployment

- **Q5.1** Why both Python/FastAPI and Node.js? (e.g. FastAPI for ticketing API + background jobs, Node.js for real-time UI or a specific service?) FastAPI and python for the backend, Nodejs for the forntend
- **Q5.2** Same Postgres as the current grievance DB or a separate DB for ticketing (tickets, users, workflows, settings)? likely separate
- **Q5.3** Should the ticketing system be deployable as a separate service (own repo / own deployment) or live in the same repo as the chatbot with clear module boundaries? currently live in the same repo. for the db, I am ok for one db for so long that the chatbot can function without the ticketing system. Most probably each country and organization will have its own db

### 6. Data and identity

- **Q6.1** Do we have a canonical “user” or “agent” store (e.g. SSO, Auth0, internal user table) to plug into access levels, or do we need to design one as part of the ticketing system? We will start with AWS Cognito
- **Q6.2** How do we map “complainant” (from the chatbot) to “contact” or “requester” in the ticket? Same ID, or ticketing maintains its own identity and we link via grievance_id? I think we should keep the denomination complainant.

---

## Next Steps

1. Answer the questions above (even with “defer” or “v2”) and record decisions in this doc or in a `00_ticketing_decisions.md`.
2. Freeze v1 scope and stack (see [01_ticketing_scope_and_stack.md](01_ticketing_scope_and_stack.md)).
3. Define the domain model and settings schema (see [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md)).
4. Specify API contracts with the chatbot and messaging (see [03_ticketing_api_integration.md](03_ticketing_api_integration.md)).
