# Devil's Advocate — Codebase Quality Review

> **Status:** Re-scored **July 15, 2026**, branch `dev/tier2-quality` (supersedes the July 13 `dev/organisation` re-score; original pass: July 2026, `integration/seah-claude`).
> **Method:** four independent adversarial reviews — Python backend (ticketing/, backend/, ops/; ~72k LOC), officer portal (channels/ticketing-ui/; 106 TS/TSX files, `tsc` + full `eslint` actually run), REST webchat (channels/REST_webchat/), and the chatbot conversation layer (orchestrator + actions). Every claim was verified in source with file:line evidence.
> **Re-score basis:** the numbers below reflect what has actually **shipped into the tree** — the **Tier-1 Hardening sprint** (`docs/sprints/2026-07_hardening/`, 7 HR tickets + CI), the **org-chart remediation** (`docs/sprints/2026-07_org_chart_positions/`, R1–R13), and now the full **Tier-2 Quality sprint** (`docs/sprints/2026-08_tier2_quality.md`, H2-01…08 + the authz-gaps and apifetch-refresh follow-ups, all landed on `dev/tier2-quality`, locally tested). Tier-2 code is **code-complete** but its browser/Keycloak manual sweeps and CI-on-integration are still pending — so the dimensions it owns move to "landed, locally verified", not "field-proven". Tier 3 has not started.
> **Stance:** adversarial but honest — real defects, not style nits, and genuine strengths stated so the numbers are credible. Spec-side companion: [`devils_advocate_specs.md`](devils_advocate_specs.md).

---

## 1. Overall score: **~76%** (was ~55% → ~64% → **~76%**)

Weighted by code volume and criticality (backend 45%, portal 25%, conversation layer 20%, webchat 10%). The `Was → Now` column shows the movement from the original pass to now (post-Tier-2); the middle July-13 value is noted where it helps. Dimensions that didn't move are the ones Tier 3 still owns.

| Area | Was → Now | What moved it | Remaining weakest point |
|---|---|---|---|
| Backend — migrations & data safety | **72 → 84** | HR-03 partial unique index enforces one-ticket-per-grievance; CL-01 schema-baseline gate in CI | Cross-stream ownership still convention-enforced, not tooling-enforced |
| Backend — performance | **63 → 74** (65 at Tier-1) | **H2-04** watermark-paged the O(all-time) grievance sync → O(delta) (72× on a 5k-row bench) + removed the GET-detail cache write-back; **H2-05** TTL-cached the per-request onboarding sync out of the auth dependency (~1.6 ms/req) | Query shapes only structurally reasoned, not profiled under load |
| Backend — maintainability | **62 → 74** (67 at Tier-1) | **H2-02** split the 2,414-line ticket router into a 7-module `routers/tickets/` package + `engine/`; dead code and in-function imports removed along the way | 2,303-line `state_machine.py` still carries `run_flow_turn` (Tier 3) |
| Backend — architecture | **58 → 68** (59 at Tier-1) | **H2-02** God router → package and `perform_action` → `engine/ticket_actions.py` (typed outcomes, no HTTP in the engine), route-surface pinned identical | 2,303-line inline conversation state machine (Tier 3) |
| Backend — correctness | **55 → 74** | HR-04 savepoint-per-ticket + `FOR UPDATE SKIP LOCKED` + idempotence guard kills the partial-commit class; H2-04 sync is now crash-safe/idempotent; R3 keeps deactivated officers out of assignment | Actions/orchestrator state machine still lightly covered |
| Backend — security | **55 → 80** (78 at Tier-1) | HR-01 fail-closed auth + HR-02 `require_ticket_access`; **authz-gaps-h2-03** closed 3 least-privilege holes (role-delete, project-metadata PATCH, 10 unauthenticated project-config reads) | ~~PII decryption still dual-pathed in ticketing~~ **(corrected 2026-07-15: not dual-pathed — the grievance API omits decryption and ticketing works around it; see the Tier-3 banner)**; project mutations tier-gated not project-scoped |
| Backend — testing | **42 → 68** (64 at Tier-1) | **H2-03** (118 authz cells) + **H2-07** (escalation L1→L3/SEAH/interleave) + H2-04/05 behavior tests + SEAH parity/integrity | Conversation state machine still thin; `@integration` tests quarantined in CI |
| Portal — architecture | **50 → 62** (53 at Tier-1) | **H2-01** the OIDC client now actually uses its refresh token; **H2-06** shared `useTicketThread` hook removed ~756 duplicated lines across the two thread pages | 4,372-line settings page (Tier 3) |
| Portal — robustness/UX | **48 → 76** (65 at Tier-1) | **H2-01** ends officer data-loss at token expiry (proactive refresh + `401→refresh→retry-once`); **apifetch-refresh** extends the same to the blob/multipart upload sites | Coverage still thin; deep flows unexercised in CI |
| Portal — types & testing | **47 → 66** (62 at Tier-1) | +32 vitest (H2-01 9, H2-06 23) + authedFetch tests; `tsc`/`eslint`/`build` still gate every push | Still no E2E; 141 lint **warnings** deferred (tracked) |
| Conversation layer | **52 → 60** (53 at Tier-1) | **H2-08** deduped the victim/focal SEAH forms into a shared mixin and repaired the broken Nepali (tripled SEAH label, OCMC referral, garbled address, stray `ू`), with a parity + utterance-integrity net | 1,485-line `run_flow_turn`, CC≈120; broken Nepali outside the SEAH flow (Tier 3) |
| REST webchat | **64 → 73** | HR-07 persists session ID at startup, adds an in-flight send lock, SRI hashes, `textContent` banner | Voice-chunk upload race (Tier 3, not done); browser regression sweep still pending-human |

