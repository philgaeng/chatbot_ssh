# Test ledger — DPG compliance & LLM independence

> **These are acceptance criteria, not suggestions.** Every ticket ships with its tests in the same commit
> ([`README.md`](README.md) → Conventions).
> Standard: [`docs/engineering/04_testing.md`](../../engineering/04_testing.md) — the pyramid, markers,
> fixtures, what CI runs, and what "pinned" means. Read it before writing the first test.
> Tracker: [`PROGRESS.md`](PROGRESS.md)

---

## The two rules that govern this ledger

**1. A test that cannot go red is not a test.** Every entry below has a **mutation check**: the specific
change to production code that must turn it red. Run the mutation, watch it fail, revert. If it stays
green, the test is decorative — this project has been bitten by exactly that
(`test_the_fixture_really_is_encrypted`, and the boundary test that pinned the code against a dict inside
itself). Record the mutation you ran in the commit message.

**2. No new quarantine.** T3 ended the `@integration` quarantine and grew CI from 364 to 897 tests. The
`live_llm` marker introduced here is deselected in `backend-tests` **and selected in
`dpg-platform-independence`** — it runs on every commit, in a different job. A marker that nothing runs
is a quarantine with better branding.

---

## Where these tests live

| Path | Contents | Runs in |
|---|---|---|
| `tests/backend/test_llm_services.py` | T-10-a…f, T-11-a…c, T-13, T-14, T-15 (chatbot surface) | `backend-tests` (mocked) |
| `tests/ticketing/test_llm_client.py` | T-10 (ticketing surface), T-12 | `backend-tests` (mocked) |
| `tests/repo/test_spdx_headers.py` | T-01 — the licence-header walker | `backend-tests` |
| `tests/repo/test_licence_scan.py` | T-02-a…c — the licence classifier | `backend-tests` |
| `tests/repo/test_image_pins.py` | T-02-d…e — container pin drift | `backend-tests` |
| `tests/repo/` **(new dir)** | **Where repo-wide pins go.** ⚠ Added to `ci.yml`'s explicit pytest path list in the same commit — that step names its directories, so an unnamed one never runs. T-11-d and T-16-a belong here too, not under `tests/backend/` | `backend-tests` |
| `tests/backend/test_llm_config.py` | T-17-a…d — the shared registry, both surfaces | `backend-tests` |
| `tests/backend/test_llm_config_pins.py` | T-11-d, T-16-a, T-17-b…c — the grep/drift pins | `backend-tests` |
| `tests/backend/test_benchmark_set.py` | T-20-a…j | `backend-tests` |
| `tests/backend/test_llm_smoke.py` | T-21-a…g | `backend-tests` |
| `tests/backend/test_llm_benchmark.py` | T-23-a…m | `backend-tests` |
| `tests/repo/test_ci_llm_job.py` | T-24-c…k | `backend-tests` |
| `tests/backend/test_llm_live.py`, `tests/ticketing/test_ticketing_llm_live.py` | T-24-a…b | **`dpg-platform-independence`** (live) |
| `tests/backend/test_pii_service.py` | T-31-a…e, T-33, T-34 | `backend-tests` |
| `tests/data/benchmark/` | DPG-20 fixtures (data, not tests) | — |
| marked `@pytest.mark.live_llm` | T-24-a…b — real round-trips against the open config | `dpg-platform-independence` only |

---

## Sprint 0

### DPG-01 — the licence-header pin

| ID | Test | Mutation check |
|---|---|---|
| **T-01** ✅ | Every in-scope source file carries `SPDX-License-Identifier: Apache-2.0` — **585 files** (583 at DPG-01; +2 from DPG-02 and the reference pin). Scope is **imported from `scripts/ops/add_spdx_headers.py`**, not restated, so the pin and the fixer cannot disagree. Also pins: header below any shebang; migrations keep their `Safe to run` header (SPDX above it); `LICENSE` is the canonical 202-line text; `NOTICE` discloses an unresolved holder rather than leaving the template placeholder silent; both files are tracked | ✅ **Checked twice.** Delete a header → red, and `add_spdx_headers.py` restores it byte-identically. Append a newline to `LICENSE` → red |

### DPG-02 — the licence scan stays true

| ID | Test | Mutation check |
|---|---|---|
| **T-02-a** | `classify_licence` puts permissive licences at `info`, weak copyleft (LGPL/MPL) at `warn`, and **anything unrecognised, absent or non-OSI at `high`** — strings taken from this repo's own resolved tree, not invented | Add `GPL` to the OSI allowlist → red |
| **T-02-b** | ⚠ **The regression pin.** `"Proprietary Limited License"` must not classify as OSI-approved. It contains the substring `MIT`, and the first implementation used `token in text` | Revert `matches()` to substring matching → red *(checked)* |
| **T-02-c** | `UNLICENSED` (npm: no licence declared) and `Unlicense` (public-domain grant) classify oppositely | Merge the two → red |
| **T-02-d** | Every container image is pinned to ≥ MAJOR.MINOR, or carries a written licence-stability reason in `ACCEPTED_LOOSE_PINS` | Restore `redis:7` → red *(checked, 3 tests)* |
| **T-02-e** | Compose and CI declare the **same** image for redis and postgres | Bump one and not the other → red |

**Why T-02-b is the one that matters.** A licence scan that silently passes a proprietary dependency
does not merely fail to help — it manufactures confidence, and the nightly job would report a clean
tree forever. That is worse than having no scan.

**Why the one test in Sprint 0 earns its place:** indicator-2 evidence decays silently. Without this,
coverage lapses the first week someone adds a module and nobody learns until a reviewer greps.

### Cross-cutting — the documentation reference pin

