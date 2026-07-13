# Tier-2 Quality & Performance Sprint — Progress

> Update at **every commit** on a sprint branch. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · Source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §3 Tier 2.
> **Prerequisite gate:** ✅ Tier-1 merged to integration — `dev/organisation` fast-forwarded into `integration/seah-claude` (`4ad7ac09`, pushed 2026-07-13); this sprint runs on `dev/tier2-quality` (pushed, CI-triggered). Safety net for the H2-02 refactor is in place: HR-02 authz matrix (86 tests), HR-04 escalation suite (6), HR-06 vitest (3). Tier-1 CI was green at landing (run `28837101159`, 2026-07-07). **Confirm the fresh CI run on `dev/tier2-quality` is green before starting H2-02:** —

## Ticket status

Ordered for **robust single-threaded execution** (see rationale below). Workstream (WS) A=backend refactor, B=backend perf, C=portal, D=SEAH.

| Order | ID | Title | WS | Status | Commits | Sequencing rationale |
|---|---|---|---|---|---|---|
| 1 | H2-01 | OIDC refresh-grant in apiFetch | C | todo | — | Isolated from the backend; closes the last open headline finding (officer data-loss at token expiry). Bank the highest-value / lowest-risk fix first; unblocks H2-06. |
| 2 | H2-02 | Split tickets.py; perform_action → engine/ | A | todo | — | Keystone refactor — all of B rebases on it. Write the route-snapshot test **first**; land under the existing HR-02 matrix (86) + HR-04 suite before any dependent work. |
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

### H2-02 — Router split
- [ ] `routers/tickets/` package; URL surface identical (route-snapshot test)
- [ ] `perform_action` branches → `engine/ticket_actions.py` (typed exceptions, no HTTP in engine)
- [ ] Workflow helpers moved to engine; `_add_event` unified in `engine/events.py` (single definition)
- [ ] In-function imports eliminated in the new modules
- [ ] Full suite + HR-02 matrix green **unchanged**
- [ ] `test_ticket_actions_unit.py` — direct engine calls, one per action
- [ ] Manual UI click-through identical

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
- [ ] `refreshTokens` + single-flight; apiFetch proactive (60 s) + reactive 401 retry-once
- [ ] Skew check corrected; status-code-based 401 detection
- [ ] AuthProvider refreshes instead of redirecting; redirect only on refresh failure
- [ ] Logout revokes refresh token (incl. sessionStale path)
- [ ] CSPRNG state + nonce + same-storage state/verifier
- [ ] Vitest: single-flight, 401-retry, proactive, skew regression
- [ ] Manual: 1-min token lifespan, 5-min typing, no data loss; replayed refresh token rejected

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
| — | — | — | — |

## Sprint close checklist
- [ ] All tickets `done`, CI green on integration branch
- [ ] Summary doc `docs/sprints/2026-08_tier2_quality.md` written
- [ ] Folder moved to `docs/sprints/archive/`; sprints README updated
- [ ] `devils_advocate_codebase.md` re-scored (architecture, performance, maintainability, portal dimensions)
