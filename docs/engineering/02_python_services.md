# Python & the service layer

**Status:** authoritative (2026-08-03). How Python code in this repo is organised, and why.
**Applies to:** `ticketing/`, `backend/`, `ops/`, `scripts/`. Language is **Python 3.11+**, typed, Pydantic v2.
**Reads with:** [03 — API layer](03_api_layer.md) (the entrypoint half of the pattern) and [`CLAUDE.md`](../../CLAUDE.md) "SERVICE BOUNDARIES".

---

## 1. The architecture, named

The pattern is **a thin entrypoint over a fat service layer, with a shared kernel between independent services.** Three named patterns compose into it, and it is worth knowing which is which, because they answer different objections:

| Layer | Pattern | Rule it gives you |
|---|---|---|
| The entrypoint (router / Celery task / CLI) | **Humble Object** (Meszaros) | The thing that is hard to test — HTTP, the broker, `argv` — holds *no* logic worth testing. |
| The logic (`services/`, `engine/`) | **Service Layer** (Fowler, *PoEAA*) | One plain Python function per use case: takes a session and typed arguments, returns typed data, raises typed errors. Framework-free. |
| Between services (`backend/` ↔ `ticketing/` ↔ `ops/`) | **Shared Kernel** (Evans, *DDD*) | Genuinely common logic lives in one module that all three import; **domain** logic never crosses — it goes over the documented HTTP contract instead. |

Said in one sentence, which is the version to remember:

> **Each service keeps only its own orchestration; everything else is a call into a shared, testable function — and nothing framework-shaped ever sits between them.**

**Why this and not "just put it in the router":** every use case in this system has at least four callers — an HTTP route, a Celery task, a seed script, and a test. Logic in a router is reachable only by HTTP, so the task re-implements it, and the two drift. The escalation engine is the proof: `engine/escalation.py` is called by the SLA watchdog *and* by the manual "Escalate" button, and they must not be able to disagree.

### What goes where

```
ticketing/
  api/           ← ENTRYPOINT. FastAPI routers + Pydantic schemas. No logic. → doc 03
  tasks/         ← ENTRYPOINT. Celery tasks. No logic.
  seed/          ← ENTRYPOINT. CLI modules. No logic.
  engine/        ← LOGIC (stateful domain): workflow_engine, escalation, ticket_actions, events
  services/      ← LOGIC (use cases): one module per capability, plain functions
  clients/       ← EGRESS: HTTP to backend/orchestrator/messaging. No domain logic.
  models/        ← SQLAlchemy models. Shape only.
  constants/     ← Enum values, role keys, fixed maps. No behaviour.
  utils/         ← Pure, dependency-free helpers. If it imports a model, it is a service.
  config/        ← pydantic-settings. The only place env vars are read.
```

**`engine/` vs `services/`:** `engine/` owns the *ticket lifecycle* — the state machine, escalation, event emission. `services/` owns everything else. When in doubt: does it move a ticket between states? Engine. Otherwise service.

---

## 2. Entrypoints hold no logic

**Rule 2.1 — A router, a task, and a CLI do exactly three things:** deserialize input, call **one** service function, shape the output. If an entrypoint has a branch on domain state, that branch belongs in a service.

**Rule 2.2 — Anything an entrypoint can do, a test can do without the framework.** The test for a use case imports the service function directly. It does not spin up FastAPI or Celery. If your test needs `TestClient` to reach the logic, the logic is in the wrong place.

**Rule 2.3 — Celery tasks are wrappers, and are thin for a second reason:** retries. A task that holds logic re-runs that logic on every retry. A task that calls one idempotent service function is safe to retry.

```python
# ticketing/tasks/escalation.py — the shape
@celery.task(name="ticketing.sla_watchdog")
def sla_watchdog() -> dict:
    db = SessionLocal()
    try:
        result = escalation.escalate_breached(db)   # ← all logic lives here
        db.commit()
        return {"escalated": len(result)}
    finally:
        db.close()
```

---

## 3. Writing a service function

**Rule 3.1 — The signature is `(db: Session, ...typed args) -> typed result`.** `db` first, always. Keyword-only for anything optional.

**Rule 3.2 — Full type hints, no bare `dict`/`Any` in a public signature.** Return a `@dataclass` or a Pydantic model, not a dict. A dict return is an undocumented contract that breaks silently.
*Existing exemplar:* `services/project_go_live.py` returns `GoLiveCheck` dataclasses with `Literal` statuses — copy that shape.

**Rule 3.3 — One module per capability, named after the capability, not the layer.** `officer_jurisdiction.py`, `project_go_live.py`, `archiving.py`. Never `helpers.py`, `utils.py`, `common.py`, `manager.py`.
*Why:* `helpers.py` has no boundary, so it accretes until it imports everything and can be imported by nothing.

**Rule 3.4 — Public surface first, private helpers below, prefixed `_`.** A reader should learn what the module offers from the top 30 lines.

**Rule 3.5 — Services do not know about HTTP.** No `HTTPException`, no `Request`, no status codes, no `fastapi` import. Raise a domain error (§5); the router maps it.
*Why:* this is what makes the same function callable from a Celery task and a seed script.

**Rule 3.6 — Services do not read env vars.** Take configuration as an argument, or read it from `config/settings.py` at the entrypoint and pass it down. `get_settings()` inside a deep service function is an untestable hidden input.

**Rule 3.7 — Keep function length under ~50 lines and nesting under 3.** Past that, name the inner block and extract it. This is a readability floor, not a metric to game.

**Rule 3.8 — Prefer pure functions.** A function that takes data and returns data — no session, no I/O — is the cheapest thing in the codebase to test and reuse. Push the pure part out of the impure one whenever you can name it.