**Reading the number:** ~76% reflects a system whose worst structural risks are fixed and CI-guarded (Tier 1) **and** whose highest-drag quality/perf items have now landed (Tier 2): the God router is a testable package, the O(all-time) sync is incremental, officer data-loss at token expiry is closed, and the SEAH Nepali is repaired. It is not higher because the two largest remaining files — `state_machine.py` (`run_flow_turn`) and the 4,372-line settings page — plus PII-path unification and profiled performance are **Tier 3**, and because Tier-2's browser/Keycloak manual sweeps and CI-on-integration are still pending (code-complete, locally verified). Clearing Tier 3 + those confirmations is what would push the low-80s.

---

## 2. The five findings that mattered most — status

1. ~~**Auth fails open by configuration.**~~ **CLOSED (HR-01).** `ticketing/config/settings.py` now gates the demo super_admin fallback behind `is_dev` + `auth_mode == "bypass"`; `main._assert_auth_configured` refuses startup when `KEYCLOAK_ISSUER`/`TICKETING_SECRET_KEY` are unset outside dev, with a per-request 503 as defense in depth. 8 acceptance tests. Backend mirror guard added for `backend/api`.
2. ~~**SEAH wall has door-sized holes at the file/PII endpoints.**~~ **CLOSED (HR-02).** A single `require_ticket_access` / `require_file_access` dependency (`ticketing/api/ticket_access.py`) now gates `GET /attachments/{file_id}`, `GET /files/{file_id}`, `GET /tickets/{id}/pii`, and ~18 other per-ticket endpoints (exists + SEAH + scope + visibility). Persona×endpoint matrix: **86 tests**. Separately, R1 closed the SEAH **notification** leak (badge/notifications/@mention/convene/tier-cast).
3. ~~**The escalation engine is lock-free, partially-committing, and untested.**~~ **CLOSED (HR-04).** `run_sla_check` wraps each ticket in `db.begin_nested()`; candidates are selected `.with_for_update(skip_locked=True)`; an idempotence re-check runs under the lock; HR-03 added the partial unique index on `tickets(grievance_id) WHERE is_deleted=false`. 6 engine tests including a mid-loop-failure case **verified red on the pre-fix code**.
4. ~~**Zero frontend tests + no CI anywhere.**~~ **CLOSED (HR-05 + HR-06).** `.github/workflows/ci.yml` runs three parallel jobs (backend pytest on a Postgres service across all 3 Alembic streams; portal `tsc`+`eslint`+`vitest`+`build`; docs-link check) on every push/PR. First green run confirmed. *Caveat:* frontend coverage is still only 3 vitest files, and `@integration` backend tests are quarantined (`-m "not integration"`) pending a seed-reconciliation fix.
5. ~~**Officers lose work by design.**~~ **CLOSED (H2-01 + apifetch-refresh).** `apiFetch` now proactively refreshes a token expiring within 60 s and does `401 → refresh → retry-once` (single-flight `refreshTokens`) before any redirect; the shared `authedFetch` extends the same to the 4 blob/multipart upload sites (FormData rebuilt on retry). The refresh token is finally used; a half-written note survives expiry. The list-page silent-empty half was already fixed by HR-06.

