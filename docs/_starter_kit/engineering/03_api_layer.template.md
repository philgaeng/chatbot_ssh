# API layer standard

**Status:** ‹authoritative› (‹YYYY-MM-DD›).
**Framework: FILL:** ‹e.g. FastAPI›.
**Reads with:** [02](02_services.template.md) — handlers are the *Humble Object* half of that pattern.

---

## 1. What a handler may do

Exactly four things, in order: **declare the contract** (path, method, response model, status, auth) → **deserialize and validate** (the framework does it) → **call one service function** → **shape the response and commit**.

**Rule 1.1 — No domain branching in a handler.** A condition on domain state is logic a background job cannot reach.

**Rule 1.2 — No raw queries or multi-step persistence work in a handler.** One service call. If you need three, you need one service function that composes them — otherwise the transaction boundary and the authorization check drift apart from the logic they guard.

**Rule 1.3 — Handlers commit; services don't.** → [02 §4](02_services.template.md)

**Rule 1.4 — FILL:** a size ceiling per router file (‹~400 lines›) and the split axis when it is exceeded. Say it plainly — router files grow to thousands of lines faster than any other file in a codebase, and become unreviewable long before anyone notices.

---

## 2. Structure & routing

**Rule 2.1 — One router per resource**, with its own prefix and tag.

**Rule 2.2 — Paths are plural nouns; the verb is the HTTP method.**
*Deliberate exception:* state transitions that are not CRUD get a named sub-path (`POST /‹records›/{id}/‹transition›`). Modelling a state machine as a generic field update hides it and lets a client invent an illegal transition.

**Rule 2.3 — Everything is versioned from day one** (`/api/v1/…`). A breaking change to a shipped contract is a new version, not a silent edit — clients deploy on their own schedule.

**Rule 2.4 — Path parameters are typed**, so malformed input is rejected before your code runs.

---

## 3. Request & response models

**Rule 3.1 — Every route declares a response model.** No route returns a loose map. *Why:* the response model is the contract, the generated documentation, and the ‹PII› filter in one. A loose return leaks whatever the persistence object happens to carry — which is how sensitive fields escape.

**Rule 3.2 — Separate input and output models.** Never accept a persistence-shaped model as input; that is how a client sets a server-owned field.

**Rule 3.3 — Reject unknown fields on input.** A client typo becomes a clear validation error instead of a silently ignored field.

**Rule 3.4 — Validate at the edge**, in the model — ranges, formats, cross-field rules — so services can trust their arguments.

**Rule 3.5 — FILL:** which fields must never appear in a response, and where the exception lives (an audited, dedicated endpoint).

**Rule 3.6 — Client-side types mirror these models.** If the client repeats them by hand, nothing enforces the match: **change both in the same commit.**

---

## 4. Authorization

**Rule 4.1 — Authorization is declared on the route**, in the signature, never an `if` in the handler body. *Why:* a declaration is visible in the signature, in the generated docs, and to a route-inventory test. A condition three levels into a handler is invisible to all three, and an added early return silently removes it.

**Rule 4.2 — Every route has an explicit auth declaration.** There is no "public by default"; genuinely public routes say so by name and are enumerated.

**Rule 4.3 — Identity is resolved in exactly one place.** Nothing else parses a token or an API key.

**Rule 4.4 — Two layers, both required:** *may this caller use this endpoint?* and *may this caller see this row?* Endpoint-only authorization means any authenticated user reads every record by guessing an id.

**Rule 4.5 — Row filtering happens in the query, not in application code afterwards.** A post-filter still leaks through totals, pagination, and aggregates.

**Rule 4.6 — Fail closed.** Missing secret, unverifiable token, unknown role → refuse. Never default to the permissive branch.

**Rule 4.7 — Every new route gets a row in the authorization matrix test**, plus a route-inventory snapshot. Adding a route should *fail* that snapshot — the failure is the feature.

---

## 5. Errors

**Rule 5.1 — Map domain error → status in one place per router.**

| Situation | Status |
|---|---|
| Malformed input | ‹422/400› |
| Unauthenticated | 401 |
| Authenticated, not permitted | 403 |
| Not found — **or out of the caller's scope** | 404 |
| Conflicting edit, illegal transition | 409 |
| Business rule refused it | ‹422› with a renderable message |
| Upstream unavailable | 502 / 503 |

**Rule 5.2 — Out-of-scope returns 404, not 403.** A 403 confirms the record exists, which leaks existence to someone who must not know. **FILL:** name the case in your domain where this matters — it is usually the most sensitive data you hold.

**Rule 5.3 — The error message is stable, translatable, and actionable.** Never a stack trace, a database error, or a raw upstream body.

**Rule 5.4 — One global handler** logs the traceback with a correlation id and returns a generic 500. Tracebacks never cross the wire.

---

## 6. Lists

**Rule 6.1 — Every list endpoint is paginated from day one**, with a consistent envelope. Retrofitting pagination breaks every caller.

**Rule 6.2 — Page size has a server-side maximum.** Unbounded means one client can exhaust the server's memory.

**Rule 6.3 — Filters and sorts are declared parameters against an allowlist.** Never interpolate a caller-supplied column name.

**Rule 6.4 — Sorting is deterministic** — always tie-break on the primary key, or rows repeat and vanish across pages.

---

## 7. Contracts with other systems

**Rule 7.1 — FILL:** which authentication each caller class uses (machine-to-machine vs human), and never mix them on one route without a comment saying why.

**Rule 7.2 — Shipped contracts change additively.** A new optional field is fine; a rename, removal, or narrowed type is a new version plus a migration note.

**Rule 7.3 — Webhooks verify their source and are idempotent.** They *will* be delivered twice.

**Rule 7.4 — The contract is documented where both sides read it**, not only in code.

---

## 8. Operational hygiene

**Rule 8.1 — Health endpoints are cheap and layered:** liveness answers without touching dependencies; readiness checks them.
**Rule 8.2 — Startup validates configuration and fails loudly.** A service that boots with a missing secret and fails every request is worse than one that refuses to boot.
**Rule 8.3 — Don't open CORS to work around a proxy problem.**
**Rule 8.4 — No secrets or ‹PII› in logs or in generated API examples.**

---

## 9. Definition of done — an endpoint

- [ ] Auth declared; row scoping in the query
- [ ] Response model set; input/output separated; no forbidden field
- [ ] Domain errors mapped; 404 (not 403) for out-of-scope
- [ ] Paginated if it returns a list
- [ ] Authorization matrix row added; route inventory updated
- [ ] Client types updated in the same commit
- [ ] Cross-service contract doc updated if another system calls it
