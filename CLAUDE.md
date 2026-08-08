# CLAUDE.md — Nepal Chatbot / GRM Ticketing System

---

## ⚡ READ THIS BEFORE ANY CODE DECISION

| File                                    | Read for                                                                    |
| --------------------------------------- | --------------------------------------------------------------------------- |
| **→ `docs/PROGRESS.md`** | Current build state, demo DB, deviations, commit log (updated every commit) |
| **→ `docs/TODO.md`**     | Open gaps, next features, tech debt                                         |
| **→ `docs/engineering/00_engineering_index.md`** | **HOW we build** — DB, service layer, API, tests, frontend, doc lifecycle. Binding on every change. |
| **→ `docs/deployment/DOCKER.md`**   | Build, start, migrate, seed, debug containers                               |
| **→ `docs/README.md`**   | Index of the full spec tree (services, ticketing, chatbot, SEAH, deployment) |

`PROGRESS.md` tells you what was _actually built_. `TODO.md` tells you what's next. `docs/engineering/` tells you **how to build it** (craft rules, per layer). `DOCKER.md` tells you how to run it. This file has the locked **architecture** — the decisions the craft rules follow from. Where a craft rule and this file disagree on a locked decision, this file wins; on _how_ to implement it, `docs/engineering/` wins.

## 🐳 BUILD & RUN ONLY WITH DOCKER (non-negotiable)

**Always build and run this stack with Docker Compose — never on the host.** Every service (chatbot, orchestrator, backend, ticketing_api, celery, ops, db, redis, keycloak, grm_ui) is built and started through the Compose stacks — `make wsl-up` / `docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml build|up` (see `docs/deployment/DOCKER.md`). **Do not** `pip install`, `npm run build`, `uvicorn …`, `redis-server`, or run migrations/seeds natively to build or serve. Native runs cause port/version/schema drift (e.g. a stray host `redis-server` on :6379, a mismatched host Python, an unmigrated DB). Host CLIs are for **reading/inspection only**; anything that builds an image, starts a service, or mutates the DB goes through Docker.

## ⚠️ SUPERSEDED BY AS-BUILT SPECS (July 2026)

The May 10, 2026 demo shipped; parts of the locked plan below were superseded during the build. Where this file and the as-built specs disagree, **the specs win**:

| This file says | As-built reality | Authoritative spec |
| --- | --- | --- |
| AWS **Cognito** OIDC + `COGNITO_GRM_*` env vars | **Keycloak** everywhere (PKCE OIDC, invites, SMTP, onboarding webhook) | `docs/deployment/16_auth_keycloak.md` |
| 12-role list incl. `local_admin` | Admin ladder: `super_admin`/`country_admin`/`project_admin` + `workflow_track` + operational role catalog | `docs/ticketing_system/11_roles_and_permissions.md` |
| Queue tabs "My Queue / Watching / Escalated / Resolved" | Actor / Supervisor / High Priority / All Tickets (+ Informed/Observer) | `docs/ticketing_system/15_ticket_queue_search_and_filters.md` |
| GRC two-step Convene + **Decide** | `GRC_DECIDE` removed in v1 — only RESOLVE ends a case | `docs/ticketing_system/08_ticket_resolution_and_case_summary.md` |
| Target `grm.facets-ai.com` (staging on facets) | Production is **`grm-chatbot.dor.gov.np`** (DOR infra); facets is staging | `docs/deployment/12_environment_urls.md` |
| "Two workflows" (Standard + SEAH) | Multi-stream workflow slots per project (safeguards/hazards/ca/seah) | `docs/ticketing_system/12_workflows_configuration.md` |
| SEAH intake per April plan | Canonical model: `grievance_parties` + PII vault, legacy SEAH tables dropped | `docs/seah/` |

---

# Read the rest of this file before touching any code.

# ALL decisions locked through Round 2.

