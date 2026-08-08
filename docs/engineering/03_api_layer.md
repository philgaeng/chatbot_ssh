# API layer standard — FastAPI

**Status:** authoritative (2026-08-03). Rules for `ticketing/api/`, `backend/api/`, and any new HTTP surface.
**Reads with:** [02 — Python & the service layer](02_python_services.md) (routers are the *Humble Object* half of that pattern) and [`01_api_contracts.md`](../services/01_api_contracts.md) (the cross-service endpoint matrix).

---

## 1. What a router is allowed to do

Exactly four things, in order:

1. Declare the contract — path, method, `response_model`, status code, auth dependency.
2. Deserialize and validate input (Pydantic does this; you don't).
3. Call **one** service function.
4. Shape the response, and commit.

```python
@router.post("/{ticket_id}/escalate", response_model=TicketOut, status_code=200)
def escalate_ticket(
    ticket_id: UUID,
    body: EscalateIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_ticket_actor),      # ← authz, declared
) -> TicketOut:
    try:
        ticket = escalation.escalate(db, ticket_id, actor=user, reason=body.reason)
    except InvalidTransition as e:
        raise HTTPException(409, detail=str(e))
    db.commit()
    return TicketOut.model_validate(ticket)
```

**Rule 1.1 — No domain branching in a router.** An `if ticket.status == ...` in a route is logic that a Celery task cannot reach. Move it.

**Rule 1.2 — No raw SQL and no multi-step ORM work in a router.** One service call. If you need three, you need one service function that composes them — otherwise the transaction boundary and the authz check drift apart from the logic.

**Rule 1.3 — Routers commit; services don't.** → [02 §4](02_python_services.md#4-transactions).

**Rule 1.4 — A router file stays under ~400 lines.** Past that, split by resource concern into a package, as `api/routers/tickets/` already is (`crud` / `actions` / `files` / `pii` / `collaboration` / `summary` / `_shared`). That split exists because the single file reached 4,000+ lines and became unreviewable — don't recreate it.

---

## 2. Structure and routing

```
ticketing/api/
  main.py           ← app factory, middleware, router registration, startup checks
  dependencies.py   ← get_db, auth, authz. The ONLY place identity is resolved.
  ticket_access.py  ← row-level visibility rules shared by ticket routes
  routers/          ← one module (or package) per resource
  schemas/          ← Pydantic v2 request/response models, one module per resource
```

**Rule 2.1 — One router per resource, mounted with its own prefix and tag.** `APIRouter(prefix="/api/v1/tickets", tags=["tickets"])`.

**Rule 2.2 — Paths are plural nouns; the verb is the HTTP method.** `/api/v1/tickets`, `/api/v1/tickets/{ticket_id}`.
*Exception, deliberate:* state transitions that are not CRUD get a sub-path verb — `POST /tickets/{id}/escalate`, `/acknowledge`, `/resolve`. Modelling those as `PATCH {status: …}` hides the state machine and lets a client invent illegal transitions.

**Rule 2.3 — Everything lives under `/api/v1/`.** A breaking change to a shipped contract is `/v2`, not a silent edit — the chatbot and the portal deploy independently.

**Rule 2.4 — Path params are typed** (`ticket_id: UUID`). FastAPI then rejects garbage with a 422 before your code runs.

---

## 3. Schemas (Pydantic v2)

**Rule 3.1 — Every route declares a `response_model`.** No route returns a bare dict.
*Why:* the response model is the contract, the OpenAPI doc, and the PII filter in one. A bare dict leaks whatever the ORM object happens to carry — which is how PII escapes.

**Rule 3.2 — Separate `…In` and `…Out` models.** Never accept an ORM-shaped model as input; that is how a client sets `is_seah` or `created_at`.

**Rule 3.3 — `model_config = ConfigDict(from_attributes=True, extra="forbid")` on request models.** `extra="forbid"` turns a client typo into a 422 instead of a silently ignored field.

**Rule 3.4 — Validate at the edge, in the schema.** Ranges, enums, formats, cross-field rules go in Pydantic validators so the service can trust its arguments.

**Rule 3.5 — A response model never exposes a PII field.** Complainant contact is served only by the dedicated reveal endpoint, which logs the access. → [`09_privacy.md`](../deployment/09_privacy.md)

**Rule 3.6 — Field names match the frontend types.** `channels/ticketing-ui/lib/api.ts` mirrors these models by hand; a rename on either side is a break. Change both in the same commit.

---

## 4. Authorization

**Rule 4.1 — Authorization is a route dependency, never an `if` in the body.**

```python
@router.get("/", dependencies=[Depends(require_admin)])
```
*Why:* a dependency is visible in the signature, in the OpenAPI output, and in a route-inventory test. An `if` three levels into a handler is invisible to all three, and is what an added early-`return` silently removes.

**Rule 4.2 — Every route has an explicit auth dependency.** There is no "public by default". Genuinely public routes (`public_closure`, `public_report`) say so by name and are enumerated in the route snapshot test.

**Rule 4.3 — Identity resolves in exactly one place** — `api/dependencies.py`. Nothing else parses a JWT or reads `x-api-key`.

**Rule 4.4 — Two authz layers, both required.** *Can this user call this endpoint?* (the dependency) and *can this user see this row?* (jurisdiction / scope filtering in the query, `ticket_access.py`). Endpoint-only authz means any authenticated officer can read every district's tickets by guessing an ID.

**Rule 4.5 — Filter rows in SQL, not in Python.** A post-filter on a fetched list still leaks through `total` counts, pagination, and aggregates.

**Rule 4.6 — Fail closed.** Missing secret, unverifiable token, unknown role → refuse. Never default to a permissive branch. Pinned by `tests/ticketing/test_fail_closed_auth.py`.

**Rule 4.7 — Every new route gets a row in the authz matrix test.** `tests/ticketing/test_authz_matrix_extended.py`, and the route inventory in `tests/ticketing/route_snapshot.txt` — which is why adding a route makes that snapshot fail. That failure is the feature: update it deliberately.

---

## 5. Errors

**Rule 5.1 — Map domain error → status in the router**, one mapping per router module.

| Situation | Status |
|---|---|
| Validation / malformed input | 422 (Pydantic, automatic) |
| Unauthenticated | 401 |
| Authenticated but not permitted | 403 |
| Not found — **or found but out of the caller's jurisdiction** | 404 |
| Illegal state transition, conflicting edit | 409 |
| Business rule refused it | 422 with a `detail` the UI can render |
| Upstream (backend/Keycloak/SMS) unavailable | 502 / 503 |

**Rule 5.2 — Out-of-jurisdiction returns 404, not 403.** A 403 confirms the record exists, which leaks the existence of SEAH cases to officers who must not know they exist.

**Rule 5.3 — `detail` is a stable, translatable message** — never a stack trace, never a SQL error, never a raw upstream body. The UI renders it via `formatUserFacingError` + `ErrorNotice`.

**Rule 5.4 — One global exception handler** logs the traceback with a correlation id and returns a generic 500. Tracebacks never cross the wire.

---

## 6. Lists, pagination, filtering

**Rule 6.1 — Every list endpoint is paginated from day one**, with the envelope already in use: `{items, total, page, page_size}`. Retrofitting pagination breaks every caller.

**Rule 6.2 — `page_size` has a server-side maximum.** Unbounded means one client can OOM the API.

**Rule 6.3 — Filters and sorts are declared query params against an allowlist.** Never interpolate a user-supplied column name into SQL.

**Rule 6.4 — Sorting is deterministic** — always tie-break on the primary key, or rows repeat and vanish across pages.

---

## 7. Contracts with other services

**Rule 7.1 — Inbound machine-to-machine calls use `x-api-key`** (chatbot → ticketing). Human traffic uses Keycloak JWT. Never mix the two on one route without saying why in a comment.

**Rule 7.2 — A shipped contract changes additively.** New optional field, fine. Renamed or removed field, or a narrowed type: that is `/v2`, plus a migration note in [`01_api_contracts.md`](../services/01_api_contracts.md).

**Rule 7.3 — Webhooks verify their source** and are idempotent — they *will* be delivered twice (`routers/webhooks.py`, Keycloak onboarding).

**Rule 7.4 — Document the endpoint where the contract lives**, not only in code: [`01_api_contracts.md`](../services/01_api_contracts.md) is the matrix both sides read.

---

## 8. Operational hygiene

**Rule 8.1 — `/health` is cheap and dependency-aware:** liveness answers without touching the DB; readiness checks the DB and the broker.

**Rule 8.2 — Startup validates configuration and fails loudly.** A service that boots with a missing secret and 500s per-request is worse than one that refuses to boot.

**Rule 8.3 — CORS is not the answer.** The portal proxies `/api/v1/...` through Next.js rewrites to `ticketing_api:5002` precisely so the browser needs one origin. Don't open CORS to work around a proxy bug.

**Rule 8.4 — No secrets, tokens, or PII in logs or in OpenAPI examples.**

---

## 9. Definition of done for an endpoint

- [ ] Auth dependency declared; jurisdiction filtering in SQL
- [ ] `response_model` set; `…In`/`…Out` separated; no PII field
- [ ] Domain errors mapped to statuses; 404 (not 403) for out-of-jurisdiction
- [ ] Paginated if it returns a list
- [ ] Row added to the authz matrix test + route snapshot updated
- [ ] Frontend types in `lib/api.ts` updated in the same commit
- [ ] [`01_api_contracts.md`](../services/01_api_contracts.md) updated if another service calls it
