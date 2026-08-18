# Sprint 2 — Open models, benchmarks, and CI evidence (DPG-20…25)

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
([`00_compliance_status.md`](../../dpg/00_compliance_status.md) consultant-Q5). **Record which models the
filter excluded and why**, so that if the answer loosens it, re-running DPG-23 is a candidate-list edit
rather than a re-design.

---

## §0 — Corrections carried into this sprint

| The guide assumes | Reality | Effect |
|---|---|---|
| One LLM surface to benchmark | Two — see [`02`](02-llm-agnostic-spec.md) §0. Ticketing's case findings and **complainant-facing** resolved summary also need a model choice | DPG-23 covers six task types, not four |
| Classification runs on `gpt-3.5-turbo` | It runs on `gpt-5-nano` (`LLM_services.py:230`) | The "current" column of the benchmark must name the real baseline, or the delta is meaningless |
| `pytest tests/test_llm_services.py` in the CI job | That file does not exist today; Sprint 1's DPG-10 creates `tests/backend/test_llm_services.py` and `tests/ticketing/test_llm_client.py` | DPG-24's job runs the real paths |
| CI is greenfield | `.github/workflows/ci.yml` already runs **four** parallel gates — `backend-tests` (`:23`, full Postgres + Redis service block, all three Alembic streams), `ui-checks` (`:202`), `webchat-checks` (`:236`), `docs-links` (`:262`) | DPG-24 adds a **fifth job to an existing file**, following its conventions — not a new workflow file with its own dialect. ⚠ This spec said "three" and named only three of the four until 2026-08-17; `webchat-checks` was the one missed |
| The candidate filter is settled: Apache-2.0 / MIT | **It is gated on the consultant.** Several of the strongest multilingual models ship under bespoke community licences with use restrictions (Llama, Gemma). Whether those count as open alternatives for indicator 4 is an open question — [`00_compliance_status.md`](../../dpg/00_compliance_status.md) consultant-Q5 | The filter may be **loosened** before DPG-23 runs, which would widen the candidate field and may materially change the Nepali quality result. **Do not build the benchmark harness around a frozen licence filter** |

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
> consultant-Q5b asks about. **Phase 1 is the honest version of the evidence, not a compromised one** —
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
   > ([`00_compliance_status.md`](../../dpg/00_compliance_status.md) consultant-Q5b). If yes, the committed
   > synthetic half of the hybrid set is already the answer — **which is a second reason to prefer hybrid.**

### Acceptance

- [ ] Set committed under `tests/data/benchmark/` with a provenance README
- [ ] Categories drawn from the live taxonomy, not invented
- [ ] Voice subset has verbatim transcripts
- [ ] PII spans labelled (serves DPG-35 — do it once)
- [ ] Data licence stated
- [ ] No production PII in any committed file — **verified, not assumed**

### Acceptance — amended for the phased scope

- [ ] Every number this set produces is labelled **synthetic (phase 1)** wherever it is published
- [ ] The README records the phase-2 hybrid intent and what would trigger it (live project data)
- [ ] Edge cases deliberately covered — Devanagari digits, third-party names, code-switching — since
      authored data is the only place they can be guaranteed
- [ ] Actual size recorded, against the aspirational target, with no implication that labellers were funded

### ✅ Questions — answered

- **Q-15** — ✅ **synthetic in phase 1**, hybrid once the project is live.
- **Q-16** — ✅ **no labeller budget or staff time**; the set grows with the project. The target is a
  direction, not a plan.
- ⚠ **See [Q-19](QUESTIONS.md) (new).** This ticket is free — it is authoring, not inference. **DPG-22 and
  DPG-23, which consume it, are not**, and there is no LLM budget. Building the set is worth doing
  regardless; **do not assume the benchmark that reads it is funded.**

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
3. Record the capability matrix in `docs/dpg/open-model-configuration.md`.

### Acceptance

- [ ] `HF_TOKEN` in `env.local` and in GitHub secrets; not in any tracked file
- [ ] `scripts/ops/llm_smoke.py` committed and runnable in-container against any base URL
- [ ] Capability matrix (chat / `json_object` / `json_schema` / audio) recorded per candidate provider
- [ ] `docs/dpg/open-model-configuration.md` updated

