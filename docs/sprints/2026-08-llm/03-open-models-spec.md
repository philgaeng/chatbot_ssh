# Sprint 2 — Open models, benchmarks, and CI evidence (DPG-20…25)

> ## 🤝 HANDOVER — read this before anything else (written 2026-08-20)
>
> **Sprint 1 is finished and merged.** `dpg/sprint1-llm-agnostic` fast-forwarded into
> `integration/stage`; every one of its ten tickets is ✅ in [`PROGRESS.md`](PROGRESS.md), plus five
> unplanned fixes it turned up (D-19, D-26, D-36, D-45, D-47). **Branch from `integration/stage`, not
> from `main`** — `main` is 300 commits behind and nothing here has reached it.
>
> **What Sprint 1 hands you.** The thing this sprint needed and did not have: one file,
> [`backend/config/llm_config.py`](../../../backend/config/llm_config.py), where every model name,
> base URL, timeout and structured-output mode in the product is declared. Both LLM surfaces read it and
> neither owns it; it imports nothing first-party, pinned by a test. **Switching the whole product to
> open weights is now an env-file swap** — [`.env.open`](../../../.env.open) already exists and already
> names candidates. Your job is to prove the swap works and measure what it costs in quality, not to
> build the mechanism.
>
> **⚠ Four things changed under this spec while it sat. Read §0 before planning — they are not cosmetic:**
>
> | | What changed | What it does to your plan |
> |---|---|---|
> | 1 | **A 25-character floor on classification** (DPG-19). Shorter text is *skipped*, not classified | A benchmark item under 25 chars measures the gate, not the model. **Constrains DPG-20's authoring.** |
> | 2 | **A 30-second interactive budget** (DPG-15b) | p95 latency stopped being a table row and became **pass/fail**: over ~30 s and the complainant never sees their own classification. |
> | 3 | **The SEAH benchmark data must stay OUT of git** — owner's decision, 2026-08-19 | Directly contradicts DPG-20's "commit under `tests/data/benchmark/`". **Both are right, about different data.** §0 resolves it; do not resolve it yourself. |
> | 4 | **CI is green** — first time since 2026-08-08 (D-26) | DPG-24's "green on the integration branch" is now reachable, and **red now means something.** Do not add a job that normalises red. |
>
> **✅ Decided [Q-21](DECISIONS.md#q-21), 2026-08-18, re-confirmed 2026-08-20 — do not re-open it:** the
> open configuration ships **two models** — one text model for every text task, one for transcription —
> mirroring the closed pair. **Benchmark many, ship two.** `.env.open` shipped three for two days after
> that decision and is now collapsed to match. The consequence is a selection rule, not just a count:
> with one model doing everything you **rank candidates by their worst per-task score, not their mean**,
> and the binding tasks are SEAH recall and the complainant-facing summary. See [DPG-23](#dpg-23).
>
> **✅ Also decided 2026-08-20:** the 30 s classification budget is **a knob, not a wall** — measure and
> raise it to 45 s or 60 s if a better model needs it, with the cost stated (see [DPG-23](#dpg-23): what
> you spend is the review step for the slow tail, not the classification itself). And **"benchmark many"
> means a shortlist** — *"not so many are decent candidates"* — so name the handful and why each made or
> missed the list.
>
> **✅ [Q-19](DECISIONS.md#q-19), the budget, was answered 2026-08-20 — every ticket is unblocked.** A few
> hundred USD, owner-funded. **But read what it covers before you spend it:** *"all the inferences during
> first months of demo in 2 districts"* — the pilot's own classification traffic comes out of the **same**
> envelope as your model sweep. A benchmark that eats the pilot's runway has not saved money, it has moved
> the failure. **Price DPG-23 against what is left after an estimate of pilot traffic**, and set the hard
> token cap on the Hugging Face account *before* DPG-24's first run, because that job is the only cost
> that outlives the demo months.
>
> **⭐ And it creates a deliverable that was not in this spec: a costed proposal to the Nepal Government** —
> *"the choices they need to make moving forward with realistic budget."* DPG-23's cost-per-1,000-grievances
> row and DPG-25's costed T2 proposal are its two halves. That gives [DPG-25](#dpg-25) a named audience and
> a real use instead of a costing nobody asked for, and it gives it the scale anchor it lacked: **two
> districts over the first demo months**, extrapolated to national — stated as an extrapolation.
>
> **Suggested order:** **DPG-20** (authoring, free) and **DPG-21** (needs only an HF token) first, because
> everything else consumes them; then **DPG-23**, priced; then **DPG-24** with its cap set; **DPG-22** last
> (audio is the most expensive per item and voice is not live); **DPG-25** any time — it is a document.
>
> **⚠ Half of DPG-20 is already in flight — do not duplicate it.** The SEAH slice has a written method
> ([`docs/models/01_seah_detection_benchmark.md`](../../models/01_seah_detection_benchmark.md)), a
> collection workbook, and a request already sent to the Nepal team for real seed cases. Read that
> document before authoring anything SEAH-shaped. The **general** classification/extraction slice —
> categories, districts, code-switching, Devanagari digits — is unstarted and is yours.
>
> **How this sprint works** — same as Sprint 1, and it is binding: read
> [`../README.md`](../README.md) and [`../../engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md)
> first; every ticket ships its tests in the same commit; every deferral gets a `followups/` doc **and** a
> `TODO.md` row in that same commit; Docker only, never the host; and never write a claim into a document
> you have not verified against the code. Sprint 1's deviation log is 47 rows long mostly because that
> last rule was enforced — **treat a wrong sentence in a spec as a defect, and log it.**


> Branch `dpg/sprint2-open-models` · **Depends on Sprint 1** (there is nothing to point at a second
> provider until the base URL is a variable). **DPG-20 does not depend on Sprint 1 — start it during Sprint 1.**
> **Goal:** a working, benchmarked open-weights configuration, with evidence.
> **Why:** this is what turns the indicator-4 claim into a demonstrated fact, and it is the configuration
> you carry forward to T2.

---

## Required reading

1. [`CLAUDE.md`](../../../CLAUDE.md) — §Docker-only, §Service boundaries, §Environment variables
2. [`docs/PROGRESS.md`](../../PROGRESS.md) → [`docs/TODO.md`](../../TODO.md)
3. [`docs/engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md) — the ten rules
4. └ [`04_testing.md`](../../engineering/04_testing.md) — **binding**: what CI runs, markers, and why a benchmark is not a test
5. └ [`06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) — honesty markers; a benchmark table with a blank cell is `⚠ Not measured`, never an implied pass
6. [`docs/deployment/DOCKER.md`](../../deployment/DOCKER.md)
7. [`docs/deployment/13_security.md`](../../deployment/13_security.md) — DPG-25 extends it (private subnet, TLS, key policy)
8. [`docs/services/03_voice_grievance_service.md`](../../services/03_voice_grievance_service.md) — the ASR consumer; DPG-22's numbers land here
9. [`docs/sprints/README.md`](../README.md) — the standing deferral rule
10. [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md) — §2 the ladder, §4 the evidence pack
11. [`02-llm-agnostic-spec.md`](02-llm-agnostic-spec.md) — the nine call sites this sprint benchmarks

**⚠ Model tags move fast.** Every model name below is a **candidate**, not a decision. The durable part is
the selection criteria: **Apache-2.0 or MIT · strong multilingual coverage including Nepali · reliable
guided decoding · fits one 24 GB GPU at 4-bit.** Check the current catalogue at ticket time and record
what you actually chose, with the date.

**⚠ And the licence limb of that filter is provisional.** "Apache-2.0 or MIT" is the *safe* filter, not a
known requirement — it excludes Llama and Gemma class models on their community licences, and on a
low-resource language that exclusion may cost real quality. The compliance briefing asks the consultant
directly whether restricted-use open weights satisfy indicator 4
([`00_compliance_status.md`](../../dpg/00_compliance_status.md) Q-04-02). **Record which models the
filter excluded and why**, so that if the answer loosens it, re-running DPG-23 is a candidate-list edit
rather than a re-design.

---

## §0 — Corrections carried into this sprint

| The guide assumes | Reality | Effect |
|---|---|---|
| One LLM surface to benchmark | Two — see [`02`](02-llm-agnostic-spec.md) §0. Ticketing's case findings and **complainant-facing** resolved summary also need a model choice | DPG-23 covers six task types, not four |
| Classification runs on `gpt-3.5-turbo` | It runs on `gpt-5-nano` (`LLM_services.py:247`) | The "current" column of the benchmark must name the real baseline, or the delta is meaningless |
| `pytest tests/test_llm_services.py` in the CI job | That file does not exist today; Sprint 1's DPG-10 creates `tests/backend/test_llm_services.py` and `tests/ticketing/test_llm_client.py` | DPG-24's job runs the real paths |
| CI is greenfield | `.github/workflows/ci.yml` already ran **four** parallel gates — `backend-tests` (full Postgres + Redis service block, all three Alembic streams), `ui-checks`, `webchat-checks`, `docs-links` | DPG-24 adds a **fifth job to an existing file**, following its conventions — not a new workflow file with its own dialect. ⚠ This spec said "three" and named only three of the four until 2026-08-17; `webchat-checks` was the one missed. **Job line numbers deliberately removed**: they were re-pointed twice and rotted twice, `.yml` citations are not covered by `tests/repo/test_doc_code_refs.py`, and the job *names* are stable |
| The candidate filter is settled: Apache-2.0 / MIT | **It is gated on the consultant.** Several of the strongest multilingual models ship under bespoke community licences with use restrictions (Llama, Gemma). Whether those count as open alternatives for indicator 4 is an open question — [`00_compliance_status.md`](../../dpg/00_compliance_status.md) Q-04-02 | The filter may be **loosened** before DPG-23 runs, which would widen the candidate field and may materially change the Nepali quality result. **Do not build the benchmark harness around a frozen licence filter** |

### §0.1 — What Sprint 1 changed under this spec (added 2026-08-20)

Sprint 1 shipped after this spec was written. These are not clarifications; each one changes a ticket.

| # | Sprint 1 fact | Where | What it does to this sprint |
|---|---|---|---|
| **A** | **`backend/config/llm_config.py` exists** — every model name, base URL, timeout and structured-output mode declared once, read by both surfaces, importing nothing first-party | DPG-17 | The migration mechanism is **built**. This sprint measures and chooses; it does not plumb. A model name written at a call site is a regression Sprint 1 removed, pinned by `tests/backend/test_llm_config_pins.py` |
| **B** | **`.env.open` already names candidates** — `openai/gpt-oss-20b` on **every** text task and `MODEL_ASR=openai/whisper-large-v3`. It shipped a `gpt-oss-120b` for translation and SEAH findings for two days after Q-21 said two models, and was collapsed on 2026-08-20 | DPG-16 | DPG-21/23 **validate or replace** these, they do not choose from a blank sheet. ⚠ They are placeholders written without measurement — treat them as a hypothesis, and record the date and the evidence when you confirm or drop each one. **DPG-21 has since measured the text half** (`gpt-oss-20b`: all six capabilities, `json_schema` honoured); the ASR half is unmeasured and its endpoint 404s (**D-53**) |
| **C** | **`MIN_CLASSIFY_CHARS=25`** — text shorter than 25 characters returns `{"skipped": "too_short"}` and is never sent to a model | DPG-19 | **Constrains DPG-20.** A benchmark item under the floor measures the gate, not the model, and would silently deflate every accuracy number. Author above it, and include a *deliberate* handful below it to pin the gate itself |
| **D** | **The interactive budget is 30 s** — `CLASSIFICATION_WAIT_SECONDS=30`, `TIMEOUT_CLASSIFY_INTERACTIVE=30`. The complainant fills contact and OTP forms while classification runs, then reviews the result | DPG-15b | **p95 latency is now pass/fail, not a metric.** A model that answers correctly in 45 s fails the product: the review step is skipped and the grievance is filed unreviewed. Measured `gpt-5-nano` today is 14–20.5 s, so the headroom is thin |
| **E** | **`_PROFILES` in `llm_config.py` decides `json_schema` vs `json_object` vs prompt-only, per model prefix** | DPG-13/17 | DPG-21's capability matrix has a **code** destination, not only a doc. A matrix that lives only in `open-model-configuration.md` is a claim nothing enforces; the ladder in `response_format_for()` is what actually runs |
| **F** | **Four voice-flow functions are declared PARKED** — `PARKED_TASKS` in `registered_tasks.py`, with docstring headers | DPG-19b | Confirms DPG-22's sequencing (last, Q-19). ⚠ It also means **nothing exercises the ASR path in production**, so DPG-22's numbers describe a path that is switched off. Say so where they are published |
| **G** | **CI is green on `integration/stage`** — first time since 2026-08-08, 1398 tests | D-26 | DPG-24's "green on the integration branch" is reachable. And the D-26 lesson binds: *a permanently red build is indistinguishable from one nobody watches.* A live-API job **will** go red on provider outages — that is Q-17's whole subject. Decide the branch-protection question before the job exists, not after the first outage |
| **H** | **`ci.yml` changed shape, and the fifth job now exists.** `docs-links` also checks the **root** `*.md` and backticked paths; `backend-tests` pins its apt mirror and deselects `-m "not live_llm"`; and `dpg-platform-independence` was added by DPG-24. Five jobs, in file order: `backend-tests`, `ui-checks`, `webchat-checks`, `docs-links`, `dpg-platform-independence` | D-26, D-48, DPG-24 | Read the file before touching the fifth job. **Line numbers are not repeated here** — this row twice carried numbers that were stale within days, and nothing tests a `.yml` citation |

### §0.2 — ⚠ The benchmark data is split, and DPG-20's acceptance is wrong as written

This spec says *"Commit under `tests/data/benchmark/`"* and treats a committed synthetic set as the
publishable artefact for Q-04-04. On **2026-08-19 the owner decided the opposite** for the SEAH
slice, and wrote the reason into
[`docs/models/01_seah_detection_benchmark.md`](../../models/01_seah_detection_benchmark.md) §3.3:

> *"Three hundred realistic Nepali harassment complaints sitting in it will be read as leaked case data
> by somebody, regardless of how the file is labelled."*

**Both positions are right, about different data.** Resolve it by splitting the set rather than choosing
a side:

| Slice | Lives | Why |
|---|---|---|
| **General** — categories, districts, dust/road-hazard narratives, code-switching, Devanagari digits | ✅ **Committed** under `tests/data/benchmark/` | It is the reproducibility artefact indicator 4 wants, and nothing in it reads as a case file |
| **SEAH** — harassment and abuse narratives | ❌ **Never committed**, never seeded into the demo DB | §3.3 above. Held by the project owner |

**The cost of the split, stated once and then repeated wherever the numbers appear:** the SEAH numbers are
**not independently reproducible from the repository**. That is a real weakness in the evidence pack and
it is the right trade. ⚠ **Do not "fix" it by committing the SEAH set** — and do not quietly drop the SEAH
numbers either, because sensitive-content recall is the one metric with a safeguarding consequence.


---

## DPG-20 — The labelled benchmark set {#dpg-20}

**Do this before migrating anything.** It is the long pole of the sprint, it is pure data work with no
code dependency, and you need it permanently for regression testing regardless of DPG.

### What to build

A few hundred grievances, labelled by hand: **category**, **severity**, **district**, and for the voice
subset, a **verbatim transcript**. Plus, for Sprint 3, **PII spans** (see DPG-35 — label them once, here,
rather than twice).

### ⚠ Provenance — **decided (Q-15): synthetic in phase 1**

> **DECIDED 2026-08-17.** Phase 1 is **synthetic, committed**; a hybrid pass follows once the live project
> has generated real grievances. Read together with **Q-16 — there is no budget or staff time for
> labellers** — this reshapes the ticket: it is **a small authored set that grows with the project**, not a
> labelling programme. The 300-text / 50-voice target below is **aspirational, not resourced**; treat it as
> a direction and record what was actually built.
>
> ✅ **Two things this makes easier, worth noticing rather than treating it as a downgrade:** synthetic data
> can deliberately cover the edge cases that matter most and are rarest in real traffic — Devanagari-digit
> phone numbers, third-party names, code-switching — which is exactly what
> [T-31-a](TESTS.md) needs; and a fully synthetic committed set is publishable, which is the artefact
> Q-04-04 asks about. **Phase 1 is the honest version of the evidence, not a compromised one** —
> provided every published number says it came from synthetic data.

**This is committed test data. It cannot be production PII.** The three routes, kept for the phase-2 pass:

| Route | Pros | Cons |
|---|---|---|
| **Synthetic, authored by Nepali-speaking staff** | No consent problem, no leak risk, can deliberately cover edge cases (Devanagari digits, third-party names, code-switching) | Won't reproduce real transcription noise or the messiness of genuine free text; risks measuring a cleaner problem than production |
| **Real grievances, redacted + consented** | Genuinely representative | Consent is slow; redaction before labelling is circular (Sprint 3 is what redacts); the third-party PII problem applies to the *labels* too |
| **Hybrid** ⭐ | Synthetic for the committed public set; a held-out real set kept **outside the repo** for the numbers that matter | Two sets to maintain; the published number must say which set it came from |

**Phase 1 = synthetic; phase 2 = hybrid** (Q-15). The committed set makes CI and the DPG evidence
reproducible; the later held-out real set is what will keep the reported accuracy honest. **The published
benchmark must state the provenance of every number** — and in phase 1 that sentence is doing real work,
because **every** number will come from authored data. A 91% on synthetic data reported as if it were
production accuracy is the kind of claim that discredits an otherwise sound submission.

### Steps

1. ~~Decide provenance~~ — **decided: synthetic (Q-15)**. Record it in the set's README with the date and
   the phase-2 intent, so a later reader knows the hybrid pass was planned rather than forgotten.
2. Build the set. Cover the real distribution: the KL Road categories from `CLASSIFICATION_DATA`, the
   districts actually in scope, Nepali and English and code-switched text, and voice-origin text (which
   is structurally different — no field boundaries, self-identification in the opening sentence).
3. Commit under `tests/data/benchmark/` with a `README.md` stating provenance, size, label definitions,
   inter-labeller agreement if more than one person labelled, and the date.
4. Add the licence of the data itself. A DPG's data dependency is in scope for indicator 4 — the
   questionnaire says so explicitly: *"For AI systems, please consider dependencies for the code, the
   model and **the data**."*
   > **The data limb is narrower here than it looks, and that is worth stating.** This system does no
   > training and no fine-tuning — every call is zero-shot prompting against an author-maintained category
   > taxonomy. So there is **no training-data licence question at all**; what is missing is an *evaluation*
   > set, which is exactly what this ticket builds. Whether the DPGA also expects the eval set **and the
   > prompt templates** published as artefacts is open with the consultant
   > ([`00_compliance_status.md`](../../dpg/00_compliance_status.md) Q-04-04). If yes, the committed
   > synthetic half of the hybrid set is already the answer — **which is a second reason to prefer hybrid.**

### Acceptance

> ⚠ **Amended 2026-08-20 — read [§0.2](#02--the-benchmark-data-is-split-and-dpg-20s-acceptance-is-wrong-as-written)
> first.** The line below is right for the general slice and wrong for the SEAH slice, and the SEAH half
> is already in flight under [`docs/models/01_seah_detection_benchmark.md`](../../models/01_seah_detection_benchmark.md).

- [x] **General slice** committed under `tests/data/benchmark/` with a provenance README —
      `general_classification.jsonl`, **105 items**, 23 of 24 categories
- [x] **SEAH slice NOT committed** — held by the owner, never seeded into the demo DB (§0.2), and every
      published SEAH number says it is not reproducible from the repository. **Pinned in both
      directions** by T-20-h: no committed item is marked `sensitive`, and ≥5 `seah_confusable`
      negatives are present — the false-alarm half of the measurement stays
- [x] **Every item ≥ 25 characters**, because `MIN_CLASSIFY_CHARS` skips shorter text without calling a
      model (§0.1-C) — plus a *deliberate* handful below the floor, labelled as gate fixtures rather than
      benchmark items, so the gate itself is pinned and nobody later "fixes" the short ones into the set
      — **8 fixtures in `gate_fixtures.jsonl`**, straddling the floor both ways (T-20-a/b)
- [x] Categories drawn from the live taxonomy, not invented — T-20-c asserts against the **live**
      catalogue (DB when seeded, CSV otherwise), never a copy inside the test
- [ ] ⏸ **Voice subset has verbatim transcripts** — **not built, and it cannot be here.** The set has
      **6 `voice_origin` items and no audio**: transcript-*shaped* text, which measures the classifier
      on voice-shaped input but yields **no WER**. Blocks DPG-22 →
      [`followups/no-audio-subset-for-asr-benchmark.md`](followups/no-audio-subset-for-asr-benchmark.md)
- [x] PII spans labelled (serves DPG-35 — do it once) — as **substrings, not offsets**, so an ambiguous
      or stale span fails the build rather than yielding a silently wrong offset (T-20-f)
- [x] Data licence stated — **CC0-1.0**, with the boundary written down: the category *strings* are
      project material under Apache-2.0, not CC0
- [x] No production PII in any committed file — **verified, not assumed**: T-20-j is an `@integration`
      test asserting no committed item is byte-identical to a stored grievance, against the seeded
      database, and confirmed **not vacuous** (the table holds 289 descriptions)

### Acceptance — amended for the phased scope

- [x] Every number this set produces is labelled **synthetic (phase 1)** wherever it is published —
      stated in the README's status line and carried into `model-benchmarks.md`
- [x] The README records the phase-2 hybrid intent and what would trigger it (live project data) — §3
- [x] Edge cases deliberately covered — Devanagari digits, third-party names, code-switching — since
      authored data is the only place they can be guaranteed. **T-20-g pins them present**, including
      at least one phone number in Devanagari digits, the case a redactor matching `\d` passes without
- [x] Actual size recorded, against the aspirational target, with no implication that labellers were
      funded — README §7: **105 against ~300 text, 6 against ~50 voice**, and *"the 300/50 target was
      aspirational and never resourced"*. T-20-i fails the build if the README's counts go stale

### ✅ Questions — answered

- **Q-15** — ✅ **synthetic in phase 1**, hybrid once the project is live.
- **Q-16** — ✅ **no labeller budget or staff time**; the set grows with the project. The target is a
  direction, not a plan.
- **[Q-19](DECISIONS.md#q-19)** — ✅ **answered 2026-08-20: a few hundred USD, owner-funded.** This ticket
  was always free (authoring, not inference); the tickets that consume it are now funded too. ⚠ **The
  envelope is shared with the pilot's own traffic**, so the size of this set has a cost consequence
  downstream — every item is re-run per candidate in DPG-23. **Size it for signal, not for volume.**

---

## DPG-21 — Provider setup and smoke test {#dpg-21}

**Hugging Face Inference Providers** is the T1 recommendation, for a reason specific to indicator 4: it
routes across multiple back-end providers (Together, Groq, Novita and others) selected in the model path
— so your evidence shows independence from *any single vendor*, not merely from OpenAI.

Base URL: `https://router.huggingface.co/v1`
Key: Hugging Face account → Settings → Access Tokens → New token with **Inference** permission.

### Verify before writing any code against it

```bash
curl https://router.huggingface.co/v1/chat/completions \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"<candidate-model>",
       "messages":[{"role":"user","content":"Reply with the JSON {\"ok\":true}"}]}'
```

Then verify the thing that actually matters for this codebase — **`json_schema` support** — because
DPG-13 depends on it and the degradation ladder exists precisely because it is not universal. Send one
request with a `response_format` of `{"type":"json_schema", ...}` and record whether it is honoured,
silently ignored, or rejected. Do this for **every** candidate provider, and put the results in the doc.

Alternatives, all OpenAI-compatible, for comparison or failover:

| Provider | Base URL |
|---|---|
| Together AI | `https://api.together.xyz/v1` |
| Fireworks | `https://api.fireworks.ai/inference/v1` |
| DeepInfra | `https://api.deepinfra.com/v1/openai` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter (aggregator, for benchmarking) | `https://openrouter.ai/api/v1` |

### Steps

1. Obtain the key; store it in `env.local` and as a GitHub secret (`HF_TOKEN`) for DPG-24. **Never in a tracked file.**
2. Write `scripts/ops/llm_smoke.py` — a committed, re-runnable script that exercises chat, structured
   output, and transcription against whatever `LLM_BASE_URL` is configured, and prints a capability
   report. This is the tool every later ticket uses, and the one a reviewer can run themselves.
   ✅ **Built.** It probes **six capabilities per model**, **verifies each licence from the model card at
   probe time** rather than trusting a table, and prints a `ModelProfile` tuple to paste into
   `_PROFILES`. Its sharpest property: **accepted-and-ignored is not a pass** — the probe schema
   requires a field the prompt never mentions, so a provider that silently drops `response_format`
   is caught and downgraded to the rung it actually honoured.
3. Keep the shortlist in `scripts/ops/llm_candidates.json`, **as data** — shortlisted models with a
   reason each, excluded ones with a licence and a reason — so a loosened Q-04-02 is an edit and not a
   redesign. ✅ **Built:** 7 shortlisted, 6 excluded, catalogue read 2026-08-20.
4. Record the capability matrix in `docs/dpg/open-model-configuration.md`.

### Acceptance

- [ ] ⚠ **`HF_TOKEN` in `env.local` and in GitHub secrets; not in any tracked file** — **half done.**
      It is in `env.local` and in no tracked file. It is **not** a GitHub secret, and neither are the
      `DPG_MODEL_*` repo variables: that is the one step nobody working in this repository can take,
      and it is why DPG-24's job has never run
- [x] `scripts/ops/llm_smoke.py` committed and runnable in-container against any base URL — probes
      **six capabilities per model** and verifies each licence **from the model card at probe time**
- [ ] ⚠ **Capability matrix (chat / `json_object` / `json_schema` / audio) recorded per candidate
      provider** — **6 of 7 candidates complete**, and the matrix renders three states (`✅` / `❌` /
      **`⚠ blocked`**), because a cell blocked by a 402 is not a measured failure (T-21-a/c/e). The
      seventh is `Apertus-70B`, which **refused a grievance** (**D-54**)
- [x] **The matrix landed in `_PROFILES` in `backend/config/llm_config.py`, not only in the doc** (§0.1-E).
      That table is what `response_format_for()` reads at runtime to pick the strictest mode a model
      actually honours; a matrix that lives only in prose is a claim nothing enforces, and the first
      symptom is a silently-ignored `json_schema` producing malformed output under load.
      ⭐ **That symptom is not hypothetical: `Qwen3.5-9B` accepts `json_schema` and silently ignores
      it**, which is why it carries a `json_object` row while the rest of the family carries
      `json_schema`. And `gpt-oss` and Qwen both **reason**, where `DEFAULT_PROFILE` assumed an
      overhead of 0 — the D-40 trap that was sitting under the repository's own open configuration
- [x] `docs/dpg/open-model-configuration.md` updated — with the measured matrix, the
      excluded-on-licence list, and what is **not** yet true

---

## DPG-22 — ASR evaluation {#dpg-22}

**The easiest win, with peer-reviewed Nepali evidence.** `whisper-1` **is** Whisper — OpenAI hosts a model
whose weights are already Apache-2.0, so switching to the open weights is functionally near-identical
while removing a closed dependency.

A 2026 comparative study fine-tuned six architectures on the **OpenSLR SLR54 Nepali corpus (~165 hours)**,
evaluating on OpenSLR, FLEURS and Common Voice:

| Model | Nepali WER | Licence — **verified from the model card, 2026-08-20** | Verdict |
|---|---|---|---|
| **Whisper-Large-v3-Turbo** | **14.76%** | **MIT** | ✅ Best-equal, drop-in for `whisper-1`. Passes the filter |
| **Whisper-Large-v3** | — | **Apache-2.0** | The `.env.open` placeholder. Passes |
| **IndicWav2Vec** (`indicwav2vec_v1_nepali`, AI4Bharat) | **14.89%** | **MIT** | ✅ Statistically tied, far smaller, CTC decoder much faster |
| MMS-1B (`mms-1b-all`) | worse | **CC-BY-NC-4.0** | ❌ Cannot ship. Excluded on licence, not on quality — as predicted |
| Whisper-Medium · XLSR-53 · Conformer-Hi | worse | Apache-2.0 | — |

> **The licence column above is measured, and it corrected this table.** Until 2026-08-20 it read
> `Apache-2.0` for Whisper-Large-v3-Turbo. It is **MIT** — both pass the filter, so no decision changes,
> but a table that a reviewer checks against a model card has to survive the check. The WER column is
> **not** measured here: it is the published study's, and this project has no audio to reproduce it with
> ([`followups/no-audio-subset-for-asr-benchmark.md`](followups/no-audio-subset-for-asr-benchmark.md)).

Two takeaways. **~85% word accuracy on Nepali is achievable under Apache-2.0** — usable for grievance
intake with on-screen confirmation, and above the threshold where correcting is slower than re-entering.
And the improvement path is concrete: fine-tuning on SLR54's 165 openly-licensed hours is a single-GPU
job, and **that fine-tune released openly would be a genuine DPG contribution**, because permissively-
licensed Nepali speech tooling barely exists.

Also benchmark **Omnilingual ASR** (covers Nepali, 300M–7B variants). The 300M model is worth
testing specifically for low-connectivity districts.

> ⚠ **Its licence is unresolved, and this line used to assert Apache-2.0.** The 2026-08-20 probe
> **could not resolve an Omnilingual ASR model card publicly**, so nothing verified that claim and it
> must not be repeated downstream. Resolve the licence before spending anything on it; if it cannot be
> resolved, it cannot ship, on the same rule that excluded MMS-1B.

### ⚠ There is no baseline — this is now confirmed, not suspected

> **ANSWERED 2026-08-17 (Q-13.2): voice transcription is not live at all**, and the reason is not the
> `language_code` bug — it is that **there is no LLM budget** for transcription. *"I can shoulder a few
> calls per day to nano, not transcription."*
>
> Two consequences, and the spec had anticipated the first as a caveat rather than the live case:
> 1. **There is no `whisper-1` baseline to compare against.** The honest framing is *"we shipped a working
>    ASR path where there was none"*, **not** *"we matched the incumbent"*. Both are fine; conflating them
>    is not. The "Current (closed)" column in DPG-23's table is **empty for ASR, and says why.**
> 2. **No field evidence exists on DPG-14.3's suspected `language_code` bug** — nobody has run a voice note
>    through it. The in-container SDK signature check is therefore **the only** way to resolve it.
> 3. ⏸ **Sequence this ticket last in Sprint 2** ([Q-19](DECISIONS.md#q-19)). Audio is the most expensive
>    input per item and, with voice not live, the least decision-relevant right now. ✅ The budget answer
>    (2026-08-20) does not change this: a funded envelope shared with the pilot makes *order* matter more,
>    not less — spend it on the decisions that are live first.

### ⚠ And decide what "good enough" means before you measure

If open-weights Nepali ASR lands materially worse than the incumbent, the honest options are: accept
documented degradation on voice while text stays at parity; keep ASR on a hosted provider and **disclose it
as a remaining closed dependency**; or fund a Nepali fine-tune. Whether the DPGA accepts *"functional, with
documented degradation"* or expects parity is open with the consultant
([`00_compliance_status.md`](../../dpg/00_compliance_status.md) Q-04-03) — and the answer decides
whether voice intake can exist at all in an open configuration. **Measure first, but record the threshold
question in the doc**; do not let a bad WER quietly become a decision nobody made.

### Steps

1. Run each candidate over DPG-20's voice subset; compute WER against the verbatim transcripts.
2. Measure p95 latency per candidate at realistic audio lengths, and cost per 1,000 minutes.
3. Check the **actual current behaviour** as the baseline column (see the caveat above).
4. Verify the licence of each candidate **from its model card at evaluation time**, not from this table.
5. Record in `docs/dpg/model-benchmarks.md`.

### Acceptance

- [ ] ⏸ **WER measured for at least Whisper-large-v3-turbo and one alternative, on this project's own
      data** — **blocked twice, and both blockers are logged.** There is no audio
      ([`followups/no-audio-subset-for-asr-benchmark.md`](followups/no-audio-subset-for-asr-benchmark.md))
      **and** the configured open ASR endpoint 404s — the router serves no `/v1/audio/*` route
      (**D-53**, [`followups/the-open-config-has-no-working-asr-endpoint.md`](followups/the-open-config-has-no-working-asr-endpoint.md)).
      Fixing either alone does not unblock it
- [x] Baseline column **empty for ASR with the reason stated** — voice is not live and never has been
      (Q-13.2), so there is no incumbent number to beat. `model-benchmarks.md` names **both** reasons
      in the cell: no baseline, and no audio in the set
- [x] Licence verified per candidate, at evaluation date — **from the model card at probe time**, which
      corrected this ticket's own table: turbo is **MIT**, not Apache-2.0; `indicwav2vec_v1_nepali`
      **MIT**; `mms-1b-all` **cc-by-nc-4.0 ❌ cannot ship**, as predicted; **Omnilingual could not be
      resolved publicly** and its Apache-2.0 claim is therefore unverified
- [ ] ⏸ **p95 latency and cost recorded** — not reachable without audio or an endpoint
- [ ] ⚠ **`docs/services/03_voice_grievance_service.md` updated with the chosen model and its measured
      WER** — **updated, but with neither.** It carries the verified licence table and the two
      blockers; no model is chosen and no WER exists
- [x] The SLR54 fine-tune opportunity logged as a followup (a genuine DPG contribution; out of scope
      here) — [`followups/slr54-nepali-asr-finetune-as-a-dpg-contribution.md`](followups/slr54-nepali-asr-finetune-as-a-dpg-contribution.md)

---

## DPG-23 — Text-model evaluation {#dpg-23}

> **⚠ The stakes changed 2026-08-17 (Q-04): production will run the open configuration.**
> The old framing — *"the DPG claim does not depend on which configuration Nepal runs"* — is still true of
> the Standard, but it is no longer true of this ticket. The decision is **cost-driven, with the closed
> models held in reserve if government users report quality problems**, which means:
>
> - **This benchmark is no longer only DPG evidence. It is the pre-flight check on a production change.**
>   A gap you under-measure here is a gap complainants and officers experience.
> - **It is also stronger DPG evidence than the Standard asks for.** Indicator 4 requires demonstrated
>   *replaceability*; you will be running the open path in production. **Say that plainly in the
>   submission** — and keep the closed configuration reachable by env var so the reserve is real.
> - **The escalation path needs to exist before it is needed.** *"If users complain we benchmark with
>   closed"* only works if the closed configuration still passes CI and someone can flip it in minutes.
>   DPG-17's registry makes that one file; the acceptance below pins it.
>
> ✅ **[Q-19](DECISIONS.md#q-19) answered 2026-08-20 — this ticket is funded, within a few hundred USD.**
> Still price it first: items × models × tasks is knowable arithmetic, and a few hundred short texts on
> per-token pricing is plausibly tens of dollars. ⚠ **The envelope is shared with the pilot's own inference
> across two districts**, so the number that matters is not "can we afford the benchmark" but "what is left
> for the pilot after it". **Estimate pilot traffic first, subtract, then size the sweep** — and let the
> cheap first pass eliminate weak candidates before the full set is spent on the survivors.

### ✅ What this ticket built — read the harness before re-deriving it

| Artefact | What it is |
|---|---|
| [`scripts/ops/llm_benchmark.py`](../../../scripts/ops/llm_benchmark.py) | The harness. It runs **the product's own call path**, not a reimplementation; proves the credential before scoring anything; scores classification **set-level** and detection **recall-first with a confusion matrix**; meters real token usage; and **refuses a `--seah-set` inside the repo** (§0.2, held in code rather than in memory) |
| [`scripts/ops/llm_candidates.json`](../../../scripts/ops/llm_candidates.json) | The shortlist — **7 candidates and 6 exclusions, as data**, each with its reason, so a loosened Q-04-02 is an edit rather than a redesign. Licences here are `expected_*`; the real ones are read from the model card at probe time |
| `InventionMeter` (in the harness) | Counts off-catalogue categories from the **resolution log**, not from the returned categories — because `resolve_categories` (D-51) repairs them first, so reading the output would report a flattering 0/105 for every model. Pinned by a test that goes red if either log line is reworded |
| [`docs/dpg/model-benchmarks.md`](../../dpg/model-benchmarks.md) | Where the numbers are published, with every unmeasured cell naming its blocker |

**The closed baseline is measured; the open column is not.** `gpt-5-nano` over 105 items: **F1 0.771**
(P 0.740 / R 0.805), exact-set 0.676, SEAH false-alarm 6.7%, p95 **24.6 s** (passes 30 s) / p99 40.6 s
(does not), and **93.8% of completion tokens are reasoning**. ⚠ **No model has been chosen**, which was
this ticket's point — see [PROGRESS.md](PROGRESS.md) §"What a reader should not conclude".

### ⚠ Two constraints Sprint 1 added (2026-08-20)

**1. p95 latency is a threshold to *measure against*, not a row to fill in** (§0.1-D).

⭐ **Decided 2026-08-20: the 30 s budget is a knob, not a wall.** *"We will measure and adjust the number to
45 s or 60 s if needed."* So a candidate that is more accurate and slower is **not** automatically
disqualified — but the raise has to be a stated decision with the cost beside it, not a config tweak that
lands in a diff.

**Understand what the wait actually is before you spend it.** Classification is triggered when the
grievance form completes; the complainant then fills the contact and OTP forms while it runs. The poll
happens **after they submit**, and it only ever catches the slow tail — most complainants never wait at all.
`CLASSIFICATION_WAIT_SECONDS` bounds that tail.

**And what timing out costs, which is less than it sounds and more than nothing.** From
`backend/actions/grievance_intake/classification.py`:

> *"the review step runs **after** submission, so the grievance is already filed and the classification
> reaches the officer through the two-minute ticketing sync whether or not the complainant ever sees it.
> A longer wait buys silence."*

Nothing is lost operationally — the ticket exists, the officer gets the classification. What is lost is
**the complainant's chance to see and correct how their own grievance was understood**, which is the
accountability half of the feature. So the trade is *seconds of spinner* against *the review step for the
users in the slow tail* — and the ceiling is not technical, it is how long someone will watch a spinner on
a rural mobile connection after they have already submitted.

**What to do:** measure p95 and p99 per candidate; report both against 30 / 45 / 60 s; and if the best
model needs the raise, say what fraction of complainants would wait that long and recommend a number.
`gpt-5-nano` measures 14–20.5 s today, so 30 s is roughly one slow model away from being tight already.
⚠ **Raise `CLASSIFICATION_WAIT_SECONDS` and `TIMEOUT_CLASSIFY_INTERACTIVE` together** — the poll deadline
and the first-attempt SDK timeout are the same decision, and DPG-15b's tests pin that they stay coherent.

**2. ⭐ The open configuration ships TWO models.** Benchmark many candidates; keep **one text model for
every text task, plus one for transcription**, mirroring the closed pair.

⚠ **This was already decided on 2026-08-18** — [Q-21](DECISIONS.md#q-21), in the owner's words: *"we just
need two models… That will be aligned with what we discussed as well for the open weights model where we
agreed to just have two."* It was **re-confirmed 2026-08-20**, and the reason it needed re-confirming is
worth noticing: `.env.open` shipped **three** models for two days after the decision that said two — a 120b
for translation and SEAH findings that nobody had measured. **The decision record was right and the
artefact never got the message.** The template is now collapsed to match; every `MODEL_*` except
`MODEL_ASR` carries the same value.

**This is a benchmark-many-ship-one decision, and it changes how you select, not just how many rows the
table has:**

- **Select on the hardest task, not the average.** One model does everything, so the binding constraints
  are **SEAH recall** — a miss is a safeguarding failure, not a quality complaint — and the
  **complainant-facing resolved summary**, which is the only generated text that reaches the public. A
  candidate that classifies dust complaints beautifully and reads harassment poorly is disqualified
  whatever its headline accuracy. **Rank candidates by their worst per-task score, not their mean.**
- **A per-task split is a decision to re-open with evidence, never a default.** The registry keeps eight
  separate keys precisely so that stays cheap — one env var re-opens it. If a second text model turns out
  to buy something large enough to justify operating it, say what it bought and what it cost; do not let
  it back in because a template had it.
- **"Many" means a shortlist, not a sweep** (owner, 2026-08-20): *"anyway not so many are decent
  candidates."* The filter in §Required reading does most of the narrowing before you spend anything —
  permissive licence, real multilingual coverage including Nepali, reliable guided decoding, fits one
  24 GB GPU at 4-bit. **Expect a handful, and name them in the doc with the reason each one made or missed
  the list** — including the ones the licence limb excluded, because that limb is provisional
  (Q-04-02) and a loosened answer should be a candidate-list edit, not a re-design.
- ⚠ **Still price it before running it ([Q-19](QUESTIONS.md#q-19)).** A shortlist is affordable in a way a
  sweep is not, which is the point — but "affordable" is a number, not an adjective. A **cheap first pass
  on a small slice** eliminates the weak candidates before the full set is spent on the two or three that
  survive.

### Candidates and criteria

| Task | Candidate class | Licence target | Note |
|---|---|---|---|
| Grievance classification + summary | ~27–31B dense instruct, or a MoE of similar quality at lower inference cost | Apache-2.0 | Needs strong native multilingual coverage — this is the deciding criterion for Nepali |
| Contact / field extraction | Same model, schema-constrained | Apache-2.0 | Guided decoding does the work, not model size. A smaller model is likely fine here |
| Sensitive-content detection | Same model, or a small dedicated guardrail classifier | Apache-2.0 | Cheaper and faster than routing through a general model. ⚠ This is the SEAH path — evaluate recall, not accuracy |
| Nepali ↔ English translation | **The same LLM to start (Q-09 ✅)**; benchmark a specialist seq2seq (IndicTrans2 class, MIT) against it | MIT / Apache-2.0 | ✅ **Decided: start on the chat LLM.** Stand up a dedicated translation service **only if it is materially better** — in which case it becomes a government-wide asset for any translation case, the same reasoning as the Q-12c anonymiser. Note there is **no translate-then-classify pipeline**: classification consumes Nepali directly (`LLM_services.py:355`) and the separate translation call (`:558`) exists only for the English record. ⚠ **Two corrections since this row was written:** that call ran on `gpt-4` and now runs on the one text model (DPG-18), and the chatbot path that invokes it is **parked** (`translate_grievance_to_english_task`, DPG-19b) — officers read English generated by the *ticketing* surface instead. So Q-09 is a decision about a path that is switched off; benchmark it, but do not sequence anything behind it |
| Ticketing case findings | Same model | Apache-2.0 | Longer context; check the token budget against real ticket timelines |
| Ticketing resolved summary (**complainant-facing**) | Same model | Apache-2.0 | Highest quality bar in the set — this text reaches the public |

### The benchmark table

Measure on identical data (DPG-20), per task:

| Metric | Current (closed) | Open config | Delta |
|---|---|---|---|
| *(ASR row: **no baseline** — voice was never live, Q-13.2)* | — | | n/a |
| Classification accuracy | | | |
| Category-set F1 (multi-label) | | | |
| Field extraction F1 | | | |
| Sensitive-content **recall** | | | |
| Translation quality (chrF++ or human rating) | | | |
| Nepali ASR WER *(from DPG-22)* | | | |
| p95 latency **(vs the 30 s interactive budget — pass/fail, §0.1-D)** | | | |
| Cost / 1,000 grievances | | | |

**Expect the open configuration to score somewhat worse, and report the number rather than implying
parity.** If the open model hits 89% against the closed model's 93%, that is an acceptable trade for
jurisdictional data control and DPG eligibility — and saying so plainly is far more credible than a claim
of equivalence. A reviewer who finds an overstated number stops trusting the rest of the submission.

**Two metrics deserve special handling:**

- **Sensitive-content detection is recall-first, not accuracy-first.** A missed harassment report is a
  safeguarding failure; a false positive is an officer reading one extra case. The current prompt already
  encodes this (*"be extra sensitive as awareness around the issue is low"*, `LLM_services.py:625`).
  Score it accordingly, and set the threshold accordingly.
- **Multi-label classification.** The system returns `grievance_categories` **and**
  `grievance_categories_alternative`. Single-label accuracy would misrepresent it. Score set-level.

### Acceptance

> ⚠ **This ticket is 🟡, and the unticked boxes are the sprint's headline finding, not loose ends.**
> The harness, the data, the scoring rules and the CI gate are built and reproducible. **No model has
> been chosen**, because the open column is blocked on **D-50** and because SEAH recall — the metric the
> selection rule turns on — is not measurable from this repository at all.

- [x] **Priced before built** — the estimated token spend recorded and confirmed against the envelope
      **after** an estimate of pilot traffic is subtracted (Q-19). The budget is shared with production
- [ ] ⛔ **Cost per 1,000 grievances recorded for the chosen model** — **no model is chosen.** Cost *is*
      metered per run and `model-benchmarks.md` §6 carries the measured token figures, including that
      **93.8% of `gpt-5-nano`'s completion tokens are reasoning** — which is the number that will decide
      this row once a model exists
- [x] **The closed configuration still passes CI after the switch** — Q-04's reserve is only real if it can
      be flipped in minutes from DPG-17's registry. Pin it with a test, not an intention —
      `test_every_task_resolves_to_todays_model_by_default` asserts a fresh clone gets the closed models
- [ ] ⛔ **The production switch to the open configuration recorded as a deliberate, cost-driven
      decision** with its measured quality gap beside it — **not made, and it cannot be**: there is no
      open model to switch *to*. Blocked behind the row above
- [x] Benchmark table complete, every cell filled or explicitly marked `⚠ Not measured` — **ASR's baseline
      cell says "never live" rather than sitting blank.** ⚠ *Complete* is the wrong word and the document
      says so: the closed column is full, the open column has **detection only**, and every unmeasured
      cell names its blocker
- [x] Published at `docs/dpg/model-benchmarks.md`, with data provenance, model versions, and date
- [x] Sensitive detection scored on **recall** — recall-first, with a confusion matrix. ⚠ And the
      published number is a **false-alarm rate on a set with no positives** (§5 of that document), which
      is the half that can be measured here and must never be read as the whole
- [x] Classification scored **set-level** — a correct two-label answer scores 1.0; a subset is partially
      credited and is **not** an exact-set match (T-23-c)
- [ ] ⛔ **Translation decision (Q-09) made and recorded with the number that decided it** — **no number.**
      And see the candidates table: the chatbot's translation path is **parked**, so this decision is
      about a path that does not run
- [ ] ⚠ **p95 and p99 measured against 30 / 45 / 60 s per candidate** — **measured for the closed
      baseline only**: `gpt-5-nano` p95 **24.6 s** (passes 30 s), p99 **40.6 s** (does not). Detection
      latency is measured for `gpt-oss-20b` (p50 0.35 s vs nano's 3.73 s); classification latency for the
      open column is not, because the run stopped at 2/105. **No raise is recommended, because nothing
      has been ranked yet**
- [ ] — **Conditional, and it did not trigger.** The budget did not move, so
      `CLASSIFICATION_WAIT_SECONDS` and `TIMEOUT_CLASSIFY_INTERACTIVE` are unchanged at 30 s and
      DPG-15b's coherence tests are still green
- [ ] ⚠ **Exactly two models in the shipped configuration** — one text, one ASR (owner's decision,
      2026-08-20). **The shape is right, the names are not confirmed:** every `MODEL_*` in `.env.open`
      except `MODEL_ASR` now carries the same value, but they remain **unmeasured placeholders** and the
      file says so
- [ ] ⛔ **Candidates ranked by worst per-task score, not mean** — **not done, and this is the reason no
      model was chosen.** The binding constraint is SEAH recall, which is not measurable here (§5 of
      `model-benchmarks.md`). ⚠⚠ Ranking on what *is* measurable would select `gpt-oss-20b` on a
      **0.000 false-alarm rate** — a detector that flags nothing scores perfectly on a set with no
      positives. Do not let that number become a choice
- [ ] — **Conditional, and it did not trigger.** No per-task split was proposed; the eight registry keys
      stay as the seam that makes re-opening it one env var
- [ ] ⛔ **Chosen defaults written into `.env.open` and `docs/dpg/open-model-configuration.md`** — no
      defaults chosen. `.env.open` still carries placeholders, labelled as such in three places
- [x] The gap, wherever it exists, stated plainly in the DPG submission language — including the
      clause-by-clause verdict in
      [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md#4-dpg-evidence-pack), where
      **four of seven clauses do not hold** and a version that is true today is drafted beside them

### ✅ Questions — answered

- **Q-04** — ✅ **production runs the open configuration**, on cost, with the closed one held in reserve
  against quality complaints. See the banner above: this makes the benchmark a production pre-flight check.
- **Q-09** — ✅ **the chat LLM first**; a dedicated specialist service only if it is materially better.
- **Q-19** — ✅ **answered 2026-08-20**: funded to a few hundred USD, owner-paid, **shared with the pilot's
  own inference**. See [DECISIONS.md](DECISIONS.md#q-19) for what that obliges.

---

## DPG-24 — CI platform-independence job {#dpg-24}

**The strongest indicator-4 evidence available**: the full LLM suite, green against the open
configuration, on every commit.

### Shape — a fifth job in the existing workflow

Add to `.github/workflows/ci.yml` as the **fifth** job, alongside `backend-tests` / `ui-checks` /
`webchat-checks` / `docs-links`, following that file's existing conventions (header comment explaining
the gate, explicit `env:` block with rationale comments, `timeout-minutes`).

> ✅ **Built as `dpg-platform-independence`.** Read the job itself, not the sketch below — it is the
> authority and it differs in three ways that matter: the models come from **repo variables with a
> router fallback** (so a model swap is a settings change, and this file never becomes a second place
> a model name lives); the live tests are **`tests/backend/test_llm_live.py` and
> `tests/ticketing/test_ticketing_llm_live.py`**, not the mocked suites; and the run is guarded so
> that **skips are tolerated but an empty gate fails**, because a run where everything skipped is the
> quarantine pattern wearing a green tick.

> ⚠ **Read the file first — it changed on 2026-08-19** (§0.1-G/H). `docs-links` now also checks the root
> `*.md` and backticked repo paths; `backend-tests` pins its apt mirror and gives the system-libraries step
> its own timeout, after a mirror outage burned four runs by consuming the job budget silently. **The
> lesson is directly yours:** a step that can hang must fail fast and say why, and a workaround that leaves
> no evidence of having run costs you the next debugging round too. Your job calls a live third-party API —
> it is the most hang-prone thing in the workflow.

```yaml
  dpg-platform-independence:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      LLM_BASE_URL: https://router.huggingface.co/v1
      LLM_API_KEY: ${{ secrets.HF_TOKEN }}
      ASR_BASE_URL: https://router.huggingface.co/v1
      ASR_API_KEY: ${{ secrets.HF_TOKEN }}
      MODEL_CLASSIFY: ${{ vars.DPG_MODEL_CLASSIFY }}
      # … the rest of DPG-17's registry (declared_env_vars()), as repo variables so a model swap is
      # not a code change. Both LLM surfaces read these — that is what makes this job's green
      # meaningful rather than partial.
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/backend/test_llm_live.py tests/ticketing/test_ticketing_llm_live.py -v -m live_llm
```

⚠ **This is the sketch that was planned, kept for the shape.** The built job adds the fork-PR skip
gate, a scoped `pip install` (the OpenAI SDK, pydantic and pytest — not `requirements.txt`), a
per-step `timeout-minutes: 8`, `LLM_MAX_RETRIES: "1"`, and the empty-gate guard. Two of those exist
because of D-26 and are not decoration.

### ⚠ CI routes freely; production pins — and that is deliberate

The privacy analysis concludes that **production must pin one named provider** (`model:provider`) instead
of `:fastest`, so exactly one company processes grievance text and DPG-04 can assess it. Read naively that
would gut this job's value: the multi-provider routing *is* the "independent of any single vendor"
evidence.

**The two needs separate cleanly, because the data differs.** This job sends **only DPG-20's synthetic
benchmark data** — no complainant text ever — so automatic routing is safe here and the evidence stays
strong. Production sends real grievances and pins. **Write that split into the job header**, or someone
will later "fix" the inconsistency in the wrong direction.

⚠ **The invariant that keeps it safe:** if this job ever gains access to production data, the routing
policy must change with it. Put that sentence next to the reason.

### ⚠ Four design decisions this job must get right

1. **It calls a live third-party API from CI.** That makes it *flaky by construction* — provider outages
   will redden the build. Mark it `continue-on-error: false` but **exclude it from branch protection**
   unless the team accepts provider downtime blocking merges. Whichever you choose, decide deliberately
   and write the reason in the job header. **Q-17.**
2. **The mocked tests and the live tests are different suites.** DPG-10's tests are mocked and belong in
   `backend-tests` (fast, hermetic, blocking). This job runs a **live-marked subset** — a handful of real
   round-trips proving the open config actually works end to end. Use a pytest marker (`live_llm`), and
   make sure `backend-tests` deselects it, per [`04_testing.md`](../../engineering/04_testing.md).
   > ⚠ CLAUDE.md history: T3 ended an `@integration` quarantine and grew CI from 364 to 897 tests. **Do
   > not re-create a quarantine here.** A marker that nothing ever runs is exactly the pattern that was
   > just dismantled. This marker runs in *this* job, on every commit.
3. **Cost — ✅ funded, and still the one to cap first.** Every push runs real inference.
   **[Q-19](DECISIONS.md#q-19) (2026-08-20) funds it — a few hundred USD, owner-paid, covering the first
   demo months.** ⚠ **This job is the only cost in the whole plan that outlives those months**, which is
   exactly why the advice below did not change when the money arrived: a recurring charge against a
   time-boxed, personally-expensed envelope is the one that turns into an awkward conversation. **Set the
   hard token cap before the job's first run**, and record the measured monthly spend in the job header —
   the government proposal Q-19 commits to will need a real figure, and this job is where it comes from.
   This job is the **only recurring** cost in the whole plan, so it is the one to cap first: a small fixed
   live subset (a handful of round-trips, **not** the suite), a hard token cap on the HF account, and the
   **measured** monthly spend in the job header.
   > **If even that is unaffordable, degrade honestly rather than quietly:** nightly plus release tags,
   > with the badge and the job header saying so. That is weaker evidence than per-commit and it still
   > cannot silently rot — which is the property that made this the strongest indicator-4 artefact.
   > **What is not acceptable is a job that exists, never runs, and is cited as evidence.**
4. **Fork PRs get no secrets.** The job must skip cleanly (not fail) when `secrets.HF_TOKEN` is absent —
   otherwise every external contribution shows a red X, which for a *public good* repo is precisely the
   wrong signal.

### Acceptance

> ⚠ **The job is written and pinned by 14 tests. It has never run.** Every box below describes the job
> as authored; the last one is what the ticket is actually waiting on.

- [x] **Fifth** job in `.github/workflows/ci.yml`, following the file's conventions —
      `dpg-platform-independence`
- [x] `live_llm` marker defined; `backend-tests` deselects it; this job selects it; **neither is a
      quarantine** — and a test asserts the **composite** property (not deselected in both places),
      because asserting each half separately is how T3-08's quarantine came back
- [x] Job skips cleanly without secrets (fork PRs) — an explicit gate step emitting a `::notice`, not a
      failure
- [x] Branch-protection decision made and its reason written in the job header (Q-17) — **every commit,
      never a required check**
- [x] The job header states **why CI may route automatically while production pins** — synthetic data only —
      and that the policy changes if that ever stops being true. Pinned by a test
- [ ] ⚠ **Measured CI inference spend recorded in the job header** — the header says
      **`MEASURED SPEND: ⚠ not yet measured`**, because the job has never run. What *is* measured, by
      hand on 2026-08-20: 5 live tests, ~7 requests. Stated, not left blank
- [ ] ⚠ **Hard token cap set on the HF account before the first run** — **the criterion was
      unactionable and was replaced rather than ticked.** A configurable spending limit is a
      Team/Enterprise feature; this is a personal free account (verified via `whoami-v2`). What actually
      bounds the spend is structural and is now written in the header: the free tier 402s at ~$0.10/month,
      and extra usage is **pre-paid**, so the balance loaded *is* the ceiling
- [ ] — **Conditional, and it did not trigger.** The cadence is still per-commit as authored; nothing was
      reduced for cost, so there is nothing for the badge to say
- [x] **Who pays after the demo months is named in the job header**, or the ticket says plainly that it is
      unresolved. Q-19's envelope is time-boxed and owner-funded; this job is not time-boxed —
      the header says **`WHO PAYS AFTER THE DEMO MONTHS: ⚠ UNRESOLVED`**, which is the second limb
- [x] Badge in the repo `README.md` linking the job — this is the link that goes in the submission.
      ⚠ It is in place and the README explains **what it does and does not mean**, which matters while
      the job has never run
- [ ] ⛔ **Green on the integration branch** — **the job has never executed.** It needs `HF_TOKEN` as a
      repo secret and the `DPG_MODEL_*` repo variables set, which is the one step nobody working in this
      repository can take (see DPG-21's first box). Until then the badge renders a job that has produced
      no evidence — which is precisely the *"exists, never runs, and is cited as evidence"* failure this
      ticket's own §3 forbids. **This is DPG-24's only real blocker.**
      ⚠ **Do not be the job that undoes CI's green** when it does run: a live-API gate reddens on
      provider outages by construction; that is what Q-17's never-a-required-check answer is for, and
      the reason is in the job header where the next person will read it before "fixing" it

### ✅ Questions — answered

- **Q-17** — ✅ **run on every commit, never a required status check**, with the reason in the job header so
  nobody later "fixes" it by making it required.
- **Q-19** — ✅ **answered 2026-08-20**, and it reframes Q-17 rather than closing it. Q-17 settled
  *flakiness*; frequency is also a budget decision, and this is the **only recurring** line in the plan
  against a **time-boxed** envelope. Cap first, degrade cadence only if you must, say so, and name the
  payer for after the demo.

---

## DPG-25 — T2: vLLM, documented and costed — **not deployed** {#dpg-25}

> **⚠ SCOPE CHANGED 2026-08-17 — T2 is parked** (Q-03 + Q-05). There is no owner for the run costs, and
> that is precisely the failure mode that killed Rwanda's Babyl: an excellent system nobody funds to keep
> running. **Not starting is the right call.** The best case remains ADB financing subcontractor-managed
> instances leased to member countries under a TA with the Ministry of Finance; absent that, there is no T2.
>
> **So this ticket delivers a document and a price, not a deployment.** Its old acceptance had
> *"⚠ documented and tested, not deployed"* as a fallback — that is now the **plan**, and the honest thing
> is to say so everywhere the ladder is described rather than leave a reader to infer it.
>
> **Two consequences worth carrying into every other ticket:**
> 1. **T1 is the steady state, not a stepping stone.** Grievance text leaves the country **indefinitely**,
>    not during a transition. That promotes [Sprint 3](04-pii-redaction-spec.md) from prudent to
>    **necessary** — it is the only remaining control on that egress.
> 2. **Sizing is Hugging Face pricing, not GPU count** (Q-11). Per-task model downsizing becomes *more*
>    attractive, not less: there is no fixed GPU whose capacity is already paid for.

Same code, different `LLM_BASE_URL`. That is the whole point — and with T2 parked, this ticket's job is to
keep that claim **true and costed** so unparking is a procurement decision rather than an engineering one.

```bash
# chat / classification
vllm serve <chosen-text-model> \
  --host 0.0.0.0 --port 8000 \
  --quantization awq \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --api-key "$LOCAL_LLM_KEY"

# transcription — vLLM exposes /v1/audio/transcriptions
vllm serve <chosen-asr-model> \
  --host 0.0.0.0 --port 8001 \
  --api-key "$LOCAL_ASR_KEY"
```

Both endpoints match what the code already calls after Sprint 1. Guided decoding for DPG-13's schemas is
built in — which is why DPG-13's schemas are also a *T2 enabler*, not only a robustness fix.

### Deployment requirements — carry into `docs/deployment/13_security.md`

- Private subnet, reachable **only** from the application security group. Never exposed to the internet.
- TLS terminated at a reverse proxy.
- An API key set **even on a private network** (defence in depth; the codebase already has a TODO row
  about a service bound to `0.0.0.0` "because the firewall holds" — do not add a second).
- Snapshot the instance once configured, so a rebuild is minutes rather than a day.
- Monitoring and restart policy — name the owner (Q-05).

### ⭐ This document now has an audience — added 2026-08-20

[Q-19](DECISIONS.md#q-19)'s answer commits to one: *"we will submit to Nepal Gvt the choices they need to
make moving forward with realistic budget."* **That is this ticket's costed proposal, plus DPG-23's
cost-per-1,000-grievances row.** Two rungs, one decision document:

| Option | The number it needs | From |
|---|---|---|
| **T1 — hosted inference** (what runs today) | Cost per 1,000 grievances at pilot volume, extrapolated to national | DPG-23 |
| **T2 — self-hosted vLLM** | Monthly instance cost at the volume where it overtakes T1 | this ticket |

**The crossover is the whole point of the document.** Hosted inference is cheaper until volume makes a
dedicated GPU cheaper; **say where that line falls** and the government has an actual choice rather than
two unrelated prices. Below the line, T2 stays parked and that is the right answer; above it, unparking
becomes a procurement decision with a payback period attached.

⚠ **State the extrapolation as an extrapolation.** Two districts over a few demo months is a small base,
and a national figure derived from it is an estimate with a stated method — not a forecast.

### Sizing — measure, do not inherit

The $700–900/month, 5–15-concurrent-user figure in the source narrative is a generic estimate.
**Size against this system's measured load**: the GRM's traffic is intake-shaped and bursty around road
works and public meetings, not chat-shaped, and classification is one request per grievance rather than
per turn.

⚠ **The old instruction here was "pull real volumes from the grievance table" — and that table holds no
genuine grievances**, only seed and demo rows. Q-19's answer supplies the anchor it was missing: **two
districts over the first months of the demo**, which will be real traffic by the time this document is
written. Size against that, and extrapolate to national with the method stated.

### Acceptance — rewritten for the parked scope

- [x] vLLM deployment documented at `docs/dpg/vllm-deployment.md` — instance class, quantisation, flags,
      networking, snapshot procedure
- [x] ⚠ **A costed proposal**, not an estimate inherited from the source narrative — **costed, but not
      from pilot volume**: the pilot has not run, so sizing comes from **this project's own measured
      token usage** (DPG-23) rather than the source narrative's generic chat estimate. The Q-19 anchor
      remains the right input the day it exists, and the document says which number came from where
- [x] **The T1/T2 crossover volume identified** — the point where a dedicated GPU becomes cheaper than
      hosted inference. Without it the Nepal Government proposal is two prices, not a choice.
      ⭐ **And the answer changed the ticket's conclusion:** the crossover is **40,000–780,000
      grievances/month** across every price assumption, against **tens/month** for two districts and
      **7,700/month** for all 77. T1 wins by three to four orders of magnitude and **volume growth does
      not close it** — one request per grievance, not per turn, so a dedicated GPU is idle almost always.
      **T2 is therefore a data-sovereignty decision with a price, not a cost decision**, and presenting
      it as a break-even would have misled
- [x] **Any national figure labelled as an extrapolation**, with the method and the base it came from
- [x] `docs/deployment/13_security.md` updated with the intended network posture, marked `⚠ not deployed`
      — §8.1
- [x] **The ticket is marked `⚠ documented and costed, not deployed`, and every place that describes the
      ladder says the same** — `00-dpg-context-and-decisions.md` §2, the indicator-4 answer, and
      `docs/dpg/00_compliance_status.md` §4. A ladder that still reads "T2 ⭐ the production target" is a
      claim the submission cannot support
- [x] Q-03 (jurisdiction) and Q-05 (operator/payer) recorded as **parked with their reason**, so unparking
      starts from the analysis rather than repeating it
- [ ] ⏸ **Deferred, explicitly:** the end-to-end test against a live vLLM endpoint. It cannot run without an
      instance. Logged as a followup + `TODO.md` row per the standing rule — **not** silently dropped, because
      it is the step that would turn "documented" into "demonstrated".
      ✅ Logged: [`followups/vllm-end-to-end-test-deferred.md`](followups/vllm-end-to-end-test-deferred.md)

---

## Sprint 2 acceptance criteria

> **Checked against reality 2026-08-20, and mirrored in [`PROGRESS.md`](PROGRESS.md) §"Sprint 2
> acceptance".** Two lines are qualified and say why. ⚠ **Read the note below the list** — the ticks do
> not add up to the thing the sprint was for.

- [x] Labelled benchmark set built and committed (test data, **not** production PII), with provenance —
      105 items, CC0-1.0. *"No production PII"* is **verified by a test against the live DB**, not assumed
- [x] ⚠ Benchmark table completed and published in `docs/dpg/model-benchmarks.md` — **"complete" is the
      wrong word and the document says so**: the closed column is full, the open column has detection
      only, and every unmeasured cell names its blocker
- [x] The full test suite green against the open configuration — **4 passed, 1 xfailed, exit 0**, both
      surfaces, real calls, `openai/gpt-oss-20b`. The xfail is D-53 (the open ASR endpoint 404s) and is
      `strict=True`, so it reddens the day someone fixes it
- [ ] ⚠ **CI platform-independence job passing; badge in the repo `README.md`** — **written and pinned by
      14 tests; it has never run.** Needs `HF_TOKEN` + `DPG_MODEL_*` as repo secrets/variables, the one
      step nobody in this repository can take. Badge is in place
- [x] `docs/dpg/open-model-configuration.md` written — the reviewer-facing document, with the measured
      capability matrix, the excluded-on-licence list, and what is **not** yet true
- [x] T2 vLLM deployment **documented and costed** — `⚠ not deployed`, T2 parked per Q-03/Q-05, and the
      deferred end-to-end test logged as a followup. And the costing **changed the conclusion** — see
      the crossover in DPG-25
- [ ] ❌ **The indicator-4 answer now true sentence by sentence** — **no, and that is the finding.**
      Checked clause by clause in
      [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md#4-dpg-evidence-pack):
      **four of seven do not hold**, chiefly that the repository default is still proprietary because no
      open model has been *chosen*. A version that **is** true today is drafted beside it
- [x] Every deferral logged in `followups/` + `TODO.md`, same commit — nine follow-ups, nine `TODO.md`
      rows

### ⚠ What a reader should not conclude from the ticks above

**Sprint 2 did not choose a model, and choosing one was its point.** The mechanism, the data, the
harness, the scoring rules and the CI gate are all built, tested and reproducible. What is missing is
**SEAH recall** — and until that exists for both candidates, selecting on the numbers that *do* exist
would mean picking a detector that flags nothing because it scored a perfect false-alarm rate.