**New top findings (what now caps the score):**
- **God files remaining** — `app/settings/page.tsx` (4,372) and `run_flow_turn` inside a 2,303-line `state_machine.py`. (The 2,414-line `tickets.py` was **split** by H2-02 into a 7-module package + engine.) Tier 3.
- ~~**PII decryption still dual-pathed** in ticketing~~ — **CORRECTED 2026-07-15: it is not dual-pathed.** `pii_vault.py` decrypts ciphertext the grievance API already returned; the real defect is that `get_grievance_by_id` omits server-side decryption. The unification item is real but lives in `backend/`, not ticketing. See [`../sprints/2026-08_tier3_structural/00-reassessment.md`](../sprints/2026-08_tier3_structural/00-reassessment.md) §3.
- **Conversation layer size** — a lightly-tested 1,485-line `run_flow_turn` (**CC measured at 189, not ~120**); broken Nepali *outside* the SEAH flow remains (the SEAH copy was repaired by H2-08). Tier 3. **Also: 3 of the 4 stack-introspected utterance call sites raise `ValueError` today** — a live bug, not a refactor item.
- **Confirmation debt** — Tier-2 is code-complete + locally tested but its browser/Keycloak manual sweeps and CI-on-integration are not yet run.

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

### Tier 2 — ✅ DONE (`docs/sprints/2026-08_tier2_quality.md`), code-complete + locally tested on `dev/tier2-quality`

| Fix | Ticket | Status |
|---|---|---|
| OIDC refresh-grant in `apiFetch` (single-flight, retry-once) | H2-01 | ✅ shipped + 9 vitest; manual Keycloak sweep pending-human |
| Split `tickets.py` into crud/actions/files/pii; `perform_action` → `engine/` | H2-02 | ✅ 7-module package + engine; 174-route snapshot pinned identical + 12 engine tests |
| Authz test matrix extension (all actions × personas; unauthenticated sweep) | H2-03 | ✅ 118 tests; the 3 gaps it surfaced fixed in the authz-gaps follow-up |
| Watermark + page the grievance sync | H2-04 | ✅ keyset-incremental + full-sweep backstop; 72× bench; 6 DB tests |
| Cache the onboarding sync out of the auth dependency | H2-05 | ✅ in-process TTL cache + writer invalidation; 6 tests |
| Shared `useTicketThread` hook for desktop + `/m` ticket pages | H2-06 | ✅ −756 duplicated lines; 23 vitest |
| Escalation engine test extension (full L1→L3, SEAH isolation, interleaving) | H2-07 | ✅ 5 tests |
| SEAH form mixin + fix garbled Nepali strings | H2-08 | ✅ mixin (−228 lines) + Nepali repair (AI-translated) + parity/integrity tests |
| — follow-up: 3 authz gaps (role-delete, project PATCH, unauth config reads) | authz-gaps-h2-03 | ✅ gated + tests |
| — follow-up: silent refresh on blob/multipart fetch sites | apifetch-refresh | ✅ `authedFetch` + tests |