| ID | Test | Mutation check |
|---|---|---|
| **T-03-a** ✅ | Every `file.py:NNN` citation in the **live** docs (`archive/` excluded) resolves to a file **git knows about**. Deliberately-removed files need an entry in `KNOWN_ABSENT` **with the reason**, and a second test fails if one comes back | Add a citation to a nonexistent file → red *(checked)*; re-add and track a `KNOWN_ABSENT` file → red *(checked)* |
| **T-03-b** ✅ | Every cited line is within the file it names — catches truncation | Cite line 99999 of `LLM_services.py` → red *(checked)* |
| **T-03-c** ✅ | ⚠ **The one that catches a *shift*.** 20 load-bearing citations — the nine model call sites, the four duplicated-model sites, and the privacy assessment's encryption/hash/decrypt/SEAH anchors — must land on a line containing an expected token | Move any anchor by **one line** → red *(checked)* |

⚠ **Index from git, not from the filesystem — this bit within a minute of landing.** The first version
walked `rglob("*.py")`, which picked up **agent worktrees under `.claude/`**: whole gitignored copies of
the repository at older commits. Four genuinely dangling `tickets.py` citations (H2-02 split it into a
package) resolved against a ghost, so the test **passed locally and failed in CI** — the one environment
difference that matters, found the only way it could be. It now reads `git ls-files`, which is exactly
what CI checks out.

**Why this exists, and what it does not do.** Sprint 0's SPDX pass shifted every source line by +2 and
with it ~80 citations across the specs and the evidence pack. One stale number was then *copied into*
`docs/dpg/privacy-assessment.md` — the document whose entire claim is that each leg was verified at the
line cited. **A citation that names a line is a claim about that line.**

⚠ **T-03-a and T-03-b are a floor, not a guarantee**: a reference that moved but stayed in range and is
not in `ANCHORS` still passes silently. Only T-03-c catches drift, and only for the 20 it names. Widening
`ANCHORS` is cheap — do it when a citation becomes load-bearing.

⚠ **Sprint 1 will turn T-03-c red on purpose.** DPG-11/12 move all nine call sites out of
`LLM_services.py`. That red is the reminder that the citing documents move in the same commit —
the discipline `privacy-assessment.md` §2.2 needs, and would otherwise only get from DPG-30 months later.
**Fixing `ANCHORS` alone, without re-pointing the docs, is the failure this test exists to prevent**; the
assertion message says so and gives the grep.

⚠ **The other Sprint 0 tickets have no tests, deliberately.** DPG-02/03/04 are documents; DPG-05 (hygiene
files) and DPG-06 (the root README) are documents too. DPG-06's real check — *no claim in `README.md` that a
grep of the compose files contradicts* — is **manual, and must run before the consultant meeting**. The
existing `docs-links` CI gate catches link rot, not false claims. If that check is ever automated, it lands
here as T-06.

---

## Sprint 1

### DPG-10 — the net (must pass on **unmodified** code)

| ID | Test | Mutation check |
|---|---|---|
| **T-10-a** ✅ | Each of the 9 call sites sends the expected model name and `response_format` to a mocked client | ✅ **Checked** — `gpt-5-nano`→`gpt-4o-mini` → red; collapsing `_MODEL_SEAH` onto `_MODEL_STANDARD` → red (2 tests) |
| **T-10-b** ✅ | Each call site's **happy-path parse**: realistic provider response in, documented dict out | ✅ Covered by exact-dict assertions, so a dropped *or added* key is red |
| **T-10-c** ✅ | Each call site's **failure contract** — raise / sentinel dict / `None`, per the table in [`02`](02-llm-agnostic-spec.md#dpg-10). Nine functions, three different idioms; pinned as they are. ⚠ **Two of them are not the documented contract**: `extract_contact_info` and `translate_grievance_to_english_LLM` raise `UnboundLocalError` on any pre-call failure (D-28, D-29) | ✅ **Checked** — `return None` → `return {}` in `generate_case_findings` → red |
| **T-10-d** ✅ | `client is None` guard, per function (module client is `None` when the key is unset). ⚠ Includes the pin that **classification ignores it entirely** — it builds its own client, so an unkeyed deployment still calls the provider there | ✅ **Checked** — removed translation's guard → red |
| **T-10-e** ✅ | `parse_llm_response`: valid JSON · the `"{}"` sentinel → localized "not enough information" · malformed JSON → `{}` · all four language codes **plus an unknown one** · and that the sentinel branch is grievance-only | ✅ **Checked** — changed the `en` fallback string → red |
| **T-10-f** ✅ | `detect_sensitive_content_llm` clamps an out-of-range `level` to `"low"` (4 cases, incl. the correct-word-wrong-case `"HIGH"`), and coerces a non-string `message` | ✅ **Checked** — removed the clamp → red (4 tests) |

⚠ **T-10-a must patch `backend.services.LLM_services.OpenAI` (the class), not the module-level `client`.**
`classify_and_summarize_grievance` builds its own client at `:199`; patching only the module attribute
misses the product's primary AI path.

### DPG-17 — one config file

