# Sprint tracker — DPG compliance & LLM independence

> **Update this file at every commit.** Status, checklist ticks, deviations.
> Sprint index: [`README.md`](README.md) · Test ledger: [`TESTS.md`](TESTS.md) · Questions: [`QUESTIONS.md`](QUESTIONS.md)
> Status legend: ⬜ not started · 🟡 in progress · ✅ done · ⏸ blocked · ❌ dropped (log why)

**Sprint status: ⬜ NOT STARTED** · Created 2026-08-17 · Baseline `integration/stage` @ `f0d4552d`

---

## Status board

| Ticket | Title | Status | Branch | Commit(s) | Tests green | Notes |
|---|---|---|---|---|---|---|
| **DPG-01** | LICENSE + NOTICE + SPDX | ✅ | `dpg/sprint0-licensing` | | ✅ T-01 (9) | Apache-2.0 landed **provisionally** (owner: proceed, revisit if the consultant advises — Q-02). 583 files stamped; `NOTICE` holder is an explicit `⚠ PENDING` per DPG-03 |
| **DPG-02** | Dependency licence audit | ✅ | `dpg/sprint0-licensing` | | ✅ T-02 (16) | 153 pkgs, 4 sets, 0 unknown/non-OSI. Rasa closed. Scan **scheduled** (Q-06). Found 2 transitive LGPL + our own npm manifest declaring `UNLICENSED` |
| **DPG-03** | IP ownership (ADB OGC) | ⬜ | non-code | | n/a | **Longest lead. Date sent: ______** |
| **DPG-04** | Privacy assessment + data-flow | ⬜ | `dpg/sprint0-licensing` | | n/a | Gates Q-03 (jurisdiction) |
| **DPG-05** | Project hygiene (indicator 8) | ⬜ | `dpg/sprint0-licensing` | | n/a | Added 2026-08-17 from the compliance audit. `SECURITY.md` needs a **private** channel — SEAH |
| **DPG-06** | Root `README.md` vs reality | ⬜ | `dpg/sprint0-licensing` | | n/a | Added 2026-08-17. **Do before the consultant meeting** — it contradicts our own "no Rasa" claim |
| **DPG-10** | **Test net (must land first)** | ⬜ | `dpg/sprint1-llm-agnostic` | | | Nothing in Sprint 1 starts before this |
| **DPG-11** | `backend/services/llm_client.py` | ⬜ | `dpg/sprint1-llm-agnostic` | | | Stable shared service — re-grep callers |
| **DPG-12** | Ticketing client via settings | ⬜ | `dpg/sprint1-llm-agnostic` | | | |
| **DPG-13** | `json_object` → `json_schema` | ⬜ | `dpg/sprint1-llm-agnostic` | | | 7 call sites |
| **DPG-14** | Three latent defects | ⬜ | `dpg/sprint1-llm-agnostic` | | | 14.3 is **unverified** — confirm in-container |
| **DPG-15** | Degraded mode audit + probe | ⬜ | `dpg/sprint1-llm-agnostic` | | | Mostly already built — audit, don't rebuild |
| **DPG-16** | Env plumbing | ⬜ | `dpg/sprint1-llm-agnostic` | | | Generated from DPG-17's `declared_env_vars()` |
| **DPG-17** | **One config file** (`backend/config/llm_config.py`) | ⬜ | `dpg/sprint1-llm-agnostic` | | | **Lands before DPG-11/12.** Defaults stay on today's models — the open-default flip is Sprint 2 |
| **DPG-20** | Benchmark set | ⬜ | `dpg/sprint2-open-models` | | n/a | **Start during Sprint 1** — long pole |
| **DPG-21** | Provider setup + smoke | ⬜ | `dpg/sprint2-open-models` | | | |
| **DPG-22** | ASR evaluation | ⬜ | `dpg/sprint2-open-models` | | | **No baseline exists** — voice never live (Q-13.2). Sequence last: costliest, least urgent (Q-19) |
| **DPG-23** | Text-model evaluation | ⬜ | `dpg/sprint2-open-models` | | | Now a **production pre-flight check** (Q-04), not only DPG evidence. ⚠ Price it first (Q-19) |
| **DPG-24** | CI platform-independence job | ⬜ | `dpg/sprint2-open-models` | | | **5th** job in existing `ci.yml`. Only recurring cost — cap it first (Q-19) |
| **DPG-25** | T2 vLLM — documented + costed | ⬜ | `dpg/sprint2-open-models` | | n/a | ⏸ **T2 PARKED** (Q-03/Q-05). No deployment; the e2e test is a logged deferral |
| **DPG-30** | **Egress inventory (first)** | ⬜ | `dpg/sprint3-pii` | | n/a | Nothing in Sprint 3 starts before this |
| **DPG-31** | Deterministic PII layer | ⬜ | `dpg/sprint3-pii` | | | Ships without DPG-32 |
| **DPG-32** | NER layer | ⏸ | — | | | **MOVED OUT of Sprint 3** (Q-12c) → standalone anonymiser-service initiative. ⚠ Leaves person names unredacted; disclose it |
| **DPG-33** | Model-call boundary | ⬜ | `dpg/sprint3-pii` | | | |
| **DPG-34** | Log / Celery / backup boundary | ⬜ | `dpg/sprint3-pii` | | | The leak that actually happens |
| **DPG-35** | Recall measurement | ◐ | `dpg/sprint3-pii` | | | **Split** (Q-12c): deterministic recall stays; PERSON/third-party travel with DPG-32 |
| **DPG-36** | Reconcile the live spec | ⬜ | `dpg/sprint3-pii` | | | |