**Effect of Tier 2: ~64% → ~76%** — moved performance, architecture, maintainability, portal architecture/robustness, security, and the conversation layer. **Residual Tier-2 debt:** browser/Keycloak manual sweeps (H2-01/02/06), the SEAH EN/NE webchat walk-through (H2-08), and CI-on-integration + merge are still pending-human; the SEAH translation fact-check (OCMC/address) is flagged in `docs/seah/translations_seah_review.csv`.

### Tier 3 — structural (L efforts, schedule deliberately)

> ⚠️ **This table is KNOWN-WRONG as written — do not plan from it.** It was authored in the same pass as Tier 1/Tier 2 and never re-verified after those sprints (plus the org-chart sprint) landed. Re-verified against the tree on **2026-07-15**: **four of its five rows are materially wrong**, two of them in ways that would cause a regression if implemented as written. Corrected findings, with file:line evidence and hand-verification: [`../sprints/2026-08_tier3_structural/00-reassessment.md`](../sprints/2026-08_tier3_structural/00-reassessment.md). This table and the related claims in §1–§2 are corrected at Tier-3 close-out, together with the re-score.
>
> **The headline: Tier 3 is not five structural refactors — it is three live bugs and two decompositions.** The utterance item, the voice item, and part of `run_flow_turn` are latent user-facing defects, not refactorability work.

| Fix (as originally written) | Effort | 2026-07-15 verdict |
|---|---|---|
| Decompose `run_flow_turn` (1,485 lines, CC≈120) into a state→handler table; delete dead branches | L → **M** | **Confirmed, but CC is 189 not ~120** (58% understated), and the emphasis is backwards: the shape is unusually table-friendly (flat chain, zero early returns, 4 shared carriers, handler pattern already in-file). The real risk is one 304-line branch (`status_check_form`) with thin coverage. Also missed: **no terminal `else`** ⇒ unrecognized state returns zero messages (dead air). |
| Split the 4,372-line settings page into per-tab components | L → **S/M** | **Half-wrong.** The hooks-crash class was **already closed by HR-06** in Tier 1; the org sprint already extracted 7,748 lines and the shell is already a clean 206-line delegator. Purely mechanical now; the honest benefit is bundle/reviewability, not crash-class elimination. |
| Route ticketing's PII decryption through the grievance API only; drop `DB_ENCRYPTION_KEY` | M/L → **M** | **Misdiagnosed, and the prescribed order causes a silent outage.** It is **not dual-pathed**: `pii_vault.py:49-73` has no `FROM` clause — it decrypts ciphertext the API already returned (a pgcrypto oracle, not a PII read). The real defect is a **backend** omission: `get_grievance_by_id` never calls `_decrypt_sensitive_data`, unlike its sibling. Dropping the key first silently blanks every officer contact card, guarded by **zero tests**. |
| Replace stack-introspection utterance lookup with explicit keys | M → **S** | **Scope wrong by 50× — and it is a live bug.** 4 call sites, not ~200 (196 already use the explicit path). **3 of the 4 raise `ValueError` today**; one is swallowed into wrong form state. Missed: `get_buttons` has the identical flaw, and the *real* refactorability blocker is `file_name` module-derivation (~200 sites). |
| Serialize voice-chunk uploads behind chunk-0's `upload_id` | M | ✅ **Correct** — the one row that held up. Real, open, and **not** mitigated by HR-07 (whose lock is text-only). Missed: a second path yields **silently truncated** voice notes. |

**Estimated ceiling after Tier 3: ~85%.**

**Method note for future passes:** the four Tier-3 rows that were wrong all failed the same way — the review reasoned from file size and a grep, without resolving the actual call graph or checking whether a later sprint had already moved the code. The three "structural refactor" framings each concealed a live user-facing bug. Sizing a finding by *lines* rather than by *call sites and blast radius* is what produced both the 50× scope error and the two dangerous prescriptions.

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
