# DPG context, deployment ladder, and the decisions that gate this sprint

> Companion to the four specs. **Read this before Sprint 1** — it is the *why* that makes the
> engineering choices non-arbitrary, and per [engineering rule 7](../../engineering/00_engineering_index.md)
> a rule without its reason decays into cargo cult.
> Source: [`DPG-migration-guide-nepal-grm.md`](DPG-migration-guide-nepal-grm.md) §0, §1, evidence pack, open decisions.

---

## 1. The finding that shapes everything

From the DPG Standard source, **Indicator 4, Platform Independence**:

> When the digital public good has mandatory dependencies that create more restrictions than the
> original license, **proving independence from the closed component(s) and/or indicating the existence
> of functional, open alternatives that can be used without significant changes to the core product is
> required.**

The assessment questionnaire asks three things, verbatim:

> - Which are the core technologies your solution depends on?
> - Does this solution use any closed components that create proprietary dependency? **For AI systems,
>   please consider dependencies for the code, the model and the data.**
> - How can these closed component(s) be replaced with open alternative(s)? Please provide a list of the
>   active open alternatives and **demonstrate that these closed component(s) can be replaced with those
>   open alternatives with minimal configuration changes, without requiring a major overhaul of the
>   entire system.**

**The Standard does not require you to use open models. It requires you to demonstrate you could, with
minimal configuration changes.**

So the work is: turn a hard-coded dependency into a configuration value (Sprint 1), ship a tested
open-weights configuration as the repository default (Sprint 2), and produce CI evidence that both
configurations pass the same test suite (DPG-24).

### Why that makes "there are two LLM surfaces" the single most important correction in this sprint

The indicator-4 answer is a claim about **the whole product**, not about one module. A reviewer who
clones the repo, sets `LLM_BASE_URL`, and finds that ticket findings and note translation still call
`api.openai.com` has found a false claim in the submission. `ticketing/clients/llm_client.py` is not a
side path — it produces `Ticket.ai_summary_en`, the officer-facing case findings, and the complainant-facing
resolved-case summary. See [`02-llm-agnostic-spec.md`](02-llm-agnostic-spec.md) §0.

---

## 2. Deployment ladder — the code is identical at every tier

Nepal cannot host GPUs: no machines, no ops staff, and power reliability makes on-prem a liability.
That constraint is real and the architecture should respect it rather than argue with it.

But note the distinction that opens the path: **self-hosting the software ≠ hosting the hardware.**
Running vLLM on a rented GPU instance in AWS Mumbai is self-hosted for data-control and DPG purposes,
with zero hardware in Nepal.

| Tier | What it is | Who sees grievance text | Use it for |
|---|---|---|---|
| **T1 — Hosted inference API** ⭐ | Hugging Face Inference Providers, Together, Fireworks, DeepInfra | Third-party inference provider | Development, CI, DPG evidence — **and, as of 2026-08-17, production** |
| **T2 — Your own model instance** | vLLM on a rented GPU VM under the agency's own contract | Nobody outside the agency's contracted infrastructure | ⏸ **PARKED** — documented and costed, not deployed |
| **T3 — On-prem** | A box inside the ministry | Nobody | Not Nepal. Possibly Georgia or Uzbekistan later. |

> **⚠ The ⭐ moved on 2026-08-17, and it is the most consequential decision in this file.**
> **T2 is parked** (Q-03 + Q-05): nobody owns the GPU run costs, and starting a system with no funded
> operator is the Babyl failure mode. **Not starting is the right call** — but it means **T1 is the steady
> state, not a stepping stone.** Production will run a *hosted open-weights* provider (Q-04, on cost), so the
> provider changes and the third-party exposure does not.
>
> **Three things follow, none cosmetic:**
> 1. **Grievance text leaves the country indefinitely.** DPG-04's cross-border position must be argued for a
>    permanent arrangement, not a transition.
> 2. **[Sprint 3](04-pii-redaction-spec.md) is promoted from prudent to necessary** — the only remaining
>    control on that egress. And with DPG-32 deferred (Q-12c) it closes numeric identifiers but **not** person
>    names; that residual is disclosed, not solved.
> 3. **The indicator-4 answer below loses its last sentence** — see the honesty markers.
>
> Unparking is a **procurement** decision, not an engineering one: DPG-25 keeps the design and the price
> current so it can be taken in a meeting rather than a sprint.

