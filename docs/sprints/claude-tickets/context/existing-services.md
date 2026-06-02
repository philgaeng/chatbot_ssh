# Existing Services — Reference Contracts
# Claude Code: READ ONLY. Never modify. Leave INTEGRATION POINT comments.
# Last updated: April 2026 — all decisions locked.

---

## 1. Backend Grievance API — Port 5001

Primary data source. Handles pgcrypto decryption of PII.
Never query `public.complainants` directly from ticketing.

**GET /api/grievance/{grievance_id}**
```json
{
  "grievance_id": "GRV-2024-001",
  "status": "UNDER_EVALUATION",
  "description": "...", "summary": "...",
  "categories": ["Environmental"],
  "location": "Birtamod, Ward 5",
  "sensitive_issue": false, "high_priority": false,
  "files": [{ "file_id": "uuid", "file_type": "image", "file_path": "..." }]
}
```

**POST /api/grievance/{grievance_id}/status**
```json
{ "status_code": "ESCALATED", "notes": "string|null", "created_by": "string" }
```

**GET /api/grievance/statuses**
→ SUBMITTED, UNDER_EVALUATION, ESCALATED, RESOLVED, DENIED, DISPUTED, CLOSED

---

## 2. Messaging API — Port 5001

Used by ticketing for:
- Complainant SMS fallback (when chatbot session expired)
- Quarterly report emails

**POST /api/messaging/send-sms**
```json
{
  "to": "+639XXXXXXXXX",
  "text": "Your grievance GRV-2024-001 has been escalated to Level 2. Link: https://...",
  "context": {
    "source_system": "ticketing",
    "purpose": "complainant_escalation_notice",
    "grievance_id": "GRV-2024-001",
    "ticket_id": "uuid"
  }
}
```
AWS SNS — works internationally (PH numbers confirmed for demo).
No PII in SMS text — links only.

**POST /api/messaging/send-email**
```json
{
  "to": ["officer@dor.gov.np"],
  "subject": "Q1 2026 GRM Quarterly Report",
  "html_body": "<p>...</p>",
  "context": { "source_system": "ticketing", "purpose": "quarterly_report" }
}
```

Auth: `x-api-key` header. Handle 429 with retry + backoff.

---

## 3. Orchestrator — Port ~8000

Used for officer → complainant replies via chatbot channel.

**POST /message**
```json
{
  "user_id": "session_id_from_ticket",
  "message_id": "optional-uuid",
  "text": "Your grievance has been escalated to Level 2. An investigator will contact you.",
  "payload": null,
  "channel": "ticketing"
}
```

`session_id` stored on `ticketing.tickets.session_id` at creation.
If POST /message errors (session expired) → fall back to send-sms.

---

## 4. Celery — Separate app for ticketing

Existing: `backend.task_queue.celery_app` — DO NOT ADD TO.

Ticketing app in `ticketing/tasks/__init__.py`:
```python
from celery import Celery
from celery.schedules import crontab

ticketing_celery = Celery(
    "grm_ticketing",           # distinct app name
    broker=settings.redis_url, # same Redis instance
    backend=settings.redis_url,
    include=[
        "ticketing.tasks.escalation",
        "ticketing.tasks.notifications",
        "ticketing.tasks.reports",
    ]
)

ticketing_celery.conf.beat_schedule = {
    "grm-sla-watchdog": {
        "task": "ticketing.tasks.escalation.sla_watchdog",
        "schedule": 900.0,  # every 15 min
    },
    # Quarterly report schedule set via admin settings — not hard-coded here
}
```

---

## 5. Database — Postgres (grievance_db)

**Check .env for:** POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT

### Existing tables (READ ONLY — never query from ticketing):
```
public.grievances       grievance_id VARCHAR(50) PK, session_id VARCHAR(255)
public.complainants     PII as BYTEA (pgcrypto encrypted) — never touch
public.file_attachments file_id VARCHAR(50) PK, grievance_id FK, file_path TEXT
public.office_management, public.office_municipality_ward, public.office_user
```

### Schema setup (run once):
```sql
CREATE SCHEMA IF NOT EXISTS ticketing;
```

### SQLAlchemy model pattern:
```python
class AnyModel(Base):
    __tablename__ = "table_name"
    __table_args__ = {"schema": "ticketing"}  # REQUIRED
    grievance_id = Column(String(64))   # NO FK — string ref only
    complainant_id = Column(String(64)) # NO FK — string ref only
```

### Alembic env.py (REQUIRED):
```python
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        return object.schema == "ticketing"
    return True

# In configure():
context.configure(
    ...,
    include_object=include_object,
    include_schemas=True,
    version_table_schema="ticketing",
)
```

---

## 6. File Storage

Existing chatbot files: `uploads/` on server filesystem.
Served via: `GET /files/{grievance_id}`, `GET /download/{file_id}`

Officer-uploaded files (proto):
- Path: `uploads/ticketing/{ticket_id}/`
- Post-proto: migrate to S3

---

## 7. Cognito — GRM pool (separate from Stratcon)

New pool. Stored in env:
```
COGNITO_GRM_USER_POOL_ID
COGNITO_GRM_CLIENT_ID
COGNITO_GRM_REGION
```

Account creation: admin UI → ticketing calls Cognito AdminCreateUser API → Cognito sends email.
JWT validation middleware in `ticketing/api/main.py`.

Initial users: philgaeng@pm.me, philgaeng@gmail.com, philgaeng@stratcon.ph,
philippe@gaeng.fr, philgaeng@soriano.ph,
susen@adb.org, rmascarinas@adb.org, jlang@adb.org, skhadka@adb.org