| ID | Test | Mutation check |
|---|---|---|
| **T-17-a** ✅ | All eight task keys resolve to today's models by default, and each honours its documented `MODEL_*` override; `ticket_translate` falls back to `translate` when unset. **Also pins the timeouts** (SDK default / 120 s classify / 30 s ticketing), the ASR endpoint's per-field fallback, that an unknown task key names the known ones, and that an invalid `LLM_STRUCTURED_OUTPUT` fails at load rather than degrading silently. 30 assertions | ✅ **Checked** — changed a default model → red; pointed `ticket_findings_seah` at the standard model → red (3 tests) |
| **T-17-b** ✅ | **Portability pin.** `backend/config/llm_config.py` imports nothing **first-party** — no `backend.*`, `ticketing.*`, `ops.*`, `channels.*`, `scripts.*`, and no relative import (AST-parsed, not grepped). Second assertion is the stronger form: the file is **copied to a tmp dir and imported with the repo off `sys.path`** | ✅ **Checked** — added `from backend.config.constants import ...` → red (both tests) |
| **T-17-c** ✅ | **The single-source pin.** No model literal in `backend/` or `ticketing/` outside `llm_config.py` (AST-parsed, docstrings exempt), and `findings_task()` is the only SEAH model selection — checked as **both** a literal ternary *and* any reference to the retired `_MODEL_*` constants, because the fourth copy contained no model name at all. ⚠ The is_seah-ternary half is deliberately narrow (only model-looking literals): `is_seah` ternaries are ordinary here, and a noisy pin gets deleted | ✅ **Checked** — restored `_MODEL_STANDARD` in `resolved_summary_builder.py` → red (2 tests) |
| **T-17-d** ✅ | **The drift pin.** One `LLM_BASE_URL` / `LLM_API_KEY` change moves **both** factories — both are constructed in one test and asserted onto the same endpoint and key. Lives in `tests/ticketing/test_llm_client.py`, where both can be built without a circular import | ✅ **Checked** — hard-coded the ticketing factory's base URL → red |

**T-17-d is the test that makes "two factories, one config" enforceable.** T-11-d stops a *new* hard-coded
model; T-17-d stops the subtler failure — two registries that both read env, drift apart, and leave the
complainant-facing output on a closed model while the repo advertises an open one.

⚠ **T-17-c must cover `ticketing/services/resolved_summary_builder.py` and `ticketing/tasks/llm.py`**, not
just the two client modules. Those two files are where the duplication already happened, and `:299` writes
its copy into a **persisted** provenance field.

### DPG-11 / DPG-12 — the factories

| ID | Test | Mutation check |
|---|---|---|
| **T-11-a** ✅ | `get_llm_client()` honours `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`; is built **lazily and once**; and **refuses to build a keyless client** — no key means no client, which is what keeps each call site's documented fallback reachable | ✅ **Checked** — hard-coded the base URL → red (2 tests) |
| **T-11-b** ✅ | `get_asr_client()` is independent — a different `ASR_BASE_URL`, key and timeout produce a different client, and moving one does not move the other | ✅ **Checked** — pointed ASR at the chat endpoint → red |
| **T-11-c** ✅ | The model registry resolves per task and each is overridable by env — **landed with DPG-17** as `tests/backend/test_llm_config.py` (T-17-a, 16 of its 30 assertions), because the registry is where that behaviour now lives. Restating it against the factory would test the same code twice | ✅ **Checked** — see T-17-a |
| **T-11-d** ◐ | **The pin.** No `OpenAI(` outside the two client modules; no `gpt-`/`whisper-1` literal outside the registry — **AST-parsed, with docstrings exempt** (documentation naming the current default is useful; an executable literal is not). ⚠ Scoped to `backend/` on arrival and **widened to `ticketing/` by DPG-12**, in the commit that removes that surface's literals: a pin that is red on the day it lands teaches the next reader that red is normal here | ✅ **Checked** — `model="gpt-4o"` re-introduced → red; shadow client re-introduced → red |
| **T-12-a** ✅ | ⚠ **The ticket changed this test's premise, correctly.** `TicketingSettings` exposes **nothing** LLM-related — a second settings object is the drift this sprint removes. `_get_client()` builds from the **shared** registry's `llm_endpoint()`: base URL, key, timeout and retries | ✅ **Checked** — hard-coded `base_url` in the ticketing factory → red (2 tests) |
| **T-12-b** ✅ ⏳ | The standard/SEAH model split survives as **two registry keys**, resolved by `findings_task(is_seah)`. ⏳ **Changing under Q-21:** with one text model the two keys resolve to the same *value*, so the assertion moves from *"they resolve to different models"* to *"they are independently overridable"* — the split survives as **configuration**, which is what makes DPG-23 able to re-open it without a code change | ✅ **Checked** — made `findings_task()` always return `ticket_findings` → red (2 tests) |
| **T-12-c** ✅ | A config with only the deprecated `OPENAI_API_KEY` set **warns and still authenticates — on both endpoints**, because a key that authenticates chat but not ASR fails as what looks like a model problem. Warns **once per alias, not once per resolution**, and never logs the key's value. Landed with DPG-17, where the alias handling lives | ✅ **Checked** — removed the warning call → red |

**T-11-d is the test that keeps the indicator-4 claim true after this sprint ends.** Without it, the
next feature adds a hard-coded model and nobody notices until a DPG reviewer does.

### DPG-13 — structured output

| ID | Test | Mutation check |
|---|---|---|
| **T-13-a** ✅ | Each of the 7 JSON call sites sends the strongest format **its model actually supports** — pinned as a measured table (`gpt-3.5-turbo` 400s on schema; `gpt-4` 400s on both), not as an assumption | ✅ **Checked** — reverted the findings site to `json_object` → red (2 tests) |
| **T-13-b** ✅ | Validated through its Pydantic model on both surfaces; a schema-violating reply is rejected, not silently accepted — `grievance_categories` as a string, `urgency: "URGENT"`, a list where complainant-facing prose belongs | ✅ **Checked** — swapped `model_validate` for `json.loads` → red, and the warning log printed `['D','u','s','t',…]`, which is the defect itself |
| **T-13-c** ✅ | The ladder: the endpoint ceiling clamps every task down at once; a task capability can be lifted alone; the `prompt` rung sends **no `response_format` key at all** (not `None` — the SDK serialises that into the body); the schema is made strict before sending; the rung is logged | ✅ **Checked** — made `model_for` ignore the task capability → red (3 tests) |
| **T-13-d** ✅ | **The silent-failure fix**: `"{}"` (the model saying *not enough information*) and `"{not json"` (the model failing) now produce different results on the classification path — the localized fallback vs `status="error"`. The log carries a **length, not the narrative**. ⚠ Honest limit, stated in the test: on `extract_all_contact_info` the *return value* is the same as an outage; only the log distinguishes them | ✅ **Checked** — restored `except JSONDecodeError: return {}` → red (3 tests) |
| **T-13-e** ✅ | Category values are checked against the catalogue built from `CLASSIFICATION_DATA` **at call time**; adding one to the catalogue needs no code change; unlisted values are **logged, not discarded**; and the schema declares no enum | ✅ **Checked** — froze a `Literal[...]` of two categories → red (3 tests) |

