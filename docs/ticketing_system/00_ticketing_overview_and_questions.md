# Ticketing System – Overview (as-built, June 2026)

> All design questions from the original spec have been resolved. This document is the stable vision statement.
> For settled decisions → `00_ticketing_decisions.md`. For schema → `04_ticketing_schema.md`. For API → `03_ticketing_api_integration.md`.

---

## Vision

A **GRM ticketing system** that manages all grievances produced by the Nepal chatbot, routed through configurable multi-level approval workflows, with a full officer web UI and ADB-compliant audit trail.

The ticketing system is **independent** of the chatbot: it integrates via REST APIs only. The chatbot can run without ticketing; ticketing can run without the chatbot (with manual ticket creation).

---

## Goals (as implemented)

| Goal | Status |
|---|---|
| Manage grievances as tickets: view, assign, route, approve, track | ✅ Built |
| Configurable access control (roles, org scope, location scope) | ✅ Built — `OfficerScope` + 4-tier model |
| Configurable approval workflows (steps, SLA, escalation) | ✅ Built — workflow_definitions + workflow_steps |
| Multi-tenant data model (country, org, project, location) | ✅ Built |
| Integration only via API (no direct DB coupling to chatbot) | ✅ Built |
| Full web UI for officers and admins | ✅ Built — Next.js 16 on port 3001 |
| Complainant notifications on key events | ✅ Built — chatbot + SMS fallback |
| SEAH workflow (invisible to standard roles) | ✅ Built — `is_seah` flag + DB-level filter |
| Quarterly reports (XLSX) + pivot builder | ✅ Built |
| LLM translation + findings digest | ✅ Built |
| QR token intake linking | ✅ Built |
| Executive summary tab (ADB Project Director) | 🔲 Specified, not yet built (§12 of `09_reports_and_report_builder.md`) |

---

## Principles

| Principle | Meaning |
|---|---|
| **Ticketing is independent** | Deployable and usable without any chatbot. Chatbot opts in by calling `POST /api/v1/tickets`. |
| **API-only integration** | Chatbot → Ticketing: create ticket, link conversation. Ticketing → Chatbot: reply via orchestrator `POST /message`. Messaging via Messaging API. |
| **Settings-driven** | Workflows, roles, organizations, locations, packages are DB-driven. No hard-coded business rules. |
| **PII isolation** | No PII in `ticketing.*` ever. Fetched on-demand via `GET /api/grievance/{id}`. |
| **Audit trail** | Every state change written to `ticket_events` (append-only). |
| **SEAH invisibility** | SEAH tickets filtered at DB query level; never exposed to standard roles via any endpoint. |

---

## High-Level Integration Picture

```
┌─────────────────┐   webhook    ┌──────────────────────┐   SMS/email   ┌──────────────────┐
│  Chatbot        │ ──────────► │  Ticketing API        │ ──────────── ► │  Messaging API   │
│  (Orchestrator  │             │  FastAPI :5002         │               │  FastAPI :5001   │
│   + backend)    │  reply      │  Celery (grm_ticketing)│               │  SMTP / AWS SNS    │
│                 │ ◄────────── │  PostgreSQL ticketing.*│               └──────────────────┘
└─────────────────┘             └──────────────────────┘
                                         │
                                         ▼
                                ┌──────────────────────┐
                                │  Officer UI           │
                                │  Next.js 16 :3001     │
                                │  Keycloak OIDC auth   │
                                └──────────────────────┘
```

---

## Deployment

| Environment | URL | Notes |
|---|---|---|
| Local (bypass auth) | http://localhost:3001 | `NEXT_PUBLIC_BYPASS_AUTH=true`, role switcher in header |
| Staging | https://grm.stage.facets-ai.com | Same EC2 as chatbot, separate Nginx location block |
| Production | https://grm.facets-ai.com | Docker compose with Keycloak auth stack |

Auth compose file: `docker-compose.grm.yml` — adds `grm_ui_auth` (:3002) + `ticketing_api_auth` (:5003) for production mode.
