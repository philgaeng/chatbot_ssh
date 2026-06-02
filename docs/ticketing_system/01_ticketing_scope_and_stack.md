# Ticketing System – Scope and Stack (as-built, June 2026)

---

## Scope (as implemented)

- **Ticket = Grievance from chatbot.** Created via fire-and-forget webhook when a grievance is submitted. Also creatable manually in UI (future).
- **Two workflows:** Standard GRM (4 escalation levels) and SEAH (dedicated officers, DB-level invisibility to standard roles).
- **Configurable workflows:** Steps, SLA timers, tier assignments, and notification rules are all DB-driven via Settings UI.
- **Multi-tenant data model:** `country_code`, `organization_id`, `project_id`, `location_code`. v1 ships with one country (NP), one org (DOR), one project (KL Road).
- **QR-linked intake:** Physical QR codes on road signs link to chatbot URL; token encodes package + location context, pre-filling ticket metadata.
- **API-only chatbot integration:** No direct DB access from chatbot. All integration via REST endpoints.

---

## Stack

| Layer | Technology | Notes |
|---|---|---|
| **Ticketing API** | Python 3.11 + FastAPI | Port 5002 (standard) / 5003 (Keycloak auth mode) |
| **Officer UI** | Next.js 16, TypeScript, Tailwind CSS v4 | Port 3001 (bypass) / 3002 (auth mode). App Router. |
| **Background workers** | Celery (`grm_ticketing` app) | Separate from chatbot Celery; own queues |
| **Message broker** | Redis 6+ | Shared with chatbot broker |
| **Database** | PostgreSQL 13+, `ticketing.*` schema | Same `grievance_db` instance; isolated schema |
| **ORM / migrations** | SQLAlchemy 2 (mapped_column) + Alembic | `ticketing/migrations/alembic.ini` — scoped to `ticketing.*` only |
| **Auth (production)** | Keycloak OIDC | `grm_ui_auth` + `ticketing_api_auth` containers |
| **Auth (local/demo)** | `NEXT_PUBLIC_BYPASS_AUTH=true` | Header role-switcher; officer list from `GET /api/v1/users/roster` |
| **LLM** | OpenAI GPT-4 | Per-note translation + findings digest; Celery tasks |
| **Reports** | openpyxl (XLSX) | No pandas; lightweight |
| **File storage** | Local filesystem `uploads/ticketing/{ticket_id}/` | S3 planned post-v1 |

---

## Repository layout

```
ticketing/
├── api/
│   ├── main.py                    FastAPI app, port 5002
│   └── routers/
│       ├── tickets.py             POST/GET/PATCH /api/v1/tickets + actions
│       ├── workflows.py           Workflow CRUD
│       ├── users.py               Officer roster, invite, onboarding
│       ├── settings.py            Settings CRUD
│       ├── reports.py             Overview, pivot, quarterly, export
│       ├── locations.py           Location tree CRUD
│       ├── scan.py                Public QR scan + admin token CRUD
│       ├── viewers.py             Ticket viewer/tier management
│       ├── tasks.py               Ticket tasks CRUD
│       ├── webhooks.py            Keycloak webhook
│       ├── auth.py                Auth utilities
│       └── public_closure.py     Public ticket closure (complainant self-service)
├── engine/
│   ├── workflow_engine.py         Step resolution, workflow lookup
│   └── escalation.py             SLA check, auto-assign, escalation chain
├── models/                        SQLAlchemy models (all schema="ticketing")
│   ├── ticket.py                  Ticket, TicketEvent
│   ├── workflow.py                WorkflowDefinition, WorkflowStep, WorkflowAssignment
│   ├── organization.py            Organization
│   ├── project.py                 Project, Package
│   ├── officer_scope.py           OfficerScope (user × org × location scopes)
│   ├── user.py                    Role, UserRole
│   ├── officer_onboarding.py      OfficerOnboarding (invited → active lifecycle)
│   ├── ticket_viewer.py           TicketViewer (Informed/Observer tiers)
│   ├── ticket_overdue_episode.py  TicketOverdueEpisode (SLA breach audit)
│   ├── ticket_resolved_summary.py TicketResolvedSummary (structured closure doc)
│   ├── ticket_task.py             TicketTask (officer action items)
│   ├── ticket_file.py             TicketFile (attachments)
│   ├── ticket_context_cache.py    TicketContextCache (LLM context window)
│   ├── qr_token.py                QrToken
│   ├── settings.py                Settings (key/value JSON store)
│   ├── country.py                 Country
│   ├── project_type.py            ProjectType
│   └── admin_audit_log.py         AdminAuditLog
├── services/
│   ├── report_rows.py             Report query + filtering
│   ├── pivot_table.py             Pivot crosstab builder
│   ├── quarterly_assignments.py   Quarterly email assignment logic
│   ├── quarterly_library.py       Named report library
│   └── report_limits.py           Per-user rate limiting
├── tasks/
│   ├── escalation.py              SLA watchdog (every 15 min)
│   ├── notifications.py           Complainant notify + in-app badge
│   └── reports.py                 XLSX generation + email dispatch
├── clients/
│   ├── grievance_api.py           GET /api/grievance/{id}
│   ├── messaging_api.py           POST /api/messaging/send-sms / send-email
│   └── orchestrator.py            POST /message (complainant reply)
├── constants/
│   └── grm_role_catalog.py        9 seeded GRM roles + workflow_scope mapping
├── utils/
│   └── organization_identifier.py Server-allocated org ID generation
├── config/
│   └── settings.py                Pydantic-settings (env vars)
├── migrations/
│   ├── alembic.ini
│   └── versions/                  ~30 migration files, ticketing.* only
└── seed/
    ├── kl_road_standard.py        Standard 4-level workflow + org + locations
    ├── kl_road_seah.py            SEAH workflow
    ├── mock_tickets.py            Demo tickets (6 tickets, both scenarios)
    └── grm_roles.py               Role catalog seed

channels/ticketing-ui/             Next.js 16 officer dashboard
```

---

## Docker compose

- **`docker-compose.yml`** — base services (postgres, redis, chatbot services)
- **`docker-compose.grm.yml`** — adds: `ticketing_api` (:5002), `ticketing_celery`, `grm_ui` (:3001)
- **Auth extension** (production): `grm_ui_auth` (:3002), `ticketing_api_auth` (:5003)

Start ticketing: `docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d`
