# Agent runbook — H2-04 + H2-05: Backend performance

**Branch:** `tier2/h2-04-05-perf` off `integration/seah-claude`, rebased on the merged backend-refactor branch (shared ticket-router files) · **Spec:** [`../03-backend-performance-spec.md`](../03-backend-performance-spec.md) · Read [`README.md`](README.md) first. Order: H2-04 → H2-05.

## Mission

Turn the heaviest recurring query from O(all-time) to O(delta) (grievance sync watermark + paging), stop GETs from writing, and take the per-request onboarding sync off the hot path. Both tickets require **before/after measurements** recorded in PROGRESS.

## H2-04 steps

1. **Verify the modification column first.** Read `ticketing/tasks/grievance_sync.py` and the `public.grievances` schema (`migrations/public/versions/`), then grep the chatbot's update paths (`backend/services/database_services/`, submit/modify actions) to confirm the modification timestamp is bumped on every relevant write. List any non-bumping paths in PROGRESS and apply the spec's hybrid fallback if needed.
2. **Baseline measurement**: run one sync on the seeded dev DB; record wall-time + processed-row count.
3. Implement per spec §1: watermark in `ticketing.settings`, batched processing, advance-after-commit, `full=True` escape hatch, HR-03 conflict-skip retained.
4. Remove the cache refresh + commit from the ticket detail GET (post-H2-02 location: `ticketing/api/routers/tickets/crud.py`). First grep `channels/ticketing-ui` for flows relying on GET-triggered freshness; decide (and document in PROGRESS) whether the optional explicit refresh endpoint is needed.
5. Tests per spec (extend `tests/ticketing/test_grievance_sync.py`): no-op run, single-change, paging, crash-safety watermark hold, full sweep, zero-writes-on-GET.
6. **After measurement**: same seeded run; record delta in PROGRESS.

## H2-05 steps

1. Read `ticketing/api/dependencies.py` (post-Tier-1 shape) and every writer of `officer_onboarding` (`grep -rn "officer_onboarding" ticketing/` — webhook, invite, resend, seed).
2. Implement per spec §2: TTL cache (default 300 s, `TICKETING_AUTH_SYNC_TTL_SECONDS`, 0 = off), invalidation hooks on every onboarding writer, in-process unless redis is genuinely one line.
3. Tests per spec (extend `tests/ticketing/test_auth_dependencies.py`): once-per-TTL, expiry, invalidation, TTL=0 parity, warm-cache-no-writes.
4. Latency spot check: 50 sequential `GET /tickets` before/after; record numbers.
5. Manual: invite → set-password → first login activates immediately (invalidation, not TTL wait).

## Constraints

- No schema changes (settings key/value only — no migration needed; confirm `ticketing.settings` accepts the key shape used elsewhere).
- Don't alter sync mapping/classification logic — only *selection* (watermark/paging) and transaction placement.
- Scope/role loading in the auth dependency stays untouched (out of scope; note profiling observations in PROGRESS if relevant).

## Done means

Both checklists ticked in `../PROGRESS.md` including the four measurement fields; suites green in CI; manual checks recorded.