**The only thing that changes between tiers is `LLM_BASE_URL`.** That is the entire point of Sprint 1,
and it is also the DPG indicator-4 answer.

### Realistic T2 sizing and cost

A single 24 GB GPU instance (AWS `g5.xlarge` / `g6.xlarge` class, A10G or L4) serves one 27–31B model at
4-bit quantisation to roughly 5–15 concurrent chat users under vLLM's continuous batching, and can
co-host a Whisper-turbo-class ASR model since it is small. On demand that is roughly **$700–900/month**;
a one-year commitment cuts it materially. For a national road-sector GRM's volumes, one instance is very
likely enough.

⚠ **Unverified against this deployment.** Nobody has measured this system's actual concurrent-user
profile. The GRM's peak is not chat-shaped — it is *intake-shaped*, bursty around road works and
public meetings, and the classification call is one request per grievance, not per turn. Size against
DPG-20's measured volumes (see [`03-open-models-spec.md`](03-open-models-spec.md#dpg-25)), not against this paragraph.

### Two decisions to resolve before committing to T2

- **Jurisdiction (→ Q-03).** AWS Mumbai is still a cross-border transfer from Nepal. Check it against
  Nepal's **Individual Privacy Act 2018** and whatever the implementing agency's data terms say. Also
  worth naming honestly: Nepal–India data flows carry political sensitivity that a Singapore region
  would not. If the legal read is tight, evaluate Singapore (`ap-southeast-1`) alongside Mumbai —
  latency to Kathmandu is worse but tolerable for this workload. **Gated on DPG-04.**
- **Who operates it, and who pays after the pilot (→ Q-05).** A managed instance is a much smaller ops
  burden than a datacenter, but it is not zero — patching, monitoring, restarts, cost control. Plan for
  ADB or a vendor to run it initially with a documented handover path, and make "named budget line for
  run costs" a condition before the pilot converts to production. This is the failure mode that killed
  Rwanda's Babyl: excellent system, no owner of the running costs.

---

## 3. What the codebase already gives us, for free

Worth stating, because it changes the effort estimate and because two of these were mis-scoped in the
source narrative as work to be done:

| Already built | Where | What it means for this sprint |
|---|---|---|
| **Async LLM pipeline with status codes** | `backend/task_queue/registered_tasks.py`, `backend/config/classification_status.py` (`LLM_FAILED`, `LLM_SKIPPED`) | Degraded mode (DPG-15) is an audit, not a build |
| **Intake writes to Postgres before any model call** | `backend/actions/grievance_intake/classification.py` — grievance row exists, then `classify_and_summarize_grievance_task.delay(...)` | The hardest degraded-mode requirement is already satisfied |
| **A bounded wait, not an infinite one** | `classification.py:16-17` — 20 s deadline, 0.5 s poll, terminal-status short-circuit | The "chatbot hangs when OpenAI is slow" failure mode is already handled |
| **A PII-conscious logging helper** | `backend/services/db_debug_log.py` — `text_len_for_log` logs *lengths*, not text | DPG-34 has a precedent to follow and extend, not to invent |
| **A pinned PII boundary** | `tests/ticketing/test_pii_boundary.py`, `tests/ticketing/test_boundary_policy.py` | Sprint 3 must keep these green; they are the guard that structured PII stays out of `ticketing.*` |
| **CI with four parallel gates** | `.github/workflows/ci.yml` — `backend-tests` (`:23`, Postgres + Redis services, all three Alembic streams), `ui-checks` (`:202`), `webchat-checks` (`:236`), `docs-links` (`:262`) | DPG-24 adds a **fifth** job to an existing, working pipeline. ⚠ This row said "three" and omitted `webchat-checks` until 2026-08-17 |
| **Server-side PII decryption at one boundary** | T3-04 — `GET /api/grievance/{id}` returns plaintext; ticketing holds no key | The structured-PII problem is *solved*. Sprint 3 is only about free text. |

