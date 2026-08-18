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
