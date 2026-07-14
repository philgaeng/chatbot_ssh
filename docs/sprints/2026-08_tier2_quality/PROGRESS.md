# Tier-2 Quality & Performance Sprint — Progress

> Update at **every commit** on a sprint branch. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · Source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §3 Tier 2.
> **Prerequisite gate:** ✅ Tier-1 merged to integration — `dev/organisation` fast-forwarded into `integration/seah-claude` (`4ad7ac09`, pushed 2026-07-13); this sprint runs on `dev/tier2-quality` (pushed, CI-triggered). Safety net for the H2-02 refactor is in place: HR-02 authz matrix (86 tests), HR-04 escalation suite (6), HR-06 vitest (3). Tier-1 CI was green at landing (run `28837101159`, 2026-07-07). **Confirm the fresh CI run on `dev/tier2-quality` is green before starting H2-02:** —

## Ticket status

Ordered for **robust single-threaded execution** (see rationale below). Workstream (WS) A=backend refactor, B=backend perf, C=portal, D=SEAH.

| Order | ID | Title | WS | Status | Commits | Sequencing rationale |
|---|---|---|---|---|---|---|
| 1 | H2-01 | OIDC refresh-grant in apiFetch | C | **review** | this commit | Code + 9 vitest tests green (tsc/eslint/build clean). Manual Keycloak sweep pending-human. Isolated from the backend; closes the last open headline finding (officer data-loss at token expiry); unblocks H2-06. |
| 2 | H2-02 | Split tickets.py; perform_action → engine/ | A | **review** | pin + passes 1–4 | Keystone refactor — all of B rebases on it. Passes 1–4 landed under the route-snapshot pin + HR-02 matrix (86) + HR-04 suite; 408 passed / 5 skipped unchanged. Only pending-human manual UI click-through remains. |
| 3 | H2-07 | Escalation test extension | A | todo | — | Thickens the engine net immediately after the refactor; "direct engine calls, one per action" only works once `perform_action` lives in `engine/`. Verifies H2-02's core move. |
| 4 | H2-03 | Authz matrix extension | A | todo | — | Broadens authz coverage (all actions × personas + unauthenticated sweep) on the split routers. Locks H2-02's authz behavior before backend behavior changes land. |
| 5 | H2-04 | Grievance sync watermark + paging | B | todo | — | Heaviest recurring query; behavior change now lands on a refactored, maximally-covered backend. Ships with its own crash-safety/paging tests + before/after timing. |
| 6 | H2-05 | Auth-dependency onboarding cache | B | todo | — | Latency win on the now-stable sync/auth path. Invalidation must hook every onboarding writer — do it after H2-04 settles that area. |
| 7 | H2-06 | Shared useTicketThread hook | C | todo | — | Portal dedup (~350 lines); consumes H2-01's `apiFetch`. Do after H2-01 has soaked so the auth path is stable beneath the refactor. |
| 8 | H2-08 | SEAH form mixin + Nepali repair | D | todo | — | **Start the translator packet at sprint open** (long human pole) — generate `translations_seah_review.csv` on day 1. Code merges last, gated on translator sign-off; parity/utterance tests green. |

### Robust execution order — why this sequence

The numbers above are the **single-threaded** order that keeps every step on verified ground:

1. **Fix the live bug first, in isolation.** H2-01 touches only the portal auth path — nothing else in Tier 2 can destabilize it, and it can't destabilize the backend refactor. It closes the last open headline finding, so the worst user-facing risk is gone before the risky work starts.
2. **Refactor under a net, then thicken the net.** H2-02 is the riskiest change; it goes in guarded by the Tier-1 HR-02 authz matrix + HR-04 escalation suite + a route-snapshot test written first. H2-07 then H2-03 immediately extend coverage on the *new* structure, so all later backend work builds on a maximally-tested engine (pin → refactor → extend — never refactor on thin coverage).
3. **Behavior changes only after the structure is stable and covered.** H2-04 (query change) and H2-05 (cache) land last on the backend, each with its own before/after evidence.
4. **Start the long human pole on day 1.** H2-08 needs a translator sign-off — a dependency no code can shorten — so send the review CSV at sprint open even though the code merges last.

**If parallelizing** (multiple engineers), the tracks are independent: backend critical path **H2-02 → {H2-03, H2-07} → H2-04 → H2-05**, portal **H2-01 → H2-06**, SEAH **H2-08** (human-gated). The serial numbers are the robust order when one engineer runs the whole sprint.

