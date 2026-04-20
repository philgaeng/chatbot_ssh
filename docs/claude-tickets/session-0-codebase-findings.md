# Session 0 — Codebase Findings
# Generated: 2026-04-20 | Branch: feature/grm-ticketing
# Read-only analysis. No code was modified.

---

## 1. FastAPI Patterns

### 1.1 Router structure and prefix conventions

The existing backend (`backend/api/fastapi_app.py`) creates a plain `FastAPI()` app
and includes routers **without any prefix** — all routers self-declare their full paths:

```python
# fastapi_app.py
from backend.api.routers import grievance, files, voice_grievance, gsheet, messaging

app.include_router(grievance.router)    # paths: /api/grievance/...
app.include_router(files.router)         # paths: /, /upload-files, /files/..., etc.
app.include_router(voice_grievance.router)
app.include_router(gsheet.router)
app.include_router(messaging.router)     # paths: /api/messaging/...
```

Each router file does `router = APIRouter()` (no prefix, no tags). Paths are hard-coded
in each `@router.get(...)` / `@router.post(...)` decorator.

**Pattern to use in ticketing:** same approach — `APIRouter()` with no prefix, full paths
declared in each router file. Group under `/api/v1/tickets/`, `/api/v1/workflows/`, etc.

### 1.2 App entry point pattern

```python
# Copy this pattern for ticketing/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def _lifespan(app: FastAPI):
    # startup work here
    yield

app = FastAPI(title="Ticketing API", version="0.1.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
```

### 1.3 Authentication / middleware

- **Existing backend has NO JWT auth middleware on any route.** The messaging router
  has a `_auth_check` dependency that checks `x-api-key` header but the `expected` key
  is hardcoded to `None`, making it effectively open.
- Pattern for the `x-api-key` check (copy into ticketing for inter-service calls):

```python
# backend/api/routers/messaging.py — copy this pattern
from fastapi import Depends, Header, HTTPException, status

def _auth_check(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("MESSAGING_API_KEY")  # currently None = disabled
    if expected and x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "FAILED", "error_code": "UNAUTHORIZED", "error": "Invalid API key"},
        )

@router.post("/api/v1/tickets", ...)
def create_ticket(..., _auth: None = Depends(_auth_check)):
    ...
```

For Cognito JWT validation (officer UI calls), ticketing will need its own dependency —
there is **no existing Cognito middleware** in this repo to copy from.

### 1.4 Pydantic response model patterns

- All Pydantic models are **inline in router files** — there is no separate `schemas/` folder.
- Named simply: `UpdateStatusBody`, `SendSmsRequest`, `MessagingResponse`, etc.
- Pydantic v2 is installed (`pydantic>=2.0`); use v2 syntax in ticketing.
- Envelope response shape used by existing API:

```python
# Success
{"status": "SUCCESS", "message": "...", "data": {...}}
# Error (JSONResponse)
{"status": "ERROR", "message": "Internal server error: ..."}
```

For ticketing, CLAUDE.md does not prescribe this envelope; use clean Pydantic response
models with HTTP status codes per REST convention.

---

## 2. Database Connection Pattern

### 2.1 Existing pattern — psycopg2 (NOT SQLAlchemy ORM)

**Critical finding:** The existing codebase uses **raw psycopg2**, not SQLAlchemy ORM.
`BaseDatabaseManager` in `backend/services/database_services/base_manager.py` manages
connections directly:

```python
# backend/services/database_services/base_manager.py

import psycopg2
from psycopg2.extras import DictCursor
from backend.config.constants import DB_CONFIG

class BaseDatabaseManager:
    def __init__(self, ...):
        self.db_params = DB_CONFIG.copy()   # dict of host/port/db/user/password

    @contextmanager
    def get_connection(self):
        conn = psycopg2.connect(**self.db_params, cursor_factory=DictCursor)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
```

`DB_CONFIG` is assembled in `backend/config/constants.py` from env vars:

```python
DB_CONFIG = {
    'host':     os.getenv('POSTGRES_HOST', 'localhost'),
    'database': os.getenv('POSTGRES_DB', 'grievance_db'),
    'user':     os.getenv('POSTGRES_USER', 'nepal_grievance_admin'),
    'password': os.getenv('POSTGRES_PASSWORD', 'K9!mP2$vL5nX8&qR4jW7'),
    'port':     os.getenv('POSTGRES_PORT', '5432'),
}
```

