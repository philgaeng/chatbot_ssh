# Agent runbook — HR-03 + HR-04: Data integrity

**Branch:** `hardening/hr-03-04-data` off `integration/seah-claude` (rebase on the merged auth branch if it landed — shared file `tickets.py`) · **Spec:** [`../02-data-integrity-spec.md`](../02-data-integrity-spec.md) · Read [`README.md`](README.md) common rules first. Do HR-03 fully before HR-04.

## Mission

Make "one grievance = one active ticket" a database-enforced invariant (HR-03), then make the SLA escalation watchdog crash-safe and concurrency-safe (HR-04). These close the silent-corruption findings on the product's core workflow.

## HR-03 steps

1. Read `ticketing/models/ticket.py` (`__table_args__`), `ticketing/services/ticket_intake.py` (duplicate guard ~286-293), `ticketing/tasks/grievance_sync.py`, and `backend/actions/utils/ticketing_dispatch.py` (how the chatbot treats the webhook response — your idempotent response must not break it).
2. Check current head: `cd ticketing/migrations && alembic heads` (expected `g0h2i4j6`; chain on whatever is actual). New revision per spec §1: pre-flight dedup (oldest survives, losers soft-deleted + SYSTEM event), partial unique index `WHERE is_deleted = false`, drop the old non-unique index, real `downgrade()`, safety header (`# Safe to run: only creates/modifies ticketing.* tables...`).
3. Intake + sync idempotency per spec (IntegrityError ⇒ return existing / skip-and-continue). Decide and document the API status semantics (existing ticket ⇒ 200 with same body shape) after checking what `ticketing_dispatch.py` accepts.
4. Write `tests/ticketing/test_ticket_uniqueness.py` (5 cases incl. the two-session race and the migration dedup test).
5. Manual: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` on the seeded dev DB (see `docs/deployment/DOCKER.md`). Record in `../PROGRESS.md`.

## HR-04 steps

1. Read `ticketing/engine/escalation.py` **fully** (single code path for manual/auto/GRC — keep it that way), plus `ticketing/tasks/escalation.py` (beat config, `acks_late`) and the ESCALATE branch of `perform_action` in `tickets.py`.
2. Implement per spec §2: `with_for_update(skip_locked=True)` candidate selection, bulk WorkflowStep load, `begin_nested()` savepoint per ticket with rollback-and-continue, idempotence re-check under lock, row lock on the manual path.
3. Session/transaction care: confirm how the task acquires its `db` session (`SessionLocal` pattern) and that `begin_nested` semantics work with the existing commit structure — write the mid-loop-failure test FIRST and watch it fail against current code (proves the corruption mode), then fix.
4. Write `tests/ticketing/test_escalation_engine.py` (6 cases per spec; the concurrency case uses two sessions — Postgres required, no sqlite shortcuts; follow the DB-backed patterns in existing ticketing tests).
5. Manual: past-deadline ticket on the seeded DB escalates exactly once across two runs; new assignee + ESCALATED event visible in the UI. Record in `../PROGRESS.md`.

## Constraints

- Do not restructure `perform_action` or split the router (Tier-2/3).
- Do not change SLA policy, step resolution, or notification behavior — only transactional/locking semantics.
- Migration touches `ticketing.*` only (three-stream rule, `docs/deployment/07_migrations_policy.md`).

## Done means

All HR-03 + HR-04 checklist boxes ticked in `../PROGRESS.md`, both test files green in the full ticketing suite, migration round-trip verified, manual checks recorded.
