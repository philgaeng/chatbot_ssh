# Tier-3 Structural Sprint — Progress

> Update at **every commit** on `dev/tier3-structural`. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · **Reassessment (read first): [00-reassessment.md](00-reassessment.md)** · Source review: [`../../reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md)

## Ticket status

| ID | Title | WS | Phase | Status | Commits | Notes |
|---|---|---|---|---|---|---|
| T3-01 | Explicit utterance keys + repair 3 non-resolving keys + delete dead `get_buttons` | A | **1?** | todo | — | 3 of 4 call sites derive keys that don't resolve ⇒ `ValueError`; one wrapped in a bare `except` at `form_grievance_complainant_review.py:525`. **⚠️ Phase is GATED on the §0 reachability trace (D-13) — ~10 min, do it first.** Reachable ⇒ Phase 1 bug fix; dead/swallowed ⇒ Phase 3 refactor. Deliverable identical either way. Spec [01](01-conversation-layer-spec.md) §1. |
| T3-02 p1 | `run_flow_turn`: delete `form_dust` + `submit_grievance`, add terminal `else` | B | 1 | todo | — | **Severable — land in Phase 1 even if p2-4 slip.** 31 deleted lines + 1 `else`. Terminal-`else` absence = dead-air bug. Spec [01](01-conversation-layer-spec.md) §2. |
| T3-03 | Serialize voice-chunk uploads behind chunk-0's `upload_id` | C | 1 | todo | — | **Live bug**: whole recording aborts when RTT > 1 s. HR-07's lock is text-only — does NOT cover this. Spec [02](02-webchat-voice-spec.md). |
| T3-04 | Unify the PII boundary (backend decrypt → delete workaround → drop key) | D | 2 | todo | — | **⚠️ STRICT ORDER — see spec [03](03-pii-boundary-spec.md) §Order.** Review misdiagnosed; fix is in `backend/`, not `ticketing/`. Touches a stable shared service (~20 callers). |
| T3-02 p2 | `run_flow_turn`: characterization tests (`status_check_form` + 3 `add_*` branches) | B | 3 | todo | — | **Gate for p3/p4.** 509 lines of thinly/un-tested code. |
| T3-05 | Extract the 6 remaining settings tab clusters | E | 3 | todo | — | Mechanical. Shell already clean; hooks-crash already fixed by HR-06. Spec [04](04-portal-settings-spec.md). |
| T3-02 p3 | `run_flow_turn`: split `status_check_form` (304 lines, depth 9) | B | 3 | todo | — | Blocked on p2. |
| T3-02 p4 | `run_flow_turn`: handler table | B | 3 | todo | — | **STRETCH.** Blocked on p3. Cheap once p1-p3 land. |

## Baselines at sprint start (`dev/tier3-structural` @ `87fbba86`, 2026-07-15)

Record these now so regressions are attributable:

| Suite | Baseline |
|---|---|
| `tests/ticketing` | 545 passed / 5 skipped / 0 xfailed |
| `tests/orchestrator` + `tests/actions` | 173 passed / 1 skipped |
| Portal vitest | 61 passed (8 files) |
| Portal `tsc` | clean |
| Portal `eslint` | 0 errors / 141 warnings |
| Portal `next build` | green |
| `app/settings/page.tsx` | 4,372 lines |
| `state_machine.py` / `run_flow_turn` | 2,303 / 1,485 lines, CC 189 |

## Acceptance checklists

### T3-01 — Explicit utterance keys
- [ ] **§0 FIRST — reachability traced** for the 3 non-resolving sites; **verdict recorded in Deviations (D-13)**; ticket phase confirmed (Phase 1 bug fix / Phase 3 refactor). ~10 min. Start with `ValidateMenuForm.validate_language_code` — is `language_code` button-only or free-text?
- [ ] `try/except` presence checked for `form_seah_1.py:199` and `form_story_main_route_step.py:33` (only the category-review site has been checked so far)
- [ ] **`BaseFormValidationAction.get_buttons` (`base_classes.py:126-128`) DELETED** — dead code, 0 callers (confirm by MRO yourself; a grep misleads — see D-06)
- [ ] `key=` param added to `get_utterance` (`base_classes.py:118`) — `get_buttons` is deleted, not parameterized
- [ ] All 4 call sites pass explicit keys (`form_otp.py:352`, `form_grievance_complainant_review.py:495`, `form_seah_1.py:199`, `form_story_main_route_step.py:33`) — complete set per AST+MRO (4/196/0-unresolved); re-run the resolution if the tree moved
- [ ] 3 missing mapping entries authored (EN + NE); NE AI-translated per standing directive, logged in a review CSV with `needs_translator=0`; **`form_story_main_route_step` added as a top-level key** (do NOT rename the module — 200-site blast radius)
- [ ] Introspection deleted (`f_back` line + `inspect` import); `key` now required
- [ ] Swallow narrowed at `form_grievance_complainant_review.py:525` — a missing utterance can no longer become a `SKIP_VALUE`. **Do this regardless of §0's verdict.**
- [ ] `check_form_function_name` (`base_mixins.py:313`) wired up or deleted — not left dead
- [ ] `tests/actions/test_utterance_key_integrity.py` — walks **call sites** (resolved by MRO), not the dict; scoped to `get_utterance`
- [ ] **Verified red pre-fix** (record the run) — goes red regardless of §0's verdict, since it asserts key *resolution*, not branch execution
- [ ] Swallow regression test — verified red pre-fix. **If §0 finds the branch unreachable**, this test can't be written as specified: log it in Deviations and unit-test the `except` path directly instead. Do not silently drop.
- [ ] Full `tests/actions` + `tests/orchestrator` green vs baseline
- [ ] Manual: EN + NE re-prompts render at all 3 repaired sites (**these double as the §0 trace** — do them first if a browser is available; combine with H2-08's pending SEAH walk-through)
- [ ] If §0 found any branch dead ⇒ dead-code finding logged (Deviations + followup + TODO.md row), not fixed here

### T3-02 p1 — Dead branches + terminal `else`
- [ ] `grep -rn '"form_dust"'` and `'"submit_grievance"'` **re-run and still showing only the self-comparisons** (the deletion proof)
- [ ] `grep` confirms nothing outside `state_machine.py` writes `session["state"]` (the proof's precondition)
- [ ] `form_dust` (1039–1050) deleted
- [ ] `submit_grievance` (1522–1540) deleted
- [ ] SEAH branches **NOT** touched (both arms ship + are tested — `965`/`973`)
- [ ] `location_consent` / `location_method` / `grievance_review` / `map_location` **NOT** touched (reached via helper returns)
- [ ] Terminal `else` added: logs at `error` + dispatches a fallback message
- [ ] Dead-air test — verified red pre-fix
- [ ] Full `tests/orchestrator` green vs baseline

### T3-03 — Voice-chunk serialization
- [ ] Chunk queue serialized (chunk N chains on N-1) in `voiceNote.js`
- [ ] `FormData` built **inside** the retry closure (`voiceChunkUpload.js:65-76`) — follows the `authedFetch` precedent
- [ ] `"out of order"` swallow gated on `isStopping`/`uploadFinalized` (`voiceNote.js:32-34`) — kills the silent-truncation path
- [ ] Server **not** changed (it is correct)
- [ ] Test-harness decision recorded (a: JS harness / b: server-only + manual) — **recommendation is (a)**
- [ ] Race test — verified red pre-fix
- [ ] Ordering / retry-heals / truncation-guard / fast-network-no-regression tests
- [ ] `tests/backend/test_fastapi_files.py` extended: id-less chunk > 0 ⇒ 400
- [ ] Manual: Slow 3G ≥5 s recording completes (**confirm red pre-fix first**) + plays back full length

### T3-04 — PII boundary
- [ ] **Commit 1** — `tests/ticketing/test_pii_boundary.py` green on **today's** code (plaintext officer card, parametrized ciphertext/plaintext at the client boundary)
- [ ] **Commit 2** — `get_grievance_by_id` decrypts (`grievance_manager.py:170`); fallback `get_grievance_core_by_id` path checked; commit-1 test still green
- [ ] Blast radius: all ~20 callers audited; **double-decryption checked** (`_decrypt_sensitive_data` on plaintext input)
- [ ] `ticketing_dispatch.py:96` verified: no PII now lands in `ticketing.*` (data rule #3)
- [ ] Full `tests/actions` + `tests/orchestrator` + `tests/backend` green vs baseline
- [ ] **Commit 3** — `decrypt_ciphertext`/`reveal_field` deleted; `scrub_pii_value` decision recorded (fail-loud, not silent-mask); commit-1 test still green
- [ ] **Commit 4** — `db_encryption_key` removed from ticketing settings + compose + `env.local`; **left on `backend`**; commit-1 test still green
- [ ] Grep-guard test: `ticketing/` no longer references `db_encryption_key`
- [ ] Backend test: `get_grievance_by_id` returns plaintext — verified red pre-fix
- [ ] Docs updated: `13_security.md`, `seah/02_vault_privacy_and_reveal.md:58`, **`CLAUDE.md:121`** (currently false)
- [ ] Manual: standard card shows real PII; SEAH masked + reveal works; chatbot status-check still renders; ticketing serves with the key absent

### T3-02 p2 — Characterization tests
- [ ] `status_check_form` interior (`1562`–`1858`) characterized
- [ ] `add_more_info_flow` / `add_missing_info_otp_flow` / `add_missing_info_flow` characterized (205 lines, currently zero refs)
- [ ] Driven over HTTP (`post_turn` → `/message`), matching the existing suite's shape
- [ ] Bugs found while characterizing are **recorded, not fixed** (tests pin current behavior) → Deviations + followups

### T3-05 — Settings extraction
- [ ] `friendlyError` moved first (34 call sites)
- [ ] 6 clusters extracted, **one commit each**, ascending risk: AdminAccess → Locations → SystemConfig → Roles → Workflows → Projects
- [ ] The 2 cross-cluster imports wired (`RoleCreateModal` → workflows `StepForm`; `ProjectWorkflowsEditor` → projects `ProjectEditor`)
- [ ] Code moved **verbatim** — no renames/restyles/re-types in a move commit
- [ ] `page.tsx` down to ~250 lines (shell + `MAIN_TABS` + `SettingsSubTabs` + `ComingSoon`)
- [ ] `tsc` clean / `eslint` 0 errors + warnings **not increased** / `build` green / 61 vitest green — at **every** commit
- [ ] Per-tab smoke tests added (or deferral logged)
- [ ] **Bundle size measured** before/after — reported honestly even if it didn't move
- [ ] Manual: every tab at every role tier; gating unchanged

---

## Deviations

> Log every deviation from the spec, every adjacent bug found and **not** fixed, and every deferral. Standing rule: [`../README.md`](../README.md) — a deferral not logged here **and** in `docs/TODO.md` 🔵 TECH DEBT **and** in `followups/` is a defect, not a deferral.

### Opened at sprint planning (2026-07-15)

| # | Finding | Disposition |
|---|---|---|
| D-01 | **The source review's Tier-3 table is wrong in 4 of 5 rows.** Full evidence in [00-reassessment.md](00-reassessment.md). | Corrections owed to `devils_advocate_codebase.md` at close-out (listed in 00-reassessment.md §Consequences). Sprint tickets follow the **corrected** findings. |
| D-02 | `file_name` derived from module name (`base_mixins.py:63`) — affects **~200** sites; the *real* refactorability blocker T3-01 was nominally aimed at. M+. | **Deferred** → [`followups/utterance-file-name-derivation.md`](followups/utterance-file-name-derivation.md) + TODO.md |
| D-03 | Ticketing reads `public.grievances` (`services/grievance_content.py:22-38`, incl. the raw narrative) and `public.file_attachments` (`routers/tickets/files.py:91`, `api/ticket_access.py:167`) **directly via its own session** — violates data rules #1/#5. | **Deferred** → [`followups/ticketing-cross-schema-direct-reads.md`](followups/ticketing-cross-schema-direct-reads.md) + TODO.md. **T3-04 must not claim the boundary is fully unified.** |
| D-04 | `run_flow_turn` CC measured at **189**, not the reviewed ~120. Line counts (1,485 / 2,303) exact. | Recorded; correction owed to the review at close-out. |
| D-05 | `check_form_function_name` (`base_mixins.py:313`) is defined and **never called** — a guard built for exactly the T3-01 bug class, never wired up. | **In scope for T3-01** (wire up or delete). |
| D-06 | ~~`get_buttons` (`base_classes.py:126`) has the identical introspection flaw~~ → **CORRECTED 2026-07-15: it is DEAD CODE.** AST+MRO shows 0 of 200 call sites reach it; all 76 `get_buttons` calls go through `ActionHelpersMixin`'s explicit path. The `get_buttons` calls in the same files live in sibling `Ask*` classes. | **In scope for T3-01 — but DELETE, not fix.** Free win. |
| D-13 | **T3-01 reachability is UNTRACED.** The 3 keys provably don't resolve, but whether their branches can be hit at runtime is unknown — they may be dead or swallowed. Surfaced by a second independent assessment (the H2-08 agent), which correctly refused to assert reachability it hadn't traced. | **GATES T3-01's phase** (Phase 1 bug fix vs Phase 3 refactor). ~10 min. **Do first.** Deliverable unchanged either way. Record the verdict here before starting T3-01. |
| D-14 | Call-site count disputed between two assessments: 4/196 (this pass) vs 6/180 (H2-08 pass). Settled by AST+MRO: **4 introspection / 196 explicit / 0 unresolved**. Not load-bearing — both concluded *below M*. | Recorded. **Resolve by MRO, never by grep** (`ValidateFormOtp` has multiple bases). |
| D-15 | **Spec error, self-inflicted:** `02-webchat-voice-spec.md:82` credited the FormData-rebuild-on-retry precedent to **H2-08** (the SEAH mixin/Nepali sprint). The actual precedent is **H2-01 + the `apifetch-refresh-non-json-sites` follow-up**. | ✅ **Fixed 2026-07-15** in the spec. Recorded because it would have sent an agent to read the wrong sprint. |
| D-07 | `isIgnorableLateChunkError` swallows `"out of order"` unconditionally (`voiceNote.js:32-34`) → **silently truncated voice notes**; review never mentioned it. | **In scope for T3-03** (serializing kills the class). |
| D-08 | `run_flow_turn` has **no terminal `else`** → unrecognized state returns zero messages (dead air). | **In scope for T3-02 p1.** |
| D-09 | **No test imports `pii_vault`**; `test_ticket_access_matrix.py:68` asserts against the `_backend_unavailable` branch and would pass whether decryption works or is deleted. | **In scope for T3-04 commit 1** (the test net is the first commit). |
| D-10 | `CLAUDE.md:121` — "Grievance API … handles PII decryption" is **factually false today**. | Fixed by T3-04 step 2; doc corrected in T3-04 step 4. |
| D-11 | No JS test suite exists for `channels/REST_webchat/` at all. | Decision point in T3-03 (§Tests). If (b) is chosen, log the harness as a followup. |
| D-12 | `app/settings/page.tsx` has **zero** direct test coverage (portal vitest = 61 tests, none on settings). | T3-05 adds smoke tests, or logs the deferral. |

### During execution

*(append here — one row per deviation, with commit ref)*

| # | Finding | Ticket | Disposition |
|---|---|---|---|
| — | — | — | — |

---

## Inherited pending-human debt (NOT cleared by this sprint)

Carried from Tier 1 / Tier 2 — listed so they aren't forgotten, but they are **not** in this sprint's DoD:

- HR-07 webchat manual browser sweep (**overlaps T3-03's manual sweep — do them together**)
- HR-05 live deliberate-failure + branch-protection checks
- H2-01 Keycloak token-expiry sweep; H2-02 / H2-06 UI click-through parity (**overlaps T3-05's manual sweep**)
- H2-08 SEAH EN/NE webchat walk-through (**overlaps T3-01's manual sweep**)
- CI-on-integration + merge from `dev/tier2-quality`
- `@integration` backend tests quarantined (`-m "not integration"`)
- SEAH translation fact-check (`docs/seah/translations_seah_review.csv`)