---

## 4. Transactions

**Rule 4.1 — The caller owns the transaction. Service functions never `commit()`.** They may `flush()` when they need a generated ID.

*Why:* a router that calls three services must be able to make all three succeed or all three fail. If service #2 commits, service #3's failure leaves the database in a state no code path intended — and no test will catch it, because each service passes in isolation.

*Corollary:* a service that "needs" to commit is telling you it is really two use cases. Split it, and let the caller sequence them.

**Rule 4.2 — Rollback is the framework's job**, not a `try/except` in every service. `get_db()` closes the session; the router's error handler rolls back.

**Known deviation:** 18 sites in `ticketing/services/` still commit (`grep -rn "\.commit()" ticketing/services/`). Do not add more; unwind opportunistically.

---

## 5. Errors

**Rule 5.1 — Domain errors are typed exceptions defined near their service**, subclassing a small shared base. Not `ValueError`, not `Exception`, not a `(ok, msg)` tuple.

```python
class TicketError(Exception): ...
class TicketNotFound(TicketError): ...
class InvalidTransition(TicketError):
    def __init__(self, frm: str, to: str): ...
```

**Rule 5.2 — The router maps domain error → HTTP status**, in one place per router. → [03 §5](03_api_layer.md#5-errors)

**Rule 5.3 — Never swallow an exception.** `except Exception: pass` is forbidden. If a failure is genuinely tolerable, catch the *specific* type, log at `warning` with context, and say in a comment why continuing is correct.

**Rule 5.4 — Never let a raw exception string reach a user.** → [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md) rule 5.

**Rule 5.5 — Fail closed on auth, config, and secrets.** If the secret is missing, refuse to serve. The one exception is the explicit dev bypass (`APP_ENV=dev AUTH_MODE=bypass`), which is itself checked, not assumed — see `api/dependencies.py`.

---

## 6. Egress: calling other services

**Rule 6.1 — Every outbound HTTP call lives in `clients/`**, one module per upstream, returning typed data. No `requests.get()` scattered through services.

**Rule 6.2 — Clients own timeout, retry, and error translation.** A client call always has an explicit timeout. A network failure becomes a typed domain error, not a raw `ConnectionError` surfacing three layers up.

**Rule 6.3 — Never reimplement an upstream capability.** Grievance PII, SMS/email, and complainant replies are HTTP calls to `backend`/`orchestrator` — the endpoint list is in [`01_api_contracts.md`](../services/01_api_contracts.md). Reimplementing is how two systems end up with two answers.

**Rule 6.4 — Cross-service *domain* logic never becomes a shared import.** The shared kernel is for genuinely generic things (formatting, location codes, validation primitives). Ticketing does not import chatbot domain modules, or vice versa.

---

## 7. Style, typing, logging

**Rule 7.1 — `from __future__ import annotations` at the top of every module.** Cheaper annotations, no import-order pain.

**Rule 7.2 — Imports absolute, at module top, grouped stdlib / third-party / first-party.** A function-level import is allowed **only** to break a real circular import, and gets a comment saying so.
*Why:* a deferred import hides a dependency from every reader and from the import graph.

**Rule 7.3 — snake_case functions, PascalCase classes, `UPPER_SNAKE` constants.** Constants live in `constants/`, not at the bottom of a service.

**Rule 7.4 — Every module has a one-line docstring** saying what capability it owns. Every non-obvious *decision* gets a comment saying **why**, not what. `# increment i` is noise; `# ranked by active load, so tests must assert on the pool, not one officer` is the comment that saves the next reader an hour.

**Rule 7.5 — Structured logging, never `print()`.** `logger = logging.getLogger(__name__)`. Levels: `debug` = developer detail; `info` = a state change worth an audit trail; `warning` = degraded but handled; `error` = the operation failed. Log **identifiers** (`ticket_id`, `grievance_id`), never PII, never a token, never a whole request body.

**Rule 7.6 — Comments and docstrings must be true.** A stale docstring is worse than none — see the `GET /api/grievance/{id}` decryption claim in [`CLAUDE.md`](../../CLAUDE.md), which was false for months and produced a whole workaround subsystem. When behaviour changes, the docstring changes in the same edit.

**Rule 7.7 — Dependencies:** chatbot → `requirements.txt`, GRM/ops → `requirements.grm.txt`, dev-only → `requirements-dev.txt`. Pin anything that has ever broken you (`uvicorn` is pinned for exactly this reason). Adding a dependency is a decision — say in the PR what it replaces.

---

## 8. Async

**Rule 8.1 — Routes may be `async def`; the service layer is synchronous.** SQLAlchemy sessions here are sync; an `async def` service that blocks on sync I/O stalls the event loop.

**Rule 8.2 — Anything slower than ~1s belongs in Celery**, not in the request. Queue registry: [`07_task_queue_service.md`](../services/07_task_queue_service.md).

**Rule 8.3 — Celery tasks must be idempotent and take serializable arguments only** — IDs, never ORM objects.

---

## 9. Known deviations — do not extend

| Deviation | Find it with | Target state |
|---|---|---|
| `commit()` in services | `grep -rn "\.commit()" ticketing/services/` | Rule 4.1 |
| `get_settings()` deep in a service | `grep -rn "get_settings()" ticketing/services/` | Rule 3.6 |
| Function-level imports without a stated cycle | `grep -rn "^\s\+from ticketing" ticketing/services/` | Rule 7.2 |
| `utils/` holding one-off helpers | `ticketing/utils/` | Rule 3.3 — promote to a named service when it grows |