**Important:** `POSTGRES_DB` default is `grievance_db` — this is the real database name
(NOT `app_db` from docker-compose.yml, which uses placeholder credentials).

### 2.2 SQLAlchemy for ticketing

CLAUDE.md mandates SQLAlchemy + Alembic for the ticketing schema. SQLAlchemy 2.x is
already installed (`SQLAlchemy>=2.0.36` in requirements.txt).

**Ticketing must create its own engine using the same env vars:**

```python
# ticketing/config/settings.py — pattern to implement
from pydantic_settings import BaseSettings

class TicketingSettings(BaseSettings):
    # Reuse existing DB env vars — same Postgres instance
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "grievance_db"
    postgres_user: str = "nepal_grievance_admin"
    postgres_password: str = ""

    # Build SQLAlchemy URL from parts (avoids DATABASE_URL conflict — see §4)
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = "env.local"
```

**SQLAlchemy engine + session factory pattern for ticketing:**

```python
# ticketing/models/base.py
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from ticketing.config.settings import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**All models must use:**

```python
__table_args__ = {"schema": "ticketing"}
```

### 2.3 Alembic — no existing setup

There is **no alembic.ini or migrations/ directory** in this repo. Ticketing will be
the first Alembic migration setup. Create fresh at `ticketing/migrations/`.

Required Alembic `env.py` pattern (from CLAUDE.md):

```python
# ticketing/migrations/env.py — must include both of these
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        return object.schema == "ticketing"
    return True

# In run_migrations_online() context.configure():
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_schemas=True,
    include_object=include_object,
    version_table_schema="ticketing",   # stores alembic_version in ticketing schema
)
```

Each migration must start with:

```python
# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
```

---

## 3. Celery Configuration

### 3.1 Existing Celery setup

```python
# backend/task_queue/celery_app.py
from celery import Celery
celery_app = Celery('task_queue')   # app name = QUEUE_FOLDER = 'task_queue'

celery_app.conf.update(
    broker_url=CELERY_BROKER_URL,       # env: CELERY_BROKER_URL, default: redis://localhost:6379/1
    result_backend=CELERY_RESULT_BACKEND, # env: CELERY_RESULT_BACKEND, default: redis://localhost:6379/2
    task_serializer='json',
    task_default_queue='default',
    task_queues=(
        Queue('llm_queue', ...),
        Queue('default', ...),
    ),
    ...
)
```

Workers are launched as:
```bash
celery -A backend.task_queue.celery_app worker -Q default --concurrency=2
celery -A backend.task_queue.celery_app worker -Q llm_queue --concurrency=6
```

### 3.2 Ticketing Celery app

CLAUDE.md requires a **separate Celery app** named `"grm_ticketing"`. This avoids
task name collisions with the existing `task_queue` workers. Pattern:

```python
# ticketing/tasks/__init__.py
from celery import Celery
from ticketing.config.settings import get_settings

settings = get_settings()
celery_app = Celery(
    "grm_ticketing",
    broker=settings.celery_broker_url,    # same CELERY_BROKER_URL env var
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_default_queue="grm_default",
    task_queues=(
        Queue("grm_default", ...),
        Queue("grm_escalation", ...),   # for SLA watchdog
    ),
)
```

Worker launch (add to docker-compose.override.yml):
```bash
celery -A ticketing.tasks celery_app worker -Q grm_default,grm_escalation \
    --loglevel=info --concurrency=2