---

## 8. Stratcon — Reference only (never fork/merge)

**Live:** https://stratcon.facets-ai.com
**Login:** philippe@stratcon.ph / 0bPwPstU9sJnYTBQr2f*
**Repo:** https://github.com/philgaeng/stratcon
**Stack:** Next.js 16, TypeScript, Tailwind CSS v4, Cognito OIDC, FastAPI + SQLite

Cursor reads Stratcon and manually copies into `channels/ticketing-ui/`:
- Cognito OIDC auth middleware and route guards
- Role-based access pattern
- Settings page shell
- User management + invite flow (Cognito AdminCreateUser)
- Sidebar layout structure

New screens built from scratch: ticket queue, case detail, timeline, SLA countdown, notification badge.

---

## 9. Ticket Creation Payload (chatbot → ticketing)

```json
POST /api/v1/tickets
{
  "grievance_id": "GRV-2024-001",       ← string ref, no FK
  "complainant_id": "123",               ← string ref, no FK
  "session_id": "rasa_session_xyz",      ← CRITICAL: for POST /message replies
  "chatbot_id": "nepal_grievance_bot",
  "organization_id": "dor_kl_road",
  "location_code": "PROVINCE_1",
  "project_code": "KL_ROAD",
  "workflow_type": "standard",           ← "standard" or "seah"
  "priority": "NORMAL",
  "grievance_summary": "Dust from road, children sick",    ← cached non-PII
  "grievance_categories": ["Environmental", "Health"],     ← cached non-PII
  "grievance_location": "Birtamod, Ward 5"                 ← cached non-PII
}

Response: { "ticket_id": "uuid", "status": "OPEN", "created_at": "ISO8601" }
```

---

## 10. Environment Variables

Already in .env (reuse, never duplicate):
```
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
AWS_REGION
```

New (append to .env):
```env
TICKETING_PORT=5002
TICKETING_SECRET_KEY=
MESSAGING_API_KEY=
BACKEND_GRIEVANCE_BASE_URL=http://localhost:5001
ORCHESTRATOR_BASE_URL=http://localhost:8000
COGNITO_GRM_USER_POOL_ID=
COGNITO_GRM_CLIENT_ID=
COGNITO_GRM_REGION=
```

---

## SECTION H — New Questions from Session 0 Codebase Analysis

*Added: 2026-04-20. Resolve before or during Session 1.*

### H.1 Which Postgres user creates the `ticketing` schema?

`POSTGRES_USER` defaults to `nepal_grievance_admin`. Alembic needs `CREATE SCHEMA`
privilege. Recommended: add this guard to `ticketing/migrations/env.py` inside
`run_migrations_online()` before `context.run_migrations()`:

```python
with connection.begin():
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS ticketing"))
```

If `nepal_grievance_admin` lacks this privilege, run once as superuser:
```sql
CREATE SCHEMA IF NOT EXISTS ticketing AUTHORIZATION nepal_grievance_admin;
```

**Decision needed:** Does `nepal_grievance_admin` have CREATE SCHEMA privilege on `grievance_db`?

---

### H.2 Missing packages — add to `requirements.grm.txt`

```
pydantic-settings>=2.0        # ticketing/config/settings.py
alembic>=1.13                 # ticketing/migrations/
openpyxl>=3.1                 # quarterly XLSX reports
python-jose[cryptography]>=3.3 # Cognito JWT token validation
```

`httpx`, `SQLAlchemy`, `celery` already in `requirements.txt`.

---

### H.3 Celery Beat — separate Docker service?

SLA watchdog runs every 15 min via Celery Beat. Separate `grm_celery_beat` service
in `docker-compose.override.yml` is recommended (running Beat inside a worker is
deprecated for production). **Confirm.**

---

### H.4 Redis DB index for GRM Celery

Current allocation: DB0=SocketIO, DB1=Celery broker, DB2=Celery results.
GRM Celery reuses same `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` env vars —
queue isolation is by name (`grm_default`, `grm_escalation`). No DB conflict.
**Confirm this is acceptable, or assign GRM its own DBs (3 and 4).**

---

### H.5 Cognito GRM pool — already created?

`COGNITO_GRM_USER_POOL_ID/CLIENT_ID/REGION` needed. Auth can be stubbed in Sessions
1–2 and wired in Session 3. **Confirm pool exists or confirm stub-first approach.**

---

### H.6 Officer notifications — `seen` flag vs separate table

Badge count = unread tickets. Two options:

- **Option A (recommended for proto):** Add `seen BOOLEAN DEFAULT FALSE` to
  `ticketing.ticket_events`. Badge = `COUNT(*) WHERE assigned_to = user AND seen = FALSE`.
- **Option B (post-proto):** Separate `ticketing.notifications` table for SSE upgrade.

**Confirm Option A.**

---

### H.7 Additional columns needed in `ticketing.tickets` (missing from schema spec)

Will be added in Session 1 Alembic migration:

| Column | Type | Reason |
|---|---|---|
| `session_id` | `VARCHAR(255)` | Complainant notification via orchestrator |
| `grievance_summary` | `TEXT` | Cached non-PII at creation (CLAUDE.md rule 4) |
| `grievance_categories` | `TEXT` | Cached non-PII at creation |
| `grievance_location` | `TEXT` | Cached non-PII at creation |
| `is_seah` | `BOOLEAN DEFAULT FALSE` | DB-level SEAH visibility filtering |
