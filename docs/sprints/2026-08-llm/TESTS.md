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
| **T-18-a** | `call_llm()` is the **only** thing in either surface that calls `.create()` — AST-parsed, same shape as T-11-d. A call site that builds its own request is the drift this ticket removes | Rebuild a request at any call site → red |
| **T-18-b** | The `prompt` rung's instruction is **generated from the Pydantic schema** and names every required field — so the three rungs cannot describe different shapes | Hand-write the fallback text, or drop a field from the generated text → red |
| **T-18-c** | `parse_response()` handles what providers actually return: a bare object, an object wrapped in ```` ```json ```` fences, leading prose before the brace. Each yields the validated model or a **typed** error — never a silent `{}` | Remove fence-stripping → red |
| **T-18-d** | One task key change moves the model for every call site that uses it, on **both** surfaces — the consolidation of §18.2 is a config edit and this proves it | Pin a model at a call site → red |
| **T-18-e** | ⭐ **The profile pin (D-40).** For a `gpt-5*` model the request carries **no `temperature`** and uses **`max_completion_tokens`**; for `gpt-4o*` it carries `temperature` and `max_tokens`. Asserted on the request the layer builds, per profile — the call site asks for the same thing either way | Send `temperature` to a `gpt-5*` model, or `max_tokens` → red |
| **T-18-f** | ⭐ **`finish_reason == "length"` is a failure, not an empty answer.** A truncated response never reaches a parser and never becomes `None`-that-means-empty | Treat a length-truncated response as empty content → red |

### DPG-19 — meaningful input (second wave)

| ID | Test | Mutation check |
|---|---|---|
| **T-19-a** | Below `MIN_CLASSIFY_CHARS`, **no model call is made** and the status is `LLM_SKIPPED` — asserted on a mocked client that must not be touched | Call the model anyway → red |
| **T-19-b** | ⭐ **The owner's point, pinned.** At or above the threshold, an empty-but-valid result (`"{}"`) is **not** a failure: the localized "not enough information" response, `is_failed_classification()` False, and a warning carrying the **length only** | Make an empty result count as a failure → red *(this is the regression the guardrail could introduce)* |
| **T-19-c** | The threshold is measured on **whitespace-stripped** length and is a registry value — a 30-space "grievance" is below it, and Devanagari counts by character like anything else | Count raw `len()` → red |
| **T-19-d** | The translation error message contains the `grievance_id`, **at most three words** of the description, and **never** the summary, the full description or `input_data` | Restore the `input_data` interpolation → red |
| **T-19-e** | D-29's underlying bug: a pre-call failure now raises the declared `ValueError`, not `UnboundLocalError` | Move the `result` binding back inside the `try` → red |

### DPG-19b — the dead paths, deleted (second wave)

| ID | Test | Mutation check |
|---|---|---|
| **T-19b-a** | `PARKED_TASKS` names all four voice-flow paths with a reason, and every name in it is a real task — a parked declaration for a task that no longer exists is a stale excuse | Park a task that does not exist, or park one without a reason → red |
| **T-19b-b** | ⭐ **The reachability pin.** Every LLM-calling task is either **enqueued in production** (`test_tasks.py` does not count) **or declared in `PARKED_TASKS` with a reason**. Nothing else is allowed | Add an LLM task that is neither enqueued nor parked → red |

⚠ **T-19b-b is the general fix, and the distinction it enforces is the whole point.** *Live*,
*parked* and *rotted* look identical to a grep — which is how a nine-item egress inventory ended up
with four phantoms in a **compliance document**, and how a correction in `DECISIONS.md` Q-11 told the
owner his mental model was wrong when it was right. A path that is parked **and says so** is
documentation. A path that is unreachable and silent is a liability. The pin costs ten lines.

### DPG-15b — the classification checkpoint (second wave)

| ID | Test | Mutation check |
|---|---|---|
| **T-15b-a** | The deadline is `CLASSIFICATION_WAIT_SECONDS` from the registry, default 90 — no literal deadline survives anywhere | Hard-code a timeout → red |
| **T-15b-b** | The review step does **not** block when the classification has not arrived; submission does the waiting | Make the review step wait again → red |
| **T-15b-c** | ⭐ A classification that lands **after** submission still updates the grievance, and the update reaches the ticket | Drop the late-update path → red |
| **T-15b-d** | `LLM_failed` is written once retries are exhausted — the state D-34 showed to be unreachable. **Verified against the database**, not only against a mock | Return the FAILED dict instead of re-raising → red |

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
| **T-24-a** | `@live_llm` — a real chat round-trip against the configured open endpoint returns a parseable structured result | Point at an invalid model → red |
| **T-24-b** | `@live_llm` — a real transcription round-trip against the configured open ASR endpoint | Same |
| **T-24-c** | The `live_llm` marker is **deselected** by `backend-tests` and **selected** by `dpg-platform-independence`. Assert on the config, so the "runs nowhere" quarantine cannot re-form silently | Remove the marker from the DPG job's selection → red |
| **T-24-d** | The DPG job **skips cleanly** (not fails) when `HF_TOKEN` is absent — fork PRs must not show a red X on a public-good repo | Make the absent-secret path fail → red |

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
