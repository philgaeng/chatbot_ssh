# T3-01 / T3-02 — Conversation layer (utterances + `run_flow_turn`)

> Workstreams A (T3-01) and B (T3-02) · Branch `dev/tier3-structural` · **Independent of each other** (`backend/actions/` vs `backend/orchestrator/`) — may run in parallel.
> Evidence: [`00-reassessment.md`](00-reassessment.md) §4 (T3-01) and §1 (T3-02). **Read it first — the source review is wrong about both.**
> Line numbers as of `dev/tier3-structural` @ 2026-07-15 — **re-locate before editing.**

---

## 1. T3-01 — Explicit utterance keys (S)

### Problem (verified by hand, 2026-07-15 — corroborated by a second independent assessment)

**3 of 4 call sites derive mapping keys that do not resolve** ⇒ `ValueError`. Whether this is a *live* bug or a *latent* one depends on an untraced question — see §0 immediately below. **Resolve that first; it decides this ticket's phase.**

`BaseFormValidationAction.get_utterance` (`backend/actions/base_classes/base_classes.py:118-122`) derives the mapping key from the **calling function's name** via stack introspection:

```python
def get_utterance(self, utterance_index: int=1):
    function_name = inspect.currentframe().f_back.f_code.co_name
    return get_utterance_base(self.file_name, function_name, utterance_index, self.language_code)
```

`get_utterance_base` **raises `ValueError`** on a missing key (`utils/utterance_mapping_rasa.py:2310-2312`).

### §0 — DO THIS FIRST: trace reachability (~10 min, gates the phase)

The three keys provably don't resolve. **Whether their branches can be hit at runtime is UNTRACED** — they may be dead, or swallowed upstream.

- **Reachable** ⇒ this ticket stays **Phase 1**, a latent-bug fix. Land it first.
- **Dead / fully swallowed** ⇒ demote to **Phase 3**, pure refactorability; the three branches become a *dead-code* finding to log separately.

**The deliverable below is identical either way** — only the urgency and the "verified red" framing change. Record the verdict in [`PROGRESS.md`](PROGRESS.md) → Deviations before starting.

**Where to start:** `ValidateMenuForm.validate_language_code` (`forms/form_story_main_route_step.py:33`) — the cleanest case. Reachable iff `language_code` can be filled with a value outside `["en","ne"]`, so the question reduces to whether that slot is button-only or accepts free text. It is also the only one where the **file key is absent entirely**, not merely the action key. Then check whether `form_seah_1.py:199` and `form_story_main_route_step.py:33` sit inside a `try/except` — **only the category-review site has been checked** (it does: `try:` at `:493`, `except Exception` at `:525`).

> **This uncertainty is the ticket's own justification.** With introspection keys you *cannot answer reachability statically* — that is the whole argument for explicit keys, and precisely why H2-08's integrity tests (which validate the mapping **data**) structurally cannot catch this class.

**The four call sites** — these are *all* of them, established by **AST + MRO resolution** over `backend/actions/` (200 total `self.get_utterance`/`get_buttons` sites: **4 introspection / 196 explicit / 0 unresolved**). `ActionHelpersMixin.get_utterance` (`base_mixins.py:303`) already uses the explicit `self.name()` and serves the other 196 — **do not touch those**.

| # | Call site (class) | Derived key | Status |
|---|---|---|---|
| 1 | `forms/form_otp.py:352` (`ValidateFormOtp`) | `validate_otp_input` | ✅ resolves — **the control** |
| 2 | `forms/form_grievance_complainant_review.py:495` (`ValidateFormGrievanceComplainantReview`) | `validate_grievance_cat_modify` | ❌ key missing — **wrapped in `try/except` at `:493`/`:525`** |
| 3 | `forms/form_seah_1.py:199` (`ValidateFormSeah1`) | `validate_sensitive_issues_follow_up` | ❌ key missing — `try/except` **unchecked** |
| 4 | `forms/form_story_main_route_step.py:33` (`ValidateMenuForm`) | `validate_language_code` | ❌ **file key absent entirely** — `form_story_main_route_step` isn't a top-level mapping key; `try/except` **unchecked** |

