# Tier-3 Structural Sprint — Progress

> Update at **every commit** on `dev/tier3-structural`. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · **Reassessment (read first): [00-reassessment.md](00-reassessment.md)** · Source review: [`../../reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md)

## Ticket status

| ID | Title | WS | Phase | Status | Commits | Notes |
|---|---|---|---|---|---|---|
| T3-01 | Explicit utterance keys + repair 3 non-resolving keys + delete dead `get_buttons` | A | **1** | **done** | `dev/tier3-structural` | **§0 gate answered (D-13): Phase 1 CONFIRMED — two live bugs, not latent.** `form_seah_1` was a **HTTP 500** on SEAH intake; the category-review site was **silent** (0 messages + wrong slots). Site 4 proved **dead** → logged (D-22), not fixed. Introspection deleted, `key` now required; dead `get_buttons` + dead `check_form_function_name` deleted; swallow narrowed. **Only 1 new mapping entry needed — sites 2/3 reuse existing reviewed copy (D-23).** 15 new call-site tests (10 red pre-fix). Suites 188/1 vs 173/1 baseline. Manual EN/NE sweep pending-human (D-24). Spec [01](01-conversation-layer-spec.md) §1. |
| T3-02 p1 | `run_flow_turn`: delete `form_dust` + `submit_grievance`, add terminal `else` | B | 1 | todo | — | **Severable — land in Phase 1 even if p2-4 slip.** 31 deleted lines + 1 `else`. Terminal-`else` absence = dead-air bug. Spec [01](01-conversation-layer-spec.md) §2. |
| T3-03 | Serialize voice-chunk uploads behind chunk-0's `upload_id` | C | 1 | **done** | `dev/tier3-structural` | **Live bug — fixed.** Queue serialized; `FormData` rebuilt per attempt; `"out of order"` swallow gated on `isStopping`. Server untouched. Harness decision: **(a)** — vitest seeded for `channels/REST_webchat/` + wired into CI (closes D-11). 7 client tests (4 verified red pre-fix) + server contract test. Manual Slow-3G sweep **pending-human** (D-17). Spec [02](02-webchat-voice-spec.md). |
| T3-04 | Unify the PII boundary (backend decrypt → delete workaround → drop key) | D | 2 | todo | — | **⚠️ STRICT ORDER — see spec [03](03-pii-boundary-spec.md) §Order.** Review misdiagnosed; fix is in `backend/`, not `ticketing/`. Touches a stable shared service (~20 callers). |
| T3-06 | Harden the grievance API: authn + authz + read audit + `response_model` | F | **2** | **done** | `2b0190c5` · `696b7410` · `590f48e2` · `089318dc` | **§0 gate answered (D-25): `:5001` is NOT internet-open ⇒ Phase 2 confirmed, not an incident.** Read live from the AWS SG, not inferred. Order followed: contract → audit → client-key → authn. **Verified red: unauthenticated the GET returned 200 with `grievance_description`** (D-30). Spec's "commit 3" **split in two** (D-29) — the clients sent *no* key, so one commit couldn't meet its own precondition. `response_model` = 51 fields, `extra="allow"` (a strict model **silently drops** columns — verified); text fields typed `Any` because `_parse_field_from_database` json-parses every string (D-28). Audit = structured log at **INFO** (D-27). Rate limit **deferred + logged** (D-31) ⇒ §6's chokepoint is **2/3 built**. Suites: backend 140/1 (+33), ticketing 549/5 (+5), actions+orch 188/1 (`+15` = T3-01's). **Authz deferred by design** — see note. Manual sweep pending-human (D-33). **Bonus finding: orchestrator `:8000` IS open + unauthenticated (D-35).** Spec [05](05-grievance-api-hardening-spec.md). |
| T3-07 | Amend the data rules to as-built; pin no-FK + no-PII-columns with tests | F | 3 | todo | — | **Docs + tests only — no runtime changes.** Implements the §6 boundary DECISION: drop "no joins into `public.*`" (false for months, unenforceable, honoring it would degrade security); keep + pin the two rules that hold. Absorbs the `grievance_sync.py` column-list TODO row. Spec [06](06-boundary-policy-spec.md). |
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

### T3-01 — Explicit utterance keys ✅ DONE

- [x] **§0 reachability traced — verdict in D-13. Phase 1 CONFIRMED (live bug fix).** Sites 2 + 3 **reachable**; site 4 **dead**. Traced statically (importer graph, `_FORMS` registry, compose services) **and empirically** (each validator invoked directly, both languages).
- [x] `try/except` checked at the 2 previously-unchecked sites: `form_seah_1.py:199` has **none** (⇒ 500); `form_story_main_route_step.py:33` has none (moot — dead).
- [x] **`BaseFormValidationAction.get_buttons` DELETED** — 0 callers **re-confirmed by AST+MRO myself** (D-06): every `Validate*` class on that base has *only* a `get_utterance` call; all 76 `get_buttons` calls sit in sibling `Ask*` classes on `BaseAction`/`BaseOtpAction`. The grep trap was real — `form_grievance_complainant_review.py:621/648/651/657` are `Ask*` classes *below* the `Validate` class in the same file.
- [x] `key=` param added to `get_utterance` (`base_classes.py`) — **keyword-only and required**, not optional
- [x] All 4 call sites pass explicit keys. **AST+MRO census re-run on today's tree: 4 introspection / 196 explicit / 0 unresolved — reproduces exactly** (`introspection by method: {'get_utterance': 4}`, zero `get_buttons`).
- [x] Mapping entries — **only 1 new entry was needed, not 3 (see D-23)**. Sites 2 and 3 point at existing, already-reviewed, already-translated copy authored *for those very branches*; only the dead site 4 needed new copy. NE AI-translated per the standing directive → [`translations_t3-01_review.csv`](translations_t3-01_review.csv), **1 row, `needs_translator=0`**. `form_story_main_route_step` added as a top-level key (module **not** renamed — 200-site blast radius).
- [x] Introspection deleted (`f_back` line + `inspect` import + the now-unused `get_buttons_base` import); `key` is required
- [x] Swallow narrowed at `form_grievance_complainant_review` — `except Exception` → `except (ValueError, KeyError)`, and a `ValueError` from the utterance layer is **re-raised** rather than becoming a `SKIP_VALUE`. The recoverable `.remove()`-on-absent-category case it actually existed for stays handled.
- [x] `check_form_function_name` (`base_mixins.py`) **DELETED** (D-05). It is an *instance method* needing `self.logger` (so it could not be called from a test as the spec's "use it in the new test" suggested), and it only checks `[form][action]` exists — strictly weaker than the new test, which checks form + action + **index** + **both languages** across every call site. Two mechanisms for one invariant is how the weaker one rots.
- [x] `tests/actions/test_utterance_key_integrity.py` — walks **call sites** by MRO, not the dict; scoped to `get_utterance`. Includes a *guard-the-guard* test (a resolver that finds nothing must fail loudly, not vacuously pass), a census pin (4 sites), and a `get_buttons`-never-returns pin.
- [x] **Verified red pre-fix** — see the evidence table below
- [x] Swallow regression covered: the branch **is** reachable, so it is exercised directly (probe + `test_call_site_key_resolves`) — no need for the D-13 fallback the spec described
- [x] Full `tests/actions` + `tests/orchestrator`: **188 passed / 1 skipped** vs baseline **173 / 1** (+15 = exactly the new file). No regressions.
- [ ] Manual: EN + NE re-prompts render at the repaired sites — **PENDING-HUMAN (D-24)**: no browser in the build env. **Largely pre-empted**: the §0 probe drove both live sites in EN *and* NE and captured the rendered strings (below). Combine with H2-08's pending SEAH walk-through.
- [x] §0 found site 4 dead ⇒ dead-code finding logged (D-22 + followup + TODO row), **not fixed here**

**Red-pre-fix evidence (HR-04 standard).** `tests/actions/test_utterance_key_integrity.py` on pre-fix source ⇒ **10 failed / 5 passed**; after ⇒ **15 passed**. The `form_otp` control passing pre-fix is what proves the suite isn't failing on everything:

| Test | Pre-fix | Evidence |
|---|---|---|
| `test_call_site_key_resolves` × 3 broken sites | 🔴 | `ValueError` — key resolves nowhere |
| `test_call_site_key_resolves[form_otp:352]` | 🟢 | **control** — the one site whose key exists |
| `test_call_site_ne_is_translated` × 3 | 🔴 | can't resolve to compare |
| `test_call_site_passes_an_explicit_key` × 4 | 🔴 | all 4 relied on `f_back` introspection |
| `test_no_introspecting_get_buttons_call_sites` | 🟢 | pins D-06 (already 0 callers) |
| `test_introspection_sites_are_the_known_four` | 🟢 | census pin |

**Empirical before/after (the actual user impact, both languages).** Each validator invoked directly:

| Site | Before | After |
|---|---|---|
| 3 `form_seah_1` (SEAH intake, unrecognized reply) | `ValueError` → `form_loop.py:231` (unguarded `getattr` call) → `main.py:135` ⇒ **HTTP 500** | EN *"Please choose anonymous grievance or grievance with contact details."* · NE *"कृपया बेनामी गुनासो …"* |
| 2 `form_grievance_complainant_review` (user happy with categories) | **0 messages**, slots `{status: 'LLM_generated', cat_modify: 'slot_skipped'}` — the `ValueError` laundered into a skip | EN *"No category selected. skipping this step."* · NE *"यदि कुनै समूह चयन गरिएको छैन …"*, slots `{status: None, …}` — **the correct confirm shape** |

Note site 2's fix restores **both** the message and the slot state: `grievance_categories_status` was being set to `LLM_GENERATED` by the swallow, not just silenced.

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

### T3-03 — Voice-chunk serialization ✅ DONE

- [x] Chunk queue serialized (chunk N chains on N-1) in `voiceNote.js` — `enqueueRecordingChunk` chains on the previous chunk's **settlement** (`uploadChain`), so one failed chunk is not re-reported once per queued chunk. `resetUploadState` resets the chain. `Promise.all(pendingChunkUploads)` join at stop preserved.
- [x] `FormData` built **inside** the retry closure (`voiceChunkUpload.js`) — follows the `authedFetch` precedent. **`uploadId` value → `getUploadId` resolver**: rebuilding the body alone was *not* enough — the param was captured at call time, so a rebuilt body would have re-read the same stale `null`. Only caller was `voiceNote.js:74`, so the signature change is contained.
- [x] `"out of order"` swallow gated on `isStopping` (`voiceNote.js`) — kills the silent-truncation path
- [x] Server **not** changed (it is correct)
- [x] **Test-harness decision: (a)** — `channels/REST_webchat/{package.json,vitest.config.js,.gitignore}` + `modules/__tests__/`. Node-env vitest, hand-rolled fakes, **no jsdom** (the modules are transport/ordering logic, not DOM). The fake server mirrors `files.py`'s real contract so a client bug fails here the way it fails in prod. **CI wired in the same commit** (`webchat-checks` job) ⇒ **D-11 closed, no followup owed.**
- [x] Race test — **verified red pre-fix**
- [x] Ordering / retry-heals / truncation-guard / fast-network-no-regression tests
- [x] `tests/backend/test_fastapi_files.py` extended: id-less chunk > 0 ⇒ 400 (`test_upload_voice_chunk_without_upload_id_after_first_is_rejected`)
- [ ] Manual: Slow 3G ≥5 s recording completes + plays back full length — **PENDING-HUMAN (D-17)**: no browser in the build env. Do together with HR-07's webchat sweep.

**Red-pre-fix evidence (HR-04 standard).** Final tests run against pre-fix source via `git stash push -- <the 2 modules>` ⇒ **4 failed / 3 passed**; restored ⇒ **7 passed**. The 3 that pass pre-fix are the guard tests — they are what proves the suite isn't just failing on everything:

| Test | Pre-fix | Evidence |
|---|---|---|
| Race — every chunk > 0 carries an `upload_id` | 🔴 | later chunks id-less ⇒ 400 |
| Ordering — one at a time, in index order | 🔴 | `[0,1,2,1,2,1,2]` — the concurrent retry storm, caught verbatim |
| Mid-recording 409 surfaces | 🔴 | `['recording']` only — no `upload_error`; the silent truncation |
| Retry re-reads `upload_id` | 🔴 | `[null, null]` — the frozen body, caught verbatim |
| Late 409 **after** stop still ignored | 🟢 | guard: the legitimate swallow still works |
| Fast network unchanged | 🟢 | no-regression baseline |
| Retry exhaustion surfaces server status | 🟢 | existing behavior pinned |

**Suites:** webchat vitest **7/7** (new baseline) · `tests/backend/test_fastapi_files.py` **20 passed** (was 19 + 1 new).

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

### T3-06 — Grievance API hardening ✅ DONE (manual sweep pending-human)

- [x] **§0 FIRST — EC2 :5001 inbound checked** (staging security groups). **ANSWERED: NOT open ⇒ Phase 2 confirmed, not an incident (D-25).** Read live from the AWS account, not inferred from the repo. **Prod (DOR infra) remains unverified — carried as an open TODO row (D-26).**
- [x] Full HTTP caller inventory recorded in PROGRESS.md **before** commit 1 — see §T3-06 caller inventory below. **Confirmed no browser/webchat JS calls `/api/grievance/*`** (the sole `channels/` hit, `ticketing-ui/lib/api.ts:2719`, is a comment).
- [x] **Commit 1** (`2b0190c5`) — `response_model` on the GET; **payload not narrowed**; the 9 `grievance_content.py` fields present. **Inertness proved against a real row: 51 fields before and after, envelope byte-identical.**
- [x] Schema-drift test — model fields checked against their **owning** tables (D-28), both directions, mutation-verified.
- [x] **Commit 2** (`696b7410`) — read audit incl. **caller identity**; emits at **INFO**; **verified red** (switching to `.debug` fails 5 tests). Log-vs-table decision recorded (D-27).
- [x] **Commit 3** (`590f48e2` client key) + **Commit 4** (`089318dc` enforce) — `Depends(_ticketing_auth_check)` on **both** endpoints; every caller confirmed sending the key **first** (D-29); `AUTH_MODE=bypass` dev loop still works (pinned by test).
- [x] 401-without-key / 200-with-key on **both** endpoints — **verified red pre-fix**: unauthenticated, the GET returns **200 carrying `grievance_description`** (D-30).
- [x] Rate limit **deferred, logged** ([`followups/grievance-api-rate-limiting.md`](followups/grievance-api-rate-limiting.md) + TODO row) — measured: no reusable mechanism reaches these endpoints (D-31).
- [x] Full `tests/backend` (140/1, +33) + `tests/actions` + `tests/orchestrator` (188/1 — `+15` is T3-01's, not this ticket) + `tests/ticketing` (549/5, +5) green vs baselines.
- [ ] **Manual: chatbot file + status-check end-to-end; portal acknowledge + resolve — PENDING-HUMAN (D-33).** `curl` GET without key ⇒ **401 verified** (D-32).
- [x] Prod `5001:5001` host mapping — **necessity recorded, not dropped**: it is in `grm.yml` (shared, not a prod overlay) and compose **merges** `ports`, so it cannot be cleanly overridden per-overlay (D-34) → [`followups/grievance-api-host-port-binding.md`](followups/grievance-api-host-port-binding.md).
- [ ] **`authz` — NOT DONE. The ticket's title promises it; its steps never define one, and the `x-api-key` scheme cannot express it (D-38).** A service key says "this is ticketing", not "this is officer X in district Y", so the SEAH/jurisdiction gate the §6 table compares against is not derivable from it. Left open deliberately rather than silently dropped.

#### What T3-06 actually closed — the §6 scorecard

The ticket exists because §6 measured `GET /api/grievance/{id}` on four properties and found it worse than the direct SQL read it was supposed to replace. Post-T3-06:

| Property | Before | After T3-06 |
|---|---|---|
| Authn | none | ✅ `Depends(_ticketing_auth_check)`, both endpoints |
| Response contract | none (`SELECT g.*` → untyped dict) | ✅ `response_model`, 51 fields, drift-gated |
| Read audit | none | ✅ structured log at INFO, with principal (**not** a queryable table — D-27) |
| **Authz** | none | ❌ **still none** (D-38) — needs officer identity, not a service key |
| Rate limit | none | ❌ **still none** (D-31) — no reusable mechanism reaches `:5001` |

**⇒ The endpoint is no longer the least-protected path to grievance data — but it is still not an authorization chokepoint.** The §6 DECISION to legitimize ticketing's direct reads as-built **survives unchanged**: the direct read keeps a JWT + jurisdiction gate the API still cannot offer. **Do not cite T3-06 as having made "route reads through the API" viable.** It made the *option* discussable, which is exactly what the spec claimed for it — no more.

#### T3-06 caller inventory (recorded before commit 1, per the spec's step 0)

Grepped repo-wide. **Every HTTP call funnels through two functions in one file** — `ticketing/clients/grievance_api.py`:

| Endpoint | Client fn | Callers | Sent `x-api-key` before T3-06? |
|---|---|---|---|
| `GET /api/grievance/{id}` | `get_grievance_detail` | `api/routers/tickets/pii.py:55`, `services/resolved_summary_builder.py:139`, `clients/grievance_api.py:218` (`begin_reveal_session` proto fallback) | **NO** ⇒ fixed in `590f48e2` |
| `POST /{id}/status` | `update_grievance_status` | `engine/ticket_actions.py:375`, `services/archiving.py:247`, `:312` | **NO** ⇒ fixed in `590f48e2` |
| `GET /api/grievance/statuses` | `get_grievance_statuses` | no non-test caller | n/a — endpoint stays public |
| `PATCH /{id}/classification` | `patch_grievance_classification` | — | yes (already) |
| `PATCH /api/complainant/{id}` | `patch_complainant` | — | yes (already) |
| chatbot in-process | — | ~20 non-test callers of `grievance_manager.get_grievance_by_id` | n/a — **not HTTP**, unaffected by authn (confirmed: 173 baseline tests still green) |
| browser / webchat | — | **none** | n/a |

**The spec's table said "verify" for the first two rows. Verdict: neither authenticated.** Only the two PATCHes did — which is why this was 2 of 5 endpoints rather than a missing convention.

### T3-07 — Boundary policy amendment
- [ ] **Commit 1** — `CLAUDE.md` §Data rules amended: rule 1 → enumerated read/write contract (5 tables); rules 2/3 kept + marked pinned; rule 4's free-text caveat stated; rule 5 scoped to PII only
- [ ] `CLAUDE.md:121` fixed — **coordinate with T3-04 step 4, which also owns this line** (whichever lands second must not revert the other)
- [ ] **Dated pointer to §6 added so the rationale survives** — this is the ticket's whole point; `21631051` deleting the March rationale is why the rule read as fiat for a year
- [ ] **Commit 2** — no-cross-schema-FK guard test (**green today** — pins an invariant, not a bug fix; say so in the docstring)
- [ ] No-complainant-PII-columns guard test (green today)
- [ ] Contract-drift guard over the enumerated `public.*` reads; **proven to go red** when a column is renamed in a scratch DB
- [ ] `grievance_sync.py` hardcoded-column-list TODO row **closed** by the drift guard (same family)
- [ ] **Commit 3** — `04_ticketing_schema.md:4` (restore the March rationale), `09_privacy.md:25-27` (motivated by a retired worktree model), `03_ticketing_api_integration.md` (document the contract), `00_ticketing_overview_and_questions.md:42`
- [ ] `followups/ticketing-cross-schema-direct-reads.md` closed with the decision + §6 pointer; its TODO.md row retired
- [ ] `scripts/ops/create_scoped_roles.sql:50` — comment is factually wrong (3 writes exist) and grants cover **1 of 5** tables; fixed or marked unsafe-as-written
- [ ] Full `tests/ticketing` green vs baseline
- [ ] **`git diff --stat` shows docs + tests only** — no runtime file changed

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
| D-03 | ~~Ticketing reads `public.grievances` + `public.file_attachments` **directly via its own session** — violates data rules #1/#5.~~ → **SUPERSEDED 2026-07-15 by D-19.** The framing was wrong on three counts: the surface is **11 statements / 5 tables / 3 writes**, not 3 reads; the rule violated protects a goal both sides of the codebase abandoned; and the prescribed fix (route via the API) is a **security downgrade**. | **Reclassified, not deferred.** Rule dropped per the §6 DECISION → **T3-07**. The reads are **legitimized as-built**. **T3-04 must still not claim the boundary is fully unified** — that part stands. |
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
| D-11 | No JS test suite exists for `channels/REST_webchat/` at all. | ✅ **CLOSED by T3-03 (2026-07-15).** Path **(a)** taken: vitest harness seeded at `channels/REST_webchat/` + `webchat-checks` CI job, both in the same commit. No followup owed — the CI wiring the spec allowed deferring was completed. The webchat now has a test suite where it had none. |
| D-12 | `app/settings/page.tsx` has **zero** direct test coverage (portal vitest = 61 tests, none on settings). | T3-05 adds smoke tests, or logs the deferral. |

### During execution

*(append here — one row per deviation, with commit ref)*

| # | Finding | Ticket | Disposition |
|---|---|---|---|
| D-25 | **§0 PHASE GATE ANSWERED — `:5001` is NOT internet-open. Not an incident.** Read live from the AWS account (`ap-southeast-1`), not inferred: SG `sg-01739221c73ab3eb1` — attached to `chatbot-main` **and** `chatbot-rest` — admits **80, 443, 22 (158.62.26.255/32), 8000, 3000, and tcp/0 (103.41.172.170/32)**. **No rule matches 5001.** Corroborates the repo-side reasoning (no `location /api/grievance` in any nginx conf). All 7 instances in the account are currently **stopped**. | **T3-06** | **Phase 2 CONFIRMED** — D-20's gate resolved. The unauthenticated endpoints were reachable only from the host/Docker network, never the internet. TODO row updated from "⚠️ UNVERIFIED" to the measured answer. |
| D-26 | **Prod (DOR) firewall is NOT verifiable from here.** Production is `grm-chatbot.dor.gov.np` on **DOR infra**, not this AWS account (CLAUDE.md §Superseded), so D-25 clears **facets/staging only**. No repo artifact can answer it. | T3-06 | **Open — carried to TODO.md** as a question for whoever operates DOR infra (`:5001` and `:8000` inbound). Mitigated but not closed by the authn now shipping: an open port is no longer an *anonymous* read. |
| D-27 | **Read audit: structured log, not a `public.*` table** — the spec's own recommendation, taken. Own logger name (`audit.grievance_read`) so the trail is filterable/shippable and promotable to a table later without touching call sites. JSON payload; **INFO** (not `.debug`, which is invisible at the deployed `LOG_LEVEL=INFO` — the exact way `grievance_manager.py:172` already fails to be a trail). | T3-06 | **Decision recorded per the spec.** A log line is reversible; a `public.*` table is a migration-stream commitment (CLAUDE.md §Migration traceability). Revisit if the trail must be queryable/retained. |
| D-28 | **The spec's drift test ("model's fields exist in `public.grievances`") is under-specified — implemented stronger.** `get_grievance_by_id` is **not** just `SELECT g.*`: it **joins `complainants` + `grievance_parties`**, so of the **51** response fields only **23** are grievances columns (26 complainants, 2 parties). Checking all 51 against `grievances` alone would fail on 28 correct fields. Each field is checked against its **owning** table, plus the reverse direction (a new `grievances` column must be declared). Reads the **CL-01 canonical baseline** (`expected_public_schema.sql`) that CI already pins ⇒ no live DB needed. | T3-06 | **Deviation taken deliberately — better than the spec.** Both directions mutation-verified (a fabricated new column and a typo'd field each fail the gate), so it is not vacuous. |
| D-29 | **Spec's "commit 3" split into two commits (`590f48e2` then `089318dc`).** The spec makes it binding that *"every caller [is] confirmed sending the key **before** this commit lands"* — but the GET and POST clients **sent no key at all**, so a single commit could not satisfy its own precondition. Client-sends-key landed first (inert; the backend ignored it), enforcement second. | T3-06 | **Deviation taken deliberately — implements the spec's binding requirement literally.** Also makes the breaking change independently revertible without stranding callers. |
| D-30 | **Verified-red evidence is stronger than the spec's phrasing.** The spec says the 401 test should fail "because today it returns 200". With a non-existent id it returns **404** — which only shows the request was *served*, not that data leaked. The test therefore mocks a **real** grievance: pre-fix it returns **200 carrying `grievance_description`** to an anonymous caller. Removing just the two `Depends` fails **6 of 13** tests. | T3-06 | **Recorded.** The disclosure — not the routing — is the finding, and the test now pins it. |
| D-31 | **Rate limit dropped — measured, not assumed.** nginx `limit_req_zone` **does** exist (`webchat_rest_compose_prod.tls.conf:8-10`) but **cannot reach these endpoints**: there is no `location /api/grievance` block, so `:5001` bypasses nginx entirely. No Python limiter is installed. The in-code `rate_limit` hits are outbound geocode throttles / report quotas. | T3-06 | **Deferral logged** ([`followups/grievance-api-rate-limiting.md`](followups/grievance-api-rate-limiting.md) + TODO row), per the spec: §6's chokepoint argument cites rate-limiting, so its absence stays visible. **§6's "loggable, authorizable, rate-limitable" is now 2/3 built, not 3/3.** Not solved by network posture: `_ticketing_auth_check` failures are unthrottled ⇒ the key is brute-forceable. |
| D-32 | **`curl` GET without `x-api-key` ⇒ 401 — verified against the running container**, not only via TestClient. Rebuilt the `backend` image and ran it in the deployed posture (key set, `APP_ENV=production`): no key ⇒ **401**, wrong key ⇒ **401**, valid key ⇒ **200 with all 51 fields and `grievance_description` intact**, `POST /status` no key ⇒ **401**. Separately confirmed the shipped dev config (`env.local`: empty key + `AUTH_MODE=bypass`) still returns **200** ⇒ **the local loop is not broken**. Audit verified under the **real** logging config (not `caplog`): emits at INFO with `principal=ticketing`, client IP and outcome, and the secret appears **0 times** in the logs. | T3-06 | Done — see the T3-06 checklist. |
| D-39 | **A rejected (401) request emits no audit record.** Verified against the container: `_ticketing_auth_check` raises before the handler, so `_audit_grievance_read` never runs. Defensible by design — the spec scopes step 2 as a **read** audit, and a 401 reads nothing; uvicorn's access log still shows the bare 401, but with no principal and outside the audit stream. **Consequence: a caller probing keys leaves no trace in the audit trail.** | T3-06 | **Logged, not built** — outside step 2's scope, and it pairs naturally with the throttle deferred in D-31 (unthrottled **and** unaudited is what makes a brute-force cheap *and* invisible). Folded into [`followups/grievance-api-rate-limiting.md`](followups/grievance-api-rate-limiting.md) DoD item 5 so the two are fixed together rather than separately. |
| D-33 | T3-06's manual sweep (chatbot file + status-check; portal acknowledge + resolve) not executed — no browser in the build env. | T3-06 | **Pending-human.** Joins the same queue as D-24 (T3-01 EN/NE) and D-17 (T3-03 Slow-3G) — one browser session covers all three. **Partly pre-empted**: the officer-portal paths are exercised by `tests/ticketing` (549 green, incl. the PII/reveal + archiving routes that call both endpoints), and the `curl` 401 + container audit check (D-32) cover the endpoint itself. |
| D-34 | **`5001:5001` not dropped — the spec's premise is off.** It says to drop it "from the **prod** overlay"; the mapping is in **`docker-compose.grm.yml`** (shared by dev and both deploys), and compose **merges `ports` by concatenation**, so `docker-compose.aws.yml` cannot override it (you'd get both binds). Removing it outright breaks the documented host-browser dev loop. | T3-06 | **Necessity recorded + deferred** ([`followups/grievance-api-host-port-binding.md`](followups/grievance-api-host-port-binding.md) + TODO row). Defence-in-depth only — D-25 shows the firewall already closes it. Suggested shape: `"${BACKEND_HOST_BIND:-0.0.0.0}:5001:5001"`. |
| D-35 | **NEW SECURITY FINDING, surfaced by D-25's SG check — out of T3-06's scope.** Orchestrator **`:8000` is open to `0.0.0.0/0`** (SG `sg-01739221c73ab3eb1`), **host-mapped** by `docker-compose.grm.yml:122` (the overlay the staging deploy composes), and **`POST /message` has no auth** (`backend/orchestrator/main.py:102`; no `Depends`/`Header` in the module). **Honest severity: lower than it reads** — `/message` is the *public* chatbot entry point, so it discloses nothing the web chat doesn't. What it bypasses is nginx: **no TLS** (plaintext `session_id`) and **no rate limit** (the `public` 30r/m zone is nginx-level) on a path that triggers **LLM spend**. Also `tcp/3000 0.0.0.0/0` appears **vestigial** — no compose file maps 3000. | — | **Logged, not fixed** ([`followups/orchestrator-port-8000-open.md`](followups/orchestrator-port-8000-open.md) + TODO row). **Worth reading as a pair with D-25:** T3-06 spent 4 commits authenticating a port the firewall already **closed**, while the port it leaves **open** has no auth at all. Repo-level reasoning and infrastructure reality pointed opposite ways; only checking both surfaced it. |
| D-38 | **⚠️ THE TICKET'S TITLE PROMISES `authz`; ITS STEPS DO NOT CONTAIN ONE — AND IT IS NOT IMPLEMENTABLE AS SPEC'D.** Title: *"authn + **authz** + read audit + contract"*. The binding Order block lists only `CONTRACT → AUDIT → AUTHN → RATE LIMIT`, and steps 1-4 match. **No step defines authz, so none was built.** This is not an oversight in execution — it is not derivable from the current scheme: `x-api-key` is a **service** credential (`TICKETING_SECRET_KEY` = "this is ticketing"), carrying **no user identity**. The authz the §6 table compares against — `assert_ticket_visibility`, i.e. **SEAH + jurisdiction gating** (`crud.py:446`) — is a **per-officer** decision. A service key cannot express it: after T3-06, *any* holder of the ticketing key can read *any* grievance, incl. SEAH cases, exactly as ticketing's own process can. Real authz here needs the **officer's JWT propagated through ticketing to the backend**, which is a design change (token exchange / on-behalf-of), not a `Depends`. | **T3-06 / T3-07** | **Recorded as an open gap — do not read T3-06 as having closed the §6 authz row.** Post-T3-06 the §6 comparison stands at: **Authn ✅ · Audit ✅ (log) · Contract ✅ · Authz ❌ · Rate-limit ❌ (D-31).** ⇒ **"Route reads through the grievance API" is still NOT equivalent to the direct read**, which keeps its JWT + jurisdiction gate. The §6 DECISION (legitimize the direct reads as-built) therefore **survives T3-06 unchanged and is, if anything, better supported** — the API is now *safer*, but it is still not an authorization chokepoint. **Whoever revisits the boundary must not cite T3-06 as having made the API a credible authz boundary; it made it a credible *authn + audit* one.** |
| D-36 | **Host `pytest tests/ticketing` is broken by stale `env.local` DB credentials** — `108 failed / 234 errors`, all `password authentication failed for user "nepal_grievance_admin"`. `_host_env.py:44-55` prefers `env.local` over its own correct `setdefault("user"/"password"/"app_db")` fallbacks; compose actually runs `user`/`app_db` (verified against the `db` container). **This is the "dead config" `00-reassessment.md` §6 already named** (`grievance_db` "is dead config, overridden by every compose `environment:` block") — but it is not merely unused, it **actively breaks the host test loop** and reads as a code regression. | — | **Logged, not fixed** (TODO row) — out of T3-06's scope. Workaround used for this ticket's baselines: `POSTGRES_USER=user POSTGRES_PASSWORD=password POSTGRES_DB=app_db POSTGRES_PORT=5433 pytest` (the `:54` guard yields to `os.environ`). With it, host and container agree exactly (544/1/5). |
| D-37 | **`tests/backend` is not in CI.** The `backend-tests` job runs `pytest tests/ticketing tests/orchestrator tests/actions` (`.github/workflows/ci.yml`) — **`tests/backend` is absent**, so all 33 tests added by T3-06 (and the 107 pre-existing) are **ungated**. Found while checking whether the new auth tests would pass under CI's env. | — | **Logged, not fixed** — adding a suite to CI is out of a `backend/` security ticket's scope, and `tests/backend` needs a live DB for some tests (`test_get_grievance_statuses`), so it is not a one-line addition. **Mitigated meanwhile:** every T3-06 test was verified green under **four** env configurations incl. CI's exact vars (`TICKETING_SECRET_KEY=ci-test-secret APP_ENV=dev AUTH_MODE=bypass`). Worth a row in the next CI pass. |
| **D-13 ✅ ANSWERED** | **§0 reachability trace done (2026-07-15) — T3-01 CONFIRMED Phase 1, a live bug fix.** Verdict per site, established statically (AST+MRO, importer graph, `_FORMS` registry, compose services) **and empirically** (each validator invoked directly): **Site 2** `form_grievance_complainant_review:495` — **REACHABLE**: `grievance_cat_modify` is a required slot (`:281`) on the mainline category-review path, and the branch is the *"user is happy with the selection"* case, not an error case. Probe returns `{'grievance_categories_status': 'LLM_generated', 'grievance_cat_modify': 'slot_skipped'}` with **zero messages dispatched** — the `ValueError` is laundered into a `SKIP_VALUE` exactly as predicted. **Silent.** · **Site 3** `form_seah_1:199` — **REACHABLE**: `sensitive_issues_follow_up` is a required slot (`:70`) for `role == "victim_survivor"`; **no `try/except`** (was unchecked). Probe raises `ValueError: Error getting utterance: 'validate_sensitive_issues_follow_up'`. It propagates through `form_loop.py:231` (bare `getattr` call, no guard) to `main.py:127-135` ⇒ **HTTP 500 on the SEAH intake flow.** · **Site 4** `form_story_main_route_step:33` — **DEAD** (see D-22). | T3-01 | **Phase confirmed: 1.** Two live bugs, one dead site. **Severity is worse than the reassessment estimated** — it framed these as "error/re-prompt branches only, which is why nobody noticed". Site 2 is a *mainline* branch, and site 3 is a **500**, not a silent skip. C-2's open "if" is now closed: reachable **and** swallowed. |
| D-22 | **`backend/actions/forms/form_story_main_route_step.py` is entirely dead code** (both `ValidateMenuForm` and `ValidateFormStoryStep`, 79 lines). Proof: repo-wide grep for the module name returns **no importer**; `ValidateMenuForm` appears nowhere but its own `class` statement; it is **not** in `form_loop.py`'s `_FORMS` registry (the only thing that instantiates form classes); and **no Rasa action server exists** to auto-discover it by class scan — the sole `action_endpoint` is under `config/source/legacy_rasa_config/`, there is no `rasa run actions` anywhere, and the compose stack has no such service. `backend/orchestrator/config/domain.yml:1054` still declares `validate_form_story_main`, which is what makes it *look* live. | T3-01 | **Deferred — spec §Out of scope: "dead branches … log, don't fix".** → [`followups/dead-form-story-main-route-step.md`](followups/dead-form-story-main-route-step.md) + TODO.md. T3-01 still gives site 4 an explicit key + a mapping entry so the "every call-site key resolves" invariant is **total** with no exclusion list; module + entry get deleted together by the followup. |
| D-23 | **Spec step 4 said "author the 3 missing mapping entries". Only 1 was needed — and authoring 3 would have been the wrong fix.** For sites 2 and 3 the copy **already existed**, translated and reviewed, written *for those exact branches*; the introspection was simply looking it up under the wrong key. **Site 2** → `validate_form_grievance_complainant_review` idx 1 = *"No category selected. skipping this step."* — this is precisely the key `self.name()` yields, i.e. the convention `ActionHelpersMixin` uses for the other 196 sites. **That is the root cause in one line: the copy was authored for the `self.name()` convention and the `f_back` override looked it up by calling-function name.** **Site 3** → `action_ask_form_seah_1_sensitive_issues_follow_up` idx 2 = *"Please choose anonymous grievance or grievance with contact details."* — the ask block's index 2, which **nothing else uses**; it was written for this re-prompt. (`validate_form_seah_1` does not exist, so the `self.name()` convention could not help there.) | T3-01 | **Deviation taken deliberately — better than the spec.** Authoring new copy for 2 and 3 would have **duplicated existing strings under second keys**, re-introducing the exact EN/NE drift class H2-08 spent a sprint merging away — and would have added 2 unnecessary AI translations to live user-facing paths. The spec permits this: step 4 says *"either add it or point the call at the correct existing key"*. Only the dead site 4 got new copy (1 CSV row, `needs_translator=0`). |
| D-24 | T3-01's manual EN/NE browser sweep not executed — no browser in the build env. | T3-01 | **Pending-human.** Overlaps H2-08's pending SEAH EN/NE walk-through and T3-03's Slow-3G sweep — one browser session covers all three. **Largely pre-empted**: the §0 probe drove both live sites in EN *and* NE and captured the rendered strings (see the T3-01 checklist), so the sweep is confirmation rather than discovery. |
| D-16 | **Voice-chunk upload sessions live in a process-local dict** (`file_server_core.py:29-31`), and the `.part` file is a local path. The protocol is stateful across requests, so every chunk must hit the same process. Works today — `docker-compose.yml:48` runs uvicorn with **no `--workers`** (verified) — but adding workers/replicas silently breaks voice notes: chunk 1 gets a 404, which the client **swallows** (`voiceNote.js:31` matches `"not found"`), so it reads as a flaky feature, not a misconfiguration. Same "invisible on dev, deterministic in prod" shape as T3-03 itself. | T3-03 | **Deferred — spec §Out of scope says log, don't fix** (`file_server_core.py` session lifecycle). → [`followups/voice-chunk-session-store-is-process-local.md`](followups/voice-chunk-session-store-is-process-local.md) + TODO.md. **Not a live bug** — do not report it as one. |
| D-17 | T3-03's manual Slow-3G browser sweep not executed — no browser in the build env. | T3-03 | **Pending-human.** Overlaps HR-07's webchat sweep — do both in one session. Automated coverage is the mitigation: the race is now guarded by a test that is verified red pre-fix, which is stronger than the manual check it substitutes for. |
| D-18 | **Scope note — the spec's change 2 was insufficient as written.** It prescribed moving `FormData` construction inside the retry closure. That alone would **not** have healed the retry: `uploadId` was a *parameter*, captured at call time, so a rebuilt body would re-read the same stale `null`. The fix required changing the param to a `getUploadId` resolver. | T3-03 | **Fixed in scope** (single caller, contained). Recorded because the spec's own acceptance test ("retry re-reads a now-populated `uploadId`") could not have passed against the change as literally specified. |
| D-19 | **The `ticketing.*` ↔ `public.*` boundary is vestigial, and D-03's framing of it was wrong.** Measured: **11 statements / 5 tables / 3 writes** ticketing→`public.*` (incl. `DELETE FROM public.grievance_classification_taxonomy`, unqualified), **~12 sites** backend→`ticketing.*` (chatbot intake location validation reads `ticketing.locations` via its own `psycopg2.connect`), **one DB, one role**, zero enforcement. Both goals the March-2026 rule was written to serve are already dead. `public.complainants` — the one table marked *"never touch"* — is joined by a Celery beat job **every 2 min** (`grievance_sync.py:178`, non-PII column only). Archaeology: rules #1/#2 are **genuine architecture** (2026-03-11, pre-dating any AI split, rationale deleted by doc reorg `21631051`); rules #3/#4/#5 have **no recorded rationale ever** and trace to a `.claudeignore` that forbade Claude from reading `backend/services/` plus a hand-written context doc that **falsely** claimed the API decrypts PII — `pii_vault.py` is the workaround that fell out of it. Full evidence: [00-reassessment.md](00-reassessment.md) §6. | T3-07 | **DECIDED 2026-07-15 by the project owner** (§6 → DECISION): drop rule #1, keep + **pin** no-FK and no-PII-columns, amend the docs to as-built. Supersedes D-03. Closes the followup's DoD item 1. |
| D-20 | **`GET /api/grievance/{id}` and `POST /api/grievance/{id}/status` are unauthenticated** (`backend/api/routers/grievance.py:249`, `:202`) — no `Depends`, while the two `PATCH`es beside them have `Depends(_ticketing_auth_check)`. The GET returns the full record incl. `grievance_description`; the POST **mutates state and fires SMS + email to the complainant** (`:227`). No read audit exists in `backend/` at all. Both bound to the host via `docker-compose.grm.yml:117` (`5001:5001`); **not** proxied by prod nginx. | **T3-06** | **New ticket** → [`05-grievance-api-hardening-spec.md`](05-grievance-api-hardening-spec.md). **⚠️ Phase gate: EC2 :5001 inbound is UNVERIFIED from the repo.** If open ⇒ Phase 1 / incident. **Check the security groups first.** |
| D-21 | **The followup doc's load-bearing justification is inverted.** [`followups/ticketing-cross-schema-direct-reads.md:50`](followups/ticketing-cross-schema-direct-reads.md) asserts reads via `GET /api/grievance/{id}` *"**are** loggable, authorizable, and rate-limitable at one place."* **None of the three is implemented** (D-20) — the verb should be *"could be"*. The direct SQL it condemns sits behind Keycloak JWT + a jurisdiction gate + an audit model; the API has none. Its DoD item 2 ("extend the API to serve what `grievance_content.py` needs") is **already satisfied** — 9/9 fields ship via `SELECT g.*`, and `resolved_summary_builder.py:139-150` already reads `grievance_description` over HTTP. Its unpriced cost: `grievance_sync.py` pages 500 rows/2 min and the API has **no bulk endpoint**. | T3-07 | **Doc corrected in T3-07 step 3**; the followup is closed with the decision rather than executed. Recorded because it was 1 sprint away from being implemented as written. |

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
