# Tier-1 Hardening Sprint — Progress

> Update at **every commit** on a sprint branch. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · Source review: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md)

## Ticket status

| ID | Title | Workstream | Status | Branch | Commits | Notes |
|---|---|---|---|---|---|---|
| HR-05 | CI pipeline (pytest + tsc + eslint + docs-links) | C | review | `dev/hardening` | `8d22727f` (pushed) | Committed + pushed. **Live Actions verification blocked: `gh` not authenticated in the dev shell.** Pending: first-run status/URL, deliberate-failure checks, branch protection — need `gh auth login` or the repo owner to check the Actions tab. Backend-tests job (Postgres+migrations+seed+pytest) is the one piece not run locally; first CI run confirms it. |
| HR-01 | Fail-closed auth | A | review | `dev/hardening` | uncommitted (working tree) | Code+tests+docs done; 8/8 in-container green + 4/4 auth-dep regression. Orchestrator to commit HR-01 first. |
| HR-02 | `require_ticket_access` on file/PII endpoints | A | review | `dev/hardening` | uncommitted (working tree) | `ticket_access.py` + tickets.py sweep + matrix. In-container: matrix **86 passed**; full `tests/ticketing` 225 passed / 1 skip / 4 pre-existing fails (confirmed on baseline HEAD). Commit after HR-01. |
| HR-03 | Unique partial index `tickets.grievance_id` | B | todo | — | — | Rebase on A (tickets.py) |
| HR-04 | Escalation savepoints + row locking | B | todo | — | — | After HR-03 |
| HR-06 | Portal error states + settings crash + error.tsx | D | todo | — | — | Coordinates with HR-05 eslint gate |
| HR-07 | Webchat session/send-lock/SRI/banner | E | todo | — | — | |

## Acceptance checklists

### HR-01 — Fail-closed auth
- [x] `TICKETING_ENV` (default `production`) in ticketing settings; backend mirror var (`BACKEND_ENV`, read via `os.environ` in `backend/api/`)
- [x] Startup guard raises on missing `keycloak_issuer` / `ticketing_secret_key` outside dev (`main._assert_auth_configured` + `backend.fastapi_app._assert_backend_auth_configured`)
- [x] Per-request 503 fallback (defense in depth); demo fallback dev-only (`verify_api_key`, `_resolve_user_identity`, backend `_ticketing_auth_check`)
- [x] Header-identity default role = least privilege (internal callers re-verified — only sender is the Next dev-bypass proxy, which always sends explicit `x-internal-role`)
- [x] `docker-compose.override.yml` sets dev (`backend`); grm/aws/prod files do NOT. Demo `ticketing_api` (:5002) reads `TICKETING_ENV=dev` from `env.local` (see Deviations — ticketing_api is not in the base compose)
- [x] `tests/ticketing/test_fail_closed_auth.py` — 6 acceptance cases (8 test fns) **green in-container: 8 passed**
- [x] `13_security.md` "Fail-closed guarantees" section added (§2.1)
- [x] Manual: startup guard verified via TestClient lifespan (2 startup-raise tests); dev bypass + explicit-role paths verified green

