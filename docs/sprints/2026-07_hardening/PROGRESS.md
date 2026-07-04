# Tier-1 Hardening Sprint — Progress

> Update at **every commit** on a sprint branch. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · Source review: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md)

## Ticket status

| ID | Title | Workstream | Status | Branch | Commits | Notes |
|---|---|---|---|---|---|---|
| HR-05 | CI pipeline (pytest + tsc + eslint + docs-links) | C | review | `dev/hardening` | `8d22727f` (pushed) | Committed + pushed. **Live Actions verification blocked: `gh` not authenticated in the dev shell.** Pending: first-run status/URL, deliberate-failure checks, branch protection — need `gh auth login` or the repo owner to check the Actions tab. Backend-tests job (Postgres+migrations+seed+pytest) is the one piece not run locally; first CI run confirms it. |
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
- [x] `.github/workflows/ci.yml`: backend-tests (postgres:15 service + public→ticketing→ops migrations), ui-checks (tsc + eslint + build), docs-links — all three jobs written, triggers on `pull_request` + push to `main`/`integration/**`/`dev/**`
- [x] 4 pytest collection errors resolved (env/requirements) — `jose`/`reportlab` already present in `requirements.grm.txt:10,14`; confirmed structurally (grep), **not** run live (host shell is Anaconda py3.13, no jose/reportlab — see Deviations)
- [x] ESLint baseline: `eslint.config.mjs` rules-override (dated comment referencing HR-05/spec §2) downgrades `react-hooks/set-state-in-effect` **plus** `react/no-unescaped-entities`, `react-hooks/static-components`, `react-hooks/purity`, `react-hooks/immutability` to `warn`, reserving the error channel for crash-class `react-hooks/rules-of-hooks` (left as error). Verified `npx eslint .` = **exactly 2 errors** (the two `rules-of-hooks` in `app/settings/page.tsx:4599,4612`, HR-06's job) + 135 warnings. See Deviations for the extended-baseline rationale.
- [ ] Deliberate-failure checks performed (tsc, doc link) and reverted — **not done**: requires pushing to GitHub and observing Actions runs; this agent was instructed not to commit/push (orchestrator's explicit override of the runbook). Pending orchestrator.
- [ ] Runtime < 10 min; first green run URL recorded here: — **pending orchestrator** (needs a real push/PR to measure). Locally: `npx tsc --noEmit` ~12s, `npx eslint .` ~seconds, `npm run build` ~19s (no backend env, no `.env.local`), docs-links script ~instant (565 links, 0 broken). Backend job (Postgres + 3 migrations + seed + pytest) not run live locally — see Deviations.
- [ ] Branch protection requested/enabled (note who/when): — **manual step for repo admin** (`gh` would need admin on `philgaeng/chatbot_ssh`); require `backend-tests`, `ui-checks`, `docs-links` as required checks on PRs to `main` and `integration/**` once the first few runs are green. Not performed by this agent.

**Notes:**
- Python pinned to **3.10** in the workflow (matches root `Dockerfile: FROM python:3.10-slim`), **not 3.11** as the spec text guessed — spec itself flagged this as "verify before pinning."
- Node pinned to **20** (matches `channels/ticketing-ui/Dockerfile: FROM node:20-alpine`).
- The ui-checks job is **expected to be red** until HR-06 fixes the 2 `react-hooks/rules-of-hooks` errors in `app/settings/page.tsx` (lines ~4599/4612) — documented, expected state per spec §2. The eslint baseline was extended (see Deviations) so the gate is red for **exactly those 2** crash-class errors and nothing else; 11 other pre-existing non-crash errors were downgraded to warnings (still surfaced, logged for a future portal lint-cleanup ticket).
- This agent did **not** commit or push; all changes are left in the working tree on `dev/hardening` for the orchestrator to review, commit, push, open the PR, and run the deliberate-failure/branch-protection steps.

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
| 2026-07-04 | HR-05 | Spec §1 guessed Python 3.11 for CI ("verify before pinning"). Root `Dockerfile` is `python:3.10-slim`. | Pinned CI to 3.10. No code change needed. |
| 2026-07-04 | HR-05 | Docs disagree on 3-stream migration order: `docs/deployment/03_operations.md` §3 ("Standard order... **ticketing → public → ops**") and `Makefile`'s `migrate_all: migrate_ticketing migrate_public migrate_ops` both say ticketing-first; but §2's Startup Runbook (bring-up-fresh-host sequence, the literal bash commands) runs **public → ticketing → ops**. Orchestrator's task explicitly directed `public → ticketing → ops` for CI, matching §2. Implemented that order in `ci.yml`. | Followed orchestrator's explicit directive (matches §2). Flagging the doc self-inconsistency (§2 vs §3/Makefile) for someone to reconcile — did not edit either doc, out of scope for HR-05. |
| 2026-07-04 | HR-05 | Neither the spec nor the runbook mentions seeding demo data before pytest — both only say "migrate, then pytest." But `tests/ticketing/test_officer_assignment.py` states in its own docstring "Requires: migrated ticketing schema + seed (kl_road_standard / mock_tickets)", and it plus `test_project_routing.py` / `test_entity_codes.py` use fixtures (`kl_road_project`, `PROJECT_KL_ROAD`) that `.scalar_one()` a `KL_ROAD` project row that only exists after seeding — not after migrations alone. Confirmed empirically that `import_locations_json.py`'s "required" locations are only verified, never inserted, by `kl_road_standard.seed_locations()`. Without a seed step, ~3 integration-marked test files (dozens of tests) would fail on a bare freshly-migrated CI DB, and the backend-tests job would be red for an *undocumented* reason. | Added a "Seed KL Road locations + demo workflows" step after the 3 migrations, running the exact commands from the dev/SSH Startup Runbook (`docs/deployment/03_operations.md` §2 step 4): `ticketing.seed.import_locations_json --country NP --en ... --ne ... --max-level 3` then `ticketing.seed.mock_tickets --reset`. This is a deviation from the literal spec text (which named only migrations) — flagging for orchestrator confirmation; not application-code, pure CI wiring, but expands the job beyond what §1 described. |
| 2026-07-04 | HR-05 | ESLint baseline: spec/runbook expected exactly 2 `react-hooks/rules-of-hooks` errors to remain after downgrading `set-state-in-effect`, but a real `npx eslint .` showed **13 errors** initially (baseline 137/85/52, matching spec recon). Beyond the 2 `rules-of-hooks` there were 11 more pre-existing *non-crash* errors across 4 rule families the spec never enumerated: `react/no-unescaped-entities` ×3 (`app/m/tasks/page.tsx:53`, `app/qr-codes/page.tsx:159`), `react-hooks/static-components` ×3 (`app/m/tickets/[id]/page.tsx:360-362`), `react-hooks/purity` ×3 (`app/queue/page.tsx:139,235,295` — `Date.now()` in render), `react-hooks/immutability` ×2 (`app/tickets/[id]/closure/page.tsx:103`, `components/reports/SummaryTab.tsx:117`). | **Resolved per spec §2 stated intent** ("the error channel is reserved for crash-class findings"), per orchestrator direction: extended the `eslint.config.mjs` rules-override to downgrade all four families (`react/no-unescaped-entities`, `react-hooks/static-components`, `react-hooks/purity`, `react-hooks/immutability`) to `warn` alongside `set-state-in-effect`. `react-hooks/rules-of-hooks` **stays an error** — untouched; those 2 are HR-06's job. Verified: **exactly 2 errors** (the two `rules-of-hooks` at `app/settings/page.tsx:4599,4612`) + 135 warnings; `tsc --noEmit` and `npm run build` still green. The 11 downgraded findings are **not lost** — they stay visible as warnings and are logged for a **future portal lint-cleanup ticket** (esp. the React-19-compiler advisories static-components / purity / immutability, plus no-unescaped-entities). ui-checks stays red for exactly the 2 documented `rules-of-hooks` errors until HR-06 lands. |

## Sprint close checklist
- [ ] All tickets `done`, CI green on integration branch
- [ ] Summary doc `docs/sprints/2026-07_hardening_tier1.md` written (June5 pattern)
- [ ] This folder moved to `docs/sprints/archive/`; sprints README updated
- [ ] `devils_advocate_codebase.md` re-scored (security, correctness, portal robustness, testing)