### DPG-14 — the defects

| ID | Test | Mutation check |
|---|---|---|
| **T-14-a** ✅ | Classification returns a populated result on a valid response, **and** the `status="error"` contract on an exception — so a model-name failure is distinguishable from an empty classification. Covered by DPG-10's pair (`…returns_the_four_documented_keys` / `…returns_a_status_error_dict_when_the_call_fails`) | ✅ Covered — the error-dict test asserts on `status` and the exception text, so swallowing the exception is red |
| **T-14-b** ⏳ **DPG-11** | Only **one** client is constructed on the classification path (no shadow). Cannot be written before the factory exists — today's code builds two by design, and DPG-10 pins that it does (`test_classify_ignores_the_module_client_entirely`) | Re-introduce the inner `OpenAI(...)` → red |
| **T-14-c** ✅ | ⚠ **Confirmed in-container** (`openai==1.70.0`: `['self','file','model','include','language',…]`, no `**kwargs`) and written. The test binds the request the code actually sends against the **installed SDK signature** — a mock accepts any keyword, so a mock-only assertion could not catch this | ✅ **Checked** — renamed the kwarg back to `language_code` → red (2 tests) |

### DPG-15 — degraded mode

| ID | Test | Mutation check |
|---|---|---|
| **T-15-a** ◐ | **The sprint's headline criterion.** With `LLM_BASE_URL` on a dead port (127.0.0.1:9 — a **real** connection failure, not a mock) the classification path returns its error contract and the grievance row survives. Two more assertions came out of the in-container run: a failed classification is *recognised* as a failure by the task layer (D-32), and an empty extraction is never written over stored contact details (D-33). ⚠ **Honest limit:** the status is `pending`, not terminal — `LLM_failed` is unreachable until D-34 is fixed, and the ledger's word "terminal" is therefore not yet satisfied | ✅ **Checked** — made the failure dict count as success again → red |
| **T-15-b** ✅ | `/health/llm` reports reachability and the base-URL **host**; the response contains no API key, and it returns **200 even when degraded** — a non-200 invites the healthcheck wiring T-15-c forbids | ✅ **Checked** — added the key to the response → red |
| **T-15-c** ✅ | `/health` stays green while `/health/llm` is red — **and the compose files are read** to assert no container healthcheck probes the LLM. The rule is not "the probe returns 200", it is "nothing restarts the chatbot when the provider is down", and that lives in compose | ✅ **Checked** — pointed a healthcheck at `/health/llm` → red |

### DPG-18 — the call layer (second wave)