**Single-agent workflow (June 2026):** this monorepo is now developed by **one** AI coding system across the whole codebase (chatbot + ticketing + ops) — no longer split between Claude (ticketing) and Cursor (chatbot) in separate parallel worktrees. The boundaries below are therefore **care boundaries** (stable shared services to change deliberately), **not ownership walls** between competing tools. Work in whichever area the task requires; just respect the stability and schema-ownership rules.

---

## PROJECT OVERVIEW

Monorepo for an ADB-compliant Grievance Redress Mechanism (GRM) ticketing system,
built alongside an existing chatbot, orchestrator, and messenger service for Nepal road
infrastructure projects (KL Road / Kakarbhitta-Laukahi Road, ADB Loan 52097-003).

**Repo:** https://github.com/philgaeng/chatbot_ssh
**WSL path:** `/home/philg/projects/nepal_chatbot`
**Windows path:** `\\wsl.localhost\Ubuntu\home\philg\projects\nepal_chatbot`
**Active branch:** `feature/grm-ticketing`
**Do not touch:** `feat/seah-sensitive-intake`, `main`

---

## Git workflow (LOCKED)

- **Never use `main` as a working branch.** Do not commit or push day-to-day implementation directly on `main` — that branch is only an integration target (merge or PR from feature branches).
- Work on explicit branches such as `features/chatbot`, `feature/grm-ticketing`, `feat/seah-sensitive-intake`, or agreed integration branches.
- Pulling or merging **`origin/main` into a feature branch** to stay current is fine; changing **`main` itself** only happens via deliberate promotion from those branches.
- If commits accidentally landed on **`main`**, fix by moving them onto the correct feature branch (cherry-pick / branch-off before pulling others’ changes) and restoring **`main`** to match **`origin/main`** per `docs/deployment/COMMIT_STRATEGY.md`.

---

## SERVICE BOUNDARIES — CHANGE WITH CARE

These are **stable, production chatbot/infra services**. With the single-agent workflow you **may** modify them when the task genuinely requires it — but do so **deliberately**: understand the service first, run its tests, and avoid regressions to the live chatbot. They are no longer off-limits because "another tool owns them"; the caution is about **stability**, not ownership.

### Stable shared services — modify only with clear intent + tests:

```
backend/orchestrator/      → stable (chatbot state machine)
backend/api/               → stable (grievance/file/messaging APIs)
backend/services/          → stable (shared service layer)
backend/task_queue/        → stable (chatbot Celery: llm/default/file queues)
channels/webchat/          → stable
channels/REST_webchat/     → stable
rasa_chatbot/              → stable
scripts/                   → stable (ops/db scripts — add new under scripts/ops or scripts/database)
deployment/                → stable (nginx/certbot/keycloak config)
docker-compose.yml         → stable base stack (overlay new services in *.grm.yml / *.prod.yml where possible)
requirements.txt           → chatbot deps (add GRM/ops deps to requirements.grm.txt)
.env / env.local           → edit deliberately; never commit secrets (env.local is gitignored)
```

### Chatbot ↔ ticketing integration points:

```
backend/actions/utils/ticketing_dispatch.py  → POST /api/v1/tickets webhook (intake_route = story_main)
backend/actions/                           → other intake/submit paths when wiring GRM
ticketing/                                 → ticketing API, schema, routing
channels/ticketing-ui/                     → officer UI
requirements.grm.txt                       → GRM/ops Python dependencies
```

### New feature code defaults to:

```
ticketing/                 → ticketing backend
channels/ticketing-ui/     → officer frontend (Next.js 16)
ops/                       → platform monitoring/health/backup/reporting (own container + ops.* schema)
```

---

## EXISTING STACK

| Service        | Tech    | Port  | Module                                         |
| -------------- | ------- | ----- | ---------------------------------------------- |
| Orchestrator   | FastAPI | ~8000 | `uvicorn backend.orchestrator.main:app`        |
| Backend API    | FastAPI | 5001  | `uvicorn backend.api.fastapi_app:app`          |
| Celery LLM     | Celery  | —     | `backend.task_queue.celery_app` `-Q llm_queue` |
| Celery default | Celery  | —     | `backend.task_queue.celery_app` `-Q default`   |
| Redis          | Redis   | 6379  | broker + result backend                        |
| PostgreSQL     | PG 13+  | 5432  | `grievance_db`                                 |

