# Tier-1 Hardening Sprint — Progress

> Update at **every commit** on a sprint branch. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · Source review: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md)

## Ticket status

| ID | Title | Workstream | Status | Branch | Commits | Notes |
|---|---|---|---|---|---|---|
| HR-05 | CI pipeline (pytest + tsc + eslint + docs-links) | C | todo | — | — | Start first |
| HR-01 | Fail-closed auth | A | todo | — | — | |
| HR-02 | `require_ticket_access` on file/PII endpoints | A | todo | — | — | After HR-01 |
| HR-03 | Unique partial index `tickets.grievance_id` | B | todo | — | — | Rebase on A (tickets.py) |
| HR-04 | Escalation savepoints + row locking | B | todo | — | — | After HR-03 |
| HR-06 | Portal error states + settings crash + error.tsx | D | todo | — | — | Coordinates with HR-05 eslint gate |
| HR-07 | Webchat session/send-lock/SRI/banner | E | todo | — | — | |

## Acceptance checklists

### HR-01 — Fail-closed auth
- [ ] `TICKETING_ENV` (default `production`) in ticketing settings; backend mirror var
- [ ] Startup guard raises on missing `keycloak_issuer` / `ticketing_secret_key` outside dev
- [ ] Per-request 503 fallback (defense in depth); demo fallback dev-only
- [ ] Header-identity default role = least privilege (internal callers re-verified)
- [ ] `docker-compose.override.yml` sets dev; grm/aws/prod files do NOT
- [ ] `tests/ticketing/test_fail_closed_auth.py` — all 6 cases green
- [ ] `13_security.md` "Fail-closed guarantees" section added
- [ ] Manual: compose up without Keycloak vars ⇒ container refuses; dev flow unaffected

### HR-02 — Ticket access dependency
- [ ] `ticketing/api/ticket_access.py` single-source gate (exists/SEAH/scope/visibility)
- [ ] File-id resolution path (`require_file_access`) incl. `public.file_attachments`
- [ ] Applied to all ~15 per-ticket endpoints; inline checks removed
- [ ] PII masking rules (TP-15) unchanged
- [ ] `tests/ticketing/test_ticket_access_matrix.py` persona×endpoint matrix green
- [ ] Existing suite: zero regressions
- [ ] Manual: direct SEAH file URL as standard officer ⇒ 403/404; reveal flow intact

### HR-03 — Unique ticket index
- [ ] Migration: pre-flight dedup + `uq_tickets_grievance_id_active` partial unique + downgrade
- [ ] Model `__table_args__` mirrors index
- [ ] Intake idempotent on IntegrityError (returns existing ticket); dispatcher tolerates response
- [ ] `grievance_sync` skip-and-continue on conflict
- [ ] `tests/ticketing/test_ticket_uniqueness.py` — all 5 cases green
- [ ] Manual: upgrade → downgrade → upgrade clean on seeded DB

### HR-04 — Escalation locking
- [ ] Candidates selected `FOR UPDATE SKIP LOCKED`; WorkflowSteps bulk-loaded (N+1 gone)
- [ ] `begin_nested()` savepoint per ticket; rollback on per-ticket failure
- [ ] Idempotence re-check under lock in `escalate_ticket`
- [ ] Manual ESCALATE path takes the row lock
- [ ] `tests/ticketing/test_escalation_engine.py` — all 6 cases green (incl. concurrency)
- [ ] Manual: past-deadline ticket escalates once; second run no-op

### HR-05 — CI
- [ ] `.github/workflows/ci.yml`: backend-tests (postgres service + 3-stream migrations), ui-checks (tsc + eslint), docs-links
- [ ] 4 pytest collection errors resolved (env/requirements)
- [ ] ESLint baseline: hooks errors gate, `set-state-in-effect` → warn (dated comment)
- [ ] Deliberate-failure checks performed (tsc, doc link) and reverted
- [ ] Runtime < 10 min; first green run URL recorded here: —
- [ ] Branch protection requested/enabled (note who/when): —

### HR-06 — Portal robustness
- [ ] Error card + Retry + seq guard on queue / tickets / escalated / m-queue / m-ticket
- [ ] Settings hooks moved above early return; 0 `rules-of-hooks` eslint errors
- [ ] `app/error.tsx` + `app/global-error.tsx`
- [ ] Notification-rules calls via `apiFetch` with visible failure
- [ ] Vitest seed: `npm test` with 3 unit tests (user-messages, queueTiles) wired into CI
- [ ] Manual: API-down error cards + retry; project_admin settings no-crash; boundary renders; rules save error visible

### HR-07 — Webchat robustness
- [ ] Session ID persisted at startup (compatible with orchestrator session store)
- [ ] In-flight send lock with timeout release
- [ ] SRI + crossorigin on socket.io + exifr (exact versions)
- [ ] `app.js:301` innerHTML → textContent
- [ ] Static greps clean (innerHTML, integrity)
- [ ] Manual regression sweep executed (all 7 items in spec §Manual) — record date/tester: —

## Deviations log

| Date | Ticket | Deviation / adjacent finding | Action |
|---|---|---|---|
| — | — | — | — |

## Sprint close checklist
- [ ] All tickets `done`, CI green on integration branch
- [ ] Summary doc `docs/sprints/2026-07_hardening_tier1.md` written (June5 pattern)
- [ ] This folder moved to `docs/sprints/archive/`; sprints README updated
- [ ] `devils_advocate_codebase.md` re-scored (security, correctness, portal robustness, testing)