> **Resolve these by MRO, not by grep.** `ValidateFormOtp(bases=['BaseFormValidationAction', 'BaseOtpAction'])` is a multiple-inheritance case where the leftmost base's override wins — a grep on the file or method name gets it wrong. Two independent assessments disagreed on the count (4 vs 6) until the AST settled it.

**The swallow** (`forms/form_grievance_complainant_review.py:493` opens `try:`, `:525` catches `except Exception` → returns `SKIP_VALUE` + `LLM_GENERATED`): **if** that branch is reachable, then when the user is happy with their category selection the confirmation utterance throws, is caught, and the form **silently returns the wrong state** — the user never sees the message. The swallow mechanism is verified; the "if" is §0's open question.

**Fix the swallow regardless of the trace result** — a bare `except Exception` that converts *any* failure into a `SKIP_VALUE` is a bug-concealer by construction (step 5 below).

### The target pattern already exists

H2-08 built it when contact validators were extracted to module-level functions and could no longer use `self.get_utterance()` — `backend/actions/services/contact/utterances.py:6`:

```python
def contact_utterance(function_name: str, language_code: str, index: int = 1) -> str:
    return get_utterance_base("form_contact", function_name, index, language_code)
```

Used explicitly at `services/contact/validators.py:224` + 11 other sites. `forms/form_status_check_skip.py:96-115` likewise calls `get_utterance_base(form_section, action_name, ...)` directly. **Copy this convention — do not invent a new one.**

### Change

