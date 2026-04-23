# CLAUDE.md — Nepal Chatbot / GRM Ticketing System

# Read this entire file before touching any code.

# ALL decisions locked through Round 2. Ready for Session 0 codebase analysis.

# DEMO DEADLINE: May 10, 2026

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

## HARD BOUNDARIES — READ BEFORE WRITING ANY CODE

### NEVER modify these:

```
backend/actions/           → DO NOT TOUCH
backend/orchestrator/      → DO NOT TOUCH
backend/api/               → DO NOT TOUCH
backend/services/          → DO NOT TOUCH
backend/task_queue/        → DO NOT TOUCH
channels/accessible/       → DO NOT TOUCH
channels/webchat/          → DO NOT TOUCH
channels/REST_webchat/     → DO NOT TOUCH
channels/monitoring-gsheet/→ DO NOT TOUCH
rasa_chatbot/              → DO NOT TOUCH
scripts/                   → DO NOT TOUCH
deployment/                → DO NOT TOUCH
docker-compose.yml         → DO NOT TOUCH
requirements.txt           → DO NOT TOUCH (use requirements.grm.txt)
.env / env.local           → DO NOT TOUCH
```

### New code lives ONLY in:

```
ticketing/                 → all new backend code
channels/ticketing-ui/     → all new frontend code (Next.js 16, Cursor handles)
requirements.grm.txt       → new Python dependencies only
```

### Integration points — leave comments, do NOT wire:

```python
# INTEGRATION POINT: backend/api/routers/messaging.py
# POST /api/messaging/send-sms  OR  POST /api/messaging/send-email
# Auth: x-api-key header
# To be wired by Cursor in WSL
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

**Grievance API** — primary data source, handles PII decryption:

```
GET  /api/grievance/{grievance_id}
POST /api/grievance/{grievance_id}/status
GET  /api/grievance/statuses
```

**Messaging API** — for complainant SMS fallback + quarterly reports:

```
POST /api/messaging/send-sms    → AWS SNS (works internationally)
POST /api/messaging/send-email  → AWS SES
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
  ├── public.*     ← existing tables — READ ONLY, never query directly from ticketing
  └── ticketing.*  ← all new tables, owned by ticketing system
```

### Data rules (LOCKED):

1. No SQL joins from `ticketing.*` into `public.*`
2. No foreign keys from `ticketing.*` into `public.*`
3. PII (name, phone, email, address) NEVER stored in `ticketing.*`
4. `ticketing.tickets` caches non-PII at creation: `grievance_summary`, `grievance_categories`, `grievance_location`, `priority`
5. Officer detail view fetches PII fresh via `GET /api/grievance/{id}`
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

### Migration traceability (two streams)

- **Ticketing (`ticketing.*`):** all forward DDL goes through **Alembic** (`ticketing/migrations/alembic.ini`). Any worktree (including Claude-only work on ticketing) should use **only** this stream for ticketing tables so revisions stay linear and visible in git.
- **Chatbot / public (`public.*`):** **not** migrated by the ticketing Alembic project (see headers and `include_object` above). Use the **second** Alembic project: `migrations/public/alembic.ini` (version table `alembic_version_public`). Some tables may still be **first-created** by app code; **structural changes** go in `migrations/public/versions/`. See **`docs/MIGRATIONS_POLICY.md`**.

### Worktree + DB operating model (LOCKED)

For parallel development across chatbot and ticketing worktrees:

1. **Keep worktrees separate**
   - `feature/seah` (chatbot-focused work)
   - `feature/grm-ticketing` (ticketing/admin work)
   - integration worktree/branch for merge validation before promoting to `main`

2. **Use isolated local DB instances per worktree**
   - One Postgres container/volume per worktree (different host ports)
   - Never share one mutable local DB across active feature worktrees
   - Purpose: avoid migration collisions and branch-state contamination

3. **Schema ownership must be explicit**
   - `ticketing.*` schema is owned by ticketing migrations (`ticketing/migrations/alembic.ini`)
   - Existing chatbot/public schema remains owned by chatbot/backend migration path
   - Do not let two migration streams own DDL for the same table

4. **Shared admin domain rule (projects/locations/settings)**
   - Ticketing is the admin UI/backend, but shared entities must have a single schema owner
   - Ticketing should integrate via stable service/API boundaries for chatbot-consumed data
   - Avoid direct cross-domain schema edits without ownership agreement

5. **Integration branch requirements**
   - Merge feature branches in integration worktree first
   - Run migrations in deterministic order and verify both chatbot + ticketing paths
   - Promote to `main` only after integration DB + smoke tests pass

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
TypeScript, Tailwind CSS v4, AWS Cognito OIDC.

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
requirements.grm.txt
docs/
  claude-tickets/       ← Claude Code session files (this file lives here)
    CLAUDE.md           ← also at repo root
    open-questions-round-2.md
    session-0-codebase-findings.md  ← generated by Session 0
    context/
      grm-specification.md
      existing-services.md
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
- Commit strategy: `docs/COMMIT_STRATEGY.md`

---

## ENVIRONMENT VARIABLES (append to .env)

```env
TICKETING_PORT=5002
TICKETING_SECRET_KEY=           ← python -c "import secrets; print(secrets.token_urlsafe(32))"
MESSAGING_API_KEY=              ← from existing backend config
BACKEND_GRIEVANCE_BASE_URL=http://localhost:5001
ORCHESTRATOR_BASE_URL=http://localhost:8000
COGNITO_GRM_USER_POOL_ID=       ← new pool (separate from Stratcon)
COGNITO_GRM_CLIENT_ID=
COGNITO_GRM_REGION=             ← same as existing AWS_REGION
```

---

## COGNITO — GRM pool (separate from Stratcon)

Initial users:
philgaeng@pm.me, philgaeng@gmail.com, philgaeng@stratcon.ph,
philippe@gaeng.fr, philgaeng@soriano.ph,
susen@adb.org, rmascarinas@adb.org, jlang@adb.org, skhadka@adb.org

Account flow: admin creates in ticketing UI → ticketing calls Cognito invite API
→ Cognito sends email → officer sets password. No console access needed.
