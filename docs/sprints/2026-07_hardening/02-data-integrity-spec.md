# HR-03 / HR-04 — Data Integrity (unique ticket index + escalation locking)

> Workstream B · Branch `hardening/hr-03-04-data` · Sequential: HR-03 (migration) then HR-04.
> Land Workstream A first or rebase on it (both touch `ticketing/api/routers/tickets.py`).
> Evidence source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §2.3. Re-locate line numbers before editing.

---

## 1. HR-03 — Unique partial index on `tickets.grievance_id`

### Problem (verified)

"One grievance = one ticket" is the workflow's cardinal invariant, but:
- `idx_tickets_grievance_id` is **non-unique** (`ticketing/models/ticket.py:32`).
- The only duplicate guard is an application-level read-then-insert (`ticketing/services/ticket_intake.py:286-293`, raising `DuplicateTicketError`) — a webhook retry racing the 2-minute `grievance_sync` backfill can create two tickets for one grievance.

### Change

1. New Alembic revision (ticketing stream, safety header, chained on current head `g0h2i4j6`):
   - **Pre-flight dedup** in `upgrade()`: find `grievance_id`s with >1 non-deleted ticket; keep the oldest (`created_at` min), soft-delete the rest (`is_deleted = true`) and write a `TicketEvent` (`type=SYSTEM`, payload noting the merge) on the survivor. Log counts. (Expected zero rows in practice — the code must still handle it.)
   - `CREATE UNIQUE INDEX uq_tickets_grievance_id_active ON ticketing.tickets (grievance_id) WHERE is_deleted = false;` (use `op.create_index(..., unique=True, postgresql_where=...)`).
   - Keep or drop the old non-unique index deliberately (drop it — the unique one covers the same lookups); real `downgrade()` restores the old index.
2. Model: mirror the index in `ticketing/models/ticket.py` `__table_args__` so metadata matches the DB.
3. Make intake **idempotent instead of racy**: in `ticket_intake.py`, wrap the insert; on `IntegrityError` for this index, rollback, re-fetch the existing ticket, and return it as the success result (webhook retries become no-ops). The API layer (`POST /api/v1/tickets`) returns the existing ticket with `201`→`200` semantics (match whatever the dispatcher `ticketing_dispatch.py` tolerates — check it; it must not treat the response as failure).
4. `grievance_sync` backfill: same IntegrityError handling (skip-and-continue, log at INFO not ERROR).

### Tests (acceptance)

New file `tests/ticketing/test_ticket_uniqueness.py`:
- [ ] Creating a second ticket for the same `grievance_id` via the service returns the existing ticket (no exception, no duplicate row).
- [ ] `POST /api/v1/tickets` twice with the same payload ⇒ second call succeeds and returns the same `ticket_id`.
- [ ] Soft-deleted ticket does **not** block re-creation (`is_deleted=true` row + new insert OK — the partial index predicate).
- [ ] Race simulation: two sessions insert the same `grievance_id`; exactly one row survives, the loser gets the winner's ticket (drive via two DB sessions with the second insert hitting IntegrityError).
- [ ] Migration test: seed a duplicate pair, run `alembic upgrade head`, assert one survivor + soft-deleted loser + SYSTEM event.

### Manual verification
- [ ] `alembic upgrade head` + `alembic downgrade -1` + `upgrade head` clean on a seeded dev DB.

---

## 2. HR-04 — Savepoints + row locking in the SLA watchdog

### Problem (verified)

`run_sla_check` (`ticketing/engine/escalation.py:497-550`, Celery beat every 15 min, `acks_late=True` at `tasks/escalation.py:25`):
- Catches per-ticket exceptions (line ~534) **without rollback**; if `escalate_ticket` throws after mutating `ticket.current_step_id`/`status_code` (lines ~262-266) but before writing the ESCALATED event, the loop continues and the final `db.commit()` (~541) persists a ticket advanced to a new step **with no audit event and no assignment** — silent workflow corruption.
- **Zero row locking** anywhere in ticketing (`with_for_update` grep: 0 hits): manual escalation via the API, the watchdog, and `grievance_sync` can mutate the same ticket concurrently; overlapping beat runs / redelivered tasks can double-escalate.
- N+1: `db.get(WorkflowStep)` per candidate, twice (~490, ~509) — fix opportunistically while in the file.

### Change

1. **Candidate selection with locks:** select breach candidates `WITH FOR UPDATE SKIP LOCKED` (SQLAlchemy: `.with_for_update(skip_locked=True)`) so concurrent runs and the manual API path can't process the same ticket simultaneously. Bulk-load the needed `WorkflowStep`s in one query keyed by step id (kills the N+1).
2. **Savepoint per ticket:** wrap each ticket's escalation in `db.begin_nested()`; on exception, roll back the savepoint, log with `ticket_id`, continue the loop. The outer commit then only persists fully-escalated tickets.
3. **Idempotence guard inside `escalate_ticket`:** re-check under the lock that the ticket is still on the step it was selected at (`current_step_id` unchanged and SLA still breached); if not, skip. This also protects the manual-escalation API racing the watchdog.
4. **Manual escalation path** (`perform_action` ESCALATE branch in `tickets.py`): acquire the same row lock (`SELECT ... FOR UPDATE` on the ticket) before mutating. Keep the lock scope minimal (inside the action transaction).
5. Do **not** restructure `perform_action` beyond the lock — the router split is Tier-2 work.

### Tests (acceptance)

New file `tests/ticketing/test_escalation_engine.py` (first tests this engine has ever had):
- [ ] SLA breach ⇒ ticket escalates: step advances, ESCALATED event written, assignment resolved — all in one transaction.
- [ ] Final-step breach ⇒ no crash; documented terminal behavior (event/flag) asserted.
- [ ] **Mid-loop failure isolation:** 3 candidates, monkeypatch escalation to throw on #2 ⇒ #1 and #3 fully escalated, #2 completely untouched (step, status, events all unchanged).
- [ ] **No partial state:** force a throw between step mutation and event write ⇒ after the run, ticket step is unchanged (savepoint rolled back).
- [ ] **Double-run idempotence:** run `run_sla_check` twice back-to-back ⇒ each breached ticket escalates exactly once (assert single ESCALATED event per level).
- [ ] **Concurrency:** session A holds the row lock (simulating manual escalation); watchdog run in session B skips the ticket (SKIP LOCKED) and completes without blocking.
- [ ] No-regression: full ticketing suite green.

### Manual verification
- [ ] On the seeded demo DB, set one ticket's deadline in the past, run the beat task once (`celery -A ticketing.tasks call ...` or invoke the function): ticket escalates, event + new assignee visible in the UI thread.
- [ ] Run it again: no second escalation.
