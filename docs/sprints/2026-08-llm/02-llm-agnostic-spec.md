# Sprint 1 — Make the code LLM-agnostic (DPG-10…17)

> Branch `dpg/sprint1-llm-agnostic` · Depends on nothing; **blocks Sprints 2 and 3**.
> **Goal:** every model call in the repository routes through a configurable, OpenAI-compatible client.
> No provider and no model name is hard-coded anywhere, in either LLM surface.
> **Why:** it is the DPG indicator-4 answer, it is what lets you move T1 → T2 without a code change, and
> it insulates you from a market where model prices fall roughly an order of magnitude a year and
> licences change without notice.
> Line numbers **corrected 2026-08-18** against `dpg/sprint0-licensing` — Sprint 0's SPDX pass shifted
> every `.py` file by exactly **+2** and this spec's ~80 references with it. **Re-locate anyway.**
> ⚠ **Read [§0.5](#05--what-sprint-0-changed-that-this-sprint-inherits) before the first commit** — six
> of the changes below alter how this sprint is executed, not just what it says.

---

## Required reading

1. [`CLAUDE.md`](../../../CLAUDE.md) — **§Service boundaries** (`backend/services/` and `backend/task_queue/` are *stable shared services*: modify with clear intent + tests, do not regress the live chatbot) · §Conventions · §Environment variables · §Git workflow
2. [`docs/PROGRESS.md`](../../PROGRESS.md) → [`docs/TODO.md`](../../TODO.md)
3. [`docs/engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md) — the ten rules
4. └ [`02_python_services.md`](../../engineering/02_python_services.md) — **binding**: entrypoints hold no logic; config through a settings object; error contracts; logging
5. └ [`04_testing.md`](../../engineering/04_testing.md) — **binding**: DPG-10 is the whole ticket
6. └ [`03_api_layer.md`](../../engineering/03_api_layer.md) — DPG-15's health probe is a route
7. └ [`06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) — honesty markers; when this spec's content is promoted to the live specs
8. [`docs/deployment/DOCKER.md`](../../deployment/DOCKER.md) — every verification step runs in-container
9. [`docs/services/06_llm_service.md`](../../services/06_llm_service.md) — **the live spec this sprint rewrites** (backend surface)
10. [`docs/deployment/11_llm_pipeline_policy.md`](../../deployment/11_llm_pipeline_policy.md) — **the live spec for the ticketing surface**; names both pipelines and their models
11. [`docs/services/03_voice_grievance_service.md`](../../services/03_voice_grievance_service.md) — the ASR consumer (DPG-14)
12. [`docs/sprints/README.md`](../README.md) — the standing deferral rule
13. [`README.md`](README.md) + [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md) — this sprint's map and its *why*

---

## §0 — Read this first: the inventory the source narrative missed

The guide says: *"`backend/services/LLM_services.py` instantiates the OpenAI client at module level with
no `base_url` override, and hard-codes `whisper-1`, `gpt-3.5-turbo`, `gpt-4`, plus a `gpt-5-nano`
reference. **No provider abstraction exists.**"*

**Three corrections, and the first one doubles the sprint.**

### 1. There are two LLM surfaces, not one

`ticketing/clients/llm_client.py` is a second, entirely independent OpenAI client. Its own docstring
says why it exists: *"DO NOT import from backend/services/ — keep ticketing independent. Replicate the
pattern here."* That instruction was right for the service boundary and it is exactly why the
hard-coding is duplicated.

| Surface | File | Client | Models hard-coded | Structured output |
|---|---|---|---|---|
| **Chatbot intake** | `backend/services/LLM_services.py` | module-level, `:32` | `whisper-1` `:47`, `gpt-3.5-turbo` `:79` `:116` `:385`, `gpt-5-nano` `:232`, `gpt-4` `:324` | `json_object` ×3, **none** ×2 |
| **Ticketing case analysis** | `ticketing/clients/llm_client.py` | lazy cached, `:30-37` | `gpt-4` `:90`, `gpt-4o-mini` `:141`, `gpt-4o` `:142` | `json_object` ×2, **none** ×1 |

The ticketing surface is not a side path. It produces `Ticket.ai_summary_en`, the officer-facing case
findings, and the **complainant-facing** resolved-case summary. A migration that fixes only `backend/`
leaves the indicator-4 claim false, and leaves the complainant-facing output on a closed model.

**And it is five files, not two — re-counted 2026-08-18 and it grew.** Four more modules carry the same
model names the client does:

| File:line | What it is | Why it matters |
|---|---|---|
| `ticketing/services/resolved_summary_builder.py:28-29` | Its **own copy** of `_MODEL_STANDARD` / `_MODEL_SEAH`, written into the resolved-case summary as `llm.model` at **`:301`** | A **persisted provenance field** computed from a copy. Miss it and every resolved case records a model that never ran it |
| `ticketing/tasks/llm.py:165` | The ternary re-derived as a **literal**, for a log line | The log can disagree with the call it is logging |
| `ticketing/tasks/llm.py:251` | ⚠ **Found 2026-08-18, not in the original inventory.** `model = _llm._MODEL_SEAH if ticket.is_seah else _llm._MODEL_STANDARD` — reaches into the **client module's privates** | Not a literal, so `grep "gpt-"` **does not find it**. DPG-12's own acceptance grep would have passed with this site untouched |
| `ticketing/api/routers/tickets/summary.py:113` | ⚠ **Found 2026-08-18.** *"calls OpenAI gpt-4, and stores the result in `ai_summary_en`"* — an **endpoint description**, so it is published in the OpenAPI document | The model name is in the **public API surface**. It becomes false the moment DPG-12 lands, and indicator 5 (documentation) is graded on OpenAPI |

**Four copies of one ternary across three modules, plus a fifth statement of it in the OpenAPI
description** — none aware of the others. Two of the four were invisible to the `grep "gpt-"` that this
spec's own acceptance criteria rely on.

> **⚠ Two factories, one config — [DPG-17](#dpg-17).**
> Two independent clients is the right answer for the service boundary. Two independent *model
> registries* is not: it puts the indicator-4 answer in two files with two default sets, and lets them
> drift — flip `backend/` to the open router, miss `ticketing/`, and the complainant-facing summary is
> still on a closed model while the repo advertises otherwise. So **every model name, endpoint, timeout
> and capability flag is declared once**, in `backend/config/llm_config.py`, which both factories import
> and neither owns. A factory decides *how* to build a client; it never decides *what* to call.
> **DPG-17 lands before DPG-11 and DPG-12.**

### 2. `gpt-5-nano` is not a stray reference — it is the live classification model

`LLM_services.py:246`, in `classify_and_summarize_grievance`, the primary AI path in the product. The
guide's §1.4 (*"Confirm whether that reference is intentional. If it is a typo falling through to an
exception handler, you may have a classification path that has been quietly failing."*) has the right
instinct pointed at the wrong thing. The real questions are in DPG-14.

### 3. Full call-site inventory — nine calls, not four

| # | Function | File:line | Model | `response_format` | Notes |
|---|---|---|---|---|---|
| 1 | `transcribe_audio_file` | `LLM_services.py` call `:45`, model `:47` | `whisper-1` | — (audio) | ⚠ suspected live defect — DPG-14 |
| 2 | `extract_contact_info` | `LLM_services.py` call `:78`, model `:79` | `gpt-3.5-turbo` | `json_object` | |
| 3 | `extract_all_contact_info` | `LLM_services.py` call `:115`, model `:116` | `gpt-3.5-turbo` | `json_object` | |
| 4 | `classify_and_summarize_grievance` | `LLM_services.py` call `:206`, model `:232` | `gpt-5-nano` | **none** | Asks for "strict JSON" in the prompt only. Uses a **shadow client** built at `:201` |
| 5 | `translate_grievance_to_english_LLM` | `LLM_services.py` call `:306`, model `:324` | `gpt-4` | **none** | Same — JSON by prompt instruction only |
| 6 | `detect_sensitive_content_llm` | `LLM_services.py` call `:370`, model `:385` | `gpt-3.5-turbo` | `json_object` | SEAH detection path |
| 7 | `translate_to_english` | `llm_client.py` call `:89`, model `:90` | `gpt-4` | — (free text) | |
| 8 | `generate_case_findings` | `llm_client.py` call `:168`, model `:169` (ternary `:162`) | `gpt-4o-mini` / `gpt-4o` | `json_object` | |
| 9 | `generate_resolved_case_summary_llm` | `llm_client.py` call `:260`, model `:261` (ternary `:254`) | `gpt-4o-mini` / `gpt-4o` | `json_object` | Complainant-facing output |

Nine call sites — **six in `LLM_services.py`, three in `ticketing/clients/llm_client.py`**, re-confirmed by
`grep -n "\.create(" ` on both files 2026-08-18. Seven produce JSON (5 with `json_object`, **2 by prompt
instruction alone**). ✅ [`docs/dpg/00_compliance_status.md`](../../dpg/00_compliance_status.md) said
*eight* in four places; **it was corrected during Sprint 0** and now says nine, with a note explaining the
merge. The two documents agree.

### 4. And there is no test net at all

**Not one test in the repository imports `LLM_services` or `ticketing/clients/llm_client`.** Verified by
grep across `tests/`. The guide's CI snippet runs `pytest tests/test_llm_services.py` — a file that does
not exist.

This is the same shape as T3-04, and it gets the same treatment:
[**the first commit of this sprint is a test, not a refactor**](#dpg-10).

### 0.5 — What Sprint 0 changed that this sprint inherits

Sprint 0 closed 2026-08-18 (branch `dpg/sprint0-licensing`, 11 commits). Six of its outcomes change how
this sprint is **executed**, not just what it documents. Read them before the first commit.

#### a. Every `.py` file gained a 2-line SPDX header — and every new file must too

`# SPDX-License-Identifier: Apache-2.0` plus a blank line, on **585 files**. That is the +2 shift that
invalidated this spec's line numbers (corrected above).

**For this sprint:** `backend/config/llm_config.py`, `backend/services/llm_client.py`,
`tests/backend/test_llm_services.py` and `tests/ticketing/test_llm_client.py` are all new files **in
scope**. `tests/repo/test_spdx_headers.py` walks the tree and **fails the build** if one is missing.
Do not hand-write the header — run the idempotent script, which knows about shebangs and
`"use client"` directives:

```bash
python3 scripts/ops/add_spdx_headers.py          # add
python3 scripts/ops/add_spdx_headers.py --check  # verify (CI runs the equivalent)
```

#### a-bis. ⚠ A pin now guards documentation line numbers — **and this sprint will turn it red on purpose**

`tests/repo/test_doc_code_refs.py` (**T-03**) parses every `file.py:NNN` citation out of the live docs and
checks three things: the file exists, the line is in range, and — for **20 load-bearing citations** — the
line still contains an expected token.

Twelve of those twenty are yours: the **nine model call sites**, plus
`resolved_summary_builder.py:301`, `tasks/llm.py:251` and `summary.py:113`. **DPG-11 and DPG-12 move all
of them, so T-03-c goes red.** That is the design.

> **The red means: re-point the documents, then update `ANCHORS` — in the same commit.**
> `grep -rn "LLM_services.py:" docs/` finds them; the assertion message prints the grep for you.
> **Updating `ANCHORS` alone, leaving the docs stale, is the exact failure this pin exists to prevent** —
> and it would silently break `docs/dpg/privacy-assessment.md` §2.2, whose entire claim is that each leg
> was verified at the line cited.

#### b. CI now runs on `dpg/**` — it did not before

`ci.yml`'s push triggers were `main`, `integration/**`, `dev/**`. **`dpg/sprint0-licensing` matched none
of them**, so nine commits — including the compliance pins DPG-01 added — ran on nobody's machine.
Fixed (sprint-0 deviation **D-24**) by adding `dpg/**`.

**For this sprint:** `dpg/sprint1-llm-agnostic` gets CI from its first push. That is new, and it is the
only reason the invariant below is checkable.

#### c. ⚠ CI is RED, and this is the baseline you measure against

**Do not read "the tests pass" as "the build is green" — it has not been green since 2026-08-08.**
Measured on the last two runs of `dpg/sprint0-licensing`, identical both times:

| Job | Baseline |
|---|---|
| `docs-links` · `webchat-checks` | ✅ |
| `backend-tests` → pytest | ❌ **18 failed, 1166 passed, 8 skipped** — measured on `dpg/sprint0-licensing` @ `e488317c` |
| `ui-checks` → Lint | ❌ **166 problems (2 errors, 164 warnings)**; **Build is skipped as a result** |

The failures are pre-existing, cluster in `test_donor_guardrail` / `test_grievance_sync` /
`test_project_type_authoring` / `test_roles_crud`, and are **identical in shape on `integration/stage`**.
They are nothing to do with LLMs.

**So this sprint's invariant needs restating in measurable terms:**

> **The invariant is not "CI is green". It is "the failure count does not increase, and DPG-10's tests
> are green, at every commit."** Record `18 failed, 1166 passed` before the first commit. **19 is yours.**

⚠ **Re-measure it yourself on your first push.** The passing count moves whenever anyone adds a test —
it went 1143 → 1166 during Sprint 0 alone. **The failure count is the invariant; the passing count is a
timestamp.** And the rule has already caught its author once: the reference pin (T-03) landed at 19 and
had to be fixed, which is exactly the signal it is there to give.

Tracked in [`followups/ci-has-been-red-for-ten-days.md`](followups/ci-has-been-red-for-ten-days.md)
(**D-26**). ⚠ **It is not this sprint's job to fix** — but if you fix the 2 lint errors as a favour, the
`ui-checks` **Build** step starts running again, which is the `next build` gate D-02b has been waiting on.

#### d. Put the tests where CI actually looks

`ci.yml` names its pytest paths **explicitly**:
`tests/repo tests/ticketing tests/orchestrator tests/actions tests/backend`.

✅ DPG-10's two files land in `tests/backend/` and `tests/ticketing/` — **both covered.** Good as specced.

⚠ **Do not put anything in `tests/` root or `tests/shared/`.** 27 test files live there and have
**never executed in CI** — a directory not named above never runs
([`followups/ci-untested-root-test-files.md`](followups/ci-untested-root-test-files.md), **D-01**). A
characterization net that CI does not run is not a net.

#### e. The `pydantic-settings` move has a compliance side-effect

DPG-17 moves `pydantic-settings>=2.0` from `requirements.grm.txt:7` to `requirements.txt` (next to
`pydantic>=2.0` at `:17`). Sprint 0 published
[`docs/dpg/dependency-licenses.md`](../../dpg/dependency-licenses.md) — **153 packages, dated and
commit-stamped**, and a nightly `licence_scan()` that now genuinely runs (verified in-container:
133 Python packages, 5 copyleft findings, all dispositioned).

**For this sprint:** moving a package between manifests changes the **declared/transitive split** the
report is built on (35 declared / 98 transitive). Update the report's counts in the DPG-17 commit, or the
next reader finds a dated audit that disagrees with the manifests. **If you add any new dependency,
check its licence before committing** — the scan will flag it as `high` if unrecognised, which is the
designed behaviour, not a bug to work around.

#### f. The privacy assessment cites these exact call sites — this sprint moves all nine

[`docs/dpg/privacy-assessment.md`](../../dpg/privacy-assessment.md) §2.2 legs **L4** and **L5** cite
`LLM_services.py:47,79,116,232,324,385` and `llm_client.py:90,169,261` as the places grievance text
leaves the country. **DPG-11 and DPG-12 move every one of them.**

Update §2.2 in the same commit that moves them. DPG-30 (Sprint 3) verifies the diagram against the code
and will report the drift — but a data-flow diagram that has silently gone stale is a compliance artefact
rather than a control, which is the assessment's own stated standard.

Two more things from that document bear directly on **DPG-17's registry**:

- **Pinning `model:provider` fixes the sub-processor. It does not fix the jurisdiction of execution**
  (assessment **F-17**) — routed inference can run anywhere the provider chooses. The registry makes the
  *choice* configurable; it does not make the *location* knowable. Do not let the registry's existence
  imply otherwise in any submission text.
- **The provider's retention and service-improvement terms are unrecorded** (**F-16**). They are the
  mitigation any transfer analysis cites, and citing an unverified mitigation is worse than citing none.
  Whoever picks the Sprint-2 provider should obtain them.

#### g. DPG-11's blast-radius warning is softer than it reads — but not by much

DPG-11 says *"The chatbot is live; a regression here is a production intake outage."* Sprint 0 established
(assessment **§0.5**, owner-confirmed) that **no genuine grievance has ever been processed** — every
record is AI-generated seed data or a demo dummy.

**So an intake regression harms no real complainant today.** That is a real reduction in risk and it is
worth knowing. It is **not** permission to be careless: the stack is deployed, demos run on it, and
Sprints 2–3 assume intake works. Treat it as *"test thoroughly, you have room to be wrong once"* rather
than *"you will take down production."* ⚠ And the statement expires at go-live.

#### h. Deviation numbering continues at **D-27**

Sprint 0's deviations run to **D-26**, and its two deviation tables were **merged into one namespace**
(**D-23**) after a collision caused an already-corrected error to be reintroduced. `PROGRESS.md` now has a
single Deviations table with a **Status** column. Add rows there; do not start a second table.

---

---

## Order (BINDING — do not reorder)

```
1. DPG-10  TEST NET     — characterize all nine call sites against a mocked client.
                          Must pass on today's code, unchanged. This is the safety net
                          for every ticket below. Without it you are refactoring the
                          product's primary AI path blind.

2. DPG-14  DEFECTS      — cheapest, highest signal. Three latent bugs found during
                          planning. Fix them under the net, before the shape changes.

3. DPG-17  ONE CONFIG   — the shared registry both factories read. Small, and it must
                          come first: build it after DPG-11/12 and you are merging two
                          registries that already disagree instead of writing one.

4. DPG-11 ∥ DPG-12      — the two client factories, both consuming DPG-17. Independent of
                          each other. DPG-10's tests must stay green, unchanged, through both.

5. DPG-13  SCHEMAS      — json_object → json_schema. Needs DPG-17 (that is where the
                          provider capability flag lives, for both surfaces).

6. DPG-16  ENV          — .env.example, compose, .env.open / .env.openai. Reads DPG-17's
                          declared_env_vars() rather than restating the list.

7. DPG-15  DEGRADED     — audit (can start any time) + the health probe (needs DPG-16).

── second wave, owner 2026-08-18 ──────────────────────────────────────────────

8. DPG-19  GUARDRAILS   — meaningful-input gate + bounded error text. Independent of
                          DPG-18; closes D-29. Cheapest of the three, land it first.

9. DPG-18  CALL LAYER   — one entry point per surface, shaping shared. Rewrites the
                          bodies of all nine call sites, so it goes AFTER DPG-19
                          rather than being rebased over it. Model consolidation is
                          the last commit of this ticket and needs Q-21.

10. DPG-15b TIMING      — the wait moves to submission, 90s, late-update. Needs Q-20
                          answered (the flow's step order) before any code.
```

**The invariant: DPG-10's tests are green at every commit.** If they go red, the behaviour changed and
you stop.

⚠ **Measured against a red baseline** — CI has 18 pre-existing pytest failures and 2 lint errors that are
nothing to do with LLMs ([§0.5c](#05--what-sprint-0-changed-that-this-sprint-inherits)). The checkable
form is: **`18 failed, 1166 passed` does not increase.** 19 is yours.

---

## DPG-10 — The test net (must land first) {#dpg-10}

**This ticket adds no production code.** Its output is `tests/backend/test_llm_services.py` and
`tests/ticketing/test_llm_client.py`, both passing against **today's unmodified code**.

### What to characterize

For each of the nine call sites, with the OpenAI client mocked at the module boundary:

- **The request shape** — model name, message roles, and whether `response_format` is set. This is what
  pins the migration: after DPG-11 the model name comes from config, and the test proves the *same*
  model name still arrives at the client unless configuration says otherwise.
- **The happy-path parse** — a realistic provider response in, the documented dict out.
- **The failure contract**, which is *different for every function* and is the part most likely to break
  silently under refactor:

  | Function | On failure it… |
  |---|---|
  | `transcribe_audio_file` | **raises** (`:53`) |
  | `extract_contact_info` | returns `{field_name: ""}` (`:102`) — and see the bug below |
  | `extract_all_contact_info` | returns a six-key dict of empty strings (`:145`) |
  | `classify_and_summarize_grievance` | returns a dict with `status="error"` and the exception text (`:241`) |
  | `translate_grievance_to_english_LLM` | **raises `ValueError`** (`:345`) |
  | `detect_sensitive_content_llm` | returns `{detected: False, level: "low", message: ""}` (`:406`) — **fails open** |
  | `translate_to_english` | returns `None` (`:102`) |
  | `generate_case_findings` | returns `None` (`:207`, `:210`) |
  | `generate_resolved_case_summary_llm` | returns `None` (`:285`, `:288`) |

  Three different failure idioms — raise, sentinel dict, `None` — across one product. Characterize them
  as they are; **do not unify them in this sprint** (that is a behaviour change outside scope; log it as
  a followup if you think it should be unified).

- **`client is None`** — the module-level client is `None` when `OPENAI_API_KEY` is unset (`:31-36`).
  Every function guards on it, differently. Pin each guard.
- **`parse_llm_response`** (`:251-285`) — the shared parser. Cover: valid JSON, `"{}"` (the sentinel that
  produces the localized "not enough information" response, `:271-278`), malformed JSON (returns `{}`,
  `:283-285`), and each of the four language codes in `error_response_dict`.
- **`detect_sensitive_content_llm` level clamping** (`:392-393`) — an out-of-range `level` becomes `low`.
  This is a SEAH path; it deserves a pinned test regardless of this sprint.

### ⚠ Two traps

1. **`extract_contact_info` has a latent `UnboundLocalError`.** At `:95` the handler reads `if not response:`
   — but `response` is only bound at `:78`. Any exception raised *before* that line (a missing/invalid
   `field_name` at `:63-68`, or a client failure) hits `:95` with `response` unbound, raising
   `UnboundLocalError` from inside the `except`. The declared contract (`{field_name: ""}`) is not what
   callers get. **Characterize the real behaviour, not the intended one** — then log it as a deviation.
   Fixing it is DPG-14 scope only if it is trivial; otherwise it is a followup.
2. **Mock at the right boundary.** `classify_and_summarize_grievance` builds its **own** client at `:201`,
   shadowing the module-level one. A test that patches only the module-level `client` will not intercept
   it. Patch `backend.services.LLM_services.OpenAI` (the class) so both paths are covered — and note that
   DPG-11 collapses this asymmetry, which is precisely why the test must exist before then.

### Acceptance

- [ ] `tests/backend/test_llm_services.py` and `tests/ticketing/test_llm_client.py` exist and pass on
      **unmodified** `integration/stage`
- [ ] All nine call sites covered: request shape, happy path, failure contract
- [ ] `client is None` guard pinned per function
- [ ] `parse_llm_response` covered for all four branches and four languages
- [ ] No network access in any test (mocked client; CI has no LLM credentials at this stage)
- [ ] **Mutation-checked**: changing a hard-coded model string turns a test red. If it does not, the test
      does not pin what this sprint needs pinned.
- [ ] The `extract_contact_info` `UnboundLocalError` recorded in `PROGRESS.md` → Deviations (next free
      number is **D-27** — one table, one namespace, see [§0.5h](#05--what-sprint-0-changed-that-this-sprint-inherits))
- [ ] Both new test files carry an **SPDX header** (`scripts/ops/add_spdx_headers.py`), and
      `python -m pytest tests/repo` stays green — the header walker fails the build without it
- [ ] Both files live in `tests/backend/` and `tests/ticketing/`, which `ci.yml` names. **Nothing in
      `tests/` root or `tests/shared/`** — 27 files there have never run in CI
- [ ] Baseline recorded before the first commit: **`18 failed, 1166 passed, 8 skipped`**. The sprint's
      real acceptance is that this number does not grow

### Tests

[`TESTS.md`](TESTS.md) → **T-10-a … T-10-f**.

---

## DPG-17 — One config file: `backend/config/llm_config.py` {#dpg-17}

**Lands before DPG-11 and DPG-12. Both consume it; neither redefines it.**

> **Settled — Q-18, 2026-08-17.** Location: **`backend/config/llm_config.py`**. Pattern:
> **`pydantic-settings`**, with `pydantic-settings>=2.0` **moved to `requirements.txt`**. Neither is open;
> the reasoning below is kept because the next reader will ask why, not to reopen the choice.

DPG-11 and DPG-12 build **two client factories**, and that is correct — two surfaces, two lifecycles, two
deployment units, one live chatbot you do not want to couple to the officer portal. But as written
they would also build **two model registries with two default sets**, and that reintroduces at the config
layer exactly the duplication this sprint exists to remove. Indicator 4 is then a claim in two files,
and the two can drift: flip `backend/` to the open router, forget `ticketing/`, and the
**complainant-facing** resolved-case summary is still on a closed model while the repo advertises
otherwise.

So the rule for this sprint:

> **Two factories. One config.** The provider endpoint, the API key, the timeouts, the retry count, the
> structured-output capability, and **every model name** are declared once, in one module, that neither
> surface owns and both import. A factory decides *how* to construct a client. It never decides *what*
> to call.

### Why `backend/config/`, and why that does not breach the boundary

The independence rule in `ticketing/clients/llm_client.py:7` names `backend/services/` — the **service
layer**. `backend/config/` is a different thing, and the precedent is already load-bearing in production:

- `backend/config/smtp_config.py` — a frozen-dataclass env resolver — is imported by
  `ticketing/auth/keycloak_smtp.py:10`, which is reached from `ticketing/services/officer_admin.py:226`
  and `:618` (the live officer-invite path in `ticketing_api`). **Same problem shape**: one external
  provider, two surfaces, one config.
- The packaging cost is zero. One `Dockerfile`, `context: .`, `COPY . /app` — `backend`, `celery_llm`,
  `ticketing_api`, `grm_celery`, `grm_celery_beat` and `ops` all run **the same image** with the whole
  repo importable. Nothing to mount, nothing to publish.
- Both surfaces already read the same `env_file` set (`env.local`, `.env`), so a shared module reads the
  same values in every container by construction rather than by convention.

**The constraint that keeps it honest — `llm_config.py` imports nothing from `backend.*`, `ticketing.*`
or `ops.*`.** Stdlib, `dataclasses`, `pydantic` and `pydantic-settings` only — the third-party pair is
fine because both surfaces already depend on it (see the dependency move below); a *first-party* import is
what would capture the file. It is therefore copy-portable: if ticketing is ever
extracted, the file moves with it and nothing else changes. **Pinned by a test** (T-17-b), because a
single convenience import from `backend.config.constants` would quietly turn a shared file into a
backend-owned one.

**Confirmed (Q-18, 2026-08-17):** take the precedent. No new top-level package.

### The config pattern: `pydantic-settings`, not `os.getenv`

`smtp_config.py` supplies the **location** precedent; it does not supply the pattern — it is the older
`os.getenv` style, and DPG-11's own binding constraint (via
[`02_python_services.md`](../../engineering/02_python_services.md) §config) rules that out. The repo's two
newest config modules, `ticketing/config/settings.py:12` and `ops/config.py:19`, are both
`BaseSettings` + `@lru_cache`. Follow those:

- env parsing, typing and `env_file=("env.local", ".env")` come free and match both surfaces' existing
  loading behaviour;
- the **deprecated aliases become declarative** — `AliasChoices("LLM_API_KEY", "OPENAI_API_KEY")`, the
  pattern `ops/config.py` already uses, instead of hand-rolled fallback chains in two places;
- it is testable by env-patch + `cache_clear()`, which is what T-17-a needs.

#### The dependency move this requires — decided, and it is part of this ticket

`pydantic-settings` lives in **`requirements.grm.txt:7`**, not `requirements.txt` — so a `backend/config/`
module importing it would make the chatbot surface depend on a GRM requirements file, against CLAUDE.md's
split (*"`requirements.txt` → chatbot deps; add GRM/ops deps to `requirements.grm.txt`"*). Every container
of this image installs both, so nothing would break today — but the rule would be false, and the first
build of the chatbot without the GRM file would fail at import of `LLM_services.py`.

**Decided (Q-18, 2026-08-17): move it.** Three edits, in DPG-17's commit:

1. `requirements.txt` — add `pydantic-settings>=2.0` next to the existing `pydantic>=2.0` (`requirements.txt:17`), with a
   comment naming `backend/config/llm_config.py` as the base-surface consumer.
2. `requirements.grm.txt:7` — remove the line. Its comment (`# ticketing/config/settings.py`) is now wrong
   in both directions: the dep is no longer GRM-only, and it has three consumers, not one.
3. Rebuild and confirm in-container — `docker compose … build` then
   `exec celery_llm python -c "import pydantic_settings"`. A requirements move that was never rebuilt is
   not verified; the layer cache will happily keep the old wheel set.

The `os.getenv` fallback — dataclasses like `smtp_config.py`, with DPG-11's settings constraint waived in
writing — was **considered and rejected**. It is recorded here so nobody re-derives it as a shortcut when
the requirements move looks inconvenient mid-ticket.

### What the module owns

Two **endpoints** and N **tasks**. A task names its endpoint, its model, and its timeout — which is what
makes ASR's separate base URL and classification's 120 s budget configuration rather than special cases.

```python
# backend/config/llm_config.py
"""
The single source of truth for *which* LLM this product calls — both surfaces.

Endpoints and models are configuration. This module resolves them from env; it constructs
no client, and imports nothing from backend.*, ticketing.* or ops.* — either surface may
import it, neither owns it.

Consumed by:
  backend/services/llm_client.py   (DPG-11) — chatbot intake
  ticketing/clients/llm_client.py  (DPG-12) — ticketing case analysis

Works unchanged against:
  T1  https://router.huggingface.co/v1   (hosted providers — what production runs)
  T2  http://<private-ip>:8000/v1        (self-hosted vLLM — designed, parked, not deployed)
  T3  http://localhost:8000/v1           (on-prem)
  --  https://api.openai.com/v1          (the configurable fallback, and benchmark comparison)
"""

class LLMSettings(BaseSettings):          # the env surface — the only one, for both surfaces
    llm_base_url: str
    llm_api_key: str = Field("", validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"))
    llm_timeout: float
    llm_max_retries: int
    llm_structured_output: Literal["json_schema", "json_object", "prompt"]
    asr_base_url: str                     # defaults to llm_base_url when unset
    asr_api_key: str = Field("", validation_alias=AliasChoices("ASR_API_KEY", "OPENAI_API_KEY"))
    asr_timeout: float                    # materially higher — audio is slow
    model_classify: str
    model_extract: str
    model_translate: str
    model_detect: str
    model_asr: str
    model_ticket_translate: str = ""      # "" → resolves to model_translate
    model_ticket_findings: str
    model_ticket_findings_seah: str
    timeout_classify: float = Field(
        120.0, validation_alias=AliasChoices("TIMEOUT_CLASSIFY", "OPENAI_CLASSIFICATION_TIMEOUT")
    )
    model_config = SettingsConfigDict(env_file=("env.local", ".env"), extra="ignore")

@dataclass(frozen=True)
class Endpoint:                           # a read-only view a factory can hand to OpenAI()
    base_url: str
    api_key: str
    timeout: float
    max_retries: int
    structured_output: str

@dataclass(frozen=True)
class TaskModel:
    task: str
    model: str
    endpoint: Endpoint                    # llm or asr
    timeout: float                        # task override, else the endpoint's

@lru_cache
def get_llm_settings() -> LLMSettings: ...
def llm_endpoint() -> Endpoint: ...
def asr_endpoint() -> Endpoint: ...
def model_for(task: str) -> TaskModel: ...
def findings_task(is_seah: bool) -> str: ...   # the SEAH ternary, declared once
def declared_env_vars() -> tuple[str, ...]:    # what DPG-16's drift pin reads
```

### The task registry — every model name in the product, in one table

| Task key | Env override | Value today | Endpoint | Call sites |
|---|---|---|---|---|
| `classify` | `MODEL_CLASSIFY` | `gpt-5-nano` | llm | `LLM_services.py:246` |
| `extract` | `MODEL_EXTRACT` | `gpt-3.5-turbo` | llm | `LLM_services.py:93`, `:116` |
| `translate` | `MODEL_TRANSLATE` | `gpt-4` | llm | `LLM_services.py:338` |
| `detect` | `MODEL_DETECT` | `gpt-3.5-turbo` | llm | `LLM_services.py:399` (SEAH path) |
| `asr` | `MODEL_ASR` | `whisper-1` | **asr** | `LLM_services.py:47` |
| `ticket_translate` | `MODEL_TICKET_TRANSLATE` | `gpt-4` → falls back to `translate` | llm | `llm_client.py:90` |
| `ticket_findings` | `MODEL_TICKET_FINDINGS` | `gpt-4o-mini` | llm | `llm_client.py:141` |
| `ticket_findings_seah` | `MODEL_TICKET_FINDINGS_SEAH` | `gpt-4o` | llm | `llm_client.py:142` |

> ⚠ **Model names carry the sub-processor choice, so the registry is where the privacy decision lands.**
> Hugging Face's router accepts a `model:provider` suffix (`openai/gpt-oss-120b:groq`); without one it
> selects the fastest available partner **per request** and fails over automatically, which means the
> company processing a given grievance is not knowable in advance. **Production must pin a provider; CI may
> route automatically because it sends only synthetic data** (DPG-24). Both are the same one-line registry
> value in different environments — which is exactly the property this ticket exists to create. Reasoning:
> [`docs/dpg/00_compliance_status.md`](../../dpg/00_compliance_status.md) §4.3a.

`ticket_translate` defaulting to `translate`'s resolved value is deliberate: one knob moves translation
everywhere, and a second knob exists for whoever needs the surfaces to differ. The
`ticket_findings` / `ticket_findings_seah` split is the cost/quality decision documented at
`llm_client.py:135-138` — it survives as **two keys**, per DPG-12.

### Deprecated aliases — resolved once, warned once

Both surfaces inherit the same alias handling, so a stale `env.local` cannot authenticate one surface and
silently break the other. `AliasChoices` resolves the value; it does **not** warn — the one-warning-per-alias
behaviour is an explicit `model_validator` (or a module-level check in the `os.getenv` fallback), and
DPG-12's T-12-c pins it:

| Old | New | Behaviour |
|---|---|---|
| `OPENAI_API_KEY` | `LLM_API_KEY`, `ASR_API_KEY` | used if the new name is unset; logs one warning |
| `OPENAI_CLASSIFICATION_TIMEOUT` (`LLM_services.py:214`) | `classify` task timeout | same |
| `ticketing` settings `openai_api_key` (`settings.py:87`) | `LLM_API_KEY` | same — satisfies DPG-12 step 1 |

### ⚠ The duplication is four files deep, not two — and one copy falsifies a stored record

The §0 inventory undercounted. Model names are hard-coded in **two more files that DPG-11 and DPG-12
never mention**:

| File | What it does | Consequence |
|---|---|---|
| `ticketing/services/resolved_summary_builder.py:28-29` | A **second copy** of `_MODEL_STANDARD` / `_MODEL_SEAH`, written into the resolved-case summary as `llm.model` at `:301` | The archival record of *which model produced this case summary* is computed from a copy, in a different module from the one that made the call. Change the client's mapping and miss this file → **every resolved case records a model that did not run it.** A grievance mechanism publishing false provenance is an honesty failure a DPG reviewer would treat as exactly that. |
| `ticketing/tasks/llm.py:165` | Re-derives `"gpt-4o" if ticket.is_seah else "gpt-4o-mini"` for a log line | The log can disagree with the call it is logging. |

Both are drift that has *already happened* — three copies of the same ternary, in three modules, none
aware of the others. `findings_task()` + `model_for()` collapse all three, which is why this ticket is
worth its own commit rather than being folded into DPG-12.

### ⚠ Correction to DPG-11: the open default cannot ship in Sprint 1

DPG-11's *"make the open configuration the default"* is right about the evidence and wrong about the
timing, and one config file is what makes the timing cheap.

Flipping `LLM_BASE_URL` to the HF router **while the model names are still `gpt-3.5-turbo`, `gpt-4o` and
`whisper-1`** ships a repository whose default configuration **cannot answer a single request** — an open
endpoint asked for model IDs only OpenAI serves. That is *weaker* indicator-4 evidence than an honest
proprietary default, because a reviewer who clones and runs gets a 404, not a working open path. And it
breaks the sprint's own invariant: DPG-10's tests pin the model name and base URL that reach the client,
so the flip turns them red in the one commit where red is supposed to mean *stop*.

**Therefore:** DPG-17 ships **today's values as the defaults** — behaviour-preserving, DPG-10 green,
unchanged. The flip to open defaults is its own commit, in Sprint 2, once DPG-23 has measured which open
models to name. Because of this ticket that flip is **one file and one line per task**, with a
corresponding test update — not a hunt across two surfaces and four modules. See **Q-10**.

### Acceptance

- [ ] `backend/config/llm_config.py` exists and is the **only** place any model name, base URL, timeout,
      retry count or structured-output mode is declared, on either surface
- [ ] It imports nothing from `backend.*`, `ticketing.*` or `ops.*` (T-17-b)
- [ ] All eight task keys resolve, each overridable by its documented env var
- [ ] `findings_task()` is the only SEAH model ternary in the repository —
      `ticketing/services/resolved_summary_builder.py:301`, `ticketing/tasks/llm.py:165` **and `:251`** all call it
- [ ] Deprecated aliases resolve with exactly one warning each; no silently keyless client
- [ ] Defaults reproduce today's models and today's endpoint — **DPG-10's tests pass unchanged**
- [ ] `declared_env_vars()` exists and DPG-16's `.env.example` pin reads it rather than a second list
- [ ] `pydantic-settings>=2.0` present in `requirements.txt`, **removed** from `requirements.grm.txt`, and
      the import verified in a rebuilt `celery_llm` container (not just in the file)
- [ ] **`docs/dpg/dependency-licenses.md` updated** — the move changes its declared/transitive split
      (35 / 98). A dated audit that disagrees with the manifests is worse than no audit
      ([§0.5e](#05--what-sprint-0-changed-that-this-sprint-inherits))
- [ ] The new file carries an **SPDX header**; `pytest tests/repo` green
- [ ] `CLAUDE.md` §Folder structure and §Environment variables name the file (it is the file every future
      agent must find before adding a model call)
- [ ] `docs/services/06_llm_service.md` and `docs/deployment/11_llm_pipeline_policy.md` both point at it
      as the single registry — neither restates the model names

### Tests

[`TESTS.md`](TESTS.md) → **T-17-a … T-17-d**. T-17-d is the drift pin that makes the single-source claim
enforceable: one `LLM_BASE_URL` change must move **both** surfaces, proven by constructing both factories
in one test.

### ❓ Questions

- ✅ **Q-18 — answered 2026-08-17.** `backend/config/llm_config.py`, `pydantic-settings`, dependency moved
  to `requirements.txt`. See the banner at the top of this ticket.
- **Q-10 / Q-11 remain open** and are now owned here: whether the open configuration becomes the repository
  default (recommended yes, flipped in Sprint 2 — see §Correction), and one text model or one per task.
  Neither blocks this ticket: DPG-17 ships today's values as defaults either way, and both answers land as
  edits to this one file.

---

## DPG-11 — `backend/services/llm_client.py` {#dpg-11}

**New file.** The single place the chatbot surface **constructs** a client. It **names no model and no
endpoint** — those come from [`DPG-17`](#dpg-17), which lands first.

```python
# backend/services/llm_client.py
"""
OpenAI-compatible client factory for the chatbot surface.

Constructs clients. Chooses nothing: every endpoint, model, timeout and capability flag
comes from backend/config/llm_config.py — the one registry both surfaces read (DPG-17).
"""
```

- `get_llm_client() -> OpenAI` — built from `llm_config.llm_endpoint()`.
- `get_asr_client() -> OpenAI` — built from `llm_config.asr_endpoint()`; separate because ASR typically
  runs on a different port or provider, and its timeout is materially higher (audio is slow).
- **No registry here.** Call sites resolve their model through `llm_config.model_for("classify")` etc.
  The task keys are the registry table in [DPG-17](#dpg-17); this file must not restate them.

### Design constraints — non-negotiable

- **The open configuration becomes the default — but not in this sprint.** A reviewer who clones the repo
  should land on the open path without configuring anything; that is materially stronger indicator-4
  evidence than a proprietary default with an open option documented elsewhere. ⚠ **But flipping
  `LLM_BASE_URL` to the HF router while the model names are still `gpt-3.5-turbo` / `whisper-1` ships a
  default configuration that cannot serve one request**, and turns DPG-10's tests red in the commit where
  red means *stop*. The flip is a Sprint-2 commit against [DPG-17](#dpg-17)'s single file, once DPG-23 has
  named the open models. Full reasoning: [DPG-17 §Correction](#dpg-17). See **Q-10**.
- **Config lives in [DPG-17](#dpg-17), not here.** No `os.getenv` in this module, and no second settings
  object — [`02_python_services.md`](../../engineering/02_python_services.md) §config. Import-time
  `os.getenv` freezes values at import and makes the settings untestable without reloading the module;
  the shared resolver is testable by env-patch.
- **Lazy, not import-time.** The current module-level `client = OpenAI(...)` at `:30` runs on import and
  swallows its own failure into `client = None`, which is why five functions each carry a different
  `if not client` guard. The factory should construct on first use and cache.
- **Delete `load_dotenv('/home/ubuntu/nepal_chatbot/.env')` (`:25`).** It is an absolute path to a
  directory that exists on the EC2 host and in no container. In a Docker-only stack it is dead code that
  reads as live configuration — the worst kind. Config arrives via `env_file:`.

### Then replace the call sites

```python
# before
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
... model="gpt-3.5-turbo" ...
... model="whisper-1" ...

# after
from backend.config.llm_config import model_for
from .llm_client import get_llm_client, get_asr_client
... get_llm_client().chat.completions.create(model=model_for("classify").model, ...) ...
... get_asr_client().audio.transcriptions.create(model=model_for("asr").model, ...) ...
```

### ⚠ Blast radius — this is a stable shared service

Per CLAUDE.md §Service boundaries. `LLM_services.py` is reached from the Celery LLM queue
(`backend/task_queue/registered_tasks.py:479`, and the four task names registered at `:71-74`), from
intake (`backend/actions/grievance_intake/`), and from the SEAH detection path. **Re-grep the caller
list before committing** — do not trust this paragraph's snapshot. The chatbot is live; a regression
here is a production intake outage.

### Acceptance

- [ ] `backend/services/llm_client.py` exists; it is the **only** place `OpenAI(` appears in `backend/`
- [ ] It declares no model name, base URL or timeout of its own — everything resolves through
      `backend/config/llm_config.py` ([DPG-17](#dpg-17))
- [ ] No hard-coded model name in `backend/` — `grep -rn "gpt-\|whisper-1" backend/` returns nothing outside
      comments **and** `llm_config.py`'s registry defaults
- [ ] The module-level import-time client and the shadow client at `:199` are both gone
- [ ] `load_dotenv('/home/ubuntu/...')` deleted
- [ ] DPG-10's tests pass **unchanged** (they may gain parametrization, not rewrites)
- [ ] `docs/services/06_llm_service.md` updated — it currently says "uses OpenAI Whisper transcription API"
- [ ] **`docs/dpg/privacy-assessment.md` §2.2 leg L4 re-pointed** — it cites `LLM_services.py:47,79,116,232,324,385`
      as the places grievance text leaves the country, and this ticket moves all six

### Tests

[`TESTS.md`](TESTS.md) → **T-11-a … T-11-d**, including the grep-based pin (T-11-d) that fails CI when a
new hard-coded model name is introduced. That pin is what stops the indicator-4 claim from decaying.

### ❓ Questions

- **Q-10** — confirm: the repository default becomes the *open* configuration, so a fresh clone with no
  `LLM_BASE_URL` talks to the HF router, not OpenAI. Stronger DPG evidence; a behaviour change for
  anyone relying on defaults today.
- **Q-11** — one model for all four text tasks, or per-task models? The registry supports both; the
  default matters for cost and for how many models T2 must host (each additional model = a second vLLM
  process or a second GPU).

---

## DPG-12 — The ticketing surface {#dpg-12}

Same goal, different constraints. **Do not import `backend/services/llm_client.py` from `ticketing/`** —
the independence rule in `llm_client.py:7` names the **service layer** and it is a real boundary this
sprint does not relitigate. It does **not** extend to `backend/config/`: `ticketing/` already imports
`backend/config/smtp_config.py` in the live officer-invite path, and [DPG-17](#dpg-17) takes that
precedent. So this ticket keeps its own **factory** and drops its own **registry**.

### Steps

1. `ticketing/clients/llm_client.py` — `_get_client()` (`:28-37`) builds from
   `llm_config.llm_endpoint()`. Delete `_MODEL_STANDARD` / `_MODEL_SEAH` (`:139-140`); the two call sites
   at `:160` and `:252` resolve via `model_for(findings_task(is_seah))`.
   **The standard/SEAH split survives** — it is a deliberate cost/quality decision documented at
   `:135-138`, and SEAH cases genuinely warrant more careful reasoning. It becomes two registry keys
   ([DPG-17](#dpg-17)), not one, and not two literals here.
2. **The two files the original inventory missed** — both hold their own copies:
   - `ticketing/services/resolved_summary_builder.py:28-29` → delete; `:301` calls
     `model_for(findings_task(ticket.is_seah)).model`. ⚠ This is a **persisted provenance field** in the
     resolved-case summary. Miss it and every resolved case records a model that did not run it.
   - `ticketing/tasks/llm.py:165` → same substitution for the log line; drop the duplicated ternary.
   - ⚠ **`ticketing/tasks/llm.py:251` — found 2026-08-18, not in the original inventory.**
     `model = _llm._MODEL_SEAH if ticket.is_seah else _llm._MODEL_STANDARD` reaches into the **client
     module's privates** rather than restating the literal. **`grep "gpt-"` does not find it**, so this
     ticket's own acceptance grep would have passed with the site untouched — and it feeds the *same*
     `llm.model` provenance path as `resolved_summary_builder.py:301`. Deleting `_MODEL_*` from the client
     turns this into an `AttributeError`, which is the good outcome; resolve it via `model_for(...)`.
   - ⚠ **`ticketing/api/routers/tickets/summary.py:113` — found 2026-08-18.** The endpoint description
     says *"calls OpenAI gpt-4, and stores the result in `ai_summary_en`"*. It is **published in the
     OpenAPI document**, so the model name is in the public API surface and indicator 5 is graded on it.
     Rewrite it to describe the behaviour without naming a model.
3. `ticketing/config/settings.py` — **do not add a parallel model registry.** `openai_api_key` (`:85`)
   becomes a deprecated alias handled inside `llm_config` so both surfaces warn identically
   ([DPG-17 §Deprecated aliases](#dpg-17)); ticketing-specific LLM knobs stay out of `TicketingSettings`
   precisely so there is one place to look. Also fix the stale docstring at `ticketing/tasks/llm.py:15`.
4. Update the module docstring (`:1-9`). It currently states "Uses OpenAI gpt-4" as fact, and instructs
   the next reader to *"replicate the pattern here"* — the instruction that produced this duplication.
   Replace it with a pointer to the single registry.

### Acceptance

- [ ] `OpenAI(` appears exactly once in `ticketing/` — in `_get_client()`
- [ ] `grep -rn "gpt-" ticketing/` returns nothing outside comments — **including
      `services/resolved_summary_builder.py` and `tasks/llm.py`**, which the first inventory missed
- [ ] ⚠ **The grep is not sufficient on its own.** `tasks/llm.py:251` imports `_MODEL_SEAH` / `_MODEL_STANDARD`
      from the client rather than restating the literal, so it is **invisible to `grep "gpt-"`**. Also assert
      `grep -rn "_MODEL_SEAH\|_MODEL_STANDARD" ticketing/` is empty — that is the check that catches it
- [ ] `ticketing/api/routers/tickets/summary.py:113` no longer names a model in its **endpoint description**;
      the OpenAPI document does not advertise `gpt-4`
- [ ] `ticketing/` declares no model name, endpoint or timeout of its own; all resolve through
      `backend/config/llm_config.py` ([DPG-17](#dpg-17))
- [ ] The resolved-case summary's `llm.model` field is read from the registry, not a copy — the model it
      records is provably the model that ran
- [ ] The standard/SEAH model split survives as **two registry keys**
- [ ] `openai_api_key` alias warns rather than silently producing a keyless client
- [ ] `docs/deployment/11_llm_pipeline_policy.md` §Overview updated — its table names `gpt-4o-mini` and
      `gpt-4o` as fact
- [ ] `tests/ticketing/test_pii_boundary.py` and `test_boundary_policy.py` still green (they are unrelated
      but they are the boundary pins; confirm you did not disturb settings loading)
- [ ] **`docs/dpg/privacy-assessment.md` §2.2 leg L5 re-pointed** — it cites `llm_client.py:90,169,261`, and
      this ticket moves all three

### Tests

[`TESTS.md`](TESTS.md) → **T-12-a … T-12-c**.

---

## DPG-13 — `json_object` → `json_schema` {#dpg-13}

**The real engineering work in this sprint**, and it makes the code more robust independent of DPG.

`response_format={"type": "json_object"}` support is uneven across open-weights providers, and open
models are less reliable than GPT-4-class at free-form JSON mode. An explicit schema with guided
decoding constrains generation to the grammar, so output is **guaranteed parseable** rather than
probably parseable.

**And two of the seven JSON call sites have no `response_format` at all** — they ask for "strict JSON
format" in the prompt and hope. Those two are `classify_and_summarize_grievance` (`:230`) and
`translate_grievance_to_english_LLM` (`:322`): the product's primary classification path, and the
translation path that feeds the English record. Both currently absorb malformed JSON through
`parse_llm_response`'s `except JSONDecodeError → return {}` (`:281-283`) — which means a parse failure
looks identical to a successful empty classification. **This is a class of bug the codebase is probably
absorbing silently today.**

### Shape

```python
from pydantic import BaseModel
from typing import Literal, Optional

from backend.config.llm_config import model_for   # DPG-17 — the only model source

class GrievanceClassification(BaseModel):
    grievance_summary: str
    grievance_categories: list[str]
    grievance_categories_alternative: list[str]
    follow_up_question: str

resp = client.chat.completions.create(
    model=model_for("classify").model,
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "grievance_classification",
            "schema": GrievanceClassification.model_json_schema(),
            "strict": True,
        },
    },
)
result = GrievanceClassification.model_validate_json(resp.choices[0].message.content)
```

⚠ **The illustrative schema in the source narrative (§1.3) does not match this system.** It invents
`category` / `severity` / `district` / `is_duplicate_suspected` / `confidence` with a fixed six-value
category enum. The real contract is the four keys above, and **categories are not a fixed enum** — they
come from `CLASSIFICATION_DATA` / `LIST_OF_CATEGORIES` (`backend/config/constants.py`) and are resynced
into `public.grievance_classification_taxonomy`. Derive the schema from the live catalogue, or leave
categories as `list[str]` and validate membership after parsing. **Do not freeze a category enum into
code** — the taxonomy is admin-configurable and freezing it would break the resync path.

### Scope — seven call sites

| Call site | Today | Target |
|---|---|---|
| `extract_contact_info` `:82` | `json_object` | `json_schema`, single dynamic field |
| `extract_all_contact_info` `:134` | `json_object` | `json_schema`, six fields |
| `classify_and_summarize_grievance` `:230` | **none** | `json_schema` — biggest win |
| `translate_grievance_to_english_LLM` `:322` | **none** | `json_schema` |
| `detect_sensitive_content_llm` `:384` | `json_object` | `json_schema` — the `Literal["high","medium","low"]` clamp at `:390-391` becomes structural |
| `generate_case_findings` `:174` | `json_object` | `json_schema`; the "missing keys → fill defaults" branch at `:184-195` becomes unreachable — keep it, log a note |
| `generate_resolved_case_summary_llm` `:266` | `json_object` | `json_schema`; same for `:272-279` |

`extract_contact_info` is the awkward one: its schema key is `field_name`, computed at runtime from
`USER_FIELDS` (`:61`). Build the schema dynamically per call; do not special-case it away.

### Provider-capability fallback

Not every OpenAI-compatible endpoint supports `json_schema`. The capability is a property of the
**endpoint**, so it lives on [DPG-17](#dpg-17)'s `Endpoint`
(`LLM_STRUCTURED_OUTPUT=json_schema|json_object|prompt`) and both surfaces degrade in that order, logging
which mode was used. Declaring it once is the point: seven call sites across two surfaces hit the same
provider, and a per-surface flag would let ticketing ask for a schema the endpoint cannot honour. Without
this, DPG-24's CI job fails against half the candidate providers and you will be tempted to weaken the
test instead of the config.

### Acceptance

- [ ] A Pydantic model per structured call site, in one module, importable by DPG-33 (which will wrap these)
- [ ] All seven sites use `json_schema` when the configured mode allows it
- [ ] `LLM_STRUCTURED_OUTPUT` degradation ladder implemented and logged
- [ ] Category values validated against the live catalogue, **not** a frozen enum
- [ ] `parse_llm_response`'s silent `{}` on malformed JSON now logs at **error** with the raw response
      length (not the content — PII), and the caller can distinguish "parse failed" from "empty result"
- [ ] DPG-10's tests extended, not rewritten
- [ ] `docs/services/06_llm_service.md` §Capabilities documents the schemas

### Tests

[`TESTS.md`](TESTS.md) → **T-13-a … T-13-e**, including one that proves a malformed response is now
distinguishable from an empty one — the specific silent failure this ticket removes.

---

## DPG-14 — Three latent defects {#dpg-14}

Found during this sprint's planning. Land them **under DPG-10's net**, before the refactor changes shape.

### 14.1 — `gpt-5-nano` on the classification path

`LLM_services.py:246`. Two things to establish, in-container, against the live key:

1. **Does the call actually succeed?** If the model name is wrong for the account, the request raises,
   `:237-246` catches it, and the function returns `status="error"` with empty summary and categories.
   Downstream, `grievance_has_classification_content` (`classification.py:20-26`) sees no content, the
   retrieve step polls for 20 s, and the complainant gets an empty classification after a delay. **That
   failure is invisible in the UI and looks like a slow model.** Check the Celery LLM-queue logs for
   `Error in classify_and_summarize_grievance` before assuming it works.
2. ~~Was the model choice deliberate?~~ ✅ **Answered (Q-13.1): yes — a deliberate cost decision**, and the
   owner reports it works well as a classifier. It is documented drift no longer; record it in
   `docs/services/06_llm_service.md`, which today names no model at all, because **DPG-23 benchmarks
   against it** as the baseline.
3. ⚠ **New, and it is the part worth the container time: check for *truncation*, not just exceptions.**
   Q-11 reports *"I'm maxing out openAI nano"*, which sits in tension with Q-13's *"it works well"*. Both can
   be true — a response that hits a length limit is **not** an exception; it is a truncated JSON body that
   `parse_llm_response` swallows into `{}` at `:281-283`, which looks exactly like a successful empty
   classification. The prompt injects the full category list **plus** `result_dict_str` **plus**
   district/province, so the pressure is plausible. **Check `finish_reason` on real responses**, not only
   the error log. If it is ever `length`, that is DPG-13's schema work becoming urgent rather than tidy.

### 14.2 — The shadow client

`:198-199` constructs a second `OpenAI(...)` inside `classify_and_summarize_grievance`, with its own
`OPENAI_CLASSIFICATION_TIMEOUT`, shadowing the module-level client. Then `:200-201` tests it for
falsiness — `if not client: raise` — which can never fire, because `OpenAI(...)` either returns an object
or raises. Dead guard. DPG-11 removes both the shadow and the guard; the timeout becomes `LLM_TIMEOUT`
(preserve the env var name as a deprecated alias, per the DPG-12 pattern).

### 14.3 — ⚠ Suspected: the ASR call passes an invalid keyword

`:43-47` calls:

```python
client.audio.transcriptions.create(file=audio_data, model="whisper-1", language_code=language_code)
```

The OpenAI Python SDK's transcription method takes **`language`**, not `language_code`, and declares its
parameters explicitly rather than accepting `**kwargs`. If that holds for the pinned `openai==1.70.0`,
**every transcription call raises `TypeError`**, is logged at `:50`, and re-raised — meaning voice-note
transcription has never worked on this path, and the failure is absorbed by the task layer.

> **Status: ⚠ unverified, and the in-container check is now the *only* way to resolve it.**
> ✅ **Q-13.2 answered: voice transcription is not live at all** — not because of this bug but because there
> is no LLM budget for transcription. So **no field evidence exists or can exist**: nobody has run a voice
> note through this path, and the Celery logs will be silent rather than exonerating. The host has no
> `openai` installed (Docker-only, correctly). **Verify in the container**, and before writing the fix:
> ```bash
> docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
>   exec celery_llm python -c "import inspect; from openai.resources.audio.transcriptions import Transcriptions; print(list(inspect.signature(Transcriptions.create).parameters))"
> ```
> Then check the Celery LLM-queue logs for `Error transcribing audio file`.

If confirmed: rename to `language`, and add the regression test **first** (T-14-c). If the parameter
turns out to be accepted, record that in `PROGRESS.md` and close the item — a corrected non-finding is
worth more than a silent one.

⚠ **Either way, do not report this as "fixed" without qualification.** With voice not live and no budget to
exercise it, the most that can honestly be claimed is *"the signature is now correct and unit-tested"* —
**not** *"transcription works"*. That distinction is exactly what DPG-22's missing baseline is about.

Either way, `docs/services/03_voice_grievance_service.md` needs its transcription section reconciled
with what the code actually does.

### Acceptance

- [ ] 14.1: classification-path liveness established from container logs; the model choice recorded (Q-13)
- [ ] 14.2: shadow client and dead guard removed (may land inside DPG-11); `OPENAI_CLASSIFICATION_TIMEOUT` aliased
- [ ] 14.3: SDK signature verified in-container; fixed if broken, **with the regression test first**;
      finding or non-finding recorded in `PROGRESS.md`
- [ ] `docs/services/03_voice_grievance_service.md` reconciled
- [ ] `extract_contact_info`'s `UnboundLocalError` (DPG-10 trap 1) either fixed here or logged as a followup

### Tests

[`TESTS.md`](TESTS.md) → **T-14-a … T-14-c**.

### ✅ Questions — answered

- **Q-13** — ✅ **(1)** `gpt-5-nano` is a deliberate cost choice that works well as a classifier.
  **(2)** Voice transcription is **not live**, for lack of LLM budget — so there is no field evidence on
  14.3, and no baseline for DPG-22. ⚠ Both answers add work rather than removing it: check `finish_reason`
  for truncation (14.1), and treat the SDK check as the sole source of truth (14.3).

---

## DPG-15 — Degraded mode: verify, close gaps, add the probe {#dpg-15}

**The requirement stands and it is correct:** *if the model endpoint is unreachable, the chatbot must
still accept the grievance and queue it for later classification.* A grievance mechanism that refuses
intake because an API is down is worse than one with no AI at all — and in Nepal that is not hypothetical.

**But this is largely already built**, and the ticket is an audit, not a greenfield build. Verified:

| Guide's requirement | Status | Evidence |
|---|---|---|
| Intake always writes to PostgreSQL first, before any model call | ✅ built | `grievance_intake/classification.py` — the grievance row exists; `trigger_async_classification` then enqueues |
| Classification is a Celery task with retry and backoff, not an inline blocking call | ✅ built | `classify_and_summarize_grievance_task.delay(...)` (`classification.py:151`); retry at `registered_tasks.py:95-98` |
| Unclassified grievances surface as "pending classification", not errors | 🟡 partial | `LLM_FAILED` / `LLM_SKIPPED` status codes exist (`backend/config/classification_status.py`) and `load_grievance_for_classification` short-circuits on terminal statuses. **What the officer portal renders for them is unverified** |
| A health endpoint reporting LLM reachability separately from application health | ❌ not built | `/health` exists on the backend API (`fastapi_app.py:125`), orchestrator (`main.py:153`), ticketing (`api/main.py:133`) — none probe the LLM |
| Celery import failure falls back gracefully | ✅ built | `classification.py:100-118` — `ImportError` → mark `LLM_SKIPPED`, return skip values |
| A bounded wait rather than an indefinite hang | ✅ built | 20 s deadline / 0.5 s poll (`classification.py:16-17`) |

### Steps

1. **Audit the other four backend paths** the way classification was audited: transcription, contact
   extraction (both), sensitive detection, translation. For each, answer in `PROGRESS.md`: *is the
   grievance already durable before this call, and what does the user see when it fails?*
   - ✅ **`detect_sensitive_content_llm`'s fail-open is now a *documented, justified* default (Q-14) — not an
     open risk.** It returns `detected: False` when the model is unreachable (`:404`), and that is
     acceptable because **it is the second of two independent detection paths**, which this spec did not
     know when it raised the question. Verified in code:
     - **Deterministic, synchronous, no LLM:** `backend/shared_functions/keyword_detector.py:259`
       `detect_sensitive_content()`, with confidence scoring at `:343` — reached via `helpers_repo.py:58` →
       `actions/services/seah/sensitive_detection.py:25` → `base_mixins.py:170`, running as **slot
       validation inside the conversation**.
     - **LLM, asynchronous:** `trigger_detect_sensitive_content_task` (`forms/form_grievance.py:200`) →
       Celery → `detect_sensitive_content_llm`.

     So an LLM outage **degrades a second pass; it does not remove detection.** The owner declined the
     `unknown`-state recommendation on exactly this basis, correctly. **The audit's job here is now to
     verify the claim keeps holding**, not to reopen the decision: confirm the keyword path really runs
     independently of the LLM leg, and record it. ⚠ **If that ever stops being true, fail-open stops being
     justified** — leave that sentence in the audit table so the next reader inherits the dependency.
2. **Audit the three ticketing paths.** They are already async (`docs/deployment/11_llm_pipeline_policy.md`
   says so and the code agrees) and all three return `None` on failure. Confirm what the officer sees.
3. **Add the LLM reachability probe.** A route separate from `/health` — `/health/llm` — that reports the
   configured base URL (host only, **never the key**), reachability, and last-success timestamp. It must
   **not** be part of the container health check: an LLM outage must not restart the chatbot. That is
   the whole point.
4. **Test it for real.** Point `LLM_BASE_URL` at a dead port and drive a full intake in-container.
   Intake must complete; the grievance must be durable; the status must be a terminal LLM status; the
   probe must report unreachable; `/health` must stay green.

### Acceptance

- [ ] Audit table for all nine call sites in `PROGRESS.md` — durable-before-call? user-visible failure?
- [ ] `/health/llm` implemented per [`03_api_layer.md`](../../engineering/03_api_layer.md); no secrets in the response
- [ ] The probe is **not** wired into the container healthcheck
- [ ] Dead-port intake test executed in-container and recorded, with the grievance ID and the observed status
- [ ] Any gap found is either fixed in-scope or logged as a followup + `TODO.md` row
- [ ] SEAH fail-open **documented as justified** (Q-14) with the two-path evidence and file:line refs,
      unchanged in behaviour — plus the standing condition that it depends on the deterministic path
      continuing to run independently

### Tests

[`TESTS.md`](TESTS.md) → **T-15-a … T-15-c**. T-15-a is the guide's own criterion — intake completes with
`LLM_BASE_URL` pointing at a dead port — as an automated test, not a manual check.

### ✅ Questions — answered

- **Q-14** — ✅ **fail-open stays.** A deterministic scored keyword pre-filter is the backup and **it exists**
  (verified above); the chatbot is scoped to road-construction grievances with a dedicated SEAH route. The
  `unknown`-state recommendation is declined on a sound premise. **This strengthens indicator 9b**, which
  `docs/dpg/00_compliance_status.md` credited to the LLM path alone — corrected there.

---

## DPG-16 — Environment plumbing {#dpg-16}

The configuration surface *is* the indicator-4 evidence. It has to be legible to a reviewer who has
never seen the repo.

### Steps

1. **`.env.example`** — today `:60-61` has only `OPENAI_API_KEY=`. Replace with the full block:
   `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `LLM_STRUCTURED_OUTPUT`,
   `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_TIMEOUT`, `MODEL_CLASSIFY`, `MODEL_EXTRACT`, `MODEL_TRANSLATE`,
   `MODEL_DETECT`, `MODEL_ASR`, `MODEL_TICKET_TRANSLATE`, `MODEL_TICKET_FINDINGS`,
   `MODEL_TICKET_FINDINGS_SEAH`. Each with a one-line comment saying what it does and what its default is.
   > **Do not hand-maintain this list.** It is [DPG-17](#dpg-17)'s `declared_env_vars()`, and T-16-a
   > compares the two — a hand-kept mirror is the failure mode CLAUDE.md §Data-rules learned the hard way.
2. **`.env.open` and `.env.openai`** — two committed **templates with empty secret values**, showing the
   two configurations side by side. This is the artefact a DPG reviewer reads. `.env.open` is the
   reference open configuration; `.env.openai` is the legacy/comparison one.
   > Confirm both are not caught by `.gitignore`'s env patterns — check before assuming they commit.
3. **Compose.** `env.local` is the runtime env file. Confirm every service that reaches an LLM
   (`celery_llm`, `backend`, `grm_celery`, `ticketing_api`) receives the new variables. ⚠ Some compose
   services hardcode values in their own `environment:` block rather than reading `env.local` — that is
   documented in `TODO.md` for `POSTGRES_*` and bit this project once. **Verify by exec-ing into each
   container and reading the variable**, not by reading the compose file.
4. **CLAUDE.md §Environment variables** — extend the block. It is the file every agent reads first.
5. **`docs/rest_chatbot/04_operations_spec.md`** — env-var reference for the chatbot runtime.
6. **`docs/dpg/open-model-configuration.md`** — the reviewer-facing document: what the open configuration
   is, how to switch, what changes (nothing but env), what to expect (DPG-23's numbers, once measured).

### Acceptance

- [ ] `.env.example` documents every new variable with its default
- [ ] `.env.open` / `.env.openai` committed with **empty** secret values, and verified not gitignored
- [ ] Each LLM-touching container verified by `exec` to see the variables
- [ ] CLAUDE.md, `04_operations_spec.md`, and `docs/dpg/open-model-configuration.md` updated
- [ ] No secret in any tracked file, test fixture, or CI log

### Tests

[`TESTS.md`](TESTS.md) → **T-16-a** (`.env.example` covers every variable the code reads — a drift pin).

---

## Second wave — DPG-18, DPG-19, DPG-15b (owner, 2026-08-18)

Raised by the owner after reading Sprint 1's result. Three of the five points are code changes and
are specced below; the other two are answered in place:

| Owner's point | Disposition |
|---|---|
| *"We use only nano now, not turbo"* + *"one entry, the layer picks the model, a parser feeds the model what it needs"* | **[DPG-18](#dpg-18)** — and ⚠ the first half is not yet true, see §18.0 |
| *"An empty summary is not necessarily a failure… we need a length guardrail, ~25 characters"* | **[DPG-19](#dpg-19)** — and ⚠ the shipped code does **not** treat an empty summary as a failure; §19.0 shows why the concern is still right |
| *"I don't understand how the phone number is sent to the LLM"* | **It is not.** Answered in §19.0b — and the answer corrects a compliance document, so it is not merely reassuring |
| *"Move the classification checkpoint to submission, ~90 s, update the submission if it lands late"* | **[DPG-15b](#dpg-15b)** — supersedes the D-30 and D-34 followups |
| *"Fix the ValueError by trimming the grievance — the first 3 words are enough to find it"* | **[DPG-19.3](#dpg-19)** — closes **D-29** inside this sprint instead of deferring it to Sprint 3 |

**On the numbering.** 20–25 belong to Sprint 2 and 30–36 to Sprint 3, so the new tickets take 18 and
19. The timing work is **DPG-15b** rather than 20-something because it is literally the continuation
of DPG-15: it closes two deviations that ticket raised (D-30, D-34), and a reader who finds those
rows should land on it.

---

## DPG-18 — One entry point: the layer picks the model and shapes the request {#dpg-18}

> *"We may need to make the functions configurable so that they work whether we call one model or
> another. Meaning: we have one entry, then the LLM orchestration layer chooses the model, and then
> we have a parser function that makes sure we feed the model what is required."* — owner, 2026-08-18

### 18.0 — What actually runs: five of the nine call sites, and four are dead

**The owner's claim — *"only gpt-5-nano is called; I combined classification, summary, translation
and SEAH detection into one call"* — was checked against the code on 2026-08-18. It is right about
what runs, wrong about one path, and the full picture is larger than either version.**

⚠ **This supersedes the first draft of this section, which said "gpt-3.5-turbo is still on three
sites and gpt-4 on two". That counted *call sites*, not *reachable* ones — the same mistake the
privacy assessment's leg L4 made, one week and one document apart.**

Reachability was established per site: does anything **enqueue** the task, anywhere outside
`backend/task_queue/test_tasks.py` (a manual script)?

| # | Call site | Model | Live? | Evidence |
|---|---|---|---|---|
| 4 | `classify_and_summarize_grievance` | **`gpt-5-nano`** | ✅ **live** | `grievance_intake/classification.py:153` `.delay(...)` |
| 6 | `detect_sensitive_content_llm` | **`gpt-3.5-turbo`** | ✅ **live** | `forms/form_grievance.py:202` → background thread → `.delay(...)`; result polled at submit |
| 1 | `transcribe_audio_file` | `whisper-1` | ❌ **switched off by design** | `registered_tasks.py:157` — *"CB-01 proto: store audio only; transcription/classification deferred to officers"*. The upload still stores the file; nothing transcribes it |
| 2 | `extract_contact_info` | `gpt-3.5-turbo` | ❌ dead | task registered, never enqueued |
| 3 | `extract_all_contact_info` | `gpt-3.5-turbo` | ❌ dead | no reference at all |
| 5 | `translate_grievance_to_english_LLM` | `gpt-4` | ❌ dead | task registered, never enqueued |
| 7–9 | ticketing: note translation, findings, resolved summary | `gpt-4`, `gpt-4o-mini`/`gpt-4o` | ✅ live | their Celery tasks are enqueued from the ticketing API |

**So: five live call sites, not nine. Two on the chatbot surface, three on ticketing.**

#### Where the owner is right

- **Classification, summary and the follow-up question are one call**, on `gpt-5-nano`. Verified
  live: the request returns exactly those keys.
- **SEAH detection *is* partly carried by that call** — and this is the part worth naming, because it
  is not in any spec. `classify_and_summarize_grievance` returns categories, and the review step
  screens them: `detect_sensitive_categories()` keeps any category containing **"gender"**
  (`form_grievance_complainant_review.py`). So the nano call is a **third** SEAH signal, alongside
  the deterministic keyword detector and the LLM detection task.
- **`gpt-4` is not called on the chatbot surface at all.**

#### Where it does not hold

⚠ **`gpt-3.5-turbo` is still called in production, once — on the SEAH path.** Not merged into the
nano call: a separate task, fired in a background thread when the complainant adds detail, whose
result is polled at submit with a keyword fallback. **It is the one live chatbot call site running
on the oldest model in the repository, and it is the harassment-detection path.**

#### The consequence nobody had written down

**Nothing translates the grievance narrative on the chatbot side.** The translation task is dead, so
`grievance_description_en` and `grievance_summary_en` are never populated by a live path. Officers
read English because **ticketing** generates it (`generate_case_findings`, `gpt-4o-mini`) — which is
almost certainly *why* the chatbot-side translation fell out of use. That is a coherent architecture;
it has simply never been stated, and three documents still describe the dead path as the English record.

⚠ **And the DPG evidence pack counts nine.** `00_compliance_status.md`, `privacy-assessment.md` and
this spec all present nine call sites as the indicator-4 and egress inventory. Four are unreachable.
An inventory that overstates exposure spends the reader's trust on paths that do not exist; corrected
in [DPG-19b](#dpg-19b).

### 18.1 — The layer

A call site today, after DPG-11/12/13, carries five concerns:

```python
task   = model_for("classify")                      # which model, which deadline
client = _llm_client()                              # which client
resp   = client.chat.completions.create(            # how to ask for JSON
    model=task.model, timeout=task.timeout,
    **response_format_kwargs("grievance_classification", GrievanceClassification.model_json_schema(),
                             task.structured_output),
    messages=[...],                                 # the actual prompt
)
parsed = GrievanceClassification.model_validate(    # how to read it back
    parse_llm_response("grievance_response", resp.choices[0].message.content, language_code))
```

After DPG-18 it carries one:

```python
result = call_llm("classify", messages, schema=GrievanceClassification)
```

**Three of those five concerns vary by provider, and none of them varies by call site.** That is the
test for what moves into the layer.

| Moves to the shared layer | Stays at the call site |
|---|---|
| Which model, which endpoint, which deadline | The prompt — the only thing that is actually about this task |
| *How* to ask for structured output (`json_schema` → `json_object` → `prompt`) | What to do with the validated result |
| *How* to read it back: fences stripped, JSON parsed, schema validated, typed error raised | |

**What "the parser feeds the model what is required" means concretely — the `prompt` rung.** When the
model supports no JSON mode at all, the requirement has to travel *in words*. Today that is
hand-written in each prompt, nine times, and the nine have already drifted: three say *"Return the
response in **strict JSON format** like this:"* with a hand-typed example, one says *"Respond with a
JSON object only, no other text"*, and the ticketing pair embed a full schema block in the system
message. `augment_prompt_for_schema()` generates that paragraph **from the same Pydantic model the
`json_schema` rung sends**, so the three rungs cannot describe different shapes — which is exactly
the failure mode a hand-written fallback has.

### Where it lives, and why it is two files and not one

| Piece | Where | Why |
|---|---|---|
| `request_for(task, messages, schema=None, **overrides) -> dict` | `backend/config/llm_config.py` | Pure. No client. Already the home of the ladder |
| `augment_prompt_for_schema(messages, schema) -> messages` | same | The `prompt` rung, generated from the schema |
| `parse_response(raw, schema) -> BaseModel` | same | Fence-stripping, JSON, validation, one typed error |
| `call_llm(task, messages, schema=None)` | **`backend/services/llm_client.py`** *and* **`ticketing/clients/llm_client.py`** | ~15 lines each: `client.chat.completions.create(**request_for(...))` then `parse_response(...)` |

⚠ **Why not one shared caller.** It would have to import an OpenAI client into `backend/config/`,
and `ticketing/` would then be reaching into the chatbot's runtime rather than its configuration —
the boundary Q-18 drew deliberately. The rule that survives is the one that matters: **the shaping
is shared, the calling is not.** *Two factories, one config* becomes *two callers, one contract*.

### 18.2 — Two models, and the seam that keeps it reversible

> ✅ **Q-21 answered 2026-08-18.** *"Given the nature of the tasks, we just need two models: one for
> transcription (so far whisper) and then nano 5 for all the other tasks. That will be aligned with
> what we discussed as well for the open weights model where we agreed to just have two."*

**Eight task keys, two values.** The keys stay — they are the seam that lets one task move later
without touching code, and Q-11's *"one text model first, then downsize"* depends on that seam
existing. What collapses is the defaults:

| Task key | Today | After |
|---|---|---|
| `asr` | `whisper-1` | `whisper-1` — the ASR model, unchanged |
| `classify` | `gpt-5-nano` | `gpt-5-nano` — unchanged |
| `detect` | `gpt-3.5-turbo` | **`gpt-5-nano`** ← the only change on a **live** path |
| `extract`, `translate` | `gpt-3.5-turbo`, `gpt-4` | `gpt-5-nano` — parked paths (DPG-19b); they change model when they unpark |
| `ticket_translate`, `ticket_findings`, `ticket_findings_seah` | `gpt-4`, `gpt-4o-mini`, `gpt-4o` | `gpt-5-nano` ⚠ **needs confirmation, below** |

**What the collapse buys, beyond the bill:**

- **`json_schema` everywhere.** Measured (D-31): every weaker rung in the registry is there because
  of the *model*, not the endpoint. On one text model the per-task `STRUCTURED_*` flags become one
  value, and DPG-13's ladder goes back to being what it was designed as — a **provider** fallback for
  the open configuration, not a workaround for four different OpenAI vintages.
- **Sprint 2 evaluates two things, not five.** DPG-22 measures an ASR model; DPG-23 measures a text
  model. `.env.open` and `.env.openai` then differ in **two** model choices. On no budget (Q-19) that
  is the difference between a benchmark that happens and one that does not.

⚠ **The one live behaviour change is the SEAH detection path**, moving off `gpt-3.5-turbo`. The
deterministic keyword pre-filter still runs underneath (Q-14), so the detection floor does not move —
but the LLM leg's sensitivity is unmeasured on nano, and this is the harassment path. **Land it as its
own commit**, and say so in `docs/services/06_llm_service.md`.

#### ✅ Confirmed 2026-08-18 — and measuring it found the trap

> *"Move to nano as well. Nano is very strong for classification especially when we just need to fill
> json."*

Two keys survive for the standard/SEAH split, both pointing at the text model, so the split stays a
**configuration** decision that DPG-23 can re-open with measurements. T-12-b's assertion moves from
*"they resolve to different models"* to *"they are independently overridable"*.

⚠ **But the migration is not a defaults edit, and this is the most important finding of the second
wave.** Measured against the live provider, 2026-08-18:

| What the ticketing calls send today | On `gpt-5-nano` |
|---|---|
| `temperature=0.0` (findings, resolved summary) / `0.2` (note translation) | **400 Bad Request** — *"does not support 0.0 with this model. Only the default (1) value is supported"* |
| `max_tokens=400` / `1200` | **400 Bad Request** — *"'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead"* |
| the same cap, renamed to `max_completion_tokens=400` | **200 OK, `finish_reason: length`, content EMPTY** — all 400 tokens went to reasoning |
| renamed and raised to `2000` | **200 OK, `finish_reason: length`, content STILL EMPTY** — 2000 tokens, all reasoning |

**And the budget the largest ticketing prompt actually needs:** the resolved-case summary consumed
**4,287 completion tokens, of which 3,904 were reasoning** — against a current cap of 1,200.

**So a naive "point the ticketing keys at nano" would have failed in three ways, and the third is
the dangerous one:** two hard 400s (loud, found immediately) and then, once someone "fixed" the
parameter name, a **200 OK with empty content**. Empty content on that path returns `None` →
`generation_status = "llm_failed"` → and per **D-36** nothing ever retries it. **The complainant is
told their case is resolved and never receives the closure document.** Silent, complainant-facing,
and it would have looked like a model-quality problem rather than a parameter one.

### 18.3 — Parameter compatibility belongs in the layer, for the same reason structured output does

D-31 established that structured-output support is a property of the **(endpoint, model)** pair. The
measurements above show `temperature` and the token cap are too — including the *name* of the
parameter. That is three properties following the model, and it is the concrete case for the layer
the owner asked for: *"a parser function that makes sure we feed the model what is required."*

So the registry gains a **model profile**, and the per-task `STRUCTURED_*` flags fold into it —
capability follows the model, not the task:

```python
@dataclass(frozen=True)
class ModelProfile:
    structured_output: str        # best rung the model honours
    supports_temperature: bool    # gpt-5 family: default only
    token_cap_param: str          # "max_tokens" | "max_completion_tokens"
    reasoning_overhead: int       # measured tokens to add on top of expected output
```

| Model family | `structured_output` | `temperature` | cap parameter | reasoning overhead |
|---|---|---|---|---|
| `gpt-5*` | `json_schema` | ❌ default only | `max_completion_tokens` | **~4,000 measured** |
| `gpt-4o*` | `json_schema` | ✅ | `max_tokens` | 0 |
| `gpt-3.5*` | `json_object` | ✅ | `max_tokens` | 0 |
| `gpt-4` | **`prompt`** | ✅ | `max_tokens` | 0 |
| unknown / open-weights | `json_object` (conservative) | ✅ | `max_tokens` | 0 |

`request_for()` then **drops** an unsupported `temperature`, **renames** the cap, and **budgets** it —
so a call site keeps asking for what it wants and the layer decides what the model can be told. That
is the same shape as the structured-output ladder, and it is what makes *"works whether we call one
model or another"* true rather than aspirational.

⚠ **Three rules that come out of the measurements and must be in the code, not only here:**

1. **`finish_reason == "length"` is a failure.** Not "an empty result" — a failure, logged as one.
   Every parse path currently treats empty content as an empty *answer*; on a reasoning model that
   is how a truncated call disguises itself.
2. **A cap is optional; a wrong cap is worse than none.** Default to sending no cap. If one is set
   for cost control, it must be ≥ the profile's reasoning overhead plus the expected output, and the
   rule above catches the day it is not.
3. **Cost moves from per-token to per-call.** Nano is cheap per token and spends 2,000–4,000 of them
   thinking on every call. The ticketing findings call goes from ~400 completion tokens on
   `gpt-4o-mini` to ~2,300 on nano. **DPG-23 must price per call**, not per thousand tokens, or the
   benchmark will recommend the wrong model. ⚠ This is also a **Q-19** input: the cost of the
   consolidation is not obviously lower, and it should be measured before it is assumed.

### Acceptance

- [ ] `call_llm(task, messages, schema=None)` exists on both surfaces and is the **only** thing that
      calls `.create()` — no call site constructs a request or parses a response itself
- [ ] `request_for`, `augment_prompt_for_schema` and `parse_response` live in `llm_config.py`, remain
      first-party-import-free (T-17-b still green), and are the only implementation of the ladder
- [ ] The `prompt` rung's instruction is **generated from the schema**; the nine hand-written "return
      strict JSON" paragraphs are gone, and a test proves the generated text names every required field
- [ ] All nine call sites migrated; DPG-10's net stays green **unchanged** for the eight sites whose
      request shape does not change
- [ ] §18.0's table is reproduced in `docs/services/06_llm_service.md` — the *why* travels with the rule
- [ ] Model consolidation applied once **Q-21** is answered, defaults only, with the previous values
      recorded in the commit message so the rollback is one env var

### Tests

[`TESTS.md`](TESTS.md) → **T-18-a … T-18-d**.

### ❓ Questions

- 🔴 **Q-21 — which single text model?** Recommendation: `gpt-5-nano` for `classify`, `extract`,
  `detect` and `translate`, leaving the ticketing findings pair alone until DPG-23 measures them
  (they are the officer- and **complainant-facing** outputs, and `gpt-4o-mini` already does
  `json_schema`). Needs the owner's word because it changes the SEAH detection path.

---

## DPG-19 — Meaningful input: an empty summary is not a failure {#dpg-19}

> *"An empty summary is not necessarily a failure. If the grievance text is too short it cannot be
> summarised. So if we decide that empty summary or empty translations are errors, then we need
> guardrails to assess the length of the grievance pushed… probably minimum 25 characters."* — owner

### 19.0 — First, what the shipped code actually does

⚠ **The risk the owner names is real, and the code does not have it — check before building.**
`is_failed_classification()` (DPG-15) keys on `status == "error"` or a non-empty `error` string.
Both are set **only when the call itself failed**. A model that answers `{}` for a three-word
grievance travels the sentinel path, gets the localized *"not enough information to proceed"*
response, and is **not** treated as a failure. Pinned by
`test_a_malformed_classification_is_distinguishable_from_an_empty_one`.

**So this ticket is not a correction. It is the guardrail that makes that distinction deliberate
rather than accidental** — and it adds the half that is genuinely missing: *today a six-character
grievance is sent to the model at all*, and we have no way to tell "the model declined to summarise
two words" from "the model failed to summarise a paragraph".

### 19.0b — And the answer to *"how is the phone number sent to the LLM?"*

**It is not.** Traced end to end, and the answer corrects a compliance document:

- The complainant's phone is validated and normalised **deterministically**, in a slot validator —
  `backend/actions/services/contact/phone.py::validate_complainant_phone` → `helpers.is_valid_phone`
  / `is_philippine_phone`. No model is involved anywhere on that path.
- `extract_contact_info` and `extract_all_contact_info` — the two LLM functions that *would* send it
  — **have no production caller.** The only reference to `extract_contact_info_task` outside its own
  definition is `backend/task_queue/test_tasks.py`, a manual test script. `extract_all_contact_info`
  has no reference at all. (Confirmed by a whole-repo grep across `.py`/`.js`/`.ts`/`.yml`.)
- What *does* reach the model is the **grievance narrative** (classification, translation, SEAH
  detection) and, on the ticketing surface, officer notes and the case timeline. If a complainant
  types their number *inside the narrative*, it goes — which is Sprint 3's subject, and is what
  DPG-31's Devanagari-digit recognisers exist for.

⚠ **This corrects `docs/dpg/privacy-assessment.md` leg L4**, which lists six call sites as places
"grievance text leaves the country". **Two of the six are unreachable.** An egress inventory that
overstates exposure is not a safe error: it is the same class of defect as one that understates it,
because it spends the reader's trust on paths that do not exist. Fixed as part of this ticket, and
logged as **D-35**.

⚠ **One real finding while tracing it**, for Sprint 3 rather than here: `phone.py:27` logs the phone
number at INFO — `logger.info("%s - Validating phone: %s", action_name, slot_value)` — and `:37`
logs it again on the invalid path. That is the log surface DPG-34 owns; recorded, not fixed.

### 19.1 — The gate

A new registry value, `MIN_CLASSIFY_CHARS` (default **25**, the owner's number), applied to the
**description**, on whitespace-stripped length:

| Input | Behaviour |
|---|---|
| Below the threshold | **The model is not called.** The grievance is marked `LLM_SKIPPED` — an existing terminal code that means exactly this — and the flow continues. Free, instant, honest |
| At or above, model returns content | Normal path |
| At or above, model returns `{}` | **Not a failure.** The localized "not enough information" response, plus a **warning log** carrying the length (not the text) so DPG-23 can count how often it happens |
| Any length, call raises | Failure — unchanged from DPG-15 |

⚠ **25 characters is not the same amount of information in every script.** In Devanagari it is a
short sentence; in English it is roughly four words. The threshold is a registry value precisely so
it can differ by language later; this ticket ships one number and says so.

⚠ **The same gate belongs on translation** — the second half of the owner's sentence. Translating
"धुलो" costs a call and returns nothing useful. Same threshold, same skip.

### 19.2 — Say which of the three happened

`LLM_SKIPPED` already exists and already means "not classified, and that is fine". What is missing
is that **nothing distinguishes *too short to classify* from *Celery was unavailable*** — both write
`LLM_SKIPPED` today. This ticket adds the reason to the log and the task result, not a new status
code: a fourth status would need a migration and an officer-portal change for a distinction only
operators need.

### 19.3 — Bounded error text (closes D-29)

> *"We can already fix the ValueError issue by trimming the grievance — we just need the first 3
> words to easily find it."*

`translate_grievance_to_english_LLM` interpolates the **whole `input_data`** into its `ValueError`,
and that message reaches the Celery error log. That is why D-29 was deferred: binding `result`
early — the obvious one-line fix — makes a PII-leaking message *reachable*. The owner's trim removes
the reason to defer:

```python
raise ValueError(
    f"Error translating grievance {input_data.get('grievance_id')}: {exc} "
    f"(text starts: {first_words(input_data.get('grievance_description'), 3)})"
)
```

- `grievance_id` **first** — it is the identifier that actually finds the record, and it is not PII
  on its own.
- Three words, whitespace-split, truncated to 60 characters as a backstop against a pasted wall of
  text with no spaces.
- ⚠ **Three words of a grievance is still narrative text**, and could be *"Er. Sharma refused"*.
  This is a deliberate, bounded trade the owner has made: enough to find the record, small enough to
  stop being a transcript. It stays in scope for DPG-34's log redaction, which will see three words
  instead of a paragraph.
- The same treatment applies to the other message in that function (`:455`) and to
  `parse_llm_response`, which DPG-13 already reduced to a length.

**With this, D-29's underlying bug is fixed here**: `result` is bound before the `try`, the declared
`ValueError` becomes reachable, and the message it carries is bounded.

### Acceptance

- [ ] `MIN_CLASSIFY_CHARS` in the registry (default 25), applied to classification **and** translation
- [ ] Below the threshold: **no model call**, status `LLM_SKIPPED`, reason logged
- [ ] At or above with an empty result: **not a failure**, warning logged with the length only
- [ ] `is_failed_classification()` unchanged in behaviour — a test asserts an empty-but-valid result
      is still not a failure, so the guardrail cannot drift into treating it as one
- [ ] D-29 fixed: `result` bound before the `try`; no message interpolates `input_data`, any
      description, or any summary — only `grievance_id` plus at most three words
- [ ] `docs/dpg/privacy-assessment.md` leg L4 corrected to four reachable call sites, with the
      unreachable two named and the reason recorded
- [ ] The `phone.py` INFO logs recorded as a Sprint-3 finding — **logged, not fixed** here

### Tests

[`TESTS.md`](TESTS.md) → **T-19-a … T-19-e**.

---

## DPG-19b — Declare the parked paths, and pin the difference {#dpg-19b}

> ✅ **Q-22 answered 2026-08-18, and it reversed this ticket.** *"`transcribe_audio_file`,
> `extract_contact_info`, `extract_all_contact_info` and `translate_grievance_to_english_LLM` are
> functions part of the voice notes flow, which I have not updated in the newest versions as we have
> no budget for the transcription part."*
>
> **The first draft of this ticket proposed deleting three of the four. That was wrong.**
> Reachability analysis found four paths nothing calls, and "unreachable" was read as "legacy".
> They are **one coherent feature, deliberately parked** — and the code corroborates it exactly.

### What the code says, and it is unambiguous

`backend/task_queue/test_tasks.py` still holds the chains this feature is made of:

```
transcribe_audio_file_task (grievance audio) → classify_and_summarize_grievance_task
transcribe_audio_file_task (contact audio)   → extract_contact_info_task
```

**Contact extraction consumes a transcription of spoken contact details.** It was never meant to run
on typed input — which is exactly why the typed path validates phone numbers with a deterministic
slot validator and no model. The switch-off is recorded in the code itself
(`registered_tasks.py:157`): *"CB-01 proto: store audio only; transcription/classification deferred
to officers."*

So the inventory is not *five live and four dead*. It is:

| | Paths | State |
|---|---|---|
| **Live** | classification (`gpt-5-nano`), SEAH detection (`gpt-3.5-turbo`), ticketing ×3 | running |
| **Parked — the voice-notes flow** | ASR, contact extraction ×2, grievance translation | ⏸ complete, switched off for lack of transcription budget (Q-13.2, Q-22) |

⚠ **`translate_grievance_to_english_LLM` belongs to that flow too**, which resolves something DPG-18
§18.0 left as a loose end: it is not that translation was "superseded by ticketing" — it is that
translation was part of the *voice* pipeline, and the typed pipeline never needed it because
ticketing generates the English officers read.

### What this ticket does instead of deleting

1. **Declare the parked set in one place.** A `PARKED_TASKS` registry — task key → the reason and the
   decision that parked it (CB-01, Q-13.2) — living beside the task registry, not in a comment
   someone has to find.
2. **Label them where a reader meets them**: a header on each parked function saying it is voice-flow
   and switched off, not dead.
3. **Fix the documents that count them as live egress** — the half that matters most, because it is
   what a DPG reviewer reads:
   - [`privacy-assessment.md`](../../dpg/privacy-assessment.md) **L4**: **two** live chatbot paths,
     four parked-with-reason. (Corrected twice on 2026-08-18 already: six → four → two.)
   - [`00_compliance_status.md`](../../dpg/00_compliance_status.md): the nine-call-site table gains a
     live/parked column.
   - [`03_voice_grievance_service.md`](../../services/03_voice_grievance_service.md): it claims the
     Whisper path *"remains"*. The **upload** remains; the transcription is parked. ⚠ This spec is
     also now the **best surviving description of the parked flow** — it should say so, because
     whoever unparks it will start there.
   - This spec's §0.3 inventory and `README.md`'s premise table.
4. **Keep every parked path on the registry.** They resolve models through `llm_config.py` like
   everything else, so unparking is a budget decision, not a migration. Their env vars stay in
   `.env.example`; T-16-a stays green.
5. ⚠ **Do not delete their characterization tests.** DPG-10's net is what makes unparking safe, and a
   parked path with no test is how a feature comes back broken. `transcribe_audio_file`'s test is the
   clearest case: DPG-14.3's `language` fix is only provably correct *because* the test exists.

### The pin that earns the ticket

**T-19b-b**: every LLM-calling task must either have a **production enqueue site** or be **declared
parked with a reason**. Nothing else is allowed.

That is the durable fix. Deleting four paths cleans today; a repository that cannot distinguish
*live*, *parked* and *rotted* is what produced a nine-item egress inventory with four phantoms in a
compliance document — and, three weeks earlier, a correction in [`DECISIONS.md` Q-11](DECISIONS.md#q-11)
that told the owner his mental model was wrong when it was right.

### Acceptance

- [ ] `PARKED_TASKS` exists, names all four with their reason and the decision that parked them
- [ ] T-19b-b green: no LLM task is silently unreachable
- [ ] Every document that says "nine call sites" says **five live, four parked**, with the reason
- [ ] `privacy-assessment.md` L4 lists **two** chatbot egress paths
- [ ] `03_voice_grievance_service.md` reads as the parked flow's specification, and says what it costs
      to unpark: an ASR budget, and DPG-22's WER baseline
- [ ] No production code deleted; no characterization test deleted
- [ ] The SEAH triple signal (keyword · nano categories · LLM task) written into
      [`06_llm_service.md`](../../services/06_llm_service.md) — load-bearing for Q-14 and in no spec

### Tests

[`TESTS.md`](TESTS.md) → **T-19b-a … T-19b-b**.

---

## DPG-15b — The wait is already in the right place; raise the budget and make failure terminal {#dpg-15b}

> ✅ **Q-20 answered 2026-08-18** — the owner described the flow and the code confirms it, so the
> premise this ticket was drafted on was wrong and the ticket shrank.
>
> *"I have allocated enough time during the submission flow for the classification to happen in the
> background while the user fills more forms, so that he can review the results of the classification
> by himself."*

### 15b.0 — The flow, verified in the state machine rather than assumed

| # | Step | Where | What happens |
|---|---|---|---|
| 1 | `form_grievance` → `submit_details` | `forms/intake_submit.py:18` | Grievance row written as `pending`; **classification enqueued**. Intake never waits |
| 2 | `form_contact` | `forms/form_contact.py` | Province, district, municipality, village, ward, address, consent, name, email |
| 3 | `form_otp` | `forms/form_otp.py` | Phone, OTP consent, **an SMS round-trip**, OTP input |
| 4 | `action_submit_grievance` | `action_submit_grievance.py:96` | Persists, sends the recap SMS, **dispatches the ticket to ticketing** |
| 5 | **review** | `state_machine.py:392` `_start_grievance_review_after_submit` → `action_retrieve_classification_results` | ⏱ **the 20 s poll**, then the complainant reviews summary + categories |
| 6 | outro | `action_update_grievance_categorization`, `action_grievance_outro` | The complainant's confirmed or corrected classification is written to the grievance row |

The state machine says it in its own docstring: *"Run review after submit"*.

**So the wait is already as late as it can be**, at the end of a flow containing two forms and an SMS
round-trip. Against the measured 14–20.5 s classification, the normal path finishes it long before
step 5. ⚠ **D-30's followup framed this as "the deadline is too short"; it is better described as "the
deadline is a backstop that is rarely reached"** — and the followup has been corrected.

**And the late-update half of the requirement already works, further than credited.** The ticket is
created at step 4 with whatever exists then; `ticketing/tasks/grievance_sync.py` runs **every two
minutes** (`celery_app.py:70`) and back-fills `grievance_summary`, `grievance_categories`,
`grievance_location` and `location_code` whenever they change. So both a late classification **and
the complainant's review edits at step 6** reach the officer automatically, within about two minutes.
Nothing to build; verify it and write it down.

### 15b.1 — ⚠ The exception, and it is the complainant who most needs the flow to work

**Steps 2 and 3 are not always long.** A complainant who declines to share contact details takes a
much shorter path:

- `complainant_consent is False` → `form_otp.required_slots()` returns **`[]`** — the whole OTP form,
  SMS round-trip included, is skipped (`form_otp.py:181-183`)
- `form_contact`'s required slots shrink correspondingly

**The gap between enqueueing the classification and needing its result can then collapse to
seconds** — and the measurement says the classification takes 14–20.5. So the case where the 20 s
poll actually bites is the **anonymous or contact-refusing complainant**: the fast path through the
flow is the privacy-conscious path, and it is the one that shows an empty classification.

That is the argument for the owner's 90 s, and it is a better argument than the average case.

### 15b.2 — ⚠ A longer budget cannot work, and the retry maths says why

Raising the deadline to 90 s makes **D-34 worse**: a failed classification leaves the row at
`pending`, which is not terminal, so the poll runs its full length. A 20-second pause becomes a
ninety-second stall. But fixing D-34 does not rescue a long budget either, because **the two failure
classes resolve on completely different timescales**:

| Failure class | Time to reach `LLM_failed` (max_retries 3, initial_delay 2, backoff ×2) | Observable inside a chat wait? |
|---|---|---|
| **Fast** — connection refused, 400 (e.g. D-40's parameter errors), bad model name | 4 attempts + 2 s + 4 s + 8 s ≈ **14 s** | ✅ yes |
| **Slow** — the model is simply slow, and the call times out | 4 × `TIMEOUT_CLASSIFY` (120 s) + backoff ≈ **8 minutes** | ❌ never |

**Retry-gated terminal marking is therefore incompatible with any chat-time deadline**, at any budget.

And today's numbers are already incoherent in the same way: **the chat waits 20 s while one attempt is
allowed 120 s.** The poll can only ever succeed if the model is fast; on a slow one it gives up six
times over before a single attempt is even due to finish.

✅ **The one thing that is already right:** `load_grievance_for_classification` **short-circuits on
terminal statuses** (`LLM_SKIPPED`, `LLM_failed`, `LLM_error`). The machinery works. The status never
arrives.

### 15b.3 — What ships instead (agreed with the owner, 2026-08-18)

**1. Lower the budget to 30 s, do not raise it.** `CLASSIFICATION_WAIT_SECONDS = 30` — the measured
classification is 14–20.5 s, so this covers the normal case with margin. A longer wait buys nothing,
because **the review runs after submission**: the grievance is filed, the ticket is dispatched, and
the classification reaches the officer through the two-minute sync whether or not the complainant
ever sees it. The only thing a 90 s budget would buy is 90 seconds of silence for the anonymous
complainant (D-41).

**2. The first attempt gets a shorter timeout than the retries.** Someone is waiting on attempt 1;
nobody is waiting on attempt 4:

```python
TIMEOUT_CLASSIFY_INTERACTIVE = 30    # self.request.retries == 0 — a person is watching
TIMEOUT_CLASSIFY             = 120   # retries, in the background
```

Roughly three lines — the timeout is already per-request since DPG-11 — and it makes the wait and the
attempt **coherent**: the chat can now observe the first attempt's outcome instead of always timing
out before it.

**3. End the wait on knowledge, not on the clock.** With (2), a fast failure marks terminal in ~14 s
and the poll exits immediately (the short-circuit already exists). The slow case resolves after the
conversation, which is acceptable because of (4) and (5).

**4. Say something in every branch. The review step must never render blank.**

| State | What the complainant is told |
|---|---|
| ready | the summary and categories, to confirm or correct |
| not ready yet | *"Your grievance is filed. We are still preparing the summary — you will see it when you check your status."* |
| terminal without content | *"Your grievance is filed. An officer will categorise it."* |

**5. Deliver late results rather than waiting for them.** The classification lands in the row anyway
and syncs to the ticket within two minutes. Pushing it to the complainant afterwards — status check
now, an orchestrator `POST /message` later — removes the entire reason to hold a conversation open.
⚠ Precedent exists: the road-hazard fast path already sets `LLM_SKIPPED` and skips the review cleanly
(`intake_submit.py:91`), so "skip the review gracefully" is a path the flow already supports.

**6. `LLM_failed` on the last attempt** (D-34) — still required, and now it is *reachable within the
budget* for the fast class, which is the class that includes every configuration error.

#### What each option actually costs the complainant

| | Today | 90 s + D-34 | **This** |
|---|---|---|---|
| Normal | works | works | works |
| Fast failure | 20 s blank | ~14 s, message | ~14 s, message |
| Slow failure / timeout | 20 s blank | **90 s blank** | 30 s, message, result delivered later |
| Anonymous fast path (D-41) | 20 s blank | 90 s blank | 30 s, message |

### Acceptance

- [ ] `CLASSIFICATION_WAIT_SECONDS` in the registry, default **30**; no literal deadline anywhere
- [ ] `TIMEOUT_CLASSIFY_INTERACTIVE` (30) applies on `self.request.retries == 0`; `TIMEOUT_CLASSIFY`
      (120) on retries — so the wait and one attempt are finally coherent
- [ ] **`LLM_failed` written on the last attempt and verified against the database**, the way DPG-15's
      runs were — reachable *within the budget* for the fast failure class
- [ ] The review step distinguishes *ready* / *not ready yet* / *will not arrive*, and **never renders
      a blank summary** — three messages, per §15b.3
- [ ] ⚠ The **no-contact path measured end to end**: decline contact sharing, drive to the review
      step, and record how long the flow actually takes. This is the case the budget exists for and
      the only one where the number matters
- [ ] The two-minute sync's back-fill of a late classification **and** of the complainant's review
      edits verified in-container with a real late arrival, and written into
      [`11_llm_pipeline_policy.md`](../../deployment/11_llm_pipeline_policy.md) — it is undocumented
      and it is what makes the whole design work
- [ ] The webchat task-status path checked against the new terminal state
- [ ] D-30 and D-34 closed; their followups updated to point here
- [ ] The verified step table above written into
      [`docs/rest_chatbot/`](../../rest_chatbot/) — Q-20 cost an hour of tracing that nobody should
      have to repeat

### Tests

[`TESTS.md`](TESTS.md) → **T-15b-a … T-15b-d**.

---

## Sprint 1 acceptance criteria

> ✅ **Closed 2026-08-18** — eight commits on `dpg/sprint1-llm-agnostic`. The ticked state, with the
> three exceptions spelled out, is in [`PROGRESS.md` §Sprint 1 — definition of done](PROGRESS.md).
> One criterion below is **restated there**: "all seven structured calls use `json_schema`" is not
> achievable against today's models — `gpt-3.5-turbo` rejects schemas and `gpt-4` rejects JSON mode
> outright (measured, D-31). What shipped is the strongest format each model supports, plus the
> ladder that lifts them all when the models change.

The guide's list, corrected for the two-surface reality and made checkable:

- [ ] **One config file.** Every model name, endpoint, timeout, retry count and capability flag is declared
      exactly once, in `backend/config/llm_config.py`; both surfaces read it and neither restates it (T-17-c)
- [ ] No `OpenAI(` instantiation outside `backend/services/llm_client.py` and `ticketing/clients/llm_client.py`
- [ ] No hard-coded model name anywhere — `grep -rn "gpt-\|whisper-1" backend/ ticketing/` is clean outside
      comments and the registry's own defaults, **and a test enforces it** (T-11-d)
- [ ] One `LLM_BASE_URL` change moves **both** surfaces — proven by test, not by inspection (T-17-d)
- [ ] `.env.example`, `.env.open`, `.env.openai` all present and documented
- [ ] All seven structured calls use `json_schema` with Pydantic validation, with a configured degradation ladder
- [ ] Intake completes successfully with `LLM_BASE_URL` pointing at a dead port — **as an automated test**
- [ ] The full test suite passes against both configurations *(the second configuration is DPG-21; until then, against mocks + the current provider)*
- [ ] `docs/services/06_llm_service.md` and `docs/deployment/11_llm_pipeline_policy.md` reconciled with the code
- [ ] Every deferral logged in `followups/` + `TODO.md`, same commit — deviations continue at **D-27**
- [ ] **No increase in the CI failure baseline** (`18 failed, 1166 passed`); `tests/repo` green throughout
- [ ] Every new `.py` file carries an SPDX header, verified by `scripts/ops/add_spdx_headers.py --check`
- [ ] **`docs/dpg/privacy-assessment.md` §2.2 legs L4 and L5 re-pointed** at the moved call sites, and
      `docs/dpg/dependency-licenses.md` reconciled with the `pydantic-settings` move
