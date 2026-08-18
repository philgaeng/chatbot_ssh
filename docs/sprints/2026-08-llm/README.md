# Sprint — August 2026: DPG compliance & LLM independence

> **Status: QUEUED** (not started) · Source narrative: [`DPG-migration-guide-nepal-grm.md`](DPG-migration-guide-nepal-grm.md)
> Goal: make the Nepal GRM chatbot submittable as a **Digital Public Good**, by turning a hard-coded
> OpenAI dependency into a configuration value, shipping a tested open-weights configuration as the
> repository default, and closing the PII egress that both create.
> Four sub-sprints, one spec each. Sprint 0 is non-code and starts **immediately, in parallel** — two of
> its items have multi-week external lead times.

---

## ⚠️ Read this before opening any spec

The source narrative was written against a partial read of the codebase. **Five of its premises are
wrong, and one of them is load-bearing.** Each spec restates the corrected version in its own
§0, but the headline is here so nobody plans off the stale version:

| The guide says | The code says | Consequence |
|---|---|---|
| "No provider abstraction exists" — one file, `backend/services/LLM_services.py` | **There are two LLM surfaces and four files.** `ticketing/clients/llm_client.py` is a second, independent OpenAI client with three more hard-coded models (`gpt-4`, `gpt-4o-mini`, `gpt-4o`) and its own settings object — and `ticketing/services/resolved_summary_builder.py:26-27` + `ticketing/tasks/llm.py:163` each keep **their own copy** of the model names | Sprint 1 is **~2× the scope** the guide assumes. A migration that fixes only `backend/` leaves the indicator-4 claim false — and one of those copies is written into a **persisted provenance field**, so drift there publishes a model name that never ran. Hence **DPG-17**: two factories, one config. |
| "plus a `gpt-5-nano` reference" (implying a stray typo) | `gpt-5-nano` **is the live grievance-classification model** (`LLM_services.py:246`) — the primary AI path in the product | Not a cleanup item. It is the model selection that Sprint 2 has to benchmark against. |
| "gpt-3.5-turbo (contact extraction, content detection, grievance classification)" | Classification is `gpt-5-nano`. `gpt-3.5-turbo` covers contact extraction (×2) and sensitive-content detection | Wrong model→task mapping; the benchmark plan inherits it. |
| §1.5 "Degraded mode — do not skip this" (written as unbuilt) | **Largely already built.** Intake writes to Postgres first, classification is a Celery task with retry, `LLM_FAILED`/`LLM_SKIPPED` status codes exist, and the retrieve step polls with a 20 s deadline | DPG-15 is a *verify-and-close-the-gaps* ticket, not a build ticket. Treating it as greenfield would duplicate working machinery. |
| "⚠️ Verify Rasa 3 specifically… far bigger indicator-2 problem" (flagged as week-one alarm) | There is **no Rasa**. No `rasa_chatbot/` directory, no Rasa service in either compose file, no Rasa NLU/server dependency — only `rasa-sdk==3.6.2` (Apache-2.0), used for the `Tracker`/`CollectingDispatcher` types the hand-rolled state machine still speaks | The alarm is ~resolved before it is raised. DPG-02 confirms it in an hour, not a week. |

The guide's **strategy** survives all five corrections intact. It is the *inventory* that was short.

### ⚠ Two question-numbering spaces — do not conflate them

[`QUESTIONS.md`](QUESTIONS.md) + [`DECISIONS.md`](DECISIONS.md) hold **Q-01…Q-19, hyphenated**: decisions
for the *project owner*, each owned by a ticket. [`docs/dpg/00_compliance_status.md`](../../dpg/00_compliance_status.md) §5 holds
**Q1…Q14, unhyphenated**: questions for *ADB's DPG consultant*. **The numbers overlap and mean different
things** — its Q4 asks whether our reading of indicator 4 is correct; our Q-04 asks which configuration
production runs. When citing across, write "consultant-Q5", as the specs now do.

### ✅ All 20 owner questions answered — 2026-08-17

[`QUESTIONS.md`](QUESTIONS.md) now holds only what is still live; the answers moved to
[`DECISIONS.md`](DECISIONS.md), verbatim. **Two of them changed the plan beyond their own tickets, and one
new question came out of them:**