And the one thing that is conspicuously absent:

> **There is not a single test that imports `LLM_services.py` or `ticketing/clients/llm_client.py`.**
> Zero. The source narrative's CI snippet runs `pytest tests/test_llm_services.py`, a file that does not
> exist. This is why [DPG-10](02-llm-agnostic-spec.md#dpg-10) is the first ticket of Sprint 1 and why
> nothing may be refactored before it lands.

---

## 4. DPG evidence pack

Answer each indicator with a link, not prose. Assemble under `docs/dpg/`.

| # | Indicator | Evidence | Owner |
|---|---|---|---|
| 1 | SDG relevance | SDG 16 (accountable institutions), SDG 9 (infrastructure). Grievance redress for road-sector beneficiaries. | DPG-04 |
| 2 | Open licensing | `LICENSE` (Apache-2.0), `NOTICE`, `docs/dpg/dependency-licenses.md` — **four dependency sets** incl. container images, with the `redis:8.10` AGPLv3 election stated | DPG-01, DPG-02 |
| 3 | Clear ownership | Written IP determination — ADB OGC | **DPG-03** (longest lead time) |
| 4 | **Platform independence** | Configurable `LLM_BASE_URL` / `MODEL_*` across **both** LLM surfaces, declared in **one config file** (`backend/config/llm_config.py`, DPG-17) with a test that one base-URL change moves both; open-weights default (**Sprint 2** — see the honesty markers below) **and open weights in production** (Q-04); `docs/dpg/open-model-configuration.md`; **CI job running the LLM suite against the open configuration on every commit**; T2 vLLM ⏸ **documented and costed, not deployed** | Sprints 1 + 2 |
| 5 | Documentation | `docs/` (the full spec tree), `docs/deployment/DOCKER.md`, OpenAPI, `docs/_starter_kit/`, and the root `README.md` | existing + **DPG-06 ✅ 2026-08-18** — the README was rewritten from the compose files. The Rasa service and Action Server rows are gone, the service table is the 13 that actually start, and three dead environment URLs were replaced with the two real hostnames |
| 6 | Data extraction | PostgreSQL, documented schema, non-proprietary export (XLSX reports, PDF closure docs) | existing |
| 7 | Privacy & applicable laws | **`docs/dpg/privacy-assessment.md`** ✅ 2026-08-18 — 13 data-flow legs verified against the code, Individual Privacy Act 2018 assessment, 17-item findings register. ⚠ Carries a mandatory honesty marker: drafted by an AI agent, **no legal review**. PII redaction is Sprint 3 | DPG-04 ✅, Sprint 3 |
| 8 | Standards & best practices | OpenAPI, OIDC (Keycloak), architectural invariants pinned by tests, GovStack alignment where applicable | existing + **DPG-05 ✅ 2026-08-18** — `SECURITY.md` (private channel, SEAH-aware scope), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/` + PR template, all at the repo root. Governance model + release/versioning **deliberately deferred** pending consultant-Q10 and DPG-03 ([followup](followups/governance-and-versioning-policy.md)) |
| 9 | Do no harm | Redaction of third-party PII; officer access controls; audit log | Sprint 3 + existing |
| 9a | Data privacy & security | **`docs/dpg/privacy-assessment.md`** §3.3 (controls), §5 (retention/deletion/breach). ⚠ **Retention has no chosen period, deletion is not built at all, and the breach procedure is unwritten** — all three now stated as gaps with named owners rather than implied. Sprint 3 builds the redaction | DPG-04 ✅, Sprint 3 |
| 9b | Inappropriate content | Content-detection path (`detect_sensitive_content_llm`) + moderation policy | existing + DPG-13 |
| 9c | Harassment protection | Complainant anonymity option; SEAH workflow isolation; officer conduct policy | existing |

**Indicator 4 answer, to be pasted once Sprints 1–2 land** — and *not before*, because until then it is false:

> Yes — an OpenAI-compatible LLM endpoint. It is configured entirely through the `LLM_BASE_URL` and
> `MODEL_*` environment variables with no code change, across both of the system's LLM surfaces
> (chatbot intake and ticketing case analysis). The repository default is an open-weights configuration
> (Apache-2.0 text model; Apache-2.0 Whisper-class ASR), documented in
> `docs/dpg/open-model-configuration.md`. CI runs the full LLM service test suite against that open
> configuration on every commit — see [link]. **The open configuration is what production runs**; the
> commercial provider is retained as a configurable fallback should users report quality problems. A
> self-hosted vLLM deployment (T2) is **documented and costed, not deployed**, for want of a funded operator.

⚠ **Second honesty marker, added 2026-08-17.** *"The repository default is an open-weights configuration"*
is also not true at the end of Sprint 1, **by design**: Sprint 1 keeps today's models as the defaults so
DPG-10's characterization tests stay green, and the flip lands in Sprint 2 once DPG-23 has named open models
the endpoint can actually serve. See [`02` §DPG-17](02-llm-agnostic-spec.md#dpg-17) §Correction.

⚠ **Third honesty marker — the T2 sentence, resolved 2026-08-17.** T2 is **parked** (Q-03/Q-05), so the
final sentence is the "documented and costed, not deployed" form, permanently until unparked — and it may
**not** call T2 "the production target", because T1 is.

✅ **Lead with the compensating gain, because it is genuinely stronger evidence.** Production running the open
configuration exceeds what indicator 4 asks: the Standard wants demonstrated *replaceability*, and you will be
running the replacement. **State that first**, then the parked T2 plainly. A DPG submission that overstates
deployment is worse than one that understates it — and here the honest version happens to be the better one.

---

## 5. Open decisions — **19 of 20 answered 2026-08-17**

> **This section is superseded by [`QUESTIONS.md`](QUESTIONS.md)**, which is now a decision register with
> every answer verbatim and a pointer to the spec each landed in. The table below is kept for its *reasoning*
> — why each decision was consequential — with the outcome added. **Only Q-02 (licence choice, delegated to
> the consultant) and the new Q-19 (LLM budget) remain open.**

These are tracked as questions in [`QUESTIONS.md`](QUESTIONS.md); listed here with the reasoning that
makes each one consequential.

| # | Decision | Why it matters | Gated on | Question |
|---|---|---|---|---|
| 1 | ~~**Hosting jurisdiction**~~ | ⏸ **Moot: T2 is parked.** The Nepal–India political dimension remains real and the analysis is kept for unparking — but the privacy assessment should not spend itself on it | — | Q-03 ✅ |
| 2 | ~~**Who operates T2, and who pays**~~ | ✅ **Answered by not proceeding.** No run-cost owner → **T2 parked.** The gate condition worked as intended: it stopped a system nobody would fund | ADB / agency | Q-05 ✅ |
| 3 | ~~**Rasa licence status**~~ | ✅ **Largely resolved before the sprint starts.** There is no Rasa — no `rasa_chatbot/`, no Rasa service in either compose file, no NLU/server dependency. Only `rasa-sdk==3.6.2`, Apache-2.0, providing the `Tracker`/`CollectingDispatcher` types the hand-rolled orchestrator still speaks. DPG-02 confirms via `pip-licenses`; budget an hour, not a week | DPG-02 | — |
| 4 | **IP ownership** — ADB OGC | Indicator 3 is categorical. If any of this was written under an ADB contract, the IP may not be yours to donate. **The only item nobody on this repo can resolve** | ADB OGC | Q-01 |
| 5 | ~~**Nepali NER model licence**~~ | ✅ **Email the author first, budget an openly-licensed fine-tune as fallback.** No longer gates Sprint 3 — the NER layer became its own initiative (Q-12c) | DPG-32 (deferred) | Q-12 ✅ |
| 6 | ~~**Translation approach**~~ | ✅ **Chat LLM first**; a dedicated specialist service only if materially better — in which case it is a government-wide asset, like the Q-12c anonymiser | DPG-23 | Q-09 ✅ |
| 7 | ~~**Which configuration production runs**~~ | ✅ **The open one**, on cost, with the closed provider as a configurable fallback. **Stronger than the Standard requires** — and it makes DPG-23 a production pre-flight check, not only DPG evidence | DPG-23 benchmark | Q-04 ✅ |

---

## References

**DPG Standard:** [standard](https://www.digitalpublicgoods.net/standard) ·
[source repo](https://github.com/DPGAlliance/DPG-Standard) ·
[assessment questions](https://github.com/DPGAlliance/DPG-Standard/blob/master/standard-questions.md) ·
[AI systems as DPGs](https://www.digitalpublicgoods.net/blog/ai-systems-as-dpgs) ·
[UNU/ADB, *AI Systems as Digital Public Goods*](https://unu.edu/publication/ai-systems-digital-public-goods)

**Inference:** [HF Inference Providers, OpenAI-compatible](https://huggingface.co/changelog/inference-providers-openai-compatible) ·
[HF Inference getting started](https://huggingface.co/inference/get-started) ·
[vLLM speech-to-text](https://docs.vllm.ai/en/latest/serving/online_serving/speech_to_text/) ·
[vLLM docs](https://docs.vllm.ai/)

**Models & Nepali evidence:** [Comparative Analysis of Multilingual Pre-trained Models for Nepali ASR (2026)](https://arxiv.org/abs/2608.12327) ·
[Whisper large-v3](https://huggingface.co/openai/whisper-large-v3) ·
[Omnilingual ASR](https://github.com/facebookresearch/omnilingual-asr) ·
[IndicTrans2](https://huggingface.co/ai4bharat/indictrans2-en-indic-1B) ·
[Open ASR Leaderboard](https://huggingface.co/blog/open-asr-leaderboard)

**PII:** [Presidio — customizing NLP models](https://github.com/microsoft/presidio/blob/main/docs/analyzer/customizing_nlp_models.md) ·
[Presidio — developing recognizers](https://github.com/microsoft/presidio/blob/main/docs/analyzer/developing_recognizers.md) ·
[Nepali NER XLM-R](https://huggingface.co/debabrata-ai/Nepali-Named-Entity-Tagger-XLM-R) ·
[Davlan multilingual NER](https://huggingface.co/Davlan/xlm-roberta-large-ner-hrl)

⚠ **Model tags move fast.** Every model name in these specs is a *candidate*, not a decision. Treat the
selection criteria — Apache-2.0 or MIT, strong multilingual coverage, reliable guided decoding, fits one
24 GB GPU — as the durable part, and check the current catalogue at DPG-22/DPG-23 time.

### Still open after 2026-08-17

| # | Decision | Why it matters | Gated on | Question |
|---|---|---|---|---|
| 8 | **Which open licence** — Apache-2.0 or MIT | Indicator 2 fails outright with no licence at all. Apache-2.0's express patent grant matters when governments adopt and other countries fork. **Now delegated to the consultant**, so DPG-01 waits on two external answers (licence *text* and copyright *holder*) | DPG consultant | **Q-02** |
| 9 | **The LLM budget** | ✅ **Answered 2026-08-20 (Q-19): a few hundred USD, owner-funded**, covering benchmarking **and** the pilot's own inference across two districts, with a costed proposal to the Nepal Government to follow. Sprint 2 is unblocked. ⚠ The envelope is **shared with production and time-boxed to the demo months**, while the CI job's cost is neither — so *cap it first* still holds, and *who pays after the demo* is now the live question. The ADB metered-line ask is no longer needed to start, but remains the obvious route for the ongoing line | Owner → Nepal Government | **Q-19** ✅ |
| 10 | **Sprint 3's person-name residual** | ⚠ **Corrected 2026-08-18 — this row said "person names go unredacted", which is D-08's error and is false.** With DPG-32 deferred, **§31.2b still redacts names at the rule layer**: honorific/role-title triggers, a Nepali thar gazetteer, and self-identification patterns — and in a road-works GRM those catch the *named official*, the sharpest exposure. What escapes is an untitled name with an unusual surname, mentioned in passing. So the decision is about a **measured residual**, not an untouched gap: publish the DPG-35 recall figure rather than describing it either way. An interim project-personnel deny-list is still on the table and would cut the residual further | owner | in [`04` DPG-32](04-pii-redaction-spec.md#dpg-32) |
