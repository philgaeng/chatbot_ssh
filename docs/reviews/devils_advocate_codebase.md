# Devil's Advocate — Codebase Quality Review

> **Status:** Re-scored **July 13, 2026**, branch `dev/organisation` (original pass: July 2026, `integration/seah-claude`).
> **Method:** four independent adversarial reviews — Python backend (ticketing/, backend/, ops/; ~72k LOC), officer portal (channels/ticketing-ui/; 106 TS/TSX files, `tsc` + full `eslint` actually run), REST webchat (channels/REST_webchat/), and the chatbot conversation layer (orchestrator + actions). Every claim was verified in source with file:line evidence.
> **Re-score basis:** the numbers below reflect what has actually **shipped into the tree** since the original pass — the full **Tier-1 Hardening sprint** (`docs/sprints/2026-07_hardening/`, all 7 HR tickets landed + CI) and the **org-chart remediation** (`docs/sprints/2026-07_org_chart_positions/`, R1–R13). Tier 2 and Tier 3 have **not** started; dimensions they own barely move.
> **Stance:** adversarial but honest — real defects, not style nits, and genuine strengths stated so the numbers are credible. Spec-side companion: [`devils_advocate_specs.md`](devils_advocate_specs.md).

---

## 1. Overall score: **~64%** (was ~55%)

Weighted by code volume and criticality (backend 45%, portal 25%, conversation layer 20%, webchat 10%). The `Was → Now` column shows the movement since the original pass; unchanged dimensions are the ones Tier 2/3 still own.

| Area | Was → Now | What moved it | Remaining weakest point |
|---|---|---|---|
| Backend — migrations & data safety | **72 → 84** | HR-03 partial unique index enforces one-ticket-per-grievance; CL-01 schema-baseline gate in CI | Cross-stream ownership still convention-enforced, not tooling-enforced |
| Backend — performance | **63 → 65** | HR-04 removed the per-ticket N+1 in escalation candidate loading | Unbounded full-scan grievance sync every 2 min (Tier 2 H2-04, not done) |
| Backend — maintainability | **62 → 67** | HR-01 makes the demo super_admin fallback dev-only, no longer welded into the prod auth path; single-source `ticket_access` gate | 2,414-line ticket router still carries most logic |
| Backend — architecture | **58 → 59** | `ticket_access.py` extracted as a single visibility gate | 2,414-line God router; 430-line inline state machine (Tier 2 H2-02, not done) |
| Backend — correctness | **55 → 74** | HR-04 savepoint-per-ticket + `FOR UPDATE SKIP LOCKED` + idempotence guard kills the partial-commit class; R3 keeps deactivated officers out of assignment; first tests | Actions/orchestrator state machine still lightly covered |
| Backend — security | **55 → 78** | HR-01 fail-closed auth **and** HR-02 `require_ticket_access` on file/PII endpoints close both named holes; R1 SEAH-notification lockdown; R2/R4 authz containment | PII decryption still dual-pathed in ticketing (Tier 3) |
| Backend — testing | **42 → 64** | Escalation-engine, authz-matrix (86), fail-closed, and uniqueness suites now exist; **CI is live** | Actions state machine untested; `@integration` tests quarantined in CI |
| Portal — architecture | **50 → 53** | ~345 lines extracted from the settings page; typed `lib/api.ts` for notification rules | 4,372-line settings page; OIDC client still never uses its refresh token (Tier 2 H2-01) |
| Portal — robustness/UX | **48 → 65** | HR-06 error card + retry + stale-response seq guard on all 5 list surfaces; hooks-order crash fixed; `error.tsx`/`global-error.tsx`; R5 friendly-error contract | Officer data-loss at token expiry remains (Tier 2 H2-01) |
| Portal — types & testing | **47 → 62** | vitest wired into CI; the 2 rules-of-hooks crashes fixed; `tsc`+`eslint`+`build` now gate every push | Only 3 test files — coverage still thin; 134 lint **warnings** deferred |
| Conversation layer | **52 → 53** | The ~90 orchestrator tests now run as a CI gate | 1,485-line `run_flow_turn`, CC≈120; broken Nepali strings (Tier 2 H2-08 / Tier 3, not done) |
| REST webchat | **64 → 73** | HR-07 persists session ID at startup, adds an in-flight send lock, SRI hashes, `textContent` banner | Voice-chunk upload race (Tier 3, not done); browser regression sweep still pending-human |

