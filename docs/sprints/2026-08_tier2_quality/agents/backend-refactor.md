# Agent runbook — H2-02 + H2-03 + H2-07: Backend refactor & test extensions

**Branch:** `tier2/h2-02-03-07-backend` off `integration/seah-claude` · **Spec:** [`../02-backend-router-split-spec.md`](../02-backend-router-split-spec.md) · Read [`README.md`](README.md) first. Strict order: H2-02 → H2-03 → H2-07.

## Mission

Turn the 2,468-line `tickets.py` God-router into a package with the ticket state machine living in `engine/` (pure refactor, zero behavior change), then extend the authz matrix and escalation suites to cover what the baseline missed.

## H2-02 steps (the refactor)

1. **Snapshot first**: write the route-surface snapshot test (dump sorted method+path from `app.routes`, commit the snapshot) and run the full suite + HR-02 matrix green on the UNCHANGED code. These are your invariants.
2. Read `tickets.py` fully; build (in your notes/PROGRESS) the function → target-module table: every endpoint, every helper, where it goes (crud/actions/files/pii/notes_tasks_viewers/_shared/engine). Flag anything ambiguous in PROGRESS before moving.
3. Move in mechanical passes, running the suite between each: (a) helpers → `engine/` (`_next_step`, `_find_supervisor_user_id`, `_validate_step_assignee`; unify `_add_event` → `engine/events.py`); (b) `perform_action` branches → `engine/ticket_actions.py` with typed exceptions, router keeps a dispatch table; (c) endpoints → package modules; (d) `__init__.py` composes the router, `main.py` mount untouched.
4. Kill in-function imports as the moves allow — module-level only, no cycles (engine imports models, never routers).
5. Add `tests/ticketing/test_ticket_actions_unit.py` (direct engine calls, one per action).
6. Gate: full suite + matrix + route snapshot all green, `grep -rn "def _add_event" ticketing/` = 1. Manual UI click-through per spec. **If any behavior difference appears, preserve the old behavior** and log the underlying bug in PROGRESS — do not fix bugs inside the refactor.

## H2-03 steps

1. Read `docs/ticketing_system/11_roles_and_permissions.md` (access matrix) and the HR-02 test file's fixtures.
2. Extend per spec §2: all VALID_ACTIONS × personas; admin-ladder × representative admin endpoints (assert the spec-11 matrix; on disagreement, mark the test xfail with the discrepancy documented in PROGRESS — never encode the bug as expected); unauthenticated sweep over `app.routes` minus the documented public set.
3. Keep total matrix runtime < 2 min (one seeded fixture set, parametrize).

## H2-07 steps

1. Read the HR-04 suite; extend `test_escalation_engine.py` per spec §3: full L1→L3 chain, SEAH-track isolation, manual-then-auto interleaving via TestClient, notification side-effect counts.
2. Reuse the seeded KL Road workflows (`ticketing/seed/`); suite stays < ~60 s.

## Constraints

- **Zero behavior change in H2-02** — the whole ticket is verifiability. Response shapes, status codes, event payloads identical.
- Don't touch `escalation.py` logic (H2-02 wraps it; HR-04 already fixed its transactions).
- No renaming of public symbols other tests/modules import without updating every importer in the same commit.

## Done means

All three checklists ticked in `../PROGRESS.md`; suite + matrix + snapshot green in CI; discrepancy list (possibly empty) recorded; manual click-through recorded.