### APIs to call (never reimplement):

**Grievance API** — primary data source for complainant PII, and it **decrypts server-side** (T3-04):

```
GET  /api/grievance/{grievance_id}    ← auth: x-api-key (T3-06) · returns PLAINTEXT PII (T3-04)
POST /api/grievance/{grievance_id}/status  ← auth: x-api-key (T3-06)
GET  /api/grievance/statuses          ← public
```

> This line claimed decryption for months before it was true. `get_grievance_by_id` returned
> pgcrypto hex, and `ticketing/services/pii_vault.py` decrypted client-side as a workaround —
> which is the *only* reason ticketing ever held `DB_ENCRYPTION_KEY`. **T3-04 made the claim
> true** (`grievance_manager.py`), deleted the workaround, and removed the key from ticketing's
> settings. The key is now owned solely by `backend`. **Ticketing decrypts nothing, and cannot:
> there is no accessor** — pinned by `tests/ticketing/test_pii_boundary.py`. History:
> [`00-reassessment.md`](docs/sprints/archive/2026-08_tier3_structural/00-reassessment.md) §3.

**Messaging API** — for complainant SMS fallback + quarterly reports:

```
POST /api/messaging/send-sms    → AWS SNS (works internationally)
POST /api/messaging/send-email  → SMTP mailbox relay
Auth: x-api-key header
```

**Orchestrator** — for officer → complainant replies:

```
POST /message  { user_id: session_id, text: str, channel: "ticketing" }
```

---

## DATABASE ARCHITECTURE (LOCKED)

### Proto: same Postgres instance (grievance_db), separate schema (ticketing.\*)

```
grievance_db
  ├── public.*     ← chatbot-owned tables. Ticketing touches only the closed set in rule 1
  └── ticketing.*  ← all new tables, owned by ticketing system
```

### Data rules (LOCKED):