## Acceptance checklists

### H2-02 — Router split  *(review — invariant + passes 1–4 landed; 396 baseline unchanged + 12 new engine tests → 408 passed / 5 skipped)*
- [x] **Invariant**: route-surface snapshot pin (`tests/ticketing/test_route_snapshot.py` + `route_snapshot.txt`, 174 routes via `app.openapi()`) committed on the pre-refactor tree — `799615cf`
- [x] **Pass 1**: `_add_event` unified in `engine/events.py` (single definition; both former sites import it; orphaned `_id`/`_case_sensitivity`/`uuid` removed from escalation.py) — `b8c5ae31`
- [x] **Pass 2**: workflow helpers moved — `_find_supervisor_user_id` → `engine/workflow_engine.py`; `_validate_step_assignee` → engine predicate `is_step_assignee_eligible` (router keeps the 422); `_next_step` was dead in the router → deleted — `817128d4`
- [x] **Pass 3**: `perform_action` branches → `engine/ticket_actions.py` (7 handlers `(db, ticket, actor, payload) → ActionOutcome`; typed `ActionError` — no HTTP in engine). Router is now validate + authz guards → `ACTION_HANDLERS[action]` dispatch → apply outcome (reopen-clears-archive, commit, refresh, enqueue, response). Router −415 net lines. — this commit
- [x] **Pass 4**: `routers/tickets/` package (7 modules: `crud`, `actions`, `files`, `pii`, `collaboration`, `summary`, `_shared`); URL surface identical — route-snapshot green (174/174, 0 added/0 removed) verified both host-side (`app.openapi()`) and in-container (full suite). Mount in `main.py` unchanged (`from ticketing.api.routers import tickets` → `tickets.router`). Endpoint/helper bodies moved byte-identical. — this commit
- [x] In-function imports eliminated in the new module (`engine/ticket_actions.py` — all imports at module top; pyflakes-clean)
- [x] Full suite + HR-02 matrix green **unchanged** (396 baseline identical; route-snapshot + 86-row authz matrix + escalation all green)
- [x] `test_ticket_actions_unit.py` — 12 direct engine calls (happy path per action + `ActionError` guard contract), rolled back per test, no residue
- [ ] Manual UI click-through identical — **PENDING-HUMAN** (no browser in this env; route surface proven identical by snapshot)

