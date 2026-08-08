# Services — the architecture and its contracts

**Status:** ‹authoritative› (‹YYYY-MM-DD›).
**Language / runtime: FILL:** ‹e.g. Python 3.11+, typed›.
**Applies to:** all business logic.

---

## 1. The architecture, named

**A thin entrypoint over a fat service layer, with a shared kernel between independent services.** Three named patterns compose into it — worth knowing which is which, because they answer different objections:

| Layer | Pattern | Rule it gives you |
|---|---|---|
| Entrypoint — route, worker, CLI | **Humble Object** (Meszaros) | The thing that is hard to test — HTTP, the broker, `argv` — holds *no* logic worth testing |
| The logic | **Service Layer** (Fowler, *PoEAA*) | One plain function per use case: session and typed arguments in, typed data out, framework-free |
| Between services | **Shared Kernel** (Evans, *DDD*) | Genuinely common code is shared; *domain* logic never crosses — it goes over a documented contract |

> **Each service keeps only its own orchestration; everything else is a call into a shared, testable function — and nothing framework-shaped ever sits between them.**

**Why, concretely:** every use case ends up with at least four callers — an HTTP route, a background job, a script, and a test. Logic in a route is reachable only by HTTP, so the job re-implements it, and the two drift until they disagree in production.

### Where code goes

**FILL** for your layout. The boundaries matter more than the names.

```
‹service›/
  ‹api›/         ENTRYPOINT — HTTP. No logic. → doc 03
  ‹tasks›/       ENTRYPOINT — background jobs. No logic.
  ‹cli›/         ENTRYPOINT — scripts. No logic.
  ‹domain›/      LOGIC — the core state machine / lifecycle
  ‹services›/    LOGIC — one module per use case
  ‹clients›/     EGRESS — outbound calls to other systems. No domain logic.
  ‹models›/      Persistence shape only
  ‹constants›/   Fixed values. No behaviour.
  ‹utils›/       Pure, dependency-free helpers
  ‹config›/      The only place environment variables are read
```

**FILL:** the rule that separates your two logic folders — e.g. *"‹domain› owns the ‹record› lifecycle and state transitions; ‹services› owns everything else. In doubt: does it move a ‹record› between states? Then ‹domain›."*

---

## 2. Entrypoints hold no logic

**Rule 2.1 — Every entrypoint does exactly three things:** deserialize input, call **one** service function, shape output. A branch on domain state inside an entrypoint belongs in a service.

**Rule 2.2 — Anything an entrypoint can do, a test can do without the framework.** If reaching the logic requires a test HTTP client, the logic is in the wrong place.

**Rule 2.3 — Background jobs are thin for a second reason: retries.** A job holding logic re-runs that logic on every retry. A job calling one idempotent function is safe to retry.

---

## 3. Writing a service function

**Rule 3.1 — Consistent signature:** ‹session› first, then typed arguments; keyword-only for anything optional.

**Rule 3.2 — Fully typed. No untyped map/dict in a public signature.** Return a typed structure, not a loose map — a map return is an undocumented contract that breaks silently at the call site.

**Rule 3.3 — One module per capability, named for the capability, not the layer.** Never `helpers`, `utils`, `common`, `manager`. *Why:* a module with no boundary accretes until it imports everything and can be imported by nothing.

**Rule 3.4 — Public surface at the top, private helpers below with a `_` prefix.** A reader learns what a module offers from its first 30 lines.

**Rule 3.5 — Services know nothing about HTTP.** No framework imports, no status codes, no request objects. Raise a domain error; the entrypoint maps it. *This is precisely what lets the same function serve a route, a job, and a script.*

**Rule 3.6 — Services do not read environment variables.** Configuration is passed in, or read once at the entrypoint. A config read deep in a function is an untestable hidden input.

**Rule 3.7 — Prefer pure functions.** Data in, data out, no I/O — the cheapest thing in any codebase to test and reuse. Push the pure part out of the impure one whenever you can name it.

**Rule 3.8 — FILL:** a soft ceiling on function length and nesting (‹~50 lines, ‹3 levels›), stated as a readability floor rather than a metric to game.

---

## 4. Transactions

**Rule 4.1 — The caller owns the transaction; service functions never commit.** They may flush for a generated id.
*Corollary:* a function that "needs" to commit is telling you it is really two use cases. Split it and let the caller sequence them.

**Rule 4.2 — Rollback is the framework boundary's job**, not a try/except in every function.

---

## 5. Errors

**Rule 5.1 — Domain errors are typed exceptions** defined near their service, from a small shared base. Not generic exceptions, not `(ok, message)` tuples, not `None` for "failed".

**Rule 5.2 — The entrypoint maps domain error → transport status**, in one place. → [03](03_api_layer.template.md)

**Rule 5.3 — Never swallow an exception.** If a failure is genuinely tolerable, catch the *specific* type, log with context, and comment why continuing is correct.

**Rule 5.4 — Never let a raw exception string reach a user.** → ‹the copy guide›

**Rule 5.5 — Fail closed on auth, config, and secrets.** Missing secret → refuse to serve. Any bypass is explicit, named, and environment-gated.

---

## 6. Calling other systems

**Rule 6.1 — Every outbound call lives in a client module**, one per upstream, returning typed data. No ad-hoc HTTP calls scattered through business logic.

**Rule 6.2 — Clients own timeout, retry, and error translation.** Every call has an explicit timeout; a network failure becomes a typed domain error, not a raw transport exception surfacing three layers up.

**Rule 6.3 — Never reimplement an upstream capability.** Two implementations produce two answers, and the discrepancy is found by a user.

**Rule 6.4 — Cross-service *domain* logic never becomes a shared import.** The shared kernel is for genuinely generic things — formatting, validation primitives, shared identifiers.

---

## 7. Style, typing, logging

**Rule 7.1 — FILL:** naming conventions, import policy, formatter and linter, and how they run in CI.

**Rule 7.2 — Imports at module top, absolute, grouped.** A deferred import is allowed only to break a real cycle, and gets a comment saying so — it otherwise hides a dependency from every reader and from the import graph.

**Rule 7.3 — Every module has a one-line docstring** naming the capability it owns.

**Rule 7.4 — Comment the *why*, not the *what*.** `# increment i` is noise; `# ranked by load, so tests must assert on the pool, not one identity` saves the next reader an hour.

**Rule 7.5 — Comments and docstrings must be true.** A stale docstring is worse than none: it is trusted, and code gets written against it. When behaviour changes, the docstring changes in the same edit.

**Rule 7.6 — Structured logging, never print.** Log identifiers, never ‹PII›, never secrets, never whole request bodies. **FILL:** what each level means here.

**Rule 7.7 — Adding a dependency is a decision.** Say in the pull request what it replaces and why the standard library won't do. Pin anything that has broken you.

---

## 8. Concurrency & background work

**Rule 8.1 — FILL:** your async/sync policy, stated once and unambiguously — mixing models is a class of bug that only appears under load.

**Rule 8.2 — Anything slower than ~‹1s› belongs in a background job**, not in the request.

**Rule 8.3 — Jobs are idempotent and take serializable arguments only** — identifiers, never live objects.

---

## 9. Known deviations — do not extend

| Deviation | Find it with | Target |
|---|---|---|
| ‹…› | ‹command› | ‹rule› |
