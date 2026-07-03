# Tier-2 Quality & Performance Sprint — Progress

> Update at **every commit** on a sprint branch. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · Source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §3 Tier 2.
> **Prerequisite gate:** Tier-1 sprint merged (CI green, HR-02 matrix, HR-04 suite, HR-06 vitest). Confirm before starting: —

## Ticket status

| ID | Title | Workstream | Status | Branch | Commits | Notes |
|---|---|---|---|---|---|---|
| H2-02 | Split tickets.py; perform_action → engine/ | A | todo | — | — | Pure refactor; land before B |
| H2-03 | Authz matrix extension | A | todo | — | — | After H2-02 |
| H2-07 | Escalation test extension | A | todo | — | — | After H2-02 |
| H2-04 | Grievance sync watermark + paging | B | todo | — | — | Rebase on A |
| H2-05 | Auth-dependency onboarding cache | B | todo | — | — | After H2-04 |
| H2-01 | OIDC refresh-grant in apiFetch | C | todo | — | — | |
| H2-06 | Shared useTicketThread hook | C | todo | — | — | After H2-01 |
| H2-08 | SEAH form mixin + Nepali repair | D | todo | — | — | Human translator sign-off required |

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