```

### 3.3 SLA watchdog (Celery Beat)

The escalation watchdog runs every 15 min. Use Celery Beat:

```python
# ticketing/tasks/__init__.py
celery_app.conf.beat_schedule = {
    "sla-watchdog": {
        "task": "ticketing.tasks.escalation.check_sla_breaches",
        "schedule": 900,  # 15 minutes in seconds
    }
}
```

---

## 4. Env Var Inventory

### 4.1 All env vars used in existing codebase

| Env var | Where used | Ticketing can reuse? |
|---|---|---|
| `POSTGRES_HOST` | `backend/config/constants.py` DB_CONFIG | ✅ YES — same Postgres instance |
| `POSTGRES_PORT` | `backend/config/constants.py` DB_CONFIG | ✅ YES |
| `POSTGRES_DB` | `backend/config/constants.py` DB_CONFIG | ✅ YES — same DB (`grievance_db`) |
| `POSTGRES_USER` | `backend/config/constants.py` DB_CONFIG | ✅ YES |
| `POSTGRES_PASSWORD` | `backend/config/constants.py` DB_CONFIG | ✅ YES |
| `DATABASE_URL` | docker-compose.yml (passed but not read by Python code) | ⚠️ NOT used by Python — safe to leave, but do NOT use as ticketing DB URL var to avoid confusion |
| `REDIS_HOST` | `backend/config/constants.py`, `task_queue/settings.py` | ✅ YES |
| `REDIS_PORT` | same | ✅ YES |
| `REDIS_DB` | same | ✅ YES |
| `REDIS_PASSWORD` | same | ✅ YES |
| `CELERY_BROKER_URL` | `task_queue/settings.py` | ✅ YES — reuse directly |
| `CELERY_RESULT_BACKEND` | `task_queue/settings.py` | ✅ YES — reuse directly |
| `SOCKETIO_REDIS_URL` | `backend/api/websocket_fastapi.py` | ❌ not needed by ticketing |
| `OPENAI_API_KEY` | `backend/services/LLM_services.py` | ❌ not needed for proto |
| `OPENAI_CLASSIFICATION_TIMEOUT` | `backend/services/LLM_services.py` | ❌ not needed |
| `AWS_ACCESS_KEY_ID` | `backend/services/messaging.py` | ❌ ticketing uses Messaging API, not direct boto3 |
| `AWS_SECRET_ACCESS_KEY` | `backend/services/messaging.py` | ❌ same |
| `SES_VERIFIED_EMAIL` | `backend/services/messaging.py` | ❌ same |
| `AWS_REGION` | (implied by boto3) | ❌ ticketing uses Messaging API |
| `SMTP_SERVER/PORT/USERNAME/PASSWORD` | `backend/config/constants.py` | ❌ not needed |
| `FLASK_URL` | docker-compose.yml → Celery tasks (calls backend) | ❌ ticketing uses its own `BACKEND_GRIEVANCE_BASE_URL` |
| `BACKEND_HTTP_URL` | `backend/config/constants.py` | ❌ ticketing uses `BACKEND_GRIEVANCE_BASE_URL` |
| `GSHEET_BEARER_TOKEN` | `backend/api/gsheet_monitoring_api.py` | ❌ not needed |
| `UPLOAD_FOLDER` | `backend/api/app.py` | ❌ ticketing uses `uploads/ticketing/{ticket_id}/` |
| `ENABLE_CELERY_CLASSIFICATION` | `backend/orchestrator/main.py` | ❌ not needed |
| `ENABLE_SEAH_DEDICATED_FLOW` | `backend/actions/generic_actions.py` | ❌ not needed |
| `ORCHESTRATOR_LOG_LEVEL` | `backend/orchestrator/main.py` | ❌ not needed |
| `GRM_MYSQL_*` | `backend/config/grm_config.py` | ❌ legacy MySQL integration, ignore |
| `DB_ENCRYPTION_KEY` | `backend/services/database_services/base_manager.py` | ❌ ticketing does not store PII |
| `MESSAGING_API_KEY` | `backend/api/routers/messaging.py` (currently unused) | ✅ YES — ticketing will read this to call Messaging API |

### 4.2 New env vars needed by ticketing (from CLAUDE.md — do NOT conflict)

```env
TICKETING_PORT=5002
TICKETING_SECRET_KEY=          # for signing (JWT or session tokens)
MESSAGING_API_KEY=             # existing var, now actually used by ticketing
BACKEND_GRIEVANCE_BASE_URL=http://localhost:5001
ORCHESTRATOR_BASE_URL=http://localhost:8000
COGNITO_GRM_USER_POOL_ID=
COGNITO_GRM_CLIENT_ID=
COGNITO_GRM_REGION=
```

---

## 5. Conventions to Match

### 5.1 Import style

- **Absolute imports only** throughout the codebase: `from backend.api.routers import ...`
- `sys.path.insert(0, str(_REPO_ROOT))` is added at FastAPI app entry points to make
  `backend.*` imports work when running with `uvicorn backend.api.fastapi_app:app`.
- Ticketing should do the same at `ticketing/api/main.py`:

```python
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
```

### 5.2 Error handling patterns

Existing routers use two patterns:

**Pattern A — try/except returning JSONResponse (grievance, files routers):**
```python
try:
    result = do_something()
    return {"status": "SUCCESS", "data": result}