---

## DPG-22 — ASR evaluation {#dpg-22}

**The easiest win, with peer-reviewed Nepali evidence.** `whisper-1` **is** Whisper — OpenAI hosts a model
whose weights are already Apache-2.0, so switching to the open weights is functionally near-identical
while removing a closed dependency.

A 2026 comparative study fine-tuned six architectures on the **OpenSLR SLR54 Nepali corpus (~165 hours)**,
evaluating on OpenSLR, FLEURS and Common Voice:

| Model | Nepali WER | Licence | Verdict |
|---|---|---|---|
| **Whisper-Large-v3-Turbo** | **14.76%** | Apache-2.0 | ✅ Best-equal, drop-in for `whisper-1` |
| **IndicWav2Vec** (AI4Bharat) | **14.89%** | Verify — AI4Bharat is generally MIT | ✅ Statistically tied, far smaller, CTC decoder much faster |
| MMS-1B | worse | **CC-BY-NC-4.0** | ❌ Cannot ship. Excluded on licence, not on quality |
| Whisper-Medium · XLSR-53 · Conformer-Hi | worse | Apache-2.0 | — |

Two takeaways. **~85% word accuracy on Nepali is achievable under Apache-2.0** — usable for grievance
intake with on-screen confirmation, and above the threshold where correcting is slower than re-entering.
And the improvement path is concrete: fine-tuning on SLR54's 165 openly-licensed hours is a single-GPU
job, and **that fine-tune released openly would be a genuine DPG contribution**, because permissively-
licensed Nepali speech tooling barely exists.

Also benchmark **Omnilingual ASR** (Apache-2.0, covers Nepali, 300M–7B variants). The 300M model is worth
testing specifically for low-connectivity districts.

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
> 3. ⏸ **Sequence this ticket last in Sprint 2** ([Q-19](QUESTIONS.md)). Audio is the most expensive input
>    per item and, with voice not live, the least decision-relevant right now.

### ⚠ And decide what "good enough" means before you measure

If open-weights Nepali ASR lands materially worse than the incumbent, the honest options are: accept
documented degradation on voice while text stays at parity; keep ASR on a hosted provider and **disclose it
as a remaining closed dependency**; or fund a Nepali fine-tune. Whether the DPGA accepts *"functional, with
documented degradation"* or expects parity is open with the consultant
([`00_compliance_status.md`](../../dpg/00_compliance_status.md) consultant-Q6) — and the answer decides
whether voice intake can exist at all in an open configuration. **Measure first, but record the threshold
question in the doc**; do not let a bad WER quietly become a decision nobody made.

### Steps

1. Run each candidate over DPG-20's voice subset; compute WER against the verbatim transcripts.
2. Measure p95 latency per candidate at realistic audio lengths, and cost per 1,000 minutes.
3. Check the **actual current behaviour** as the baseline column (see the caveat above).
4. Verify the licence of each candidate **from its model card at evaluation time**, not from this table.
5. Record in `docs/dpg/model-benchmarks.md`.

### Acceptance

- [ ] WER measured for at least Whisper-large-v3-turbo and one alternative, on this project's own data
- [ ] Baseline column **empty for ASR with the reason stated** — voice is not live and never has been
      (Q-13.2), so there is no incumbent number to beat
- [ ] Licence verified per candidate, at evaluation date
- [ ] p95 latency and cost recorded
- [ ] `docs/services/03_voice_grievance_service.md` updated with the chosen model and its measured WER
- [ ] The SLR54 fine-tune opportunity logged as a followup (a genuine DPG contribution; out of scope here)

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
> ⚠ **And see [Q-19](QUESTIONS.md): this is the most expensive ticket in the sprint and there is no LLM
> budget.** Price it — items × models × tasks is knowable arithmetic — before building the harness. A few
> hundred short texts on per-token pricing is plausibly tens of dollars, and *"no budget"* and *"$40"* may
> not be in conflict. **Get the number rather than assuming either.**