**Reading the number:** ~64% reflects a system whose **worst structural risks have been fixed and are now regression-guarded by CI** — fail-open auth, the ungated SEAH file/PII endpoints, the lock-free escalation engine, and "no tests / no CI" are all closed. It is not higher because the improvement was deliberately concentrated in security, correctness, and robustness (Tier 1). The dimensions that cap the score — the God-file architecture, the unbounded sync query, officer data-loss at token expiry, and the conversation layer's size and broken Nepali — are all Tier 2/3 work that has not begun. The doc's Tier-1 estimate of "~68%" assumed a little of that architecture/perf work would land with it; it did not, so the weighted rollup sits at ~64%.

---

## 2. The five findings that mattered most — status

1. ~~**Auth fails open by configuration.**~~ **CLOSED (HR-01).** `ticketing/config/settings.py` now gates the demo super_admin fallback behind `is_dev` + `auth_mode == "bypass"`; `main._assert_auth_configured` refuses startup when `KEYCLOAK_ISSUER`/`TICKETING_SECRET_KEY` are unset outside dev, with a per-request 503 as defense in depth. 8 acceptance tests. Backend mirror guard added for `backend/api`.
2. ~~**SEAH wall has door-sized holes at the file/PII endpoints.**~~ **CLOSED (HR-02).** A single `require_ticket_access` / `require_file_access` dependency (`ticketing/api/ticket_access.py`) now gates `GET /attachments/{file_id}`, `GET /files/{file_id}`, `GET /tickets/{id}/pii`, and ~18 other per-ticket endpoints (exists + SEAH + scope + visibility). Persona×endpoint matrix: **86 tests**. Separately, R1 closed the SEAH **notification** leak (badge/notifications/@mention/convene/tier-cast).
3. ~~**The escalation engine is lock-free, partially-committing, and untested.**~~ **CLOSED (HR-04).** `run_sla_check` wraps each ticket in `db.begin_nested()`; candidates are selected `.with_for_update(skip_locked=True)`; an idempotence re-check runs under the lock; HR-03 added the partial unique index on `tickets(grievance_id) WHERE is_deleted=false`. 6 engine tests including a mid-loop-failure case **verified red on the pre-fix code**.
4. ~~**Zero frontend tests + no CI anywhere.**~~ **CLOSED (HR-05 + HR-06).** `.github/workflows/ci.yml` runs three parallel jobs (backend pytest on a Postgres service across all 3 Alembic streams; portal `tsc`+`eslint`+`vitest`+`build`; docs-link check) on every push/PR. First green run confirmed. *Caveat:* frontend coverage is still only 3 vitest files, and `@integration` backend tests are quarantined (`-m "not integration"`) pending a seed-reconciliation fix.
5. **Officers lose work by design — STILL OPEN.** The portal still stores a refresh token it never uses (`lib/auth/token-storage.ts:47-49`); at access-token expiry a hard redirect discards any half-written note. This is Tier 2 **H2-01** (OIDC refresh-grant in `apiFetch`), which has not started. The list-page silent-empty half of this finding **was** fixed by HR-06 (error card + retry on all 5 surfaces).

**New top findings (what now caps the score):**
- **Officer data-loss at token expiry** (H2-01, unchanged) — the highest field-visible UX risk still live.
- **God files** — `tickets.py` (2,414), `app/settings/page.tsx` (4,372), `run_flow_turn` inside a 2,303-line `state_machine.py`. The main merge-conflict and untestability surface (H2-02, Tier 3).
- **Unbounded grievance sync** — still O(all-time) every 2 min against the shared chatbot DB (H2-04).
- **Conversation layer** — broken Nepali strings and a lightly-tested 1,485-line turn handler (H2-08 / Tier 3).

---

## 3. Improvement plan with impact estimates

### Tier 1 — ✅ DONE (`docs/sprints/2026-07_hardening/`)

All seven tickets landed with tests and CI. This is the ~55% → ~64% movement above; security 55→78, correctness 55→74, testing 42→64, portal robustness 48→65, webchat 64→73.

| Fix | Ticket | Status |
|---|---|---|
| Fail-closed auth (refuse startup when auth env unset outside dev) | HR-01 | ✅ shipped + 8 tests |
| `require_ticket_access`/`require_file_access` on attachments/files/PII | HR-02 | ✅ shipped + 86-test matrix |
| Partial unique index on `tickets(grievance_id) WHERE NOT is_deleted` | HR-03 | ✅ migration `h2j4l6n8` + 6 tests |
| Savepoint-per-ticket + `FOR UPDATE SKIP LOCKED` in `run_sla_check` | HR-04 | ✅ shipped + 6 tests (mid-loop verified red pre-fix) |
| GitHub Actions: pytest + tsc + eslint + vitest + build gate | HR-05 | ✅ live; first green run confirmed |
| Portal error state + retry on lists; settings hooks crash; `error.tsx` | HR-06 | ✅ shipped + vitest seed |
| Webchat: persist session ID + send lock + SRI + `textContent` banner | HR-07 | ✅ code shipped; **browser sweep pending-human** |