### HR-02 — Ticket access dependency
- [x] `ticketing/api/ticket_access.py` single-source gate (exists/SEAH/scope/visibility) — `assert_ticket_visibility` reproduces `get_ticket` exactly
- [x] File-id resolution path (`require_file_access`) incl. `public.file_attachments` (officer `ticket_files` first, then chatbot files → owning ticket via `grievance_id`)
- [x] Applied to all per-ticket endpoints (18 converted + `get_ticket` reference); inline SEAH/scope checks removed. Archived checks + per-action role checks kept inline. Only `inbound_complainant_message` (x-api-key system call) left as-is
- [x] PII masking rules (TP-15) unchanged (`get_ticket_pii` only gains the scope gate; masking body untouched)
- [x] `tests/ticketing/test_ticket_access_matrix.py` persona×endpoint matrix — **86 passed** in-container
- [x] Existing suite: no NEW regressions. Full `tests/ticketing` = 225 passed, 1 skipped, 4 **pre-existing** fails (verified identical on baseline HEAD — see Deviations), 1 pre-existing collection error resolved by syncing current tree
- [x] Manual: SEAH officer attachment (`GET /attachments/{file_id}`) as in-scope standard officer ⇒ **403** (matrix `test_seah_file_endpoints_blocked_for_standard_officer`); super_admin download ⇒ 200; reveal flow: gate moved to front, reveal-session policy unchanged

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
| 2026-07-05 | HR-01 | **Compose placement of `TICKETING_ENV=dev`.** Spec/runbook said "override.yml ONLY, never grm/aws/prod." But the base `docker-compose.yml` has **no `ticketing_api` service** (it lives in `docker-compose.grm.yml`), and the demo `ticketing_api` (:5002) hardcodes `KEYCLOAK_ISSUER: ""` + is launched by `dcg` (`-f docker-compose.yml -f docker-compose.grm.yml`, which does **not** load override.yml). So a bare `ticketing_api` stanza in override.yml would (a) be inert for the real demo path and (b) break `docker compose up` for chatbot-only devs (incomplete service, no build/image). | Set `BACKEND_ENV=dev` in `docker-compose.override.yml` (`backend` exists in base → valid) AND set `TICKETING_ENV=dev` + `BACKEND_ENV=dev` in **`env.local`** (gitignored; read via `env_file`/`--env-file` by the demo stack — this is the "env.local template mention" the spec asked for). grm/aws/prod overlays untouched → production still fails closed (default `production`, must configure real auth). Documented in `DOCKER.md`. **Note:** `env.local` is gitignored, so the committed HR-01 artifacts are the code + override.yml + docs; operators must add `TICKETING_ENV=dev` to their own `env.local` (or the demo :5002 refuses to boot — intended fail-closed behavior, now documented). |
| 2026-07-05 | HR-02 | **Endpoint → old gates → new gates** (tickets.py sweep). `require_ticket_access` = exists(404)+SEAH+admin/assignee/viewer/pending-task/scope, reproducing `get_ticket` exactly. `V` = behavior changes for a previously-over-permitted persona (hole closed — desired). Endpoints whose personas were already correct are unchanged. `get_ticket` (detail) = reference, inline block → `assert_ticket_visibility` (identical). Converted to `Depends(require_ticket_access)`: `PATCH /classification` `[V]`, `PATCH /{id}` `[V]`, `PATCH /complainant` `[V]`, `POST /actions` `[V]`, `POST /reply` `[V]`, `GET /sla` `[V]`, `GET /teammates` `[V]`, `POST /seen` `[V, also gained missing SEAH gate]`, `POST /informed` `[V]`, `PUT /complainant-reply-owner` `[V]`, `GET /files` `[V, archived check kept]`, `POST /attachments` upload `[V, archived 409 kept]`, `GET /attachments` list `[V]`, `GET /pii` `[V — the named jurisdiction hole]`, `GET /resolved-summary` `[V]`, `POST /resolved-summary` `[V, findings-role kept]`, `POST /findings` `[V, findings-role kept]`, `POST /reveal` + `/reveal/close` `[V, reveal policy unchanged]`. Via `require_file_access`: `GET /files/{file_id}` `[V — named SEAH hole]`, `GET /attachments/{file_id}` `[V — named: was auth-only]`. Left as-is: `POST /tickets` + `POST /inbound` (x-api-key system calls, no CurrentUser). | All flagged `V` are the intended class fix (out-of-scope / non-SEAH personas lose access they should never have had). Already-correct personas (admin / assignee / viewer / in-scope) unchanged — asserted by the matrix. |
| 2026-07-05 | HR-02 | **`require_file_access` is source-agnostic** (tries `ticketing.ticket_files` then `public.file_attachments`), so `GET /attachments/{file_id}` and `GET /files/{file_id}` can now each resolve *either* file source (previously each was single-source). This is a minor behavior expansion, but always visibility-gated and each endpoint keeps its own disk-resolution (`os.path.isfile` vs `_resolve_attachment_path`), so a mismatched-source id typically still 404s at the disk stage. 404 message for a missing officer attachment changed "Attachment not found" → "File not found". | Accepted: spec asked for one `require_file_access` covering both tables; expansion is strictly safer (was: no gate at all). Flagged for awareness. |
| 2026-07-05 | HR-02 | **4 pre-existing test failures + 1 collection error, NOT caused by HR-01/HR-02.** Failures: `test_auth_dependencies.py::test_country_admin_can_get_and_post_scopes`, `test_effective_role_keys.py::test_enrich_user_prefers_db_over_stale_jwt`, `test_officer_assignment.py::TestSupervisorFallback::test_l1_falls_back_to_supervisor_when_no_l1_officer`, `test_roles_crud.py::test_seah_country_admin_cannot_create_project` — verified they fail **identically on baseline HEAD** (temporarily swapped `git show HEAD:` versions of all my changed files into the container; still 4 failed). These are seed/data-drift issues on the container DB, pre-dating this workstream. Also `test_admin_scope_keycloak.py` had a collection ImportError (`officer_invite_setup_pending`) purely because the running container image was stale vs the current tree — resolved by `docker cp` of the current `ticketing/` (symbol exists at `officer_admin.py:421`); not a code issue. | Flagged for the owners of those areas (scopes / role-keys / assignment / roles-crud). Out of scope for HR-01/HR-02 — no action taken. |
| 2026-07-05 | HR-01 | **`mark_events_seen` (`POST /tickets/{id}/seen`) had NO SEAH gate at all** (only a ticket-exists check) — a non-SEAH officer could clear their own event badges on a SEAH ticket. Not one of the 4 review-listed fail-open branches; found during the dependency sweep. | Flagged here; the gate is added in HR-02 (this endpoint now goes through `require_ticket_access`, which enforces SEAH+scope). |
| 2026-07-04 | HR-05 | ESLint baseline: spec/runbook expected exactly 2 `react-hooks/rules-of-hooks` errors to remain after downgrading `set-state-in-effect`, but a real `npx eslint .` showed **13 errors** initially (baseline 137/85/52, matching spec recon). Beyond the 2 `rules-of-hooks` there were 11 more pre-existing *non-crash* errors across 4 rule families the spec never enumerated: `react/no-unescaped-entities` ×3 (`app/m/tasks/page.tsx:53`, `app/qr-codes/page.tsx:159`), `react-hooks/static-components` ×3 (`app/m/tickets/[id]/page.tsx:360-362`), `react-hooks/purity` ×3 (`app/queue/page.tsx:139,235,295` — `Date.now()` in render), `react-hooks/immutability` ×2 (`app/tickets/[id]/closure/page.tsx:103`, `components/reports/SummaryTab.tsx:117`). | **Resolved per spec §2 stated intent** ("the error channel is reserved for crash-class findings"), per orchestrator direction: extended the `eslint.config.mjs` rules-override to downgrade all four families (`react/no-unescaped-entities`, `react-hooks/static-components`, `react-hooks/purity`, `react-hooks/immutability`) to `warn` alongside `set-state-in-effect`. `react-hooks/rules-of-hooks` **stays an error** — untouched; those 2 are HR-06's job. Verified: **exactly 2 errors** (the two `rules-of-hooks` at `app/settings/page.tsx:4599,4612`) + 135 warnings; `tsc --noEmit` and `npm run build` still green. The 11 downgraded findings are **not lost** — they stay visible as warnings and are logged for a **future portal lint-cleanup ticket** (esp. the React-19-compiler advisories static-components / purity / immutability, plus no-unescaped-entities). ui-checks stays red for exactly the 2 documented `rules-of-hooks` errors until HR-06 lands. |

## Sprint close checklist
- [ ] All tickets `done`, CI green on integration branch
- [ ] Summary doc `docs/sprints/2026-07_hardening_tier1.md` written (June5 pattern)
- [ ] This folder moved to `docs/sprints/archive/`; sprints README updated
- [ ] `devils_advocate_codebase.md` re-scored (security, correctness, portal robustness, testing)