### Candidates and criteria

| Task | Candidate class | Licence target | Note |
|---|---|---|---|
| Grievance classification + summary | ~27–31B dense instruct, or a MoE of similar quality at lower inference cost | Apache-2.0 | Needs strong native multilingual coverage — this is the deciding criterion for Nepali |
| Contact / field extraction | Same model, schema-constrained | Apache-2.0 | Guided decoding does the work, not model size. A smaller model is likely fine here |
| Sensitive-content detection | Same model, or a small dedicated guardrail classifier | Apache-2.0 | Cheaper and faster than routing through a general model. ⚠ This is the SEAH path — evaluate recall, not accuracy |
| Nepali ↔ English translation | **The same LLM to start (Q-09 ✅)**; benchmark a specialist seq2seq (IndicTrans2 class, MIT) against it | MIT / Apache-2.0 | ✅ **Decided: start on the chat LLM.** Stand up a dedicated translation service **only if it is materially better** — in which case it becomes a government-wide asset for any translation case, the same reasoning as the Q-12c anonymiser. Note there is **no translate-then-classify pipeline**: classification consumes Nepali directly (`:204-231`) and the `gpt-4` translation call (`:322`) exists for the English record |
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
| p95 latency | | | |
| Cost / 1,000 grievances | | | |

**Expect the open configuration to score somewhat worse, and report the number rather than implying
parity.** If the open model hits 89% against the closed model's 93%, that is an acceptable trade for
jurisdictional data control and DPG eligibility — and saying so plainly is far more credible than a claim
of equivalence. A reviewer who finds an overstated number stops trusting the rest of the submission.

**Two metrics deserve special handling:**

- **Sensitive-content detection is recall-first, not accuracy-first.** A missed harassment report is a
  safeguarding failure; a false positive is an officer reading one extra case. The current prompt already
  encodes this (*"be extra sensitive as awareness around the issue is low"*, `LLM_services.py:372`).
  Score it accordingly, and set the threshold accordingly.
- **Multi-label classification.** The system returns `grievance_categories` **and**
  `grievance_categories_alternative`. Single-label accuracy would misrepresent it. Score set-level.

### Acceptance

- [ ] **Priced before built** — the estimated token spend recorded, and confirmed affordable, before the
      harness runs (Q-19). A benchmark nobody can pay for fails silently
- [ ] **The closed configuration still passes CI after the switch** — Q-04's reserve is only real if it can
      be flipped in minutes from DPG-17's registry. Pin it with a test, not an intention
- [ ] The production switch to the open configuration recorded as a **deliberate, cost-driven decision**
      with its measured quality gap beside it — in `PROGRESS.md` and in the submission language
- [ ] Benchmark table complete, every cell filled or explicitly marked `⚠ Not measured` — **ASR's baseline
      cell says "never live" rather than sitting blank**
- [ ] Published at `docs/dpg/model-benchmarks.md`, with data provenance, model versions, and date
- [ ] Sensitive detection scored on **recall**
- [ ] Classification scored **set-level**
- [ ] Translation decision (Q-09) made and recorded with the number that decided it
- [ ] Chosen defaults written into `.env.open` and `docs/dpg/open-model-configuration.md`
- [ ] The gap, wherever it exists, stated plainly in the DPG submission language

### ✅ Questions — answered

- **Q-04** — ✅ **production runs the open configuration**, on cost, with the closed one held in reserve
  against quality complaints. See the banner above: this makes the benchmark a production pre-flight check.
- **Q-09** — ✅ **the chat LLM first**; a dedicated specialist service only if it is materially better.
- ⚠ **[Q-19](QUESTIONS.md) is open and gates this ticket** — no LLM budget is currently allocated.

---

## DPG-24 — CI platform-independence job {#dpg-24}

**The strongest indicator-4 evidence available**: the full LLM suite, green against the open
configuration, on every commit.

### Shape — a fifth job in the existing workflow