except Exception as e:
    print(f"Error: {str(e)}")
    return JSONResponse(status_code=500,
        content={"status": "ERROR", "message": f"Internal server error: {str(e)}"})
```

**Pattern B — try/except raising HTTPException (messaging router):**
```python
except Exception as exc:
    logger.exception("Unexpected error: %s", exc)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"status": "FAILED", "error_code": "INTERNAL_ERROR", "error": str(exc)},
    )
```

**Recommendation for ticketing:** Use Pattern B (HTTPException) — cleaner with
Pydantic response models. The global exception handler in fastapi_app.py will catch
anything that leaks through.

### 5.3 Logging setup

Entry points use `logging.basicConfig(...)` with a standard format:

```python
# Pattern to copy — from backend/orchestrator/main.py
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
# Suppress noisy third-party loggers
for name in ("botocore", "boto3", "urllib3", "s3transfer"):
    logging.getLogger(name).setLevel(logging.WARNING)
```

Individual modules get loggers via `logging.getLogger(__name__)`. The `TaskLogger`
wrapper class in `backend/logger/logger.py` provides a structured logger with
`service_name` — optionally reuse this in ticketing for consistency.

### 5.4 Shared utilities ticketing should use

| Utility | Location | Use |
|---|---|---|
| `TaskLogger` | `backend/logger/logger.py` | Structured logging (optional but consistent) |
| `DB_CONFIG` | `backend/config/constants.py` | ⚠️ Do NOT import — ticketing uses SQLAlchemy + pydantic-settings, not this dict |
| `Messaging` service | `backend/services/messaging.py` | ❌ Do NOT call directly — use HTTP `POST /api/messaging/send-*` |
| `load_dotenv` pattern | `backend/api/fastapi_app.py` lines 27-39 | ✅ Copy for env.local loading at ticketing startup |

---

## 6. Gaps and Conflicts

### 6.1 Database name mismatch: docker-compose vs real env

`docker-compose.yml` uses placeholder `app_db` but `backend/config/constants.py`
defaults to `grievance_db`. The real database is `grievance_db`. Ticketing must
connect to `grievance_db` (via `POSTGRES_DB` env var), NOT `app_db`.

### 6.2 No existing Cognito auth middleware

CLAUDE.md assumes ticketing will use AWS Cognito OIDC for officer authentication.
There is **no existing Cognito JWT validation middleware** in this repo to copy.
Ticketing will need to implement its own `verify_cognito_token` FastAPI dependency
from scratch (or pull in `python-jose` / `authlib`).

### 6.3 `DATABASE_URL` env var is set but not used by Python

`docker-compose.yml` injects `DATABASE_URL=postgresql://user:password@db:5432/app_db`
into every container, but no Python code reads it. It's safe to ignore.
Ticketing should NOT use `DATABASE_URL` — compose its URL from the `POSTGRES_*` parts
to stay consistent with the existing pattern.

### 6.4 psycopg2-binary already installed — no asyncpg

`requirements.txt` has `psycopg2-binary==2.9.10`. SQLAlchemy can use this with
the sync `postgresql+psycopg2://` driver (no asyncpg needed). Ticketing routers
can be sync (def, not async def) for simplicity.

### 6.5 Celery Beat not running in docker-compose

Current docker-compose has no `celery_beat` service. Ticketing's SLA watchdog
(Celery Beat) needs a new service in `docker-compose.override.yml`:

```yaml
# docker-compose.override.yml — ADD this service
grm_celery_beat:
  build: ...
  command: celery -A ticketing.tasks.celery_app beat --loglevel=info
  env_file: [env.local]
  ...
```

### 6.6 SEAH table already exists in public.* schema

`backend/services/database_services/postgres_services.py` (`DatabaseManager`) has
`_ensure_seah_tables()` which creates `complainants_seah` and `grievances_seah` in the
`public` schema. The ticketing SEAH workflow is separate — it lives in `ticketing.*`
and references grievances via `grievance_id` only. No conflict, but be aware these
tables exist.

### 6.7 `session_id` field not in current ticketing schema spec

