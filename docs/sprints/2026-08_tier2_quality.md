# Sprint summary — August 2026: Tier-2 Quality & Performance

> Original specs, tracker, and follow-ups: [`archive/2026-08_tier2_quality/`](archive/2026-08_tier2_quality/) (PROGRESS.md, per-workstream specs, `followups/`) · Source review: [`../reviews/devils_advocate_codebase.md`](../reviews/devils_advocate_codebase.md) §3 Tier 2 · Branch: `dev/tier2-quality`
> **Status: code-complete, all tickets `review`.** Pending-human: the browser/Keycloak manual sweeps (H2-01/02/06) and the SEAH EN/NE webchat walk-through (H2-08); CI-on-integration + merge.

## Goal

Land the eight Tier-2 quality/performance tickets (H2-01…08) plus the deferral follow-ups the earlier sprints logged — the architecture, performance, maintainability, portal, and conversation-layer dimensions that Tier-1 hardening deliberately left flat.

## Delivered

- **H2-01 — OIDC refresh-grant in `apiFetch`** (portal): proactive (<60 s) refresh + single-flight `refreshTokens`; `401 → refresh → retry-once`; refresh-on-mount; back-channel logout; CSPRNG `state`/`nonce`. Ends officer data-loss at token expiry. 9 vitest.
- **H2-02 — split `tickets.py` + engine extraction** (backend): 2,414-line God router → `routers/tickets/` package (7 modules) + `engine/ticket_actions.py` (`perform_action` handlers, no HTTP in the engine). Route-surface snapshot pin (174 routes) proves identical URL surface; 12 engine unit tests.
- **H2-03 — authz matrix extension** (backend): all actions × personas + admin ladder + unauthenticated sweep (118 tests). Surfaced 3 authz gaps → **fixed in the authz-gaps follow-up** (below).
- **H2-04 — grievance-sync watermark + paging** (backend): the every-2-min O(all-time) full scan → keyset-incremental (`(grievance_modification_date, grievance_id)` watermark in `ticketing.settings`, batch paging, crash-safe advance, `full=True` sweep + daily beat backstop). GET ticket-detail cache write-back removed (idempotent reads). Bench: 72.9 ms → 1.0 ms/tick at 5000 grievances.
- **H2-05 — auth-dependency onboarding cache** (backend): in-process TTL cache (`TICKETING_AUTH_SYNC_TTL_SECONDS`=300, 0=off) throttles the per-request onboarding sync; invalidation hooked at the two low-level `officer_onboarding` writers. ~1.6 ms/req eliminated for an active officer (a Keycloak round-trip for a not-yet-active one).
- **H2-06 — shared `useTicketThread` hook** (portal): desktop + `/m` ticket-thread pages consume one hook + `threadCommands`; −756 duplicated lines in the pages; 23 vitest.
- **H2-07 — escalation engine test extension** (backend): full L1→L3 chain + SEAH isolation + manual/auto interleaving + per-transition notifications on the seeded workflow (5 tests).
- **H2-08 — SEAH form mixin + Nepali repair** (chatbot): `SeahSharedFormMixin` + `build_seah_multiselect_buttons` dedupe the victim/focal intake forms (−228 lines, thresholds `>3`/`>=8` preserved). NE copy repaired (tripled SEAH menu label, OCMC referral, garbled hospital address, stray `ू`); duplicated utterance blocks merged to one shared dict; two English-only validator messages routed through the utterance system. `translations_seah_review.csv` (60 rows); **NE AI-generated per user directive (needs_translator=0).** parity (11) + integrity (54) tests.

### Follow-ups closed the same sprint

- **authz-gaps-h2-03** — the 3 gaps H2-03 surfaced: `DELETE /roles/{id}` gated on `CREATE_OPERATIONAL_ROLE`; `PATCH /projects/{id}` gated on `MANAGE_PROJECT` (waiting `xfail` flipped to passing); 10 unauthenticated project-config GET reads locked to `get_authenticated_user` (geography stays public), sweep allowlist trimmed 15→5.
- **apifetch-refresh-non-json-sites** — a shared `authedFetch` gives the 4 blob/multipart fetch sites H2-01's proactive-refresh + `401→refresh→retry-once` (FormData rebuilt on retry); `isSessionExpiredResponse` retired.

## Test posture at close

Backend `tests/ticketing` **545 passed / 5 skipped / 0 xfailed**; chatbot `tests/orchestrator`+`tests/actions` **173 passed / 1 skipped**; portal vitest **61 passed** (8 files), `tsc` clean, `eslint` 0 errors, `next build` green. All run locally in-container / on the portal toolchain; CI-on-integration is a close-out leftover.

## Where the durable content lives now

| Content | Permanent home |
|---|---|
| Router-split layout + engine boundary | `ticketing/api/routers/tickets/`, `ticketing/engine/` (as-built) |
| Grievance-sync watermark/paging + full-sweep backstop | `ticketing/tasks/grievance_sync.py`, `ticketing/tasks/celery_app.py` beat |
| Auth-dependency onboarding cache | `ticketing/services/auth_sync_cache.py` |
| Shared SEAH slot logic | `backend/actions/forms/seah_shared.py` |
| SEAH translation review artifact | `docs/seah/translations_seah_review.csv` |
| OIDC refresh + shared authed-fetch | `channels/ticketing-ui/lib/auth/`, `lib/api.ts` (`apiFetch`/`authedFetch`) |
| Authz gates (roles/projects/config reads) | `ticketing/api/routers/users.py`, `locations.py` |

## Leftovers noted at close

- **Manual sweeps — PENDING-HUMAN** (no browser/live-Keycloak in the build env): H2-01 (1-min token / no-data-loss + replayed-refresh rejected), H2-02/H2-06 UI click-through parity, H2-08 SEAH EN/NE webchat walk-through (victim/anon/witness/focal).
- **CI-on-integration + merge** to the integration branch — not yet run/promoted from `dev/tier2-quality`.
- **SEAH translation fact-check** — the OCMC/hospital rows in `translations_seah_review.csv` are AI-translated from the existing EN copy (not invented) and flagged for optional human verification against a service-provider registry (none seeded in-tree).
- **Per-project scope-gating** of project mutations (project_admin currently tier-gated, not scoped to their own project) — noted in the authz-gaps follow-up as an optional later step.
