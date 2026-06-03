# Nepal GRM Platform

Grievance Redress Mechanism (GRM) platform for Nepal road infrastructure projects (KL Road / Kakarbhitta-Laukahi Road, ADB Loan 52097-003).

The platform combines:
- A **conversational chatbot** for grievance intake (Rasa + FastAPI)
- A **GRM ticketing system** for officer case management (FastAPI + Next.js 16)

**Repository:** https://github.com/philgaeng/chatbot_ssh
**Active branch:** `feature/grm-ticketing`

---

## Quick Start

```bash
# Copy environment template
cp env.local .env
# Edit with your credentials
nano .env

# Build and start all services
docker compose up -d --build

# Run ticketing schema migrations
docker compose exec ticketing alembic upgrade head

# Seed demo data
docker compose exec ticketing python -m ticketing.seed.kl_road_standard
docker compose exec ticketing python -m ticketing.seed.mock_tickets
```

See [`docs/deployment/SETUP.md`](docs/deployment/SETUP.md) for full installation instructions.
See [`docs/deployment/DOCKER.md`](docs/deployment/) for Docker-specific commands.

---

## Services

| Service | Tech | Port | Description |
|---|---|---|---|
| Orchestrator | FastAPI | 8000 | Message routing, session management |
| Backend API | FastAPI | 5001 | Grievance CRUD, PII handling, messaging |
| Ticketing API | FastAPI | 5002 | GRM ticket management, workflow engine |
| Ticketing UI | Next.js 16 | 3000 | Officer dashboard (React, Tailwind v4) |
| Rasa | Rasa 3 | 5005 | NLU + dialogue for chatbot |
| Action Server | FastAPI | 5055 | Custom Rasa actions |
| Celery (LLM) | Celery | — | AI classification, transcription |
| Celery (GRM) | Celery | — | SLA watchdog, notifications, reports |
| PostgreSQL | PG 13+ | 5432 | `grievance_db` (public.* + ticketing.*) |
| Redis | Redis 6+ | 6379 | Broker + result backend |

---

## Repository Layout

```
nepal_chatbot/
├── backend/                  # Existing backend services (DO NOT MODIFY)
│   ├── actions/              # Rasa custom actions
│   ├── api/                  # FastAPI grievance API (port 5001)
│   ├── orchestrator/         # Message orchestrator (port 8000)
│   ├── services/             # Shared DB, encryption, integration services
│   └── task_queue/           # Celery app + shared tasks
├── ticketing/                # GRM ticketing system (new code lives here)
│   ├── api/                  # FastAPI ticketing API (port 5002)
│   ├── engine/               # Workflow engine + escalation logic
│   ├── models/               # SQLAlchemy models (schema="ticketing")
│   ├── tasks/                # Celery tasks (SLA watchdog, reports)
│   ├── clients/              # HTTP clients to grievance/messaging/orchestrator APIs
│   ├── migrations/           # Alembic migrations (ticketing.* schema only)
│   └── seed/                 # Demo data seeders
├── channels/
│   ├── ticketing-ui/         # Officer dashboard (Next.js 16, TypeScript, Tailwind v4)
│   ├── webchat/              # Complainant web chat interface
│   └── accessible/           # Accessible (voice) interface
├── rasa_chatbot/             # Rasa NLU + stories + domain
├── migrations/               # Alembic for public.* schema (chatbot tables)
├── docs/                     # Documentation (see docs/README.md)
├── deployment/               # Docker, Nginx, EC2 configs
├── scripts/                  # Utility scripts
└── tests/                    # Test suite
```

---

## Documentation

See [`docs/README.md`](docs/README.md) for the full documentation index.

| Area | Location |
|---|---|
| Architecture, setup, operations, security | [`docs/deployment/`](docs/deployment/) |
| GRM ticketing specs | [`docs/ticketing_system/`](docs/ticketing_system/) |
| Chatbot / REST chatbot specs | [`docs/rest_chatbot/`](docs/rest_chatbot/) |
| Sprint history (read-only) | [`docs/sprints/`](docs/sprints/) |

---

## Environments

| Environment | URL |
|---|---|
| Production (chatbot) | https://chatbot.facets-ai.com |
| Staging (GRM ticketing) | https://grm.stage.facets-ai.com |
| Production (GRM ticketing) | https://grm.facets-ai.com |

---

## Hard Boundaries

These folders must **never** be modified by agents or feature work:

```
backend/actions/         backend/orchestrator/     backend/api/
backend/services/        backend/task_queue/        channels/accessible/
channels/webchat/        channels/REST_webchat/     rasa_chatbot/
scripts/                 deployment/                docker-compose.yml
requirements.txt         .env / env.local
```

New code belongs only in `ticketing/`, `channels/ticketing-ui/`, and `requirements.grm.txt`.

---

## Database

- Single PostgreSQL instance (`grievance_db`)
- `public.*` — existing chatbot tables (read-only from ticketing)
- `ticketing.*` — all new GRM tables, managed by Alembic (`ticketing/migrations/`)
- PII never stored in `ticketing.*`; fetched on-demand via `GET /api/grievance/{id}`

See [`docs/deployment/07_migrations_policy.md`](docs/deployment/07_migrations_policy.md).  
Security controls index: [`docs/deployment/13_security.md`](docs/deployment/13_security.md).
