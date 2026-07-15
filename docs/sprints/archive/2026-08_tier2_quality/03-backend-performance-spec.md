# H2-04 / H2-05 — Backend performance (sync watermark + auth-dependency cache)

> Workstream B · Branch `tier2/h2-04-05-perf` · Sequential: H2-04 then H2-05. Rebase on Workstream A once it lands (H2-04 touches the ticket detail router).
> Evidence: backend review §7 in [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md). Re-locate line numbers before editing.

---

## 1. H2-04 — Grievance sync: watermark + paging (+ cache refresh out of GET)

### Problem (verified)

- `ticketing/tasks/grievance_sync.py:62-80` full-scans **all** `public.grievances` with a 3-table JOIN (`grievance_parties`, `complainants`) **every 2 minutes**, plus all non-deleted tickets (:172-175). No watermark — O(all-time) forever, hammering the shared chatbot DB; visible degradation expected around 10⁴–10⁵ grievances.
- `get_ticket` performs a grievance-cache refresh **and commits inside a GET** (`tickets.py:799-802` pre-split; find the equivalent in the H2-02 package layout) — non-idempotent reads, write races between concurrent readers.

### Change

1. **Watermark**: persist `grievance_sync_watermark` (ISO timestamp) in `ticketing.settings`. Each run selects `WHERE <modification-column> > :watermark ORDER BY <modification-column> LIMIT :batch` — **first verify the actual column** on `public.grievances` (`grievance_modification_date` or equivalent; check `migrations/public/` + the chatbot's update paths; confirm it is set on every update path the sync cares about — if some updates don't bump it, list them in PROGRESS and fall back to a hybrid: watermark + daily full sweep).
2. **Paging**: process in batches (e.g. 500) inside the run until exhausted; advance the watermark to the max seen modification time **only after** the batch commits (crash-safe: re-processing a batch must be idempotent — it is, post-HR-03).
3. **New-grievance backfill** keeps working: creation is covered by the same modification-column predicate (verify inserts set it); the HR-03 IntegrityError skip stays.
4. **Full-sweep escape hatch**: keep a manual full sync entry point (task arg `full=True`) for ops, documented in the task docstring.
5. **Cache refresh out of GET**: delete the refresh+commit from the ticket detail endpoint; freshness is provided by (a) the 2-min sync and (b) an optional explicit `POST /tickets/{id}/refresh-cache` if the UI needs on-demand freshness — **check first** whether any UI flow depends on GET-triggered freshness (grep `channels/ticketing-ui` for usages that immediately re-read after webhook-ish events); if none, skip the new endpoint entirely.
6. **Measure**: before/after wall-time and query counts for one sync run on the seeded dev DB (log lines are fine). Record numbers in PROGRESS — this is a sprint-level DoD item.

### Tests (acceptance)

Extend `tests/ticketing/test_grievance_sync.py` (exists):
- [ ] Run 1 processes seeded grievances and sets the watermark; run 2 with no changes processes **zero** rows (assert query row counts, not just no-op result).
- [ ] Modifying one grievance ⇒ next run processes exactly that one; ticket cache updated.
- [ ] Batch paging: seed > batch-size modified rows ⇒ all processed in one task run across pages; watermark advances once at the end.
- [ ] Crash-safety: simulate failure mid-batch (monkeypatch to throw) ⇒ watermark NOT advanced; re-run converges with no duplicates (HR-03 index proves it).
- [ ] `full=True` still syncs everything.
- [ ] GET `/tickets/{id}` performs **zero writes** (assert no commit/flush of changes — e.g. session `info` flag or query-count fixture).

### Manual verification
- [ ] Seeded stack: submit a chatbot grievance → ticket appears within one sync cycle; before/after timing numbers recorded in PROGRESS.

---

## 2. H2-05 — Cache the onboarding sync out of the auth dependency

### Problem (verified)

`get_current_user` runs `sync_officer_onboarding_status` + potential `db.commit()` plus admin-scope/role loads on **every request** (`ticketing/api/dependencies.py:252-257, 222-231`) — 3–5 extra queries and a possible write per API call, on the critical path of every endpoint. Estimated 10–30% of p50 latency.

### Change

1. **TTL cache** keyed by user id, 5-minute TTL, for the onboarding-status sync: in-process dict with monotonic timestamps (module-level, thread-safe via a lock; multi-worker duplication is acceptable — the sync is idempotent). Redis is available (shared broker) but not required; choose in-process unless a one-liner with the existing redis client is cleaner — document the choice.
2. On cache miss/stale: run the sync exactly as today, then stamp the cache. On hit: skip entirely (no DB write, no extra queries for onboarding).
3. **Invalidation hooks**: bust the entry on the two events that change onboarding state — the Keycloak webhook (`webhooks.py` onboarding activation) and invite/resend endpoints (`users.py`). Grep for every writer of `officer_onboarding` and hook each.
4. Scope/role loads (:222-231) stay as-is (correctness-sensitive; caching them is out of scope — note as a possible Tier-3 item in PROGRESS if profiling shows they dominate).
5. Keep a `TICKETING_AUTH_SYNC_TTL_SECONDS` setting (default 300; `0` disables caching) for ops tuning.

### Tests (acceptance)

Extend `tests/ticketing/test_auth_dependencies.py`:
- [ ] Two consecutive authenticated requests ⇒ onboarding sync executes once (spy/counter on the service function).
- [ ] TTL expiry (freeze/patch time) ⇒ sync runs again.
- [ ] Webhook activation for a user ⇒ that user's next request re-syncs immediately (invalidation works).
- [ ] `TTL=0` ⇒ per-request behavior identical to today (escape hatch).
- [ ] Warm-cache request performs no DB write (query/flush assertion fixture, shared with H2-04's).

### Manual verification
- [ ] Rough latency check on the seeded stack: time 50 sequential `GET /tickets` before/after (script fine); record numbers in PROGRESS.
- [ ] Invite → set password → first login still flips status to active without waiting 5 minutes.