Add to `.github/workflows/ci.yml` as the **fifth** job, alongside `backend-tests` / `ui-checks` /
`webchat-checks` / `docs-links`, following that file's existing conventions (header comment explaining the
gate, explicit `env:` block with rationale comments, `timeout-minutes`).

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
      - run: pytest tests/backend/test_llm_services.py tests/ticketing/test_llm_client.py -v -m live_llm
```

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
3. **Cost — now the gating constraint, not a footnote.** Every push runs real inference, and
   **[Q-19](QUESTIONS.md) establishes there is no LLM budget** (Q-13: *"a few calls per day to nano"*).
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

- [ ] **Fifth** job in `.github/workflows/ci.yml`, following the file's conventions
- [ ] `live_llm` marker defined; `backend-tests` deselects it; this job selects it; **neither is a quarantine**
- [ ] Job skips cleanly without secrets (fork PRs)
- [ ] Branch-protection decision made and its reason written in the job header (Q-17)
- [ ] The job header states **why CI may route automatically while production pins** — synthetic data only —
      and that the policy changes if that ever stops being true
- [ ] **Measured** CI inference spend recorded in the job header, and a hard token cap set on the HF account
- [ ] If the cadence was reduced below per-commit for cost, the **badge and job header say so** (Q-19)
- [ ] Badge in the repo `README.md` linking the job — this is the link that goes in the submission
- [ ] Green on the integration branch

### ✅ Questions — answered

- **Q-17** — ✅ **run on every commit, never a required status check**, with the reason in the job header so
  nobody later "fixes" it by making it required.
- ⚠ **[Q-19](QUESTIONS.md) reframes the same question as a cost question.** Q-17 settled *flakiness*;
  frequency is now also a budget decision. Cap first, degrade cadence only if you must, and say so.

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

### Sizing — measure, do not inherit

The $700–900/month, 5–15-concurrent-user figure in the source narrative is a generic estimate.
**Size against this system's measured load**: the GRM's traffic is intake-shaped and bursty around road
works and public meetings, not chat-shaped, and classification is one request per grievance rather than
per turn. Pull real volumes from the grievance table before choosing an instance class.

### Acceptance — rewritten for the parked scope

- [ ] vLLM deployment documented at `docs/dpg/vllm-deployment.md` — instance class, quantisation, flags,
      networking, snapshot procedure
- [ ] **A costed proposal**, not an estimate inherited from the source narrative: sized against volumes
      pulled from the grievance table, with the monthly figure and its assumptions stated
- [ ] `docs/deployment/13_security.md` updated with the intended network posture, marked `⚠ not deployed`
- [ ] **The ticket is marked `⚠ documented and costed, not deployed`, and every place that describes the
      ladder says the same** — `00-dpg-context-and-decisions.md` §2, the indicator-4 answer, and
      `docs/dpg/00_compliance_status.md` §4.5. A ladder that still reads "T2 ⭐ the production target" is a
      claim the submission cannot support
- [ ] Q-03 (jurisdiction) and Q-05 (operator/payer) recorded as **parked with their reason**, so unparking
      starts from the analysis rather than repeating it
- [ ] ⏸ **Deferred, explicitly:** the end-to-end test against a live vLLM endpoint. It cannot run without an
      instance. Logged as a followup + `TODO.md` row per the standing rule — **not** silently dropped, because
      it is the step that would turn "documented" into "demonstrated"

---

## Sprint 2 acceptance criteria

- [ ] Labelled benchmark set built and committed (test data, **not** production PII), with provenance
- [ ] Benchmark table completed and published in `docs/dpg/model-benchmarks.md`
- [ ] The full test suite green against the open configuration
- [ ] CI platform-independence job passing; badge in the repo `README.md`
- [ ] `docs/dpg/open-model-configuration.md` written — the reviewer-facing document
- [ ] T2 vLLM deployment **documented and costed** — `⚠ not deployed`, T2 parked per Q-03/Q-05, and the
      deferred end-to-end test logged as a followup
- [ ] The indicator-4 answer in
      [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md#4-dpg-evidence-pack)
      now true sentence by sentence — **check each clause against reality before pasting it**
- [ ] Every deferral logged in `followups/` + `TODO.md`, same commit
