# H2-02 / H2-03 / H2-07 — Backend router split + test extensions

> Workstream A · Branch `tier2/h2-02-03-07-backend` · Sequential: H2-02 → H2-03 → H2-07.
> Evidence: backend review in [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §1. Re-locate line numbers before editing.
> **H2-02 is a pure refactor — zero behavior change. The full existing suite + the HR-02 authz matrix must pass unchanged; that is the primary acceptance gate.**

---

## 1. H2-02 — Split `tickets.py`; move `perform_action` into `engine/`

### Problem (verified)

- `ticketing/api/routers/tickets.py` is 2,468 lines / 47 functions / ~27 endpoints — the repo's main merge-conflict hotspot.
- `perform_action` (~lines 1089–1520) is a single ~430-line function implementing the entire ticket state machine inline — untestable except through HTTP.
- Workflow helpers that belong in `engine/` live in the router: `_next_step`, `_find_supervisor_user_id`, `_validate_step_assignee` (~158–277).
- `_add_event` exists **twice** with near-identical 15-parameter signatures (`tickets.py:381` and `engine/escalation.py:53`).
- 14 in-function imports in the router (circular-import symptoms).

### Change

1. **Router package** `ticketing/api/routers/tickets/` preserving the exact URL surface (mount unchanged in `main.py`):
   - `crud.py` — create/list/get/patch (incl. classification), resolved-summary
   - `actions.py` — `POST /tickets/{id}/actions` + inbound/reply/messaging
   - `files.py` — files, attachments, uploads
   - `pii.py` — pii, reveal/reveal-close
   - `notes_tasks_viewers.py` — notes, tasks, viewers, events (or split further if natural)
   - `_shared.py` — router-local helpers that are genuinely HTTP-layer (response shaping)
   Keep `from ticketing.api.routers import tickets` working (package `__init__.py` re-exports the composed router).
2. **Engine extraction**: each `perform_action` branch becomes a function in `ticketing/engine/` (e.g. `ticket_actions.py`): `acknowledge()`, `escalate()` (thin wrapper over the existing `escalation.py` path — do not duplicate it), `resolve()`, `add_note()`, `field_report()`, `grc_convene()`, `request_reassignment()`. The router action endpoint becomes: validate input → dispatch table → engine call → response. Signature discipline: engine functions take `(db, ticket, actor, payload)` and return the event(s)/result — no `Request`/`HTTPException` inside engine (raise typed exceptions; router maps to HTTP).
3. **Move the misplaced workflow helpers** (`_next_step`, `_find_supervisor_user_id`, `_validate_step_assignee`) into `engine/workflow_engine.py` (or a new `engine/steps.py`).
4. **Unify `_add_event`** into `ticketing/engine/events.py`; both former call sites import it. Kill the in-function imports this enables (module-level imports must not cycle — `events.py` imports models only).
5. **No logic edits**: behavior, status codes, response bodies, event payloads all byte-identical. If you find a bug mid-move, log it in PROGRESS deviations and preserve the buggy behavior (fix in a follow-up ticket) — the refactor must stay verifiable.

### Tests (acceptance)

- [ ] Full ticketing suite green **without modifying any existing test** (imports may need path updates only if tests imported private helpers — record each in PROGRESS).
- [ ] HR-02 authz matrix green unchanged.
- [ ] New `tests/ticketing/test_ticket_actions_unit.py`: the engine functions called **directly** (no HTTP) — one happy-path test per action proving unit-testability (ACKNOWLEDGE sets status + event; NOTE writes event; RESOLVE requires resolution fields; GRC_CONVENE sets `GRC_HEARING_SCHEDULED`; REASSIGNMENT_REQUESTED writes event).
- [ ] Route-surface snapshot: test that dumps `app.routes` (method+path sorted) and compares to a committed snapshot taken **before** the split — proves the URL surface is identical.
- [ ] `grep -rn "def _add_event" ticketing/` ⇒ exactly one definition.

### Manual verification
- [ ] Seeded stack: click through acknowledge → note → escalate → resolve in the UI; thread renders identically.

---

## 2. H2-03 — Authz matrix extension

### Problem

HR-02's matrix covers the core per-ticket endpoints × 6 personas. The class fix is only mechanically protected where the matrix reaches; users/workflows/reports/settings routers and the full action set are unswept.

### Change

Extend `tests/ticketing/test_ticket_access_matrix.py` (or add `test_authz_matrix_extended.py`):
1. **All action types** × personas on `POST /tickets/{id}/actions` (ACKNOWLEDGE, ESCALATE, RESOLVE, NOTE, FIELD_REPORT, GRC_CONVENE, REASSIGNMENT_REQUESTED — from `VALID_ACTIONS`).
2. **Admin-surface endpoints** × admin ladder (super_admin / country_admin / project_admin / non-admin): representative endpoints from `users.py` (invite, roles CRUD, admin-scopes), `workflows.py` (publish, step edit), `locations.py` (project create/edit), `settings.py`, `reports.py` (query, share create). Assert against the documented matrix in `docs/ticketing_system/11_roles_and_permissions.md` §access — where code and spec disagree, **fail the test and log the discrepancy** in PROGRESS (don't codify the bug).
3. **Unauthenticated** sweep: every router's endpoints return 401/403 with no token (walk `app.routes`, skip the known-public set: scan, public_report, public_closure, webhooks with their own secret, health).

### Tests (acceptance)
- [ ] Matrix runs green in CI < 2 min (parametrize efficiently; one seeded fixture set, no per-case reseeding).
- [ ] Any spec-vs-code authz discrepancies found are listed in PROGRESS with file:line.

---

## 3. H2-07 — Escalation test-suite extension

### Problem

HR-04 delivered the baseline (breach, final step, mid-loop isolation, double-run, lock skip). The untested remainder: multi-level chains, SEAH-track escalation, and watchdog/manual interleaving.

### Change — add to `tests/ticketing/test_escalation_engine.py`

- [ ] **Full chain**: L1→L2→L3(GRC convene)→resolve on the seeded KL Road workflow — each level escalates on breach with correct assignee resolution (workflow-role/package-based assignment per `docs/ticketing_system/07`), events in order.
- [ ] **SEAH track**: SEAH ticket escalates within the SEAH workflow only; assignee always SEAH-capable; no notification/event leaks to standard-role visibility (assert via the HR-02 access dependency).
- [ ] **Manual-then-auto interleaving**: officer manually escalates between watchdog selection windows ⇒ watchdog run does not double-advance (idempotence re-check under lock, proven at the API layer this time: perform manual ESCALATE via TestClient, then run the watchdog).
- [ ] **Notification side-effects**: escalation enqueues exactly one notification task per transition (assert on the celery mock/outbox — match however HR-04 stubbed `_enqueue_celery`).
- [ ] Suite total runtime stays reasonable (< ~60 s locally).