| ID | Test | Mutation check |
|---|---|---|
| **T-18-a** ✅ | `call_llm()` is the **only** thing that builds a chat request — AST-parsed. ⚠ ASR is exempt **and named**: `audio.transcriptions.create` is a different API surface (multipart, no messages) | ✅ **Checked** — built a request at a call site → red |
| **T-18-b** ✅ | The `prompt` rung's instruction is **generated from the Pydantic schema** and names every declared field; the call site's own system prompt survives, and one is added when there is none | ✅ **Checked** — hand-wrote the fallback text → red |
| **T-18-c** ✅ | `parse_response()` handles a bare object and the ```` ```json ```` fenced form providers without JSON mode produce; anything else is a **typed** error, never a silent `{}`. ⚠ **And the error carries the shape of the failure, never the reply** — pydantic embeds `input_value=…`, which is grievance-derived | ✅ **Checked** — the leak assertion was added *because* the first message carried the body |
| **T-18-d** ✅ | One task key change moves the model for every call site that uses it — the consolidation of §18.2 is a config edit and this proves it | ✅ Covered with T-17-d |
| **T-18-e** ✅ | ⭐ **The profile pin (D-40).** `gpt-5*` → no `temperature`, `max_completion_tokens`, **+4,000 reasoning budget**; `gpt-4o*` and `gpt-3.5*` → `temperature` and `max_tokens`; an unknown open-weights id → the conservative default. Four models, one parametrized test | ✅ **Checked** — temperature allowed for `gpt-5` → red; reasoning overhead dropped → red |
| **T-18-f** ✅ | ⭐ **`finish_reason == "length"` is a failure, not an empty answer** — refused even when the truncated body happens to parse | ✅ **Checked** — parsed a truncated reply as empty → red |

### DPG-19 — meaningful input (second wave)

| ID | Test | Mutation check |
|---|---|---|
| **T-19-a** ✅ | Below `MIN_CLASSIFY_CHARS`, **no model call is made** — asserted on a mocked client that must not be touched, and the result carries `skipped: "too_short"` with no `status` key | ✅ **Checked** — bypassed the gate → red (2 tests) |
| **T-19-b** ✅ | ⭐ **The owner's point, pinned.** At or above the threshold, an empty-but-valid result (`"{}"`) is **not** a failure: the localized response, `is_failed_classification()` False, and a warning carrying the **length only**, never the narrative | ✅ **Checked** — made an empty result count as a failure → red. *This is the regression the guardrail could have introduced, and the test was written before the guardrail* |
| **T-19-c** ✅ | The threshold is measured on **whitespace-stripped** length and is a registry value — 40 spaces is below it, a 25-character Devanagari sentence is above it, and `MIN_CLASSIFY_CHARS=500` puts everything below | ✅ **Checked** — counted raw `len()` → red |
| **T-19-d** ✅ | The translation error message contains the `grievance_id`, **at most three words** of the description (the fourth word is asserted absent), and **never** the summary or `input_data` | ✅ **Checked** — restored the `input_data` interpolation → red |
| **T-19-e** ✅ | D-29's underlying bug: a pre-call failure raises the declared `ValueError`, not `UnboundLocalError`. ⚠ **The first version of this test could not go red** — see **D-42**. The fix is the bounded *message*, not a binding; the binding was dead code and was deleted | ✅ **Checked with the honest mutation** — restore the old message that interpolates `result` → red (2 tests). *The original mutation (delete the binding) left it green, which is how the dead code was found* |

### DPG-19b — the dead paths, deleted (second wave)

| ID | Test | Mutation check |
|---|---|---|
| **T-19b-a** ✅ | `PARKED_TASKS` names each parked path with a reason, every name in it is a real LLM task, and the parked set is **exactly the voice flow** — so parking the live classification or SEAH task fails loudly rather than quietly stopping the product | ✅ **Checked** — a one-word reason → red; the live classification task parked → red |
| **T-19b-b** ✅ | ⭐ **The reachability pin.** Every task decorated `register_task(task_type='LLM')` (found by AST) is either **enqueued in production** — `.delay` / `.apply_async` / `.s(`, with `test_tasks.py` explicitly excluded — **or declared in `PARKED_TASKS` with a reason** | ✅ **Checked** — removed a parked declaration → red (3 tests) |

⚠ **T-19b-b is the general fix, and the distinction it enforces is the whole point.** *Live*,
*parked* and *rotted* look identical to a grep — which is how a nine-item egress inventory ended up
with four phantoms in a **compliance document**, and how a correction in `DECISIONS.md` Q-11 told the
owner his mental model was wrong when it was right. A path that is parked **and says so** is
documentation. A path that is unreachable and silent is a liability. The pin costs ten lines.

### DPG-15b — the classification checkpoint (second wave)

| ID | Test | Mutation check |
|---|---|---|
| **T-15b-a** ✅ | The deadline is `CLASSIFICATION_WAIT_SECONDS` (30) from the registry and the poll **actually uses it** — driven with a never-ready row and a 1 s budget, because the first version only checked that the registry *returned* 30 and stayed green when the deadline was hard-coded. First attempt 30 s, retries 120 s | ✅ **Checked** — deadline hard-coded → red; attempt 1 given the background timeout → red |
| **T-15b-b** ✅ | The poll **stops on the first read** once the status is terminal, rather than running the budget — the property that made raising the wait safe, and useless until D-34 was fixed | ✅ **Checked** — removed the terminal short-circuit → red |
| **T-15b-c** ✅ | The review step says something in **every** branch — ready / not ready yet / will not arrive, in both languages, with the *not ready* message confirming the grievance is filed before it mentions the summary. ⚠ The late-update path it originally pinned **already existed**: `grievance_sync` back-fills summary, categories and location every two minutes (Q-20), so it is documented in `02_flow_spec.md` rather than rebuilt | ✅ **Checked** — silenced the pending branch → red |
| **T-15b-d** ✅ | ⭐ `LLM_failed` is written once retries are spent — **verified against the real database**: the row reaches it and the poll then returns in 0.19 s. Also pins the two traps found in fixing it: the terminal decision is made **before** `self.retry()` (which re-raises the original exception, so `except MaxRetriesExceededError` never fires — **D-46**), and the countdown is explicit (**D-45** — the configured ladder was never applied). ⚠ Source-inspected with comments stripped, or the warning about the trap trips the check | ✅ **Checked** — restored the retry-gated write → red |

⚠ **T-19-b is the one to write first.** DPG-19 exists because an empty summary might wrongly be
treated as a failure; the cheapest way to introduce exactly that bug is to build the guardrail
carelessly. The test that fails if it happens should exist before the guardrail does.

### DPG-16 — env drift

| ID | Test | Mutation check |
|---|---|---|
| **T-16-a** ✅ | Every name in DPG-17's `declared_env_vars()` appears in `.env.example`, and `.env.example` declares nothing the registry does not read — compared programmatically, not eyeballed. **Plus two the ledger did not ask for**: `.env.open` and `.env.openai` declare **identical variables** (differ only in values, or the reviewer's diff stops meaning what it claims), and neither carries a secret — these files are *tracked*, and `env.local` holds a live key | ✅ **Checked** — added an undocumented read → red; left a stale variable in the template → red; pasted `hf_…` into `.env.open` → red |

---

## Sprint 2

| ID | Test | Mutation check |
|---|---|---|
| **T-20-a** ✅ | Every benchmark item is **above** `MIN_CLASSIFY_CHARS` — asserted through `is_too_short_to_process`, not against the literal 25, so it survives the floor moving (which the registry is designed to allow, per language) | ✅ **Checked** — moved a gate fixture into the benchmark file → red |
| **T-20-b** ✅ | The gate fixtures straddle the floor in **both** directions, and `gate-06` pins that the gate counts **stripped length**, not non-whitespace characters — 25 characters, 13 non-whitespace, **not** skipped. ⚠ This test exists because `llm_config.py`, `.env.open`, `.env.openai` and `.env.example` all said *"non-whitespace characters"*; all four were corrected in the same commit | ✅ **Checked** — reimplemented the gate as a non-whitespace count → red |
| **T-20-c** ✅ | Every gold **and** acceptable label exists in the **live** taxonomy (`LIST_OF_CATEGORIES`, DB when seeded, CSV otherwise) — never a copy of the list inside the test | ✅ **Checked** — invented a plausible category → red |
| **T-20-d** ✅ | ⭐ Severity comes from the taxonomy's **authored** `high_priority` (the CSV's final field, read positionally) combined with production's own any-category rule — not from the author's intuition. **This is the test that found D-49**, and it caught seven of my own labels following the broken production value | ✅ **Checked** — it failed on first run against real data; 7 items corrected |
| **T-20-e** ✅ | A **canary**: the four categories D-49 clears are still cleared. Fixing the loader turns this red, which is the point — the record gets closed with the fix instead of outliving it | ✅ **Checked** — fixed the CSV parser **with the database path forced** → red. ⚠ Patching the parser alone does **nothing** while the DB is reachable: the taxonomy loads from Postgres, and the seeded copy carries the same four disagreements — which is how the mutation check proved half of D-49 |
| **T-20-f** ✅ | Every PII span resolves to **exactly one** occurrence of its substring. Spans are substrings rather than offsets so an ambiguous or stale span fails the build instead of yielding a silently wrong offset | ✅ **Checked** — duplicated a name inside its item → red |
| **T-20-g** ✅ | The hard cases are present and cannot be edited away silently: `devanagari_digits`, `mixed_digits`, `third_party_name`, `code_switching`, and **at least one phone number in Devanagari digits** — the case a redactor matching `\d` passes without and then fails on in production (serves **T-31-a**) | ✅ **Checked** — removed the Devanagari-digit phone → red |
| **T-20-h** ✅ | No committed item is marked `sensitive`, and ≥5 `seah_confusable` negatives are present — the owner's 2026-08-19 decision held by a test rather than by memory, in both directions: the SEAH narratives stay out, the false-alarm controls stay in | ✅ **Checked** — flagged one item sensitive → red |
| **T-20-i** ✅ | The README's stated counts, shortest-item length and single uncovered category match the data. A benchmark README with a stale cell is worse than none | ✅ **Checked** — added an item without touching the README → red |
| **T-20-j** ✅ | `@integration` — **no committed item is byte-identical to a stored grievance.** Provenance is a claim no test can check; this checks the thing that would falsify it in the obvious way, against the seeded database | ✅ **Checked** — planted a real stored `grievance_description` into the set → red. Also confirmed **not vacuous**: the table holds 289 descriptions, so an empty-set pass is not what makes it green |
| **T-21-a** ✅ | ⭐ **A 402/401/429/5xx/timeout is `blocked`, never `refused`** — six message shapes, each asserted. The account saying no is not a measurement, and rendering it as one is D-50 | ✅ **Checked** — classified 402 as a refusal → red |
| **T-21-b** ✅ | A **400 on a parameter** stays `refused`, because that IS the measurement DPG-13's ladder is built from (`gpt-3.5-turbo` 400s on `json_schema`, `gpt-4` on both) | ✅ **Checked** — swept 400s into `blocked` → red |
| **T-21-c** ✅ | ⭐ **A report with any blocked cell emits NO `ModelProfile`.** `_PROFILES` decides the strictest rung a model is ever asked for, in the code path that runs; a row derived from a 402 is permanent pessimism on evidence that measured nothing, and looks identical to a measured row | ✅ **Checked** — emitted a tuple for a blocked model → red |
| **T-21-d** ✅ | The rung **degrades, never guesses upward**: `json_schema` refused + `json_object` accepted ⇒ `json_object`; both refused ⇒ `prompt` | ✅ **Checked** — returned the stronger rung → red |
| **T-21-e** ✅ | The matrix renders **three** states (`✅` / `❌` / `⚠ blocked`), not two. A blocked cell shown as ❌ is the defect itself | ✅ **Checked** — collapsed to two states → red |
| **T-21-f** ✅ | ⭐ **Accepted-and-ignored is not a pass.** The probe schema requires a `district` field the prompt never mentions, so a provider that silently drops `response_format` returns 200 with plausible JSON and no `district`. Downgraded to the rung that was actually honoured | ✅ **Checked** — accepted any parseable JSON → red |
| **T-21-g** ✅ | The candidate shortlist loads, every shortlisted model states **why**, every excluded one states **a licence and a reason**, and nothing is in both lists — so a loosened Q-04-02 is a data edit rather than a re-design | ✅ **Checked** — removed a reason → red |
| **T-23-a** ✅ | Raw taxonomy strings fold to the canonical key — including the case a blanket replace destroys: a hyphen **inside** the name (`Gender-Based Access Issues`) beside the `" - "` separator. Grading raw strings against canonical keys deflates every score and reads as a Nepali-quality problem | ✅ **Checked** — replaced hyphens before splitting → red |
| **T-23-b** ✅ | Normalisation is **idempotent**, and **every gold label in the committed set is a fixed point of it** — the end-to-end pin, since a fold that stops producing real labels scores every candidate near zero | ✅ **Checked, and one half honestly does not check out.** The **fixed-point** assertion is mutation-killed — a blanket hyphen replace turns 5 tests red. The **idempotence** assertion survived every mutation I tried (blanket replace, an appending fold), because the leading `.strip()` makes the property structural rather than earned. ⚠ Recorded rather than quietly counted: it is a **regression guard** against someone removing that `.strip()`, not an independent check, and claiming a kill I did not get is how a ledger stops meaning anything |
| **T-23-c** ✅ | Classification is scored **set-level**: a correct two-label answer scores 1.0, a subset is partially credited and is **not** an exact-set match | ✅ **Checked** — scored first-label-only → red |
| **T-23-d** ✅ | ⭐ An **acceptable alternate is neither rewarded nor penalised** — not a false positive, and it does not dilute precision. Counting it would rank models by how narrowly they answer, punishing exactly the behaviour `grievance_categories_alternative` exists to produce | ✅ **Checked** — counted alternates as FPs → red |
| **T-23-e** ✅ | An **invented** category IS a false positive. Not hypothetical — `gpt-5-nano` returned `Road Hazard - Dust` on every dust item in the first sample (**D-51**) | ✅ **Checked** — ignored unlisted categories → red |
| **T-23-f** ✅ | A **blocked** item (402/401) enters neither numerator nor denominator, and the smaller remaining sample is reported | ✅ **Checked** — scored blocked items → red |
| **T-23-g** ✅ | Detection reports a **confusion matrix**, never one number — a miss and a false alarm have different costs and one figure hides that | ✅ **Checked** — returned accuracy only → red |
| **T-23-h** ✅ | ⭐ **Recall over a set with no positives is `None`, never `0.0`**, and carries a note saying why. The committed set is exactly that shape, and a `0.0` would say the model missed everything | ✅ **Checked** — defaulted recall to 0.0 → red |
| **T-23-i** ✅ | The committed set declares **no positive scenarios** — §0.2 pinned from the scoring side, so breaking the split fails here too | ✅ **Checked** — marked one item sensitive → red |
| **T-23-j** ✅ | Latency reports the **fraction over 30 / 45 / 60 s**, not just percentiles — the owner made the budget a knob, and a recommendation to move it is only actionable with the fraction who would wait that long | ✅ **Checked** — reported p95 alone → red |
| **T-23-k** ✅ | The estimate prices the **real** prompt, catalogue included — cost here scales with the taxonomy, not the grievance (the catalogue is injected twice, ~20,700 chars) | ✅ **Checked** — priced grievance text only → red |
| **T-23-l** ✅ | ⭐ A `--seah-set` path **inside the repository is refused**. A path inside the repo means somebody is about to commit harassment narratives | ✅ **Checked** — accepted an in-repo path → red |
| **T-23-m** ✅ | The meter reports the **reasoning share**, and an unpriced run says so rather than reporting zero dollars | ✅ **Checked** — reported 0.0 for an unpriced run → red |
> ⭐ **T-24-a and T-24-b were RUN, 2026-08-20** — not merely written. Against `openai/gpt-oss-20b` on Hugging Face Inference Providers, both surfaces, the product's own call paths: **4 passed, 1 xfailed, exit 0**. The xfail is the transcription round-trip, because the open ASR endpoint 404s (**D-53**), and it is `strict=True` so it reddens the day someone fixes that. ⚠ They have still never run **in CI** — that needs `HF_TOKEN` and the `DPG_MODEL_*` repo variables, which is the one step nobody in this repository can take.

| **T-24-a** | `@live_llm` — a real chat round-trip against the configured open endpoint returns a parseable structured result | Point at an invalid model → red |
| **T-24-b** | `@live_llm` — a real transcription round-trip against the configured open ASR endpoint | Same |
| **T-24-c** | The `live_llm` marker is **deselected** by `backend-tests` and **selected** by `dpg-platform-independence`. Assert on the config, so the "runs nowhere" quarantine cannot re-form silently | Remove the marker from the DPG job's selection → red |
| **T-24-d** | The DPG job **skips cleanly** (not fails) when `HF_TOKEN` is absent — fork PRs must not show a red X on a public-good repo | Make the absent-secret path fail → red |
| **T-24-e** ✅ | `live_llm` is registered **and** `--strict-markers` is on in both jobs — a mistyped `-m live_lm` otherwise selects nothing and passes green having tested nothing | ✅ **Checked** — dropped `--strict-markers` → red |
| **T-24-f** ✅ | ⭐ **The marker is not deselected in BOTH places** — asserted as a composite property, because the two one-sided tests both stay green in exactly the arrangement where nothing runs the tests. That arrangement is what T3-08 dismantled | ✅ **Checked** — added `not live_llm` to the DPG job → red |
| **T-24-g** ✅ | The DPG job runs on **every commit**, not a schedule. Nightly is the documented *degraded* fallback and taking it requires saying so in the badge — so it must not arrive by someone quietly adding a trigger | ✅ **Checked** — added a `schedule:` trigger → red |
| **T-24-h** ✅ | The job exercises **both** LLM surfaces. Pointing only `backend/` at an open endpoint is the exact drift the registry exists to prevent — the complainant-facing summary would still be on a closed model | ✅ **Checked** — dropped the ticketing suite → red |
| **T-24-i** ✅ | **No model name appears in `ci.yml`** — DPG-17's rule reaches the workflow too; models come from repo variables, so a post-DPG-23 swap is a settings change rather than a commit. ⚠ This test failed on its first run, against my own job header | ✅ **Checked** — it caught a real violation before the commit |
| **T-24-j** ✅ | The job header records the **never-required** decision (Q-17), **why CI may route while production pins** *and the invariant that ends it*, the **hard token cap**, the **measured spend** and **who pays after the demo months** — each as a value or an explicit `⚠ UNRESOLVED`. A blank is the one thing disallowed | ✅ **Checked** — deleted the cost block → red |
| **T-24-l** ✅ | ⭐ **The job fails when NOTHING passed.** The live tests *skip* on a quota refusal — correct, because a 402 is not a defect here and a job that reddens on someone else's billing gets ignored (D-26). But that creates a new way to be wrong: a run where every test skipped exits 0 and shows a green tick having tested nothing — the quarantine pattern with better manners. The step greps for a pass and fails without one, and still fails on a genuine failure | ✅ **Checked** — replaced the guard with `if true` → red. ⚠ **The first version of this pin survived that mutation**: it matched the words *"NOTHING PASSED"*, which stayed in the dead else-branch. It now asserts the grep **condition**. Second time this sprint a mutation exposed a prose-matching pin (D-42's pattern), and worth noting because both were mine |
| **T-24-k** ✅ | The workflow header **counts its own jobs**. It said "Three" while there were four, for months — a header that undercounts is how a gate goes unnoticed, which is the marker-nobody-runs defect one level up | ✅ **Checked** — left it at four after adding the fifth → red |

Benchmarks (DPG-22/23) are **measurements, not tests** — they produce numbers in
`docs/dpg/model-benchmarks.md`, and they must not gate CI. A benchmark asserted as a threshold becomes a
flaky test the first time a provider changes a model behind a tag.

---

## Sprint 3

### DPG-31 — the deterministic layer

| ID | Test | Mutation check |
|---|---|---|
| **T-31-a** | ⭐ **A Devanagari-digit phone number (`९८४१२३४५६७`) is detected and replaced.** The single most important test in this sprint | Remove the digit normalisation → red |
| **T-31-b** | ASCII and Devanagari forms of the same number are both caught; `+977`, `97x`/`98x` mobiles, landlines, citizenship numbers, email | Drop any recogniser → red |
| **T-31-c** | Offset alignment: replacements land on the correct spans of the **original** string after normalisation | Apply normalised-string offsets to a non-length-preserving mapping → red |
| **T-31-d** | Consistent mapping within a document — the same name yields the same token on every occurrence; **different documents do not share a counter** | Use a global counter → red |
| **T-31-e** | `redact_for_model` → `restore` round-trips losslessly for text containing no PII | Break the reverse mapping → red |

### ⏸ DPG-32 — NER — **moved out of Sprint 3** (Q-12c)

> The NER layer became a standalone anonymiser-service initiative (Q-12c), so **T-32-a…c travel with it.**
> They stay written here because the tests are the spec of what the service must do, and re-deriving them
> later is waste. ⚠ **Do not count them toward Sprint 3's coverage** — and note that T-31-a…e now carry the
> whole of the sprint's redaction evidence, which makes T-31-a (a Devanagari-digit phone number is detected)
> the most load-bearing test in the sprint rather than merely the most important one.

### DPG-32 — NER

| ID | Test | Mutation check |
|---|---|---|
| **T-32-a** | A Devanagari person name in a realistic grievance sentence is detected | Lower the recall threshold to precision-first → red |
| **T-32-b** | ⭐ **A third-party name** (site engineer, contractor, ward official) is detected — not only complainant self-identification | Restrict detection to the opening sentence → red |
| **T-32-c** | If the NER model fails to load, the deterministic layer still runs **and the failure is loud** — a silent drop to regex-only is a privacy failure that looks like success | Make the load failure silent → red |

### DPG-33 / DPG-34 — the boundaries

| ID | Test | Mutation check |
|---|---|---|
| **T-33-a** | No raw narrative reaches a mocked client on **any** of the 9 call sites — asserted at the chokepoint, not per site | Bypass redaction on one site → red |
| **T-33-b** | `restore()` is applied where output reaches a human or storage — a complainant never receives `<PERSON_1>` | Skip restore on the summary path → red |
| **T-33-c** | `tests/ticketing/test_pii_boundary.py` and `test_boundary_policy.py` still green (existing pins; regression guard for the locked rules) | — |
| **T-34-a** | A grievance narrative passed to `TaskLogger` does not appear in the emitted record | Remove the logging filter → red |
| **T-34-b** | The translation error path does not interpolate `grievance_description` into its exception message | Restore the `input_data` interpolation → red |
| **T-34-c** | `parse_llm_response` logs a **length**, not the raw response, on parse failure | Log the raw response → red |

### DPG-35 — measurement — **split** (Q-12c)

> Deterministic recall (phone by digit system, vehicle, citizenship, email; and the classification-quality
> delta) **stays in Sprint 3**. PERSON recall/precision, third-party-name recall and the voice subset
> **travel with DPG-32** — there is nothing to measure until it ships. ⚠ **Report PERSON as "not covered"
> rather than omitting the row:** a recall table missing PERSON reads as a control that covers names.

### DPG-35 — measurement

Not a pass/fail test. A published number in `docs/dpg/pii-redaction-evaluation.md`, reported as:
PERSON recall · PERSON precision · phone recall **split by digit system** · third-party-name recall
(separately from self-identification) · classification-quality delta redacted-vs-raw · voice subset
separately. **State the weaknesses**: a WikiANN-trained NER model on colloquial transcribed speech will
underperform its published F1, and the report should say so before a reviewer does.

---

## Coverage summary

| Sprint | Test IDs | New files |
|---|---|---|
| 0 | T-01 (9), T-02-a…e (29) — ✅ landed, 38 assertions | `tests/repo/test_spdx_headers.py`, `test_licence_scan.py`, `test_image_pins.py` |
| 1 | T-10-a…f, T-11-a…d, T-12-a…c, T-13-a…e, T-14-a…c, T-15-a…c, T-16-a, T-17-a…d · **second wave:** T-18-a…f, T-19-a…e, T-19b-a…b, T-15b-a…d | `tests/backend/test_llm_services.py`, `tests/ticketing/test_llm_client.py`, `tests/backend/test_llm_config.py`, `tests/backend/test_llm_config_pins.py` |
| 2 | T-24-a…d | `@live_llm`-marked subset |
| 3 | T-31-a…e, T-33-a…c, T-34-a…c (**in scope**) · T-32-a…c + PERSON metrics ⏸ **moved out with DPG-32** | `tests/backend/test_pii_service.py` |

**Baseline: 0.** No test in the repository imports `LLM_services.py` or `ticketing/clients/llm_client.py`
today. Every number above is net new.