**Residual Tier-1 debt:** the HR-07 manual browser sweep and the HR-05 live deliberate-failure / branch-protection checks are still pending a human; `@integration` backend tests are quarantined in CI.

### Tier 2 — NOT STARTED (`docs/sprints/2026-08_tier2_quality/`, all tickets `todo`)

| Fix | Ticket | Effort | Estimated impact |
|---|---|---|---|
| OIDC refresh-grant in `apiFetch` (single-flight, retry-once) | H2-01 | M | Ends officer data loss at token expiry — highest field-visible UX win |
| Split `tickets.py` into crud/actions/files/pii; `perform_action` → `engine/` | H2-02 | M | State machine becomes unit-testable; removes main merge-conflict hotspot |
| Authz test matrix extension (all actions × personas; unauthenticated sweep) | H2-03 | M | Locks in the §2.2 class |
| Watermark + page the grievance sync (`WHERE modified > :last_sync`) | H2-04 | S/M | Heaviest recurring query O(all-time)→O(delta) |
| Cache the onboarding sync out of the auth dependency | H2-05 | S | ~10–30% off p50 API latency |
| Shared `useTicketThread` hook for desktop + `/m` ticket pages | H2-06 | M | Deletes ~350 duplicated lines |
| Escalation engine test extension (full L1→L3, SEAH isolation, interleaving) | H2-07 | M | Broadens the new engine coverage |
| SEAH form mixin + fix garbled Nepali strings (translator sign-off) | H2-08 | M | ~150 duplicate lines gone; quality for the primary Nepali/SEAH audience |

**Estimated effect of Tier 2: ~64% → ~76%** (moves performance, architecture, maintainability, portal architecture, and conversation layer — the dimensions Tier 1 left flat).

### Tier 3 — structural (L efforts, schedule deliberately)

| Fix | Effort | Estimated impact |
|---|---|---|
| Decompose `run_flow_turn` (1,485 lines, CC≈120) into a state→handler table; delete dead branches | L | Highest-risk change surface in the repo becomes reviewable |
| Split the 4,372-line settings page into per-tab components | L | Kills the hooks-crash class, cuts the settings bundle, unblocks parallel work |
| Route ticketing's PII decryption through the grievance API only; drop `DB_ENCRYPTION_KEY` | M/L | Restores the single auditable PII boundary |
| Replace stack-introspection utterance lookup with explicit keys | M | Makes the chatbot refactorable |
| Serialize voice-chunk uploads behind chunk-0's `upload_id` | M | Flagship patchy-network feature becomes deterministic |

**Estimated ceiling after Tier 3: ~85%.**

---

## 4. What is genuinely good (verified, not courtesy)

- **The worst risks are now fixed and regression-guarded.** Fail-closed auth, gated file/PII endpoints, a savepointed+row-locked escalation engine, a DB-enforced one-ticket-per-grievance invariant, and a three-job CI pipeline all shipped in one Tier-1 sprint, each with acceptance tests — including a mid-loop-failure test proven red on the pre-fix code.
- **Migration discipline better than most production shops**: linear ticketing revisions with real downgrades, safety headers, three Alembic streams that never cross, plus a CI schema-baseline self-consistency gate (CL-01).
- **Type discipline at both ends**: portal has 0 `any` across 106 strict-mode files (tsc clean, now CI-gated); ticketing backend is consistently typed with spec-citing docstrings.
- **No SQL injection surface found** in ~72k LOC of Python, including raw `text()` queries — uniformly bound parameters.
- **SEAH segregation is real and now closed at the endpoint and notification layers too** — query-layer filtering plus the HR-02 access gate plus the R1 notification lockdown.
- **The webchat renders untrusted content via `textContent` everywhere**, now with SRI on CDN scripts and an in-flight send lock.
- **The form engine and its tests**: one generic driver runs all 14 chatbot forms; ~90 orchestrator tests run with zero infrastructure and now gate every push.
- **`ops/` is a model service**: 11 small modules, own schema and scheduler, broker-independent.

---

## 5. Caveats

- Scores are reviewer judgments anchored to concrete evidence, not measured coverage/defect data — treat ±5 points as noise.
- The `Now` numbers credit **shipped, test-backed** code. Where a fix's manual/browser verification is still pending a human (HR-07 webchat sweep, HR-05 live-failure/branch-protection checks), that is noted inline and **not** counted as fully realized.
- CI runs the non-integration suite green; `@integration` ticketing tests are quarantined (`-m "not integration"`) pending seed reconciliation — real coverage is slightly below the raw test count.
- The reviews read code, not production traffic; performance findings are structural (query shapes, indexes), not profiled.
- Line numbers are as of `dev/organisation` at re-score time and will drift.
