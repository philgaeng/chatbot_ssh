# Nepal GRM Platform

Grievance Redress Mechanism (GRM) platform for Nepal road infrastructure projects
(KL Road / Kakarbhitta–Laukahi Road, ADB Loan 52097-003).

The platform combines:

- A **conversational chatbot** for grievance intake — a hand-rolled FastAPI state machine
  (`backend/orchestrator/`), multilingual (Nepali/English), text and voice
- A **GRM ticketing system** for officer case management — FastAPI + Next.js 16, with enforced
  service-level deadlines, a four-level escalation ladder up to a Grievance Redress Committee, and
  an access-isolated SEAH stream

**Repository:** https://github.com/philgaeng/chatbot_ssh
**Working branch:** `integration/stage` — `main` is an integration target only, never a working
branch (see [`CLAUDE.md`](CLAUDE.md) §Git workflow and [`docs/deployment/08_commit_strategy.md`](docs/deployment/08_commit_strategy.md)).

> **There is no Rasa server in this platform.** Intake is a hand-rolled FastAPI state machine.
> The single Rasa-family dependency is `rasa-sdk==3.6.2` (Apache-2.0), which supplies the
> `Tracker`, `CollectingDispatcher` and `DomainDict` types and the `SlotSet` / `FollowupAction`
> event helpers that the action classes under `backend/actions/` still speak; the orchestrator
> invokes those classes **in-process** ([`action_registry.py:285`](backend/orchestrator/action_registry.py#L285)),
> not over a webhook. There is no NLU model, no TensorFlow, and no action server. Stated here
> because earlier revisions of this file advertised a Rasa service on port 5005 that has never
> existed in either compose file.

---

## Quick start

Everything is built and run through Docker Compose — never on the host. Native runs cause port,
version and schema drift.

```bash
make wsl-up      # chatbot + GRM stack (UI :3001, ticketing API :5002, dev auth bypass)
make wsl-down    # stop everything
make help        # the full target list
```

Full build, migration, seed and debug commands: **[`docs/deployment/DOCKER.md`](docs/deployment/DOCKER.md)**.
First-time setup on a fresh clone or empty volume: **[`docs/deployment/02_setup.md`](docs/deployment/02_setup.md)** §3.
Those are the authoritative runbooks; this file deliberately does not restate them.

---

## Services

Thirteen services start by default across the two compose files; two more are profile-gated.
Generated from `docker-compose.yml` and `docker-compose.grm.yml` — if this table and a
`docker compose config --services` disagree, the compose files are right and this table is a bug.

| Service | Tech | Host port | What it does |
|---|---|---|---|
| `orchestrator` | FastAPI | 8000 | Conversation state machine, `POST /message`, session management |
| `backend` | FastAPI | 5001 | Grievance CRUD, PII encrypt/decrypt, files, messaging (SMS/email) |
| `ticketing_api` | FastAPI | 5002 | Ticket management, workflow engine, escalation, reports |
| `grm_ui` | Next.js 16 | 3001 | Officer dashboard (React 19, Tailwind v4, Keycloak OIDC) |
| `celery_llm` | Celery | — | Classification, summarisation, translation, transcription |
| `celery_default` | Celery | — | General chatbot async work |
| `celery_file` | Celery | — | Attachment processing |
| `grm_celery` | Celery | — | SLA watchdog, notifications, geocoding, GRM reports |
| `grm_celery_beat` | Celery beat | — | Periodic scheduler for the GRM queues |
| `ops` | APScheduler | — | Health checks, backups, dependency/licence scans, daily ops report — deliberately broker-independent, so it survives a Redis outage |
| `db` | PostgreSQL 15 | 5433 → 5432 | `app_db` (`public.*` + `ticketing.*` + `ops.*` + `keycloak`) |
| `redis` | Redis 8.10 | — | Celery broker + result backend, Socket.IO adapter (internal only) |
| `nginx` | nginx stable | 8080 → 80 | REST webchat + API proxy (80/443 under the aws/prod overlays) |
| `keycloak` *(profile `auth`)* | Keycloak 26 | 18080 → 8080 | OIDC identity provider for officer login |
| `db_init` *(profile `init`)* | — | — | One-shot schema creation into an empty Postgres volume |

---

## Repository layout

```
nepal_chatbot/
├── backend/                  # Chatbot + shared platform services
│   ├── actions/              # Intake action classes (rasa-sdk types, run in-process)
│   ├── api/                  # Grievance / files / messaging API (:5001)
│   ├── orchestrator/         # Conversation state machine (:8000)
│   ├── services/             # Shared DB, encryption, LLM, integration services
│   ├── task_queue/           # Celery app (llm / default / file queues)
│   ├── clients/, config/, logger/, shared_functions/, utils/
├── ticketing/                # GRM ticketing system
│   ├── api/                  # Ticketing API + routers (:5002)
│   ├── engine/               # Workflow engine + escalation logic
│   ├── models/               # SQLAlchemy models (schema="ticketing")
│   ├── tasks/                # Celery tasks (SLA watchdog, notifications, reports)
│   ├── clients/              # HTTP clients → grievance / messaging / orchestrator APIs
│   ├── auth/                 # Keycloak JWT verification
│   ├── migrations/           # Alembic — ticketing.* only
│   └── seed/                 # Workflow + demo data seeders
├── channels/
│   ├── ticketing-ui/         # Officer dashboard (Next.js 16, TypeScript, Tailwind v4)
│   ├── REST_webchat/         # Complainant web chat (the live intake surface)
│   ├── webchat/              # Earlier Socket.IO webchat
│   └── shared/               # Assets shared by both chat surfaces
├── ops/                      # Platform monitoring container (health, backup, security, reports)
│   └── migrations/           # Alembic — ops.* only
├── migrations/public/        # Alembic — public.* (chatbot schema)
├── deployment/               # nginx, certbot, Keycloak themes, logrotate, Docker assets
├── scripts/                  # ci/, database/, docker/, ops/, servers/
├── docs/                     # Documentation (see docs/README.md)
└── tests/                    # actions/, backend/, orchestrator/, ticketing/, repo/, shared/
```

Three Alembic streams own three schemas and never share a table:
`ticketing/migrations/` → `ticketing.*`, `migrations/public/` → `public.*`, `ops/migrations/` →
`ops.*`. See [`docs/deployment/07_migrations_policy.md`](docs/deployment/07_migrations_policy.md).

---

## Documentation

[`docs/README.md`](docs/README.md) is the index for the whole tree.

| Area | Location |
|---|---|
| How we build — DB, services, API, tests, frontend, doc lifecycle | [`docs/engineering/`](docs/engineering/) |
| Architecture, setup, operations, security, auth | [`docs/deployment/`](docs/deployment/) |
| GRM ticketing specs (+ officer UI) | [`docs/ticketing_system/`](docs/ticketing_system/) |
| Chatbot / REST chatbot specs | [`docs/rest_chatbot/`](docs/rest_chatbot/) |
| SEAH intake, privacy and the PII vault | [`docs/seah/`](docs/seah/) |
| Digital Public Good qualification + evidence pack | [`docs/dpg/`](docs/dpg/) |
| Sprint history and current sprint trackers | [`docs/sprints/`](docs/sprints/) |

---

## Environments

| Environment | Host |
|---|---|
| Local (WSL, Docker Compose) | `http://localhost:8080` (webchat) · `http://localhost:3001` (officer UI) |
| AWS staging | `nepal-gms-chatbot.facets-ai.com` |
| Nepal DOR production | `grm-chatbot.dor.gov.np` |

Routing per environment is defined by the `deployment/nginx/webchat_rest_compose_*.conf` files
and documented in [`docs/deployment/12_environment_urls.md`](docs/deployment/12_environment_urls.md).

---

## Database

- One PostgreSQL 15 instance (`app_db`), four schemas: `public.*` (chatbot), `ticketing.*` (GRM),
  `ops.*` (monitoring), `keycloak` (identity provider state)
- Ticketing reads and writes a **closed, enumerated set** of `public.*` tables through its own
  session; grievance **state** changes always go over HTTP, never SQL
- **No foreign keys** from `ticketing.*` into `public.*`, and **no complainant PII columns** in
  `ticketing.*` — both pinned by tests (`tests/ticketing/test_boundary_policy.py`,
  `tests/ticketing/test_pii_boundary.py`)
- Complainant PII is fetched on demand via `GET /api/grievance/{id}`, which decrypts server-side;
  ticketing holds no encryption key and has no accessor for one

The rules and the reasons behind them are in [`CLAUDE.md`](CLAUDE.md) §Database architecture.

---

## Contributing

- **How to contribute:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **Community standards:** [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- **Reporting a vulnerability:** [`SECURITY.md`](SECURITY.md) — please use the private channel
  described there. This platform holds SEAH (sexual exploitation, abuse and harassment)
  disclosures; **do not** open a public issue for a security report
- **Roadmap:** the current programme of work is the DPG compliance and LLM-independence sprint
  plan, [`docs/sprints/2026-08-llm/README.md`](docs/sprints/2026-08-llm/README.md)

Working conventions — branch rules, the engineering rules, the Docker-only build policy — live in
[`CLAUDE.md`](CLAUDE.md) and [`docs/engineering/00_engineering_index.md`](docs/engineering/00_engineering_index.md).
`backend/`, `channels/webchat/`, `channels/REST_webchat/`, `scripts/` and `deployment/` are stable
production surfaces: change them deliberately, with tests, not casually.

---

## Licence

Licensed under the **Apache License, Version 2.0** — see [`LICENSE`](LICENSE) and
[`NOTICE`](NOTICE). Every source file carries an `SPDX-License-Identifier: Apache-2.0` header;
`scripts/ops/add_spdx_headers.py` maintains that coverage and `tests/repo/test_spdx_headers.py`
fails the build if a file drifts out of it. A generated, dated inventory of every dependency and
its licence — 153 packages across four dependency sets — is at
[`docs/dpg/dependency-licenses.md`](docs/dpg/dependency-licenses.md), refreshed nightly by the
`ops` container.

Apache-2.0 was chosen over MIT for its express patent grant, which matters when a government adopts
the code and other country teams fork it.

> ⚠ **Two provisional points, stated rather than glossed.** The licence is adopted so that work and
> review can proceed and may be revisited on the advice of ADB's Digital Public Goods consultant.
> And the **copyright holder is not yet determined** — parts of this platform were developed under an
> ADB-financed engagement, so a written determination has been requested from ADB's Office of the
> General Counsel. `NOTICE` says so explicitly instead of naming a holder by inference. Context:
> [`docs/dpg/00_compliance_status.md`](docs/dpg/00_compliance_status.md).