> **Amended 2026-07-15 (T3-07).** Rules 1 and 5 were rewritten to describe what is actually
> built; rules 2 and 3 were kept and are now pinned by tests. **The evidence and the decision:
> [`docs/sprints/archive/2026-08_tier3_structural/00-reassessment.md`](docs/sprints/archive/2026-08_tier3_structural/00-reassessment.md) §6 — read it before changing any rule below.**
>
> **Why the old rule 1 went.** Rules 1/2 were written 2026-03-11 to keep two options open: move
> ticketing to its own database by changing a connection string, and keep the chatbot working if
> ticketing were removed. **Both goals were abandoned in the code, by both sides, months before
> anyone amended the rule** — ticketing issues 11 statements against `public.*` (3 of them
> writes), and the chatbot's intake location validation reads `ticketing.locations` through its
> own connection. The rule had no enforcement (one DB, one role), had been false for months, and
> honoring it today would *degrade* security: the direct read is behind a Keycloak JWT and a
> jurisdiction gate that `GET /api/grievance/{id}` still cannot offer (§6, and T3-06's scorecard).
> A doc reorg (`21631051`, 2026-06-02) deleted that rationale and left the bare rule, which is
> why it read as arbitrary fiat ever since. **If you amend a rule here, move its reason with it —
> a rule without its reason decays into cargo cult.**

1. **Ticketing may read and write `public.*` through its own session — but only the enumerated set below.** The set is **closed**: adding a table is a deliberate decision, not a default. **The table below is itself pinned** by `tests/ticketing/test_boundary_policy.py`, which parses it and fails when it and the code disagree — on the table set *or* on which tables are written. (Until 2026-07-15 this line claimed that and was false: the test pinned the code against a dict *inside the test*, and this table was a hand-maintained mirror. Editing it alone changed nothing. Now the chain is closed: this table ↔ the test's `CONTRACT` ↔ the code.)

   | `public.*` table | Ticketing's access | Where |
   | --- | --- | --- |
   | `grievances` | read | `services/grievance_content.py`, `tasks/grievance_sync.py` |
   | `file_attachments` | read + **write** (`UPDATE` archive tier) | `api/ticket_access.py`, `api/routers/tickets/files.py`, `engine/ticket_actions.py`, `services/archiving.py` |
   | `grievance_classification_taxonomy` | read + **write** (`DELETE`+`INSERT` resync) | `services/grievance_categories_catalog.py`, `seed/kl_road_standard.py` |
   | `complainants` | read — **join-only, non-PII columns** (`location_code`) | `tasks/grievance_sync.py` |
   | `grievance_parties` | read — join-only | `tasks/grievance_sync.py` |

   Grievance **state** changes still go over HTTP (`POST /api/grievance/{id}/status`), never SQL. That is a real invariant, not an accident — keep it.
2. **No foreign keys from `ticketing.*` into `public.*`.** Kept, unchanged. This is the half of the March rule that still earns its keep: it preserves extraction optionality, keeps the three migration streams independent, and costs nothing — links are soft `String(64)` refs. **Pinned by a test.**
3. **No complainant PII columns in `ticketing.*`** (`complainant_full_name` / `complainant_phone` / `complainant_email` / `complainant_address`), and **`public.complainants` is not a PII source for ticketing**. Kept, sharpened back to its original 2026-03 form. This is the one PII rule that stands on its own merits, independent of everything above. **Pinned by a test.**
4. `ticketing.tickets` caches non-PII at creation: `grievance_summary`, `grievance_categories`, `grievance_location`, `priority`
   > **Honest caveat:** `grievance_summary` is free text and *can* contain self-disclosed PII. It is cached by design (`models/ticket.py`); `grievance_description` — the raw narrative — deliberately is **not** (`services/grievance_content.py` writes only summary/categories/location). **The asymmetry is intentional. Do not "fix" it** by caching the description.
5. **Complainant PII** is fetched fresh via `GET /api/grievance/{id}` and never cached in `ticketing.*`. The endpoint returns **plaintext** — the backend decrypts server-side (T3-04) and ticketing holds no encryption key. **This does not extend to grievance content** — ticketing reads `grievance_description` and file metadata directly, per rule 1.
6. Complainant name: shown by default. Phone: hidden, revealed via "Reveal contact" button (action logged, no OTP for proto)

### SQLAlchemy — ALL models must use:

```python
__table_args__ = {"schema": "ticketing"}  # REQUIRED on every model
# grievance_id = Column(String(64))    ← string ref, NO FK
# complainant_id = Column(String(64))  ← string ref, NO FK
```

### Alembic — MUST be scoped to ticketing schema:

```python
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        return object.schema == "ticketing"
    return True
# Also: version_table_schema="ticketing" in configure()
```

### Each migration file must start with:

```python
# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
```

### Migration traceability (three streams)

- **Ticketing (`ticketing.*`):** all forward DDL goes through **Alembic** (`ticketing/migrations/alembic.ini`). Use **only** this stream for ticketing tables so revisions stay linear and visible in git.
- **Chatbot / public (`public.*`):** **not** migrated by the ticketing Alembic project (see headers and `include_object` above). Use the Alembic project at `migrations/public/alembic.ini` (version table `alembic_version_public`). Some tables may still be **first-created** by app code; **structural changes** go in `migrations/public/versions/`.
- **Ops / monitoring (`ops.*`):** platform health/monitoring tables (`system_health_checks`, `dependency_findings`) and the scoped `ops_app` role. Use the Alembic project at `ops/migrations/alembic.ini` (version table `alembic_version_ops`, `include_object` scoped to `schema == "ops"`). Owned by the `ops/` module — never the chatbot or ticketing streams.
- The three streams must **never** share ownership of the same table/schema. See **`docs/deployment/07_migrations_policy.md`** and **`docs/services/11_health_and_monitoring_service.md`** §5.2.

### DB operating model (LOCKED)

Single-agent workflow — parallel chatbot-vs-ticketing worktrees are no longer required. If you do use multiple worktrees/branches, isolate their DBs; otherwise a single local stack is fine.

1. **Branch hygiene**
   - Feature branches off `main` (e.g. `feature/seah`, `feature/grm-ticketing`); `main` is integration-only (see Git workflow).
   - Validate migrations + smoke tests before promoting to `main`.

2. **Isolate DBs when running multiple worktrees concurrently**
   - One Postgres container/volume per active worktree (different host ports) to avoid migration collisions and branch-state contamination.
   - A single shared local DB is acceptable when only one worktree is active.

3. **Schema ownership must be explicit (three owners)**
   - `ticketing.*` → ticketing migrations (`ticketing/migrations/alembic.ini`)
   - `public.*` → chatbot/public migration path (`migrations/public/alembic.ini`)
   - `ops.*` → ops migrations (`ops/migrations/alembic.ini`) + the `ops_app` scoped role
   - Never let two migration streams own DDL for the same table.

4. **Shared admin domain rule (projects/locations/settings)**
   - Ticketing is the admin UI/backend, but shared entities must have a single schema owner.
   - Integrate via stable service/API boundaries for chatbot-consumed data; avoid cross-domain schema edits without a clear owner.

5. **Integration requirements**
   - Run all relevant migration streams in deterministic order and verify chatbot + ticketing + ops paths.
   - Promote to `main` only after integration DB + smoke tests pass.

---

## WORKFLOW ARCHITECTURE (LOCKED)

### Two workflows — NOT parallel instances:

```
Standard GRM   → 4 levels, regular officers, visible to standard roles
SEAH           → dedicated SEAH officers only, invisible to standard roles
```

One grievance = one ticket = one workflow (never both).
SEAH tickets filtered at DB query level by role.

### Escalation — BOTH manual and auto:

- **Auto:** Celery SLA watchdog every 15 min — escalates on SLA breach
- **Manual:** Officer clicks "Escalate" button in case view at any time

### GRC (L3) — two-step:

- GRC chair action 1: "Convene" (schedules hearing, notifies all GRC members)
- GRC chair action 2: "Decide" (records resolution, advances workflow)
- All GRC members entered in system for that project receive in-app notification on convening

---

## ROLES (LOCKED)

```
super_admin               → full access, both workflows
local_admin               → admin for their org/location
site_safeguards_focal_person → L1, standard only
pd_piu_safeguards_focal   → L2, standard only
grc_chair                 → L3 (convene + decide), standard only
grc_member                → L3 (input), standard only
adb_national_project_director → observer, standard only
adb_hq_safeguards         → observer, standard only
adb_hq_project            → observer, standard only
seah_national_officer     → SEAH only
seah_hq_officer           → SEAH only
adb_hq_exec               → read-only both (senior oversight)
```

---

## FRONTEND (LOCKED)

### Stack:

Fresh Next.js 16 app in `channels/ticketing-ui/` inside chatbot_ssh.
TypeScript, Tailwind CSS v4, Keycloak OIDC (originally planned as Cognito).

### Stratcon as reference (read only — never forked/merged):

- **Live:** https://stratcon.facets-ai.com — login: philippe@stratcon.ph / 0bPwPstU9sJnYTBQr2f\*
- **Repo:** https://github.com/philgaeng/stratcon

### Patterns to copy from Stratcon into ticketing-ui:

| Pattern                       | Copy as                      |
| ----------------------------- | ---------------------------- |
| Cognito OIDC auth middleware  | Officer login + route guards |
| Role-based route protection   | GRM role checks              |
| Settings page shell           | Admin settings               |
| User management + invite flow | Officer account management   |
| Sidebar layout                | GRM navigation (see below)   |
| Help / docs page              | GRM officer guide            |

### Sidebar navigation (role-gated):

```
My Queue          ← landing, officer's assigned tickets + SLA countdowns
All Tickets       ← filterable list (admin + senior roles)
─────────────
Escalated         ← SLA-breached + manually escalated tickets
GRC               ← L3 tickets only (grc_chair, grc_member roles only)
─────────────
Reports           ← quarterly export + history
─────────────
Settings          ← admin only: workflows, users, orgs, locations
Help              ← GRM officer guide
```

### New screens (build from scratch — no Stratcon equivalent):

- Officer ticket queue (main landing)
- Ticket detail + action panel (acknowledge / escalate / resolve)
- Case timeline + audit log
- SLA countdown component
- In-app notification badge (see notifications section)
- SEAH restricted view with 🔒 badge

### SEAH visual distinction:

- Same queue page as standard (not a separate route)
- Red `🔒 SEAH` badge on ticket row
- Subtle red left border on ticket card
- Access control ensures only SEAH officers see these tickets

### Target: grm.facets-ai.com → staging: grm.stage.facets-ai.com

Same EC2 as chatbot, different Nginx location block.
Run via Docker, deploy to staging EC2 first, then production.

---

## NOTIFICATIONS (LOCKED)

### Officer notifications: in-app badge only (proto)

- Badge count on queue page, refreshes on navigation
- **Note for post-proto:** upgrade to Server-Sent Events (SSE) for real-time push
- No email, no SMS to officers in proto

### Complainant notifications: chatbot-first, SMS fallback

- **Primary:** `POST /message` to orchestrator using `session_id` stored on ticket
- **Fallback** (session expired): `POST /api/messaging/send-sms` via Messaging API
  - AWS SNS works internationally — use for demo (PH numbers work)
  - Production Nepal: revisit when local SMS entity available
- Store `session_id` on ticket at creation — critical for both paths

### GRC convening: all GRC members for that project, in-app notification

### Quarterly reports: email via Messaging API send-email, to roles:

`adb_national_project_director`, `adb_hq_safeguards`, `mopit_rep`, `dor_rep`

---

## OFFICER CASE VIEW (LOCKED)

- **Queue layout:** Tabs + tiles combined:
  - **Tabs:** My Queue 🔴 | Watching | Escalated 🔴 | Resolved
    - Red badge on My Queue and Escalated (actionable)
    - Plain count on Watching (informational)
    - No badge on Resolved (historical)
  - **Tiles inside each tab (3 per tab):** summary cards at top, clicking filters list below
    - My Queue tiles: Action Needed | Due Today | Overdue 🔴
    - Watching tiles: Active Cases | Escalated | Resolved this quarter
  - **Ticket rows:** color-coded urgency (🔴 <24h, 🟡 <3d, 🟢 >3d) + SLA countdown ⏱ + 🔒 SEAH badge
  - Tiles copy from Stratcon dashboard component, content swapped to GRM metrics
- **Case timeline:** System events + internal officer notes (B). AI summary = post-proto
- **Internal notes:** YES — visible to officers only, never to complainants
- **File attachments:** Show existing chatbot files (read) + allow officer uploads
  - Officer files stored in `uploads/ticketing/{ticket_id}/` (same filesystem, S3 later)
  - File attachment on escalate/resolve: warning encouraged but not blocked (B)
- **Officer reply to complainant:** YES via POST /message → chatbot orchestrator
- **Complainant PII:** Name shown, phone hidden → "Reveal contact" button → logged

---

## REPORTS (LOCKED)

- **Format:** XLSX (openpyxl) — lightweight, no pandas
- **Trigger:** Configurable date in admin settings (D) — admin sets schedule
- **Recipients:** By role (automatic)
- **Columns:**
  - Reference number (grievance_id)
  - Date submitted
  - Nature / categories
  - Grievance AI summary ← add
  - Location (district/municipality)
  - Organization
  - Level reached before resolution
  - Current status
  - Days at each level
  - SLA breached? (Y/N per level)
  - Instance (Standard / SEAH)

---

## DEMO SEED DATA (MAY 10)

### Mock data seeded directly into ticketing.\* tables (no chatbot DB connection needed)

### Seed data required:

- KL Road Standard workflow (4 levels) — YES
- KL Road SEAH workflow (SEAH officers only) — YES
- Organizations: DOR, ADB — YES
- Locations: Province 1 (KL Road area, match existing chatbot location data) — YES
- Mock officers: one per role — YES

### Demo scenario 1 — Standard GRM:

"Complainant files about dust in house along KL Road, children falling sick.
→ Site officer acknowledges (L1)
→ Unresolved after 2 days → auto-escalates to L2 (PD/PIU)
→ PD/PIU investigates, unresolved after 7 days → L3 (GRC convened)
→ GRC chair convenes hearing → decides: contractor required to wet-spray road twice daily
→ Resolved, complainant notified via chatbot"

### Demo scenario 2 — SEAH:

"Complainant reports harassment by construction worker.
→ SEAH officer investigates (invisible to standard officers)
→ Escalated to SEAH supervisor
→ Complaint filed with police
→ Case closed with referral"

### Demo environment:

- Develop: Docker on WSL
- Demo: staging EC2 (grm.stage.facets-ai.com)

---

## BUILD TIMELINE (MAY 10 DEADLINE)

```
Week 1 (Apr 21-27) — Backend, Claude Code:
  Session 0: codebase analysis → session-0-codebase-findings.md
  Session 1: ticketing.* schema + SQLAlchemy models + Alembic migration
  Session 2: FastAPI skeleton + ticket CRUD API + mock data seeder
  Session 3: Workflow engine + escalation logic + Celery tasks

Week 2 (Apr 28 - May 4) — Frontend, Cursor:
  channels/ticketing-ui/ setup (Next.js 16, copy Stratcon auth + layout)
  Officer queue page (tabs: My Actions | All Active | Escalated | Resolved)
  Ticket detail + action panel (acknowledge / escalate / resolve)
  SLA countdown + notification badge
  Internal notes + file attachments (read + upload)
  SEAH visual distinction (🔒 badge)

Week 3 (May 5-9) — Integration + demo prep, Cursor:
  SEAH workflow + role-based access control
  Complainant notification (chatbot + SMS fallback)
  Mock data seeded for both demo scenarios
  Chatbot → ticketing webhook (POST /api/v1/tickets on submit)
  Docker deployment to grm.stage.facets-ai.com
  Bug fixes + polish

May 10: Demo
```

---

## EXISTING TICKETING SPECS (read before coding)

```
docs/ticketing_system/00_ticketing_decisions.md   → product decisions
docs/ticketing_system/01_ticketing_scope_and_stack.md
docs/ticketing_system/02_ticketing_domain_and_settings.md
docs/ticketing_system/03_ticketing_api_integration.md
docs/ticketing_system/04_ticketing_schema.md       ← START HERE for Session 1
docs/ticketing_system/05_ticketing_impl_plan.md
docs/ticketing_system/Escalation_rules.md
```

---

## FOLDER STRUCTURE

```
ticketing/
  api/
    main.py             ← FastAPI app, port ~5002
    routers/
      tickets.py        ← POST/GET /api/v1/tickets
      workflows.py      ← workflow CRUD
      users.py          ← officer accounts + Cognito invite
      settings.py       ← settings CRUD (incl. report schedule)
      reports.py        ← XLSX quarterly export
  models/               ← SQLAlchemy, ALL with schema="ticketing"
    ticket.py           ← Ticket, TicketEvent
    workflow.py         ← WorkflowDefinition, WorkflowStep, WorkflowAssignment
    organization.py     ← Organization, Location
    user.py             ← Role, UserRole
    settings.py         ← Settings
  engine/
    workflow_engine.py  ← step resolution, workflow assignment lookup
    escalation.py       ← SLA check, chain, manual escalation
  tasks/
    __init__.py         ← separate Celery app ("grm_ticketing")
    escalation.py       ← SLA watchdog (every 15 min) + escalation chain
    notifications.py    ← in-app badge updates
    reports.py          ← quarterly XLSX generation + email dispatch
  clients/
    grievance_api.py    ← HTTP → GET /api/grievance/{id}
    messaging_api.py    ← HTTP → POST /api/messaging/send-* (SMS fallback + reports)
    orchestrator.py     ← HTTP → POST /message (complainant reply)
  config/
    settings.py         ← pydantic-settings
  migrations/
    env.py              ← Alembic with include_object + version_table_schema
    versions/
  schemas/
    workflow_definition.json
  seed/
    kl_road_standard.py ← standard 4-level GRM workflow
    kl_road_seah.py     ← SEAH workflow
    mock_tickets.py     ← demo scenarios (dust/children + SEAH)
channels/
  ticketing-ui/         ← fresh Next.js 16 + TypeScript + Tailwind v4
ops/                    ← platform monitoring (own container, broker-independent APScheduler)
  scheduler.py          ← APScheduler entrypoint (python -m ops.scheduler)
  checks.py             ← data-plane health checks → ops.system_health_checks
  security.py           ← dependency/CVE scan → ops.dependency_findings
  maintenance.py        ← prune/vacuum/os-update-check
  reports.py            ← daily ops report (activity + health)
  alerts.py             ← deduped alerts via Messaging API (HTTP)
  migrations/           ← ops Alembic stream (ops.* schema + ops_app role)
requirements.grm.txt
docs/
  README.md             ← index of the whole spec tree
  PROGRESS.md, TODO.md  ← operational build logs
  services/             ← shared backend service contracts
  ticketing_system/     ← GRM ticketing specs (+ ui/ for the officer UI)
  rest_chatbot/         ← chatbot architecture/flow/frontend specs
  seah/                 ← SEAH intake + privacy/vault specs
  deployment/           ← runbooks, auth, security, DOCKER.md
  sprints/              ← one summary per sprint; originals in sprints/archive/
```

---

## CONVENTIONS

- Python: snake_case, type hints, Pydantic v2
- Datetimes: UTC, `timestamp with time zone`
- IDs: UUID4 (`gen_random_uuid()` in Postgres, `uuid4()` in Python)
- ALL models: `__table_args__ = {"schema": "ticketing"}`
- Env vars: via `ticketing/config/settings.py` pydantic-settings
- No hardcoded URLs, credentials, or broker addresses
- Leave `# INTEGRATION POINT:` for anything needing Cursor wiring
- Commit strategy: `docs/deployment/COMMIT_STRATEGY.md`

---

## ENVIRONMENT VARIABLES (append to .env)

```env
TICKETING_PORT=5002
TICKETING_SECRET_KEY=           ← python -c "import secrets; print(secrets.token_urlsafe(32))"
MESSAGING_API_KEY=              ← from existing backend config
BACKEND_GRIEVANCE_BASE_URL=http://localhost:5001
ORCHESTRATOR_BASE_URL=http://localhost:8000
# Keycloak vars (Cognito was superseded — see docs/deployment/16_auth_keycloak.md)
KEYCLOAK_ISSUER=                ← e.g. https://<host>/keycloak/realms/grm
KEYCLOAK_CLIENT_ID=
```

---

## AUTH — Keycloak (superseded Cognito)

Officer auth runs on a self-hosted **Keycloak** realm (`grm`): PKCE OIDC login in
`channels/ticketing-ui`, JWT verification in `ticketing/auth/keycloak_jwt.py`,
invite flow (password-only setup email via realm SMTP), and an event webhook that
activates `officer_onboarding`. Full as-built guide: `docs/deployment/16_auth_keycloak.md`.

Account flow: admin creates officer in ticketing UI → ticketing calls the Keycloak
Admin API → Keycloak emails a set-password link → officer sets password. No console
access needed.