| Decision | Effect |
|---|---|
| **T2 is parked** (Q-03 + Q-05) — no owner for GPU run costs | **T1 is the steady state, not a stepping stone.** Grievance text leaves the country **indefinitely** → [Sprint 3](04-pii-redaction-spec.md) is promoted from prudent to **necessary**; [DPG-25](03-open-models-spec.md#dpg-25) becomes *documented and costed, not deployed*; the indicator-4 answer loses its vLLM-in-production sentence |
| **Production runs the open configuration** (Q-04), on cost | **Stronger than indicator 4 requires** — the Standard asks for demonstrated replaceability; you will run the replacement. It also makes [DPG-23](03-open-models-spec.md#dpg-23) a **production pre-flight check**, not only evidence |
| **The NER layer becomes its own initiative** (Q-12c) | [DPG-32](04-pii-redaction-spec.md#dpg-32) + [DPG-35](04-pii-redaction-spec.md#dpg-35) leave Sprint 3, which ships deterministic redaction only. ⚠ **Corrected 2026-08-18 — this row said "person names go unredacted". That is D-08's error and it is false.** [§31.2b](04-pii-redaction-spec.md#dpg-31) redacts names at the rule layer without any ML dependency (title triggers, thar gazetteer, self-identification), catching the *named official* — the sharpest exposure. DPG-32 **raises recall**; it is not the whole control. What must be disclosed is the **measured residual**, not an absence |
| 🔴 **New: Q-19 — there is no LLM budget** | Raised by Q-13 (*"a few calls per day to nano, not transcription"*). **Sprint 2 is made of inference calls and nobody priced them.** Cap [DPG-24](03-open-models-spec.md#dpg-24) first — it is the only recurring cost — and price [DPG-23](03-open-models-spec.md#dpg-23) before building it |

**Still open:** Q-02 (which licence — delegated to the consultant, and it now gates
[DPG-01](01-licensing-and-governance-spec.md#dpg-01)) and Q-19. **In flight:** Q-01 (IP determination — ⚠ the
owner is writing to the *consultant*, which is not the ADB OGC channel the question meant).

### Reconciliation with the compliance audit — 2026-08-17

The audit was written after these specs and from a fresh read of the code, so it found things they missed
and asserted a few things they had right. **Both directions have been reconciled**; the audit doc carries
the same note. What moved into the specs: container images as a fourth dependency set + a pin-drift check
(DPG-02), project hygiene (**new DPG-05**), the stale root README (**new DPG-06**), vehicle-registration
recognisers (DPG-31), and three consultant questions that gate Sprint 2's model criteria. What was corrected
*in the audit*: `.env.example` exists, there are nine call sites not eight, CI has four gates not three, and
Sprint 1 no longer ships the open-by-default flip.

---

## Documents in this sprint

| Document | What it is |
|---|---|
| [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md) | Why indicator 4 shapes everything · the T1/T2/T3 deployment ladder · the DPG evidence pack · the six open decisions |
| [`01-licensing-and-governance-spec.md`](01-licensing-and-governance-spec.md) | **Sprint 0** — DPG-01…06. Licence, dependency audit, IP ownership, privacy assessment. Non-code, long lead. |
| [`02-llm-agnostic-spec.md`](02-llm-agnostic-spec.md) | **Sprint 1** — DPG-10…17. Both LLM surfaces routed through configurable clients, reading **one** config file. The indicator-4 answer. |
| [`03-open-models-spec.md`](03-open-models-spec.md) | **Sprint 2** — DPG-20…25. Benchmark set, model selection, CI platform-independence job, vLLM deployment. |
| [`04-pii-redaction-spec.md`](04-pii-redaction-spec.md) | **Sprint 3** — DPG-30…36. Redaction at the model-call *and* logging boundaries. Nepali-specific. |
| [`PROGRESS.md`](PROGRESS.md) | **The tracker.** Status per ticket, checklists, deviations log. Updated at every commit. |
| [`TESTS.md`](TESTS.md) | **The test ledger.** Every test this sprint must add, with its purpose and its mutation check. |
| [`QUESTIONS.md`](QUESTIONS.md) | **What is still live** — 2 open (Q-02 licence choice, Q-19 LLM budget), 1 in flight (Q-01 IP determination), plus a one-line register of every decision taken. Short by design. |
| [`DECISIONS.md`](DECISIONS.md) | **The decision record** — the 18 answered questions, each with the owner's answer **verbatim**, the original framing, and a pointer to the spec it landed in. Read this to expand any register row. |
| [`DPG-migration-guide-nepal-grm.md`](DPG-migration-guide-nepal-grm.md) | The source narrative (Aug 2026). Kept for its reasoning and references; **superseded on facts** by the specs above. |
| [`docs/dpg/00_compliance_status.md`](../../dpg/00_compliance_status.md) | **The external view** — the indicator-by-indicator briefing for ADB's DPG consultant. Written later than these specs and from the code, so it surfaced findings they lacked (container-image licences, project hygiene, the stale README). Reconciled both ways on 2026-08-17 — see the note below. |

---

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| **DPG-01** | `LICENSE` (Apache-2.0) + `NOTICE` + SPDX headers | repo | XS | [01](01-licensing-and-governance-spec.md#dpg-01) |
| **DPG-02** | Dependency licence audit → `docs/dpg/dependency-licenses.md` | repo | S | [01](01-licensing-and-governance-spec.md#dpg-02) |
| **DPG-03** | IP ownership determination (ADB OGC) | non-code | — | [01](01-licensing-and-governance-spec.md#dpg-03) |
| **DPG-04** | Privacy assessment + data-flow diagram | non-code / docs | M | [01](01-licensing-and-governance-spec.md#dpg-04) |
| **DPG-05** | Project hygiene: `SECURITY.md` (private channel — SEAH), `CONTRIBUTING`, `CODE_OF_CONDUCT`, templates | repo | S | [01](01-licensing-and-governance-spec.md#dpg-05) |
| **DPG-06** | Root `README.md` still advertises a Rasa service on port 5005 — it contradicts our own indicator-2 claim | docs | XS | [01](01-licensing-and-governance-spec.md#dpg-06) |
| **DPG-10** | **Test net first** — characterization tests for both LLM surfaces | tests | M | [02](02-llm-agnostic-spec.md#dpg-10) |
| **DPG-11** | `backend/services/llm_client.py` factory (constructs clients; names no model) | backend | M | [02](02-llm-agnostic-spec.md#dpg-11) |
| **DPG-12** | Ticketing surface routed through settings, no hard-coded models | ticketing | S/M | [02](02-llm-agnostic-spec.md#dpg-12) |
| **DPG-13** | `json_object` → `json_schema` + Pydantic validation (7 call sites) | both | M | [02](02-llm-agnostic-spec.md#dpg-13) |
| **DPG-14** | Three latent defects: `gpt-5-nano`, the shadow client, the ASR kwarg | backend | S | [02](02-llm-agnostic-spec.md#dpg-14) |
| **DPG-15** | Degraded mode — verify what exists, close the gaps, add the probe | backend | S/M | [02](02-llm-agnostic-spec.md#dpg-15) |
| **DPG-16** | Env plumbing: `.env.example`, compose, `.env.open` / `.env.openai` | repo | S | [02](02-llm-agnostic-spec.md#dpg-16) |
| **DPG-17** | **One config file** — `backend/config/llm_config.py`, the only registry either surface reads. *Lands before DPG-11/12* | both | S | [02](02-llm-agnostic-spec.md#dpg-17) |

> **Second wave, added 2026-08-18 after the owner reviewed Sprint 1's result.** Four tickets, in the
> rows below: DPG-18, DPG-19, DPG-19b and DPG-15b. ⚠ They start from corrections, and **three of the
> corrections are of this sprint's own claims**: only **two** chatbot call sites are live (not six);
> the other four are the **voice-notes flow, parked for budget** — not legacy, and not to be deleted;
> and `gpt-3.5-turbo` survives on exactly one live path, **SEAH detection**. Decided with it:
> **two models total** — Whisper for transcription, `gpt-5-nano` for everything else (Q-21).
| **DPG-18** | **One entry point** — the layer picks the model and shapes the request; one model | both | M | [02](02-llm-agnostic-spec.md#dpg-18) |
| **DPG-19** | **Meaningful input** — 25-char gate, empty ≠ failure, bounded error text | backend | S/M | [02](02-llm-agnostic-spec.md#dpg-19) |
| **DPG-15b** | **Classification checkpoint moves to submission** — 90 s, late update | backend | M | [02](02-llm-agnostic-spec.md#dpg-15b) |
| **DPG-19b** | **Declare the parked voice-notes flow** + the live/parked pin | backend + docs | S/M | [02](02-llm-agnostic-spec.md#dpg-19b) |
| **DPG-20** | Labelled benchmark set (test data, never production PII) | data | M | [03](03-open-models-spec.md#dpg-20) |
| **DPG-21** | Provider setup + smoke script (HF Inference Providers) | ops | S | [03](03-open-models-spec.md#dpg-21) |
| **DPG-22** | ASR evaluation — Nepali WER on the labelled voice subset | eval | M | [03](03-open-models-spec.md#dpg-22) |
| **DPG-23** | Text-model evaluation + published benchmark table | eval | M | [03](03-open-models-spec.md#dpg-23) |
| **DPG-24** | CI platform-independence job + README badge | CI | S | [03](03-open-models-spec.md#dpg-24) |
| **DPG-25** | T2 vLLM deployment documented and tested once | deployment | M | [03](03-open-models-spec.md#dpg-25) |
| **DPG-30** | **Measure first** — enumerate every egress of grievance text | audit | S/M | [04](04-pii-redaction-spec.md#dpg-30) |
| **DPG-31** | `pii_service.py` deterministic layer (Devanagari digits, Nepali patterns) | backend | M | [04](04-pii-redaction-spec.md#dpg-31) |
| **DPG-32** | NER layer (Presidio transformers) + licence + image-size decision | backend | M/L | [04](04-pii-redaction-spec.md#dpg-32) |
| **DPG-33** | Redaction at the model-call boundary, both surfaces | both | M | [04](04-pii-redaction-spec.md#dpg-33) |
| **DPG-34** | Redaction at the logging / Celery / Redis boundary | backend | M | [04](04-pii-redaction-spec.md#dpg-34) |
| **DPG-35** | Recall measured on a labelled Nepali test set, published | eval | S/M | [04](04-pii-redaction-spec.md#dpg-35) |
| **DPG-36** | Reconcile `11_llm_pipeline_policy.md`'s unbuilt scrubbing claim | docs | S | [04](04-pii-redaction-spec.md#dpg-36) |

---

## Execution order & workstreams

```
Sprint 0  ── DPG-03 (ADB OGC)  ─────────────────────────────────────────▶ weeks, external
          ── DPG-04 (privacy)  ──────────────┐
          ── DPG-01, DPG-02    ──▶ done day 1│  DPG-04 gates the T2 region decision (Q-03)
          ── DPG-05, DPG-06    ──▶ hours     │  added after the compliance audit; DPG-06 before
                                             │  the consultant meeting — it is the front door
                                             │
Sprint 1  ── DPG-10 TEST NET ──▶ MUST LAND FIRST. Everything after it is a refactor
                                  under a net; today there is no net at all.
             DPG-14 (defects) ── cheapest; land it early for the signal
                        │
             DPG-17 (ONE CONFIG) ──▶ before both factories. Build it after them and you
                        │             are merging two registries that already disagree.
             ├── DPG-11 (backend)  ─┐
             └── DPG-12 (ticketing) ─┘  independent of each other — parallelisable;
                        │               both consume DPG-17, neither redefines it
                 DPG-13 (json_schema) ── needs DPG-17 (the capability flag lives on the endpoint)
                        │
                 DPG-16 (env) ── needs DPG-17 (.env.example is generated from its declared_env_vars())
                        │
                 DPG-15 (degraded mode) ── audit can start any time; the probe needs DPG-16
                                             │
Sprint 2  ── DPG-20 (benchmark set) ── can start in Sprint 1, independent of all code
             DPG-21 ─▶ DPG-22 ─▶ DPG-23 ─▶ DPG-24 (CI needs a config that passes)
                                     └────▶ DPG-25 (vLLM; needs a chosen model)
                                             │
Sprint 3  ── DPG-30 (measure) ──▶ MUST LAND FIRST, same reason as DPG-10
             DPG-31 (deterministic) ─▶ DPG-33 ─┐
             DPG-34 ─────────────────────────── ┤─▶ DPG-35* ─▶ DPG-36
                                                │
             ⏸ DPG-32 (NER) + most of DPG-35 ── moved out (Q-12c) to the standalone
                anonymiser-service initiative. *DPG-35 keeps deterministic recall only.
```

**⚠ Sprint 2 is gated on money, not code.** DPG-20 (authoring the benchmark set) is free and can start
during Sprint 1. DPG-22/23/24 all spend inference and **Q-19 is unanswered** — cap DPG-24, price DPG-23,
sequence DPG-22 last.

**Blocking dependencies across sprints:**
- ~~**DPG-04 → the T2 region decision (Q-03).**~~ ⏸ **Moot — T2 parked.** DPG-04 instead has to argue the
  cross-border position for an **indefinite** third-party arrangement, which is the harder version.
- **DPG-03 → the DPG submission itself.** Code can proceed; submission cannot.
- **Sprint 1 → Sprint 2.** There is nothing to point at a second provider until the base URL is a variable.
- **Sprint 1 → Sprint 3 (`redact_for_model`).** Redaction hooks into the client factory; without a single
  chokepoint, the hook has to be pasted into seven call sites and one will be missed.
- **DPG-20 (benchmark set) is the long pole of Sprint 2** and is pure data work. Start it during Sprint 1.
- **DPG-23 → the open-by-default flip.** Sprint 1 keeps today's models as the defaults deliberately: an
  open base URL with proprietary model IDs is a repo that cannot serve a request on a fresh clone. Once
  DPG-23 names the open models, the flip is one file — DPG-17's registry. See
  [`02` §DPG-17](02-llm-agnostic-spec.md#dpg-17) and **Q-10**.

**Conflict note:** DPG-11 and DPG-13 both rewrite the bodies of `LLM_services.py`'s five call sites.
Land DPG-11 first, or rebase. DPG-33 rewrites them a third time — which is why DPG-13's Pydantic models
should be written where DPG-33 can wrap them, not inline in each function.

---

## Conventions — binding for every agent on every ticket

### Required reading, before you touch anything

Every spec in this folder repeats this block. It is not decoration: several tickets here touch
**stable shared services** (`backend/services/`, `backend/task_queue/`) that CLAUDE.md gates.

| Read | Why, for this sprint specifically |
|---|---|
| [`CLAUDE.md`](../../../CLAUDE.md) | Locked architecture. **§Service boundaries** — `backend/services/` is stable-shared; **§Data rules 3 & 5** — no PII in `ticketing.*`, PII fetched fresh; **§Docker-only** — you cannot `pip install` your way through Sprint 3 |
| [`docs/PROGRESS.md`](../../PROGRESS.md) | What is actually built. Read before assuming any of this sprint's premises still hold |
| [`docs/TODO.md`](../../TODO.md) | Open gaps + **🔵 TECH DEBT**, where every deferral from this sprint gets a pointer row |
| [`docs/engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md) | **How we build.** The ten rules; the shared definition of done. Binding on every change here |
| └ [`02_python_services.md`](../../engineering/02_python_services.md) | **DPG-17** (config via settings — the whole ticket) and DPG-11/12/15/31/32/33 — entrypoints hold no logic; the caller owns the transaction |
| └ [`04_testing.md`](../../engineering/04_testing.md) | DPG-10/35 and every ticket — the pyramid, markers, what CI runs, what "pinned" means |
| └ [`03_api_layer.md`](../../engineering/03_api_layer.md) | DPG-15 (the health probe is a route) |
| └ [`06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) | DPG-36 and every spec update — **honesty markers**; when a sprint spec is promoted to a live spec |
| [`docs/deployment/DOCKER.md`](../../deployment/DOCKER.md) | Build, up, migrate, seed, debug. Every verification step in these specs runs in-container |
| [`docs/sprints/README.md`](../README.md) | **The standing deferral rule.** Every deferral logged in `followups/` **and** `TODO.md`, same commit |
| [`docs/README.md`](../../README.md) | Index of the full spec tree — find the live spec your ticket must update |

**Domain specs this sprint modifies** (each ticket names the ones it owns):

| Live spec | Owned by |
|---|---|
| [`docs/services/06_llm_service.md`](../../services/06_llm_service.md) | DPG-11, DPG-13, DPG-14, DPG-15, **DPG-17** (points at the single registry) |
| [`docs/deployment/11_llm_pipeline_policy.md`](../../deployment/11_llm_pipeline_policy.md) | DPG-12, DPG-17, DPG-33, **DPG-36** |
| [`docs/deployment/13_security.md`](../../deployment/13_security.md) | DPG-04, DPG-25, DPG-34 |
| [`docs/services/03_voice_grievance_service.md`](../../services/03_voice_grievance_service.md) | DPG-14 (ASR kwarg), DPG-22 |
| [`docs/rest_chatbot/04_operations_spec.md`](../../rest_chatbot/04_operations_spec.md) | DPG-16 (env vars) |
| `docs/dpg/` **(new folder)** | DPG-02, DPG-04, DPG-23, DPG-25, DPG-35 — the evidence pack |

### Working rules

- **Branch per workstream** off `integration/stage`: `dpg/sprint0-licensing`, `dpg/sprint1-llm-agnostic`,
  `dpg/sprint2-open-models`, `dpg/sprint3-pii`. **Never touch `main`.** See CLAUDE.md §Git workflow.
- **Docker only.** `make wsl-up`, `docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml …`.
  Host CLIs read; they do not build, serve, or migrate. Sprint 3 adds heavy ML dependencies — the temptation
  to `pip install presidio` on the host and "just check it works" is exactly the drift this rule exists to stop.
- **Every ticket ships with its tests in the same commit.** [`TESTS.md`](TESTS.md) is acceptance criteria,
  not a suggestion. Two tickets (DPG-10, DPG-30) *are* the test/measurement work for their sprint.
- **No behaviour change outside the ticket's scope.** Find an adjacent bug → log it in
  [`PROGRESS.md`](PROGRESS.md) → Deviations. Do not fix it. (DPG-14 exists because three such bugs were
  already found during this sprint's planning; that is where they go.)
- **Never write a doc claim you have not verified.** If the code doesn't do it yet, the spec says `⚠ Not built`.
  This sprint exists partly because `11_llm_pipeline_policy.md` says summaries "MUST be PII-scrubbed"
  and nothing scrubs them — see DPG-36. Do not add a second one.
- **Update [`PROGRESS.md`](PROGRESS.md) at every commit** — status, checklist ticks, deviations.
- **Secrets.** `env.local` is gitignored and currently holds a live OpenAI key. Nothing in this sprint
  puts a key in a tracked file, a spec, a test fixture, or a CI log. `.env.open` / `.env.openai` are
  **templates with empty values**, committed; the real values live in `env.local` and GitHub secrets.

### Definition of done — sprint level

- [ ] All 27 tickets ✅ in [`PROGRESS.md`](PROGRESS.md), tests green in CI **without deselecting anything**
- [ ] Every test in [`TESTS.md`](TESTS.md) written and mutation-checked (a test that cannot go red is not a test)
- [x] Every question in [`DECISIONS.md`](DECISIONS.md) answered and recorded **in the spec** — done 2026-08-17, except Q-02 and Q-19 which remain open and are named as blockers where they bite
- [ ] `docs/dpg/` evidence pack complete — every indicator in
      [`00-dpg-context-and-decisions.md` §Evidence pack](00-dpg-context-and-decisions.md#4-dpg-evidence-pack) answered with a link
- [ ] Live specs updated with honest verification markers (the table above)
- [ ] Every deferral logged in `followups/` + `TODO.md`, same commit
- [ ] Sprint summary written as `docs/sprints/2026-08_dpg_llm_independence.md`; this folder moved to
      [`archive/`](../archive/); [`docs/sprints/README.md`](../README.md) tables updated

---

## What this sprint deliberately does **not** do

Named here so nobody re-opens them mid-sprint as scope:

- **It does not require running open models in production.** The DPG Standard requires demonstrating you
  *could*, with minimal configuration changes. Which configuration Nepal actually runs is Q-04, a
  cost/quality decision, and it stays open after this sprint ships.
- **It does not migrate the chatbot off `rasa-sdk`.** The dependency is Apache-2.0 and architecturally
  inert (type shims for the hand-rolled state machine). DPG-02 confirms the licence; nothing more.
- **It does not build an observability stack.** There is none today — no Langfuse, no OTel, no Sentry.
  DPG-34 redacts the log surface that *exists* (`backend/logger/`, Celery payloads in Redis) and writes
  the rule that any future tracing tool must satisfy. Adding the tool is a different sprint.
- **It does not touch the ticketing PII boundary.** `tests/ticketing/test_pii_boundary.py` and
  `test_boundary_policy.py` pin CLAUDE.md rules 2/3 and stay green throughout. Sprint 3 is about
  **free-text egress to third parties**, a different problem from **structured PII at rest**, which
  T3-04 already closed.
