# Existing Services — Context for GRM Ticketing

This file documents the existing Nepal chatbot services that the ticketing system
integrates with. Updated after each analysis session.

---

## SECTION H — New Questions from Session 0 Codebase Analysis

*Added: 2026-04-20. These must be resolved before or during Session 1.*

### H.1 Which Postgres user creates the `ticketing` schema?

The existing DB user is `nepal_grievance_admin` (from `POSTGRES_USER` env var /
`backend/config/constants.py` default). Alembic needs to create the `ticketing`
schema before running migrations. This requires `CREATE SCHEMA` privilege.

**Recommended action:** Add the following guard to `ticketing/migrations/env.py`
inside `run_migrations_online()` before `context.run_migrations()`:

```python
with connection.begin():
    connection.execute(text(
        "CREATE SCHEMA IF NOT EXISTS ticketing"
    ))
```

If `nepal_grievance_admin` lacks this privilege, run once as superuser:
```sql
CREATE SCHEMA IF NOT EXISTS ticketing AUTHORIZATION nepal_grievance_admin;
```

**Decision needed from Philippe:** Does `nepal_grievance_admin` have CREATE SCHEMA
privilege on `grievance_db`? (Check with `\du` in psql.)

---

### H.2 `pydantic-settings` and other missing packages

The following packages are needed by ticketing but are NOT in `requirements.txt`.
Add to `requirements.grm.txt`:

```
pydantic-settings>=2.0        # ticketing/config/settings.py
alembic>=1.13                 # ticketing/migrations/
openpyxl>=3.1                 # quarterly XLSX reports
python-jose[cryptography]>=3.3 # Cognito JWT token validation
```

`httpx` is already in `requirements.txt`. `SQLAlchemy` and `celery` are already
in `requirements.txt`. No conflicts expected.

---

### H.3 Celery Beat — separate Docker service or shared worker process?

The SLA watchdog (`check_sla_breaches`) runs every 15 min via Celery Beat.
Running Beat inside a worker process (`--beat` flag) is deprecated and unreliable
for production. Recommended: add a dedicated `grm_celery_beat` service to
`docker-compose.override.yml`.

**Decision needed:** Confirm separate Beat service is acceptable.

---

### H.4 Redis DB index for GRM Celery

Existing Redis DB allocation:
- DB 0: Socket.IO (`SOCKETIO_REDIS_URL`)
- DB 1: Celery broker (`CELERY_BROKER_URL` → `redis://…/1`)
- DB 2: Celery results (`CELERY_RESULT_BACKEND` → `redis://…/2`)

GRM Celery will reuse the same `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`
env vars. Queue isolation is by name (`grm_default`, `grm_escalation` vs
`default`, `llm_queue`). No DB-level conflict expected.

**Decision needed:** Is shared broker/result DB acceptable, or assign GRM its
own DBs (3 and 4) for extra isolation?

---

### H.5 Cognito GRM pool — already created?

CLAUDE.md lists `COGNITO_GRM_USER_POOL_ID`, `COGNITO_GRM_CLIENT_ID`, and
`COGNITO_GRM_REGION` as required env vars. The pool must be separate from Stratcon.

**Decision needed:** Has this pool been created in AWS? If not, auth can be stubbed
in Sessions 1–2 and wired in Session 3. Confirm.

---

### H.6 `ticketing.notifications` table vs `seen` flag on `ticket_events`

CLAUDE.md officer notifications = badge count on queue page, refreshes on navigation.
Two implementation options:

**Option A** — `seen BOOLEAN DEFAULT FALSE` column added to `ticketing.ticket_events`.
Badge count = `COUNT(*) WHERE assigned_to = current_user AND seen = FALSE`.
Simple; no extra table.

**Option B** — Separate `ticketing.notifications` table with one row per
(user, ticket, event). More flexible for future SSE upgrade.

**Recommendation:** Option A for proto (simpler). Option B in post-proto SSE upgrade.

**Decision needed:** Confirm Option A.

---

### H.7 Additional columns needed in `ticketing.tickets` (not in schema spec)

The following columns are in CLAUDE.md but missing from `04_ticketing_schema.md`.
Will be added in Session 1 Alembic migration:

| Column | Type | Reason |
|---|---|---|
| `session_id` | `VARCHAR(255)` | Complainant notification via orchestrator |
| `grievance_summary` | `TEXT` | Cached at creation (CLAUDE.md rule 4) |
| `grievance_categories` | `TEXT` | Cached at creation (CLAUDE.md rule 4) |
| `grievance_location` | `TEXT` | Cached at creation (CLAUDE.md rule 4) |
| `is_seah` | `BOOLEAN DEFAULT FALSE` | DB-level filtering for SEAH visibility |

---