---

## Question status

Answers verbatim + reasoning: [`DECISIONS.md`](DECISIONS.md). Still live: [`QUESTIONS.md`](QUESTIONS.md).
**All 20 answered 2026-08-17**; Q-19 was raised by the answers and is open.

| Q | Subject | Owns | Answer | Recorded in |
|---|---|---|---|---|
| Q-18 | Shared LLM config module | DPG-17 | ✅ `backend/config/llm_config.py`, pydantic-settings, dep → `requirements.txt` | [`02` DPG-17](02-llm-agnostic-spec.md#dpg-17) |
| Q-03 | T2 jurisdiction | DPG-25 | ✅ **Moot — T2 parked** | [`03` DPG-25](03-open-models-spec.md#dpg-25), [`00` §2](00-dpg-context-and-decisions.md#2-deployment-ladder--the-code-is-identical-at-every-tier), [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| Q-05 | T2 operator + payer | DPG-25 | ✅ **T2 parked** — no run-cost owner | [`03` DPG-25](03-open-models-spec.md#dpg-25), [`00` §5](00-dpg-context-and-decisions.md) |
| Q-04 | Which config production runs | DPG-23 | ✅ **The open one**, on cost; closed as fallback | [`03` DPG-23](03-open-models-spec.md#dpg-23), [`00` §4](00-dpg-context-and-decisions.md#4-dpg-evidence-pack) |
| Q-10 | Open config as repo default | DPG-17 | ✅ Yes, flipped in Sprint 2 | [`02` DPG-17](02-llm-agnostic-spec.md#dpg-17) §Correction |
| Q-11 | One model or per-task | DPG-17 | ✅ One text model first, then downsize; HF pricing is the driver | [`02` DPG-14](02-llm-agnostic-spec.md#dpg-14) (truncation check), [`03` DPG-25](03-open-models-spec.md#dpg-25) |
| Q-12b | Redact when | DPG-31, DPG-36 | ✅ **At transmission** — and the restore mapping is PII | [`04` DPG-31](04-pii-redaction-spec.md#dpg-31), [`04` DPG-36](04-pii-redaction-spec.md#dpg-36) |
| Q-12c | Where the ML dependency lives | DPG-32 | ✅ Dedicated service, **own initiative** — DPG-32/35 leave Sprint 3 | [`04` DPG-32](04-pii-redaction-spec.md#dpg-32), [`04` DPG-35](04-pii-redaction-spec.md#dpg-35) |
| Q-12 | Nepali NER licence | DPG-32 | ✅ Email the author; fine-tune as fallback | [`04` DPG-32](04-pii-redaction-spec.md#dpg-32) |
| Q-13 | `gpt-5-nano` · voice live? | DPG-14 | ✅ Deliberate cost choice · **voice not live** | [`02` DPG-14](02-llm-agnostic-spec.md#dpg-14), [`03` DPG-22](03-open-models-spec.md#dpg-22) |
| Q-14 | SEAH fail open/closed | DPG-15 | ✅ **Fail-open stays** — deterministic pre-filter verified in code | [`02` DPG-15](02-llm-agnostic-spec.md#dpg-15) |
| Q-15 | Benchmark provenance | DPG-20 | ✅ Synthetic phase 1; hybrid later | [`03` DPG-20](03-open-models-spec.md#dpg-20) |
| Q-16 | Benchmark size + labellers | DPG-20 | ✅ **No labeller budget** — target is aspirational | [`03` DPG-20](03-open-models-spec.md#dpg-20) |
| Q-06 | Licence scan scheduled? | DPG-02 | ✅ Scheduled in `ops/security.py` | [`01` DPG-02](01-licensing-and-governance-spec.md#dpg-02) |
| Q-07 | Privacy-assessment author | DPG-04 | ✅ Agent drafts, consultant advises — **no legal review, must be disclosed** | [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| Q-08 | Assess against what | DPG-04 | ✅ Nepal Individual Privacy Act 2018; no existing agreement | [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| Q-09 | Translation: specialist? | DPG-23 | ✅ LLM first; dedicated service only if better | [`03` DPG-23](03-open-models-spec.md#dpg-23) |
| Q-17 | Provider outage blocks merges? | DPG-24 | ✅ Every commit, never a required check | [`03` DPG-24](03-open-models-spec.md#dpg-24) |
| Q-01 | Who opens the OGC request | DPG-03 | 🔶 **In flight** — writing to the consultant. ⚠ Not the same channel as ADB OGC | [`01` DPG-03](01-licensing-and-governance-spec.md#dpg-03) · **date sent: ______** |
| Q-02 | Apache-2.0 over MIT | DPG-01 | 🔴 **OPEN** — delegated to the consultant. **DPG-01 gated** | [`01` DPG-01](01-licensing-and-governance-spec.md#dpg-01) |
| Q-19 | **LLM budget** (new) | DPG-22/23/24 | 🔴 **OPEN** — gates most of Sprint 2 | [`QUESTIONS.md`](QUESTIONS.md#q-19) |

## Deviations

> Every departure from the specs goes here, in the commit that creates it — including adjacent bugs found
> and **not** fixed (per the sprint conventions: log, don't fix). Per
> [`docs/sprints/README.md`](../README.md), a deferral also needs a `followups/<slug>.md` doc and a
> `TODO.md` pointer row **in the same commit**. A deferral logged only here is half-logged.

| # | Ticket | What changed vs the spec | Why | Followup / TODO row |
|---|---|---|---|---|
| D-01 | | | | |

### Pre-sprint findings — carried in from planning

These were found while writing the specs, against `integration/stage` @ `f0d4552d`. They are **not yet
deviations** (no code has changed); they are the inbox DPG-10 and DPG-14 inherit. Move each to the table
above once a ticket touches it.

| # | Finding | Location | Owner |
|---|---|---|---|
| P-01 | A **second LLM surface** the source narrative missed entirely — 3 more hard-coded models, its own client, its own settings | `ticketing/clients/llm_client.py` | DPG-12 |
| P-02 | `gpt-5-nano` is the **live classification model**, not a stray reference | `LLM_services.py:230` | DPG-14.1 |
| P-03 | Classification builds a **shadow client** at `:199` that shadows the module-level one, then tests it with a guard that can never fire (`:200-201`) | `LLM_services.py:198-201` | DPG-14.2 |
| P-04 | ⚠ **Suspected** — ASR call passes `language_code=` where the SDK takes `language=`; if the SDK rejects it, transcription has never worked on this path. **Unverified: host has no `openai` (Docker-only)** | `LLM_services.py:46` | DPG-14.3 |
| P-05 | `extract_contact_info`'s `except` reads `response` at `:93`, which is unbound if the failure happened before `:76` → `UnboundLocalError` instead of the documented `{field_name: ""}` | `LLM_services.py:92-102` | DPG-10 / DPG-14 |
| P-06 | Two JSON-producing calls have **no `response_format` at all** — classification and translation ask for "strict JSON" in the prompt and absorb parse failures as empty results | `LLM_services.py:230`, `:322` | DPG-13 |
| P-07 | `load_dotenv('/home/ubuntu/nepal_chatbot/.env')` — an absolute EC2 path in a Docker-only stack. Dead code that reads as live config | `LLM_services.py:25` | DPG-11 |
| P-08 | **Zero tests** import either LLM module. The guide's CI snippet targets `tests/test_llm_services.py`, which does not exist | `tests/` | DPG-10 |
| P-09 | Translation error paths interpolate the whole `input_data` dict — including `grievance_description` — into a `ValueError` message that is then logged and may reach the Celery result backend | `LLM_services.py:335`, `:343` | DPG-34 |
| P-10 | `parse_llm_response` logs the **raw model response** on JSON parse error | `LLM_services.py:282` | DPG-34 |
| P-11 | `detect_sensitive_content_llm` **fails open** — LLM unreachable ⇒ `detected: False` on the SEAH path | `LLM_services.py:403-404` | DPG-15 / Q-14 |
| P-12 | `11_llm_pipeline_policy.md` asserts summaries "MUST be PII-scrubbed before storage". **Nothing scrubs them** | `docs/deployment/11_llm_pipeline_policy.md` | DPG-36 |
| P-13 | CLAUDE.md §Folder structure lists `rasa_chatbot/` — the directory does not exist | `CLAUDE.md` | DPG-02 (cheap fix alongside) |
| P-14 | `env.local` holds a live OpenAI key in plaintext. Gitignored and normal for a local env file, but it is the credential this sprint replaces — rotate when the migration lands | `env.local:39` | DPG-16 |
| P-15 | ⚠ **A second copy of `_MODEL_STANDARD` / `_MODEL_SEAH`**, in a module the inventory missed — written into the resolved-case summary as `llm.model` (`:299`), i.e. a **persisted provenance field** computed from a copy rather than from the module that made the call. Change the client's mapping and miss this file → every resolved case records a model that never ran it | `ticketing/services/resolved_summary_builder.py:26-27`, `:299` | DPG-17 / DPG-12 |
| P-16 | A **third** copy of the same SEAH ternary, re-derived for a log line — the log can disagree with the call it is logging | `ticketing/tasks/llm.py:163` (and a stale key reference at `:15`) | DPG-17 / DPG-12 |
| D-08 | ⚠ **I under-scoped the deterministic redaction layer, and the DPG docs inherited the error.** DPG-31 listed only numeric identifiers and email, so the briefing and compliance status both said person names would reach the provider unaddressed. **Names are substantially tractable without ML** — honorific/role-title triggers (`Er.`, Engineer, overseer, ward chairperson), a Nepali family-name gazetteer, and self-identification patterns. Added as §31.2b + §31.2c (addresses); DPG-32's deferral banner, DPG-35's metrics and both DPG docs corrected. **Owner-flagged** | `04-pii-redaction-spec.md`, `docs/dpg/*` | ✅ corrected |
| D-09 | ⚠ **Hugging Face's terms do not say what a privacy assessment needs them to say** — verified by reading them, not assumed. No Inference-Providers-specific clause on retention or training use; ToS references no DPA and frames confidentiality around private repos, not inference traffic; general processing location is *"the United States or any other country in which the Company or its affiliates … maintain facilities"*. **And the default routing policy picks a different third-party processor per request**, so the processor is not knowable under the default config. Engineering response: pin `model:provider`. Raised as consultant-Q16 | `docs/dpg/00_compliance_status.md` §4.3a | **open — Q16** |
| D-04 | ⚠ **The DPG-02 spec's "two images" premise is wrong.** One `Dockerfile` serves every Python service and installs **both** `requirements.txt` and `requirements.grm.txt` into a single image — verified by importing packages from each inside `ticketing_api`. The report therefore splits by **manifest** (parsed from the requirements files), which is the only split that exists: 35 declared, 98 transitive | `Dockerfile:22-25` | DPG-02 (spec corrected) |
| D-05 | **Our own npm manifest declared no licence** — fixed (`"license": "Apache-2.0"` in both). ⚠ **But the follow-on claim was wrong and is corrected:** the report predicted the scanner row would flip to `Apache-2.0` after an image rebuild. It does not. `license-checker` hard-codes `UNLICENSED` for any `"private": true` package and ignores the `license` field — verified by rebuilding `grm_ui` and re-scanning (`{"licenses": "UNLICENSED", "private": true}`). The row is a tool artefact for an unpublished package, not a finding; the fix stands on its own merits | `channels/*/package.json` | DPG-02 ✅ fixed, claim corrected |
| D-06 | ⚠ **Two LGPL dependencies nobody knew about**, both transitive so no manifest read would show them: `jwcrypto` (LGPL-3.0-or-later, via the Keycloak JWT path) and `@img/sharp-libvips-linux*-x64` (LGPL-3.0-or-later, via Next.js image optimisation). Both are unmodified dynamically-loaded libraries — the LGPL-compliant pattern — and both are now dispositioned in the report | `docs/dpg/dependency-licenses.md` | DPG-02 ✅ recorded |
| D-07 | ⚠ **The first licence classifier passed a proprietary licence silently.** `"Proprietary Limited License"` contains the substring `MIT`, so `token in text` classified it as OSI-approved and the nightly scan would have reported clean. Fixed with word-boundary matching and pinned by a mutation-checked test | `ops/licences.py` | DPG-02 ✅ fixed |
| D-01 | ⚠ **CI never runs 21 test files.** `ci.yml`'s pytest step names four paths explicitly (`tests/ticketing tests/orchestrator tests/actions tests/backend`), so the **21 test files sitting directly in `tests/`** — `test_complainant_functions.py`, `test_postgres_services.py`, `test_seah_*.py` and 18 more — plus `tests/shared/`, have never executed in CI. Found while deciding where T-01 should live; it is why `tests/repo/` exists rather than `tests/test_spdx_headers.py`. **Not fixed here** — those files may not pass, and finding out is its own ticket, not a licence commit. Logged as a followup | `.github/workflows/ci.yml:178` | followup |
| D-02 | ✅ **CLOSED 2026-08-18 — `next build` succeeded.** Rebuilt `grm_ui` in Docker after the SPDX pass and the container came up healthy; the built image carries the current sources (verified via the new `license` field), so the build genuinely re-ran over all 110 `.tsx` files that now have the header above `"use client"`. The reasoning below was right — comments are trivia and do not break a Directive Prologue — but it is now confirmed by the actual Next.js compiler rather than by argument. Original note: | 110 files under `channels/ticketing-ui/` | ✅ verified |
| D-02b | ⚠ **The `"use client"` directive placement was reasoned, not empirically confirmed** (superseded by D-02). 110 `.tsx` files now carry `// SPDX-License-Identifier` **above** their `"use client"` directive. Per ECMAScript, comments are trivia and do not break a Directive Prologue, so the directive is still the first *statement* — and `tsc --noEmit` is clean plus all 88 vitest tests pass. But **vitest does not exercise the directive** and there was no prior comment-above-directive precedent in the repo to lean on. `next build` is the confirming gate and it must not run on the host (CLAUDE.md §Docker-only). **Check `ui-checks` on the first CI run of this branch** — if it fails, the fix is to move the header below the directive for `.tsx` only, which is a three-line change to `insertion_line()` | 110 files under `channels/ticketing-ui/` | **verify in CI** |
| D-03 | The pre-sprint reading of "encoding declarations in scope" was a **false positive** — the grep matched `encoding="utf-8"` inside `open()` calls, not PEP 263 headers. There are **no** encoding declarations in scope; the shebang case (13 files) is real and handled | — | closed |
| P-22 | **There is no LLM budget** — *"I can shoulder a few calls per day to nano, not transcription"* (Q-13). Voice transcription is consequently **not live at all**, and Sprint 2 is built almost entirely from inference calls that nobody priced | Q-13 · DPG-22/23/24 | **Q-19** (new) |
| P-23 | **T2 parked** (Q-03/Q-05) — no run-cost owner. T1 becomes the steady state, so grievance egress to a third party is **permanent, not transitional**, which promotes Sprint 3 and removes the vLLM-in-production sentence from the indicator-4 answer | Q-03, Q-05 | DPG-25, DPG-04, Sprint 3 |
| P-24 | ✅ **A deterministic SEAH pre-filter exists and is wired in** — `shared_functions/keyword_detector.py:257` (scored, `:342`) via `helpers_repo.py:58` → `services/seah/sensitive_detection.py:25` → `base_mixins.py:170`, as synchronous slot validation. So the LLM leg's fail-open degrades a **second** pass. Strengthens indicator 9b, which the compliance doc credited to the LLM alone | verified 2026-08-17 | DPG-15, compliance §2.6 |
| P-25 | Owner's Q-11 answer states translation and classification run **in one call**; the code has them as **two** (`:204-231` classify/summarise/follow-up; `:322` translate). The true and useful version: there is no translate-then-classify pipeline — the model consumes Nepali directly | `LLM_services.py:204-231`, `:322` | DPG-23, Q-11 |
| P-26 | Q-12b's *"in practice we store both"* implies a persisted `restore()` mapping — **a plaintext PII store by construction**. Must not land in `ticketing.*` (data rule 3); prefer never persisting it | Q-12b | DPG-31 |
| P-18 | Container images were a **fourth dependency set nobody was auditing** — and the one place licence drift actually happened (`redis:7`, a floating tag onto the non-OSI 7.4 line). Fixed outside the sprint plan: `redis:8.10`, AGPLv3 elected. DPG-02 now audits four sets + a pin-drift check | `docker-compose.yml:222`, `.github/workflows/ci.yml:42` | DPG-02 |
| P-19 | No ticket covered indicator-8 project hygiene (`SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, templates) — all verified absent | repo root | **DPG-05** (new) |
| P-20 | Root `README.md` advertises a **Rasa service on port 5005** plus an Action Server on 5055, and names a stale active branch. It contradicts the compliance briefing's own indicator-2 argument, on the most-read file in the repo | `README.md:6`, `:10`, `:46-47`, `:60`, `:76`, `:116` | **DPG-06** (new) |
| P-21 | The compliance audit asserted "**No `.env.example`**". It exists (5982 B, `OPENAI_API_KEY=` at `:61`) — the spec was right and the audit wrong. Corrected in the audit doc; the real gap is that it documents only the key, not the endpoint/model surface | `.env.example:61` | DPG-16 |
| P-17 | DPG-11's "open configuration by default" cannot ship in Sprint 1: an HF-router base URL with `gpt-3.5-turbo` / `whisper-1` model IDs is a default configuration that serves **no** request, and it turns DPG-10's tests red in the commit where red means *stop*. Deferred to Sprint 2 against DPG-17's single file | — (planning finding) | DPG-17, DPG-23, Q-10 |

---

## Degraded-mode audit table (DPG-15)

Fill during DPG-15. One row per call site: is the grievance durable before the call, and what does the
user see when it fails?

| # | Call site | Durable before call? | On failure, user sees | Gap? |
|---|---|---|---|---|
| 1 | `transcribe_audio_file` | | | |
| 2 | `extract_contact_info` | | | |
| 3 | `extract_all_contact_info` | | | |
| 4 | `classify_and_summarize_grievance` | ✅ (row written, then `.delay()`) | 20 s poll, then empty classification | |
| 5 | `translate_grievance_to_english_LLM` | | | |
| 6 | `detect_sensitive_content_llm` | | | ⚠ fails open — Q-14 |
| 7 | `translate_to_english` (ticketing) | | | |
| 8 | `generate_case_findings` | | | |
| 9 | `generate_resolved_case_summary_llm` | | | |

---

## Commit log

| Date | Ticket | Commit | What landed |
|---|---|---|---|
| 2026-08-18 | **DPG-02** | _(this branch)_ | `docs/dpg/dependency-licenses.md` — 153 packages, in-container scans · `ops/licences.py` + `licence_scan()` scheduled nightly at 01:50 (Q-06) · `pip-licenses` declared · pin-drift + classifier tests (`tests/repo/`, 16 assertions) · **`redis:8.10` pin verified live** — the caveat on commit `800aa803` is closed · npm manifests now declare Apache-2.0 |
| 2026-08-17 | **DPG-01** | _(this branch)_ | `LICENSE` (canonical Apache-2.0, 202 lines, md5 `3b83ef96…`) · `NOTICE` with an explicit pending-holder disclosure · `scripts/ops/add_spdx_headers.py` (idempotent, `--check` mode) · **583 files stamped** (408 `.py`, 175 `.ts`/`.tsx`) · `tests/repo/test_spdx_headers.py` (T-01, 9 assertions) · `tests/repo` wired into `ci.yml` |

| Date | Ticket | Commit | Summary |
|---|---|---|---|
| | | | |

---

## Sprint close checklist

- [ ] All 27 tickets ✅, or ❌ with a logged reason
- [ ] Every test in [`TESTS.md`](TESTS.md) written and mutation-checked
- [ ] Every question in [`QUESTIONS.md`](QUESTIONS.md) answered **and its answer written into the spec**
- [ ] All P-## findings above dispositioned (fixed, or moved to a followup + `TODO.md` row)
- [ ] `docs/dpg/` evidence pack complete; every indicator row points at a real file
- [ ] Live specs updated with honest verification markers (see [`README.md`](README.md) → domain specs table)
- [ ] Indicator-4 submission text checked **clause by clause** against reality before pasting
- [ ] Summary written as `docs/sprints/2026-08_dpg_llm_independence.md`
- [ ] This folder moved to [`../archive/`](../archive/); [`../README.md`](../README.md) tables updated
- [ ] `docs/PROGRESS.md` and `docs/TODO.md` updated