**Deviations (H2-02):**
- `_next_step` in the router was dead code (no caller; `services/supervisor.py` keeps its own copy) → deleted rather than moved. `_first_step` is likewise unused but left untouched (not in the ticket's named scope).
- `_validate_step_assignee` moved as a **bool predicate** (`is_step_assignee_eligible`) rather than a typed-exception raiser — simpler for a single validator, keeps HTTP out of the engine; the 422 + message stays at the router call site (behavior-identical).
- **Pass 3:** `ActionError` carries an explicit `status_code` (default 422). Every current action error is a 422, but the field keeps the router mapping (`ActionError → HTTPException(status_code, detail)`) an exact 1:1, so a future non-422 branch needs no special-casing.
- **Pass 3:** helpers `_ticket_has_image_attachment`, `_extract_mentions`, `_get_viewer_ids`, `_auto_acknowledge_if_assigned_actor`, `_has_resolution_record_event` moved with the branches into the engine. The router imports two back — `_auto_acknowledge_if_assigned_actor` (used by `reply_to_complainant`) and `_has_resolution_record_event` (used by the two resolved-summary endpoints). `_now`/`_actor_role` are duplicated in the engine per the repo's per-module convention (not shared-imported).
- **Pass 3 (pre-existing debt, not introduced here):** pyflakes on the touched router flags 5 dead items that are **already present at HEAD** — unused imports `_apply_step_tier_roles`, `auto_assign_for_workflow_step`, `_scope_candidates`, `country.Location`, and an unused `rerouted` local in `validate_ticket_classification`. Left untouched to keep the diff surgical (unrelated to `perform_action`); logged in [`followups/`](followups/) + TODO.md for the cleanup sprint. Pass 3 introduced **no new** pyflakes findings. *(Resolved in Pass 4 — see below.)*
- **Pass 4 — module layout vs spec:** the [split spec](02-backend-router-split-spec.md) §1 sketches `crud`/`actions`/`files`/`pii`/`notes_tasks_viewers`/`_shared`. Landed 7 modules — spec-exact on `crud`, `actions` (incl. `reply`/`inbound` messaging, per spec), `files`, `pii`, `_shared`. Two "split further if natural" (spec-permitted) deviations: **`collaboration.py`** holds `sla`/`teammates`/`seen`/`informed`/`reply-owner` (the spec's `notes_tasks_viewers` bucket — but notes/tasks/viewers are *separate* routers, not in `tickets.py`, so renamed for what's actually here); **`summary.py`** holds `resolved-summary` (GET/POST) + `findings` (the spec placed `resolved-summary` in `crud` — pulled out so the AI-closure endpoints are one cohesive, smaller module).
- **Pass 4 — dead code folded in (resolves the Pass 3 debt row above):** splitting rewrote the import block, so the **4 dead imports were not carried across** (each submodule imports only what it uses). The **`rerouted` binding was dropped** in `validate_ticket_classification` (the `maybe_reroute_ticket_workflow` call is kept — it re-resolves the workflow as a side effect; its `-> bool` return has no response field). Also removed **3 dead private helpers** (`_lookup_workflow`, `_first_step`, `_is_viewer`) — zero call sites, imported nowhere; `_first_step` was the item Pass 2 had "left untouched." `pyflakes` clean on all 7 modules; followup doc + TODO row closed.
- **Pass 4 — shared helpers:** `_enqueue_celery`/`_now`/`_new_id`/`_actor_role` (cross-cutting, used by ≥2 submodules) live in `_shared.py`; single-use helpers/constants co-locate with their sole caller (`_can_resolve_ticket`→`actions`, `_step_supervisor_available`/`_can_assign_ticket`/`_COMPLAINANT_EDIT_ROLES`→`crud`, `_resolve_attachment_path`/`_media_type_for_path`→`files`, `_FINDINGS_ROLES`→`summary`, reveal request models→`pii`). Aggregation is `include_router` per submodule in `__init__.py` (no path prefixes) — the snapshot is a method+path **set**, so include order is irrelevant. The pre-existing unreachable `return False` at the tail of `_media_type_for_path` was moved **verbatim** (out of Pass 4's structural scope).

### H2-03 — Authz matrix extension
- [ ] All action types × personas
- [ ] Admin-surface endpoints × admin ladder (vs spec 11 — discrepancies logged, not codified)
- [ ] Unauthenticated sweep over `app.routes` (public set excluded)
- [ ] Runs < 2 min in CI
- [ ] Spec-vs-code discrepancies found: —

### H2-07 — Escalation extension
- [ ] Full L1→L3 chain on seeded workflow
- [ ] SEAH-track escalation isolation
- [ ] Manual-then-auto interleaving (API-level)
- [ ] Notification side-effect assertions (one per transition)

### H2-04 — Sync watermark
- [ ] Modification column verified on all update paths (gaps listed): —
- [ ] Watermark in `ticketing.settings`; advance-after-commit; batch paging
- [ ] `full=True` escape hatch documented
- [ ] Cache refresh removed from GET (zero writes on detail reads)
- [ ] Sync tests: no-op run = 0 rows; single-change; paging; crash-safety; full sweep
- [ ] Before/after timing on seeded DB: — → —

### H2-05 — Auth-dependency cache
- [ ] TTL cache (setting `TICKETING_AUTH_SYNC_TTL_SECONDS`, default 300, 0 = off)
- [ ] Invalidation on webhook activation + invite/resend (all `officer_onboarding` writers hooked)
- [ ] Tests: once-per-TTL, expiry, invalidation, TTL=0 parity, warm = no writes
- [ ] Latency before/after (50 × GET /tickets): — → —
- [ ] Invite → first login flips status without TTL wait

### H2-01 — OIDC refresh
- [x] `refreshTokens` + single-flight (module `refreshPromise`); `apiFetch` proactive (60 s) + reactive 401 → refresh → retry-once (`lib/auth/oidc-auth.ts`, `lib/api.ts`)
- [x] Skew check corrected (`session-expired.ts` `- 30_000` → `+ 30_000`, via new `isAccessTokenExpiringSoon`); 401 detection now status-code-based in `apiFetch` (substring `isSessionExpiredResponse` kept only at the 4 multipart/blob sites — see Deviations)
- [x] AuthProvider mount check refreshes instead of redirecting; redirects only on refresh failure (`AuthProvider.tsx`)
- [x] Logout revokes refresh token via back-channel `logout` POST (keepalive), incl. the sessionStale path (`oidc-auth.ts signOut`)
- [x] CSPRNG `state` + `nonce` (`crypto.getRandomValues`, was `Math.random`); nonce verified in callback; `state`/`verifier`/`nonce` all in sessionStorage (cross-tab login fails cleanly at the state check)
- [x] Vitest: single-flight (3→1 POST), 401→refresh→retry→success, 401→refresh-fail→`handleSessionExpired` once, proactive near-expiry, skew regression — **9 new tests green** (`lib/auth/session-expired.test.ts`, `lib/auth/oidc-auth.test.ts`, `lib/api.test.ts`); full `npm test` 35/35; `tsc --noEmit` clean; `eslint` 0 errors; `next build` clean
- [~] Manual: 1-min token lifespan / 5-min typing / no-data-loss + replayed-refresh-token rejected — **PENDING-HUMAN** (no browser + live Keycloak in this env; needs the auth-profile stack per `DOCKER.md`). Record date/tester: —

### H2-06 — Thread hook
- [ ] `lib/useTicketThread.ts` + `lib/threadCommands.ts`; both pages consume; ~300+ lines net deleted
- [ ] Drift resolutions (mobile `system` filter; command ordering) logged as intentional deviations
- [ ] Vitest: parseThreadCommand cases; chip-filter parity
- [ ] tsc + eslint + build green; side-by-side manual parity check

### H2-08 — SEAH quality
- [ ] `seah_shared.py` mixin; thresholds preserved exactly (`>3` / `>=8`)
- [ ] 5× multiselect helper deduped; dead commented blocks removed
- [ ] Utterance blocks merged (lookup keys verified/aliased — no mechanism change)
- [ ] Mechanical NE fixes (:44/:48 typos, :90 tripled phrase)
- [ ] `docs/seah/translations_seah_review.csv` generated; `needs_translator` count: —
- [ ] English-only validator messages routed through utterances
- [ ] Parity + utterance-integrity tests green; full SEAH suites green
- [ ] Manual EN/NE walk-through (victim/anon/witness/focal)
- [ ] **Translator sign-off:** name — · date —

## Deviations log

| Date | Ticket | Deviation / adjacent finding | Action |
|---|---|---|---|
| 2026-07-13 | H2-01 | **Scope: only `apiFetch` got refresh+retry.** `api.ts` has 4 other fetch sites that hard-logout on 401 via `isSessionExpiredResponse` — a blob GET (`fetchAuthenticatedBlobUrl`), two multipart uploads (attachment, org-import), and the XLSX export. Spec item 3 scoped the change to `apiFetch:214-236`. | Left the 4 sites as-is (behavior unchanged — no regression). `apiFetch`'s proactive 60 s refresh keeps the token fresh during active use, so an upload shortly after JSON activity is unlikely to hit expiry. Deferred with a tracked ticket: [`followups/apifetch-refresh-non-json-sites.md`](followups/apifetch-refresh-non-json-sites.md) (+ TODO.md row). |
| 2026-07-13 | H2-01 | **Spec's "AuthProvider periodic check (:309-317)" is actually the mount-time expiry check** — there is no `setInterval` in the provider. | Implemented as refresh-on-mount (try silent refresh before redirecting). No background timer added — `apiFetch`'s proactive refresh already covers active use; a polling timer would be new scope. |
| 2026-07-13 | H2-01 | **Nonce verification is strict** (throws on id_token `nonce` mismatch) — standard OIDC replay protection, but a new failure path in the callback. | Happy path validated by `next build` + the callback-flow reasoning; the live cross-check lands with the pending-human Keycloak sweep. If a realm quirk drops the nonce claim, the guard only fires when a nonce was *sent* AND an id_token is present. |

## Sprint close checklist
- [ ] All tickets `done`, CI green on integration branch
- [ ] Summary doc `docs/sprints/2026-08_tier2_quality.md` written
- [ ] Folder moved to `docs/sprints/archive/`; sprints README updated
- [ ] `devils_advocate_codebase.md` re-scored (architecture, performance, maintainability, portal dimensions)