1. **DELETE `BaseFormValidationAction.get_buttons` (`base_classes.py:126-128`) outright — do not add a `key=` param to it.**
   > **Corrected 2026-07-15.** An earlier draft of this spec said `get_buttons` "has the identical flaw — same fix, same pass." **Wrong.** It carries the same introspection but is **dead code**: AST+MRO resolution shows **0 of 200** call sites reach it (all 76 `get_buttons` calls go through `ActionHelpersMixin`'s explicit path). The `get_buttons` calls in `form_otp.py`/`form_seah_1.py`/`form_grievance_complainant_review.py` are **red herrings** — they live in sibling `Ask*` classes on `BaseAction`/`BaseOtpAction`, not in the `Validate*` classes.
   >
   > Deleting is free and removes an introspection site that would re-seed this bug class the moment someone adds the first caller. **Confirm the 0-caller result yourself by MRO before deleting** (a grep will mislead you — that is exactly how the earlier draft went wrong).
2. **Add an explicit key parameter** to `get_utterance` in `base_classes.py`:
   ```python
   def get_utterance(self, utterance_index: int = 1, *, key: str | None = None):
       function_name = key or inspect.currentframe().f_back.f_code.co_name
       ...
   ```
   Keep the introspection **temporarily** so the change is bisectable; it is deleted in step 5.
3. **Pass an explicit `key=` at all four call sites.** These four are the complete set (AST+MRO, 0 unresolved) — no grep-and-confirm sweep is needed, but **do re-run the resolution** if the tree has moved since 2026-07-15.
4. **Author the 3 missing mapping entries** in `utils/utterance_mapping_rasa.py`. **This is the real work, not the plumbing.** For each:
   - Decide the correct `file_name` key. `form_story_main_route_step` does not exist as a top-level key — either add it or point the call at the correct existing key (inspect `self.file_name` at runtime; it derives from the module name, so it *will* be `form_story_main_route_step`). **Prefer adding the key** over renaming the module — renaming has a 200-site blast radius (see [`followups/utterance-file-name-derivation.md`](followups/utterance-file-name-derivation.md)).
   - Write EN copy that matches the branch's intent (they are all error/re-prompt branches — read the surrounding code).
   - **NE translation:** follow the H2-08 precedent — AI-translated from the EN copy, logged in a review CSV alongside `docs/seah/translations_seah_review.csv` with `needs_translator=0`, per the standing user directive. **Do not leave NE == EN** (the integrity tests assert `ne != en`).
5. **Delete the introspection**: remove the `f_back` line and the now-unused `inspect` import from `base_classes.py` (step 1 already removed the other `f_back` site). Make `key` a **required** parameter at that point. This is the step that actually delivers the ticket's stated goal — and it is what makes the reachability question in §0 answerable statically **forever after**.
6. **Narrow the swallow** at `form_grievance_complainant_review.py:525`: catch the specific exception(s) the body can legitimately raise, or re-raise `ValueError` from the utterance layer. A missing utterance must **never** be laundered into a `SKIP_VALUE`. If narrowing is too risky in this pass, at minimum log at `error` **and** re-raise — do not silently continue. **Do this regardless of §0's verdict**; a bare `except Exception` returning a sentinel is a bug-concealer independent of this ticket.
7. **Wire up the dead guard**: `check_form_function_name` (`base_mixins.py:313`) is defined and **never called anywhere** — someone built the guard for exactly this bug class and never connected it. Either use it in the new test (below) or delete it. Do not leave it dead.

### Tests (acceptance)

New file `tests/actions/test_utterance_key_integrity.py`:
- [ ] **The gap-closing test** — walk the **call sites**, not the dict. Collect every action class, resolve by **MRO** which lookup it uses, and assert every key it passes to `get_utterance` **resolves** in `UTTERANCE_MAPPING` for both `en` and `ne`. This is the test that would have caught all 3 failures; the H2-08 integrity tests walk the dict and structurally could not.
  > **Scope it to `get_utterance` only** — there are no `get_buttons` introspection sites (step 1). Once step 5 lands, the natural form of this test is "no derived keys exist anywhere", which is also the shape the `file_name` follow-up will need.
- [ ] **Verified red on pre-fix code** (the HR-04 standard): assert the 3 currently-missing keys resolve; confirm this test **fails** on `HEAD~` before the mapping entries land. Record the red run in PROGRESS.md.
  > This test goes red pre-fix **regardless of §0's verdict** — it asserts key resolution, not branch execution. That is deliberate: it is exactly the static guarantee introspection denies us today.
- [ ] `ne != en` and non-empty for each new entry (mirror `test_seah_utterance_integrity.py`'s assertions).
- [ ] **The swallow regression**: drive `validate_grievance_cat_modify` down the "user is happy / SKIP_VALUE" path and assert the confirmation message **is dispatched** and the returned slots are the confirm-shape, **not** `{"grievance_categories_status": LLM_GENERATED, "grievance_cat_modify": SKIP_VALUE}`. Verify red pre-fix.
  > **If §0 finds the branch unreachable**, this test cannot be written as described — record that in PROGRESS.md → Deviations and cover the swallow narrowing (step 6) with a direct unit test on the `except` path instead. **Do not silently drop it.**
- [ ] No-regression: full `tests/actions` + `tests/orchestrator` green (baseline at sprint start: **173 passed / 1 skipped**).

### Manual verification
**These double as §0's reachability trace** — if you can drive the branch from the UI, it is reachable, and that answers the open question empirically. Do these *first* if a browser is available; they may make the static trace unnecessary.

- [ ] Webchat EN + NE: enter an invalid language code at the `form_story_main_route_step` prompt ⇒ the re-prompt message renders. **If you cannot produce an out-of-`["en","ne"]` value from the UI, the branch is unreachable — record that as §0's answer.**
- [ ] Webchat EN + NE: reach the SEAH follow-up prompt (`form_seah_1`), send an unrecognized command ⇒ re-prompt renders.
- [ ] Webchat EN + NE: in the category review, accept the current selection ⇒ confirmation message renders and the form advances.
- [ ] *(May be marked pending-human if no browser is available in the build env — record as such. **Note H2-08's SEAH EN/NE webchat walk-through is also still pending-human** — see [`../2026-08_tier2_quality.md`](../../2026-08_tier2_quality.md) §Leftovers. Same flows, same browser session — do them together.)*

### Out of scope — log, don't fix
- **`file_name` module-name derivation** (`base_mixins.py:63`) — ~200 sites, M+. **This is what the source review's "makes the chatbot refactorable" was actually aiming at**; this ticket fixes the other axis (`action_name`). → [`followups/utterance-file-name-derivation.md`](followups/utterance-file-name-derivation.md).
- **Dead branches**, if §0 finds any of the three unreachable — that is a *dead-code* finding, not this ticket's job. Log it: PROGRESS.md → Deviations + followup + TODO.md row.

### Credit where due

The two-mechanism/MRO split, the same three failing sites, the same `form_otp` control, and the `file_name` axis were **independently identified** by the agent that did the H2-08 utterance-mapping work during Tier 2 — reaching the same conclusions from the mapping-data side while this pass came from the call-graph side. It also supplied corrections C-1 and C-2 in [`00-reassessment.md`](00-reassessment.md) §4. **H2-08's data work and this mechanism work are complementary, not overlapping:** H2-08 owned the utterance *data* for SEAH (repaired NE, merged drifted blocks, 54 integrity checks) and delivered it; the *lookup mechanism* was never in its scope and is untouched.

---

## 2. T3-02 — `run_flow_turn` decomposition (M)

> **Part 1 is severable and belongs in Phase 1.** Parts 2–4 are Phase 3 and are a **stretch goal**. Do not start part 4 before part 2's tests are green.

### Problem (measured, 2026-07-15)

`backend/orchestrator/state_machine.py:819–2303` — `run_flow_turn`, **1,485 lines**, **CC = 189** (the review's ~120 is 58% low), max nesting depth 9, 97 `await`s.

**But the shape is unusually table-friendly** — do not over-fear this function:
- Flat 22-arm `if/elif state == "..."` chain (`895`–`2292`), 4-space indent.
- **Zero early returns inside the chain.** Only 3 `return`s in 1,485 lines: `876`, `893` (prologue) and `2303` (single common epilogue).
- **No fallthrough**; mutually exclusive `elif`s.
- **Only 4 cross-branch carriers:** `next_state` (78 assignments), `slot_updates` (accumulator), `dispatcher.messages` (accumulator), read-mostly inputs. Each branch builds its own `SessionTracker` + `CollectingDispatcher` (27 each) — per-branch locals cannot leak.
- **The handler pattern already exists in this file**: helpers at `435`, `450`, `491`, `509`, `537`, `621`, `712`, `816` already have the signature `(session, dispatcher, domain, slot_updates, latest_message) -> next_state`. `_begin_location_method` (`494`) returning `"location_method"` (`509`) is a working handler today.

### The 22 branches

| Lines | State | Size | Note |
|---|---|---|---|
| 895 | `intro` | 16 | covered |
| 911 | `main_menu` | 93 | covered |
| 1004 | `form_grievance` | 23 | covered |
| 1027 | `form_road_hazard` | 12 | |
| **1039** | **`form_dust`** | **12** | **DEAD — delete (part 1)** |
| 1051 | `location_consent` | 21 | reached via helper return |
| 1072 | `location_method` | 24 | reached via helper return |
| 1096 | `map_location` | 95 | covered |
| 1191 | `form_seah_1` | 73 | covered |
| 1264 | `contact_form` | 102 | covered |
| 1366 | `form_seah_2` | 34 | |
| 1400/1422 | `form_seah_focal_point_1/2` | 22/34 | |
| 1456 | `otp_form` | 66 | |
| **1522** | **`submit_grievance`** | **19** | **DEAD — delete (part 1)** |
| 1541 | `grievance_review` | 14 | reached via helper return |
| **1555** | **`status_check_form`** | **304** | **the real monster — depth 9, thin coverage** |
| 1859 | `add_more_info_flow` | 48 | **zero test refs** |
| 1907 | `modify_grievance_menu` | 108 | |
| 2015 | `add_missing_info_otp_flow` | 103 | **zero test refs** |
| 2118 | `add_missing_info_flow` | 54 | **zero test refs** |
| 2172 | `done` | 121 | covered |

### Part 1 — dead branches + terminal `else` (S, Phase 1, severable)

1. **Delete `form_dust` (1039–1050).** Proof: `grep -rn '"form_dust"'` repo-wide returns exactly 2 hits — `state_machine.py:1039` (its own comparison) and `form_loop.py:332`, where it is an **`active_loop`** value (different namespace, leave it alone). `_begin_road_hazard_intake` (`712`) unconditionally sets `next_state = "form_road_hazard"` even for `prefill_subtype="dust"` (called at `957`). The body is a duplicate of `form_road_hazard`.
2. **Delete `submit_grievance` (1522–1540).** Proof: repo-wide the string appears **only** as its own comparison at `1522`.
   > Both proofs hold because **nothing outside `state_machine.py` writes `session["state"]`** (verified repo-wide; only tests do). **Re-run that grep before deleting** — if it ever stops holding, these proofs are void.
3. **Add the terminal `else`** — the latent bug the review missed. There is none today (verified via AST): an unrecognized `state` silently returns unchanged state with **zero messages** (dead air). Log at `error` with the offending state and dispatch a safe fallback message (reuse the existing "so we never return empty messages" defensive convention already in the file). This is also a **prerequisite** for the part-4 table — a dict lookup needs a default.

**⚠️ DO NOT DELETE the SEAH branches.** `_is_seah_enabled()` (`159`) defaults `"true"`; **both** arms ship and are tested (`965` enabled, `973` flag-off; `test_orchestrator_api.py:130` sets false, `conftest.py:30` sets true). Likewise `location_consent`/`location_method`/`grievance_review`/`map_location` look unassigned to a naive grep but are reached via helpers that **return** the state string (`491`, `509`, `537`, `435`). **Not dead.**

**Part 1 tests:**
- [ ] Terminal `else`: drive `run_flow_turn` with `session["state"] = "nonexistent_state"` ⇒ a message **is** returned + an error is logged. **Verify red pre-fix** (today: zero messages).
- [ ] No-regression: full `tests/orchestrator` + `tests/actions` green.

### Part 2 — characterization tests (M, Phase 3, **prerequisite for parts 3-4**)

**This is the actual risk mitigation. Do not skip it to get to the table faster.**

Write characterization tests (record-current-behavior, not aspirational) for the least-covered, highest-complexity code:
- [ ] `status_check_form` interior (`1562`–`1858`, 304 lines, depth 9) — today touched only at entry level by `test_form_loop.py` and `test_modify_grievance_flow.py`.
- [ ] `add_more_info_flow` (`1859`), `add_missing_info_otp_flow` (`2015`), `add_missing_info_flow` (`2118`) — **205 lines with zero state references in any test**.

Drive them the way the existing suite does — over HTTP via `post_turn` → `/message` → `main.py:124` (`tests/orchestrator/`, 17 files / 2,458 lines). `tests/test_modify_grievance_flow.py:57,82` is the only precedent for calling `run_flow_turn` directly; prefer the HTTP path for new tests.

**Gate: parts 3 and 4 do not start until these are green.**

### Part 3 — split `status_check_form` (M, Phase 3)

Extract `1555`–`1858` into named handlers following the **existing in-file convention** (`(session, dispatcher, domain, slot_updates, latest_message) -> next_state`). It is 22% of the function and where the complexity actually lives. The part-2 tests must stay green throughout, unchanged.

### Part 4 — the handler table (S once parts 1-3 land, Phase 3, **stretch**)

Only now: replace the `if/elif` chain with a `dict[str, Handler]` dispatch + the part-1 `else` as the default. The table itself is the **cheap, safe part** — 22 one-line entries against a proven signature. It buys reviewability, not correctness.

**Sequencing rationale (from [`00-reassessment.md`](00-reassessment.md) §1):** "1,485 lines / CC 189" overstates the difficulty and mis-locates the risk. The honest risk is one 304-line branch with thin coverage and three untested `add_*_info` branches — which is the *opposite* of what "decompose into a handler table; delete dead branches" implies.

### Manual verification
- [ ] Webchat: full grievance-filing walk-through (intro → main_menu → form_grievance → location → contact → otp → review → done) unchanged.
- [ ] Webchat: status-check walk-through incl. modify-grievance and add-missing-info paths (the branches touched by parts 2-3).
- [ ] *(May be marked pending-human — record as such.)*

### Out of scope — log, don't fix
Anything found in the `status_check_form` interior during part 2. Characterization tests **record current behavior, including bugs**. If a branch is wrong, write the test to the current behavior, then log the bug in PROGRESS.md → Deviations + a followup + a TODO.md row. **Do not fix it in this ticket** — you would be changing behavior under a test net you just wrote.