CLAUDE.md (notifications section) says "Store `session_id` on ticket at creation —
critical for both notification paths." But `04_ticketing_schema.md` doesn't include
a `session_id` column in `ticketing.tickets`. **Add `session_id VARCHAR(255)` to
the tickets table in Session 1.**

### 6.8 `grievance_summary` / `grievance_categories` / `grievance_location` caching

CLAUDE.md says these are cached at ticket creation (non-PII). These fields are NOT
in the schema spec (`04_ticketing_schema.md`). **Add them to `ticketing.tickets`
in Session 1** as per CLAUDE.md §Database Architecture rule 4.

### 6.9 `chatbot_id` column — not needed for proto

`04_ticketing_schema.md` includes `chatbot_id VARCHAR(64)` (e.g. `'nepal_grievance_bot'`).
There is only one chatbot. Keep the field for multi-tenancy readiness but default it
to `'nepal_grievance_bot'`.

### 6.10 `is_seah` flag missing from tickets table

The schema spec has no SEAH distinguisher on `ticketing.tickets`. The SEAH workflow
is identified by which `workflow_id` is assigned, but for DB-level filtering
(SEAH invisible to standard officers) it is more efficient to have an explicit
`is_seah BOOLEAN DEFAULT FALSE` column. **Add this in Session 1.**

---

## 7. New Questions — SECTION H

The following questions were uncovered by codebase analysis and must be resolved
before or during Session 1. Also appended to `docs/claude-tickets/context/existing-services.md`.

### H.1 Which Postgres user creates the `ticketing` schema?

The `ticketing` schema must be created before Alembic runs. The existing user
(`POSTGRES_USER`, default `nepal_grievance_admin`) must have `CREATE SCHEMA` privilege
on `grievance_db`. **Decision:** Does `nepal_grievance_admin` have this? If not,
add a manual `CREATE SCHEMA IF NOT EXISTS ticketing AUTHORIZATION nepal_grievance_admin;`
to the Alembic `env.py` `run_migrations_online()` before the migration starts,
OR run it once manually. Recommend: add to Alembic `env.py` as a one-time guard.

### H.2 Do we add `pydantic-settings` to `requirements.grm.txt`?

CLAUDE.md says ticketing config uses `pydantic-settings`. This package is NOT in
`requirements.txt`. Add to `requirements.grm.txt`:
```
pydantic-settings>=2.0
alembic>=1.13
httpx>=0.28  # already in requirements.txt — skip
openpyxl>=3.1  # for XLSX reports
python-jose[cryptography]>=3.3  # for Cognito JWT validation
```

### H.3 Celery Beat process — separate Docker service or same worker?

Recommended: separate `grm_celery_beat` service in `docker-compose.override.yml`.
Running Beat and Worker in the same process is unreliable in production. Confirm.

### H.4 Which Redis DB index does the GRM Celery use?

Existing workers use:
- DB 0: Socket.IO (`SOCKETIO_REDIS_URL`)
- DB 1: Celery broker (`CELERY_BROKER_URL`)
- DB 2: Celery results (`CELERY_RESULT_BACKEND`)

GRM Celery will reuse DB 1 and DB 2 (same broker/backend env vars, different queue
names). No conflict because queues are isolated by name. Confirm this is acceptable,
or assign dedicated DBs (3 and 4) for GRM if queue isolation is preferred.

### H.5 Cognito pool — is it already created?

CLAUDE.md says `COGNITO_GRM_USER_POOL_ID` needs a new Cognito pool separate from
Stratcon. Has this pool been created in AWS yet? If not, Session 2 (API skeleton)
can stub auth; Session 3 can wire real Cognito. Confirm timeline.

### H.6 `ticketing.notifications` table — is it needed for proto?

CLAUDE.md says officer notifications are an in-app badge count that refreshes on
navigation (option C). This requires a `ticketing.notifications` table (unread count
per user) or a computed count from `ticket_events`. Recommend: computed count from
`ticket_events WHERE seen = FALSE AND assigned_to = current_user`. Add `seen BOOLEAN`
to `ticket_events`. **Confirm: should we add `seen` to ticket_events, or create a
separate notifications table?**

---

*End of Session 0 findings. Session 1 starts with `ticketing/` directory creation,
SQLAlchemy models, and Alembic migration for `ticketing.*` schema.*
