# Running this system on open models

> **Audience:** a DPG reviewer, or anyone who wants to run this grievance system without depending on
> a proprietary model provider.
>
> **Status (2026-08-24):** the **mechanism** is built, tested and pinned. The **model choices** are
> not: the whole shortlist has been probed for *capability*, which is a different question from
> *accuracy*, and only one open candidate has any accuracy result at all — detection only, and not
> readable as a selection ([`model-benchmarks.md`](model-benchmarks.md) §4).
>
> Read [What is not yet true](#what-is-not-yet-true) before quoting anything here as evidence.

---

## The claim, and what backs it

**Every model this system calls is a configuration value.** Nine model call sites across two
independent LLM surfaces — chatbot intake and ticketing case analysis — and **none names a model, a
provider or an endpoint**. All nine resolve through one registry,
[`backend/config/llm_config.py`](../../backend/config/llm_config.py), which both surfaces import and
neither owns.

| Evidence | Where |
|---|---|
| One environment change moves **both** surfaces — both clients constructed in a single test, asserted onto the same endpoint | `tests/ticketing/test_llm_client.py::test_one_env_change_moves_both_surfaces` |
| No model name exists outside the registry — **AST-parsed, not grepped** | `tests/backend/test_llm_config_pins.py` |
| No client is constructed outside the two factories | same file |
| `.env.example` and the registry agree in **both** directions — undocumented *and* stale variables fail the build | same file |
| The two configurations declare the same variables and differ only in values | same file |

## How to switch

Two committed, secret-free templates that differ only in values:

```bash
cp .env.open   env.local.llm && $EDITOR env.local.llm   # open weights — set LLM_API_KEY=hf_…
cp .env.openai env.local.llm && $EDITOR env.local.llm   # today's default — set LLM_API_KEY=sk-…
```

Append to `env.local` and restart the services that call models (`celery_llm`, `backend`,
`ticketing_api`, `grm_celery`). **Nothing else changes** — no code, no image rebuild, no migration,
no compose edit. **`diff .env.openai .env.open` is the whole delta, and it is the answer to
indicator 4.**

## What the registry declares

| Group | Variables | Notes |
|---|---|---|
| Endpoint | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES` | Empty key ⇒ **no client is built**, and each call site takes its documented fallback rather than 401-ing per request |
| ASR endpoint | `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_TIMEOUT` | Falls back to the chat endpoint field by field; separate because transcription commonly runs elsewhere |
| Models | `MODEL_CLASSIFY`, `MODEL_EXTRACT`, `MODEL_TRANSLATE`, `MODEL_DETECT`, `MODEL_ASR`, `MODEL_TICKET_TRANSLATE`, `MODEL_TICKET_FINDINGS`, `MODEL_TICKET_FINDINGS_SEAH` | **Eight task keys, two values.** `MODEL_TICKET_TRANSLATE` empty ⇒ follows `MODEL_TRANSLATE` |
| Deadlines | `TIMEOUT_CLASSIFY`, `TIMEOUT_TICKET` | Per task; 0 ⇒ the endpoint's |
| Structured output | `LLM_STRUCTURED_OUTPUT` + `STRUCTURED_*` per task | See below |
| Deprecated | `OPENAI_API_KEY`, `OPENAI_CLASSIFICATION_TIMEOUT` | Still honoured; one warning each |

### Structured output is a per-model property, and that is measured

`json_schema` constrains generation to a grammar, so a reply is guaranteed parseable. Support belongs
to the **(endpoint, model) pair**, not the endpoint. Measured against the live provider on
2026-08-18, one request per cell:

| Model | `json_schema` | `json_object` |
|---|---|---|
| `gpt-5-nano`, `gpt-4o-mini` | ✅ | ✅ |
| `gpt-3.5-turbo` | **400** | ✅ |
| `gpt-4` | **400** | **400** |

Each task declares its own capability, `LLM_STRUCTURED_OUTPUT` is the endpoint ceiling, and the
effective mode is the weaker of the two. The ladder degrades `json_schema` → `json_object` →
`prompt`, and the rung used is logged per call. **An endpoint with no JSON mode at all still works.**

## The deployment ladder

| Tier | `LLM_BASE_URL` | Status |
|---|---|---|
| **T1** — hosted open weights | `https://router.huggingface.co/v1` | ✅ Supported; the `.env.open` configuration |
| **T2** — self-hosted vLLM | `http://<private-ip>:8000/v1` | ⏸ Designed and costed, **parked** — no owner for the GPU running costs ([`vllm-deployment.md`](vllm-deployment.md)) |
| **T3** — on-prem | `http://localhost:8000/v1` | As T2, inside DOR infrastructure |
| — | `https://api.openai.com/v1` | Today's default, and the benchmark comparison |

**The code is identical at every tier.** Only these variables change.

## The open endpoint, probed (2026-08-20) {#the-open-endpoint-probed--dpg-21-2026-08-20}

`scripts/ops/llm_smoke.py` is a committed, re-runnable probe. It resolves the endpoint from the same
registry the product uses, asks each model six questions, and prints a `ModelProfile` to paste into
the registry. A reviewer can run it:

```bash
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
  run --rm --no-deps -v "$PWD:/app" -w /app \
  -e LLM_BASE_URL=https://router.huggingface.co/v1 -e LLM_API_KEY="$HF_TOKEN" \
  backend python -m scripts.ops.llm_smoke --candidates --json report.json
```

| Model | Licence *(from the model card, at probe time)* | chat | `json_object` | `json_schema` | Probe latency |
|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | apache-2.0 | ✅ | ✅ | ✅ | **0.73 s** |
| `openai/gpt-oss-120b` | apache-2.0 | ✅ | ✅ | ✅ | **0.68 s** |
| `Qwen/Qwen3.5-27B` | apache-2.0 | ✅ | ✅ | ✅ | 20.48 s |
| `Qwen/Qwen3.5-35B-A3B` | apache-2.0 | ✅ | ✅ | ✅ | 9.35 s |
| `Qwen/Qwen3.5-9B` | apache-2.0 | ✅ | ✅ | ⚠ **accepted, not honoured** | 23.78 s |
| `swiss-ai/Apertus-70B-Instruct-2509` | apache-2.0 | ❌ **"Your request was blocked"** | — | — | 0.42 s |
| `microsoft/phi-4` | mit | ✅ | ✅ | ✅ | 1.77 s |
| *audio / transcription* | — | ❌ **404 — the router serves no `/v1/audio/*` route** | | | |

*(Probe latency is one `json_schema` request on a one-sentence prompt — not a benchmark number. It is
here because the spread is three orders of magnitude, and against a 30-second interactive budget that
is a selection input rather than a footnote.)* **Licences were verified for all seven**, Apertus
included, because model-card lookups are free.

### ⭐ Three findings the probe paid for

1. **`Qwen3.5-9B` accepts `json_schema` and ignores it** — HTTP 200, well-formed JSON, and **not one
   of the required fields.** Invisible to any probe that asks for *some JSON* and calls a successful
   parse a pass, so the probe schema requires a `district` field the prompt never mentions. Pinned to
   `json_object`. ⚠ **Unmeasured, a fresh clone pointed there would emit malformed output under load
   with nothing to explain why.**
2. ⚠ **`Apertus-70B` refused the benchmark's flagship item** — construction dust, children falling
   ill — with *"Your request was blocked."* **A content filter that blocks a grievance about
   children's health is disqualifying for a grievance system**, because it fails closed on exactly
   the reports that matter most. A real loss: Apertus was the strongest *DPG story* in the shortlist,
   with open weights **and** open training data.
3. ⚠ **Latency varies by 30×**, and the slow end is not survivable against a 30-second budget.

### ⚠ A trap for anyone re-running this: the router rate-limits and calls it credit exhaustion

Probing several models in quick succession returns **HTTP 402**, *"You have depleted your monthly
included credits"*. **It does not mean what it says.** It is a short-window **rate** limit worded as a
monthly one, and the same models pass when probed one at a time seconds later. Taken at face value it
reports most of a shortlist as unmeasurable.

The committed probe therefore backs off and retries **account-level** refusals and paces itself
between models — but never retries **model-level** refusals, because a 400 on `json_schema` is the
answer being sought rather than an obstacle.

### The candidate shortlist, and what the licence filter excluded

The list lives in [`scripts/ops/llm_candidates.json`](../../scripts/ops/llm_candidates.json) as
**data**, deliberately: the licence limb is provisional
([`00_compliance_status.md`](00_compliance_status.md) Q-04-02), so widening the field is an edit to
one file rather than a redesign.

**Excluded on licence, not on quality** — worth naming, because on a low-resource language this may
be costing real accuracy:

| Model | Licence | Note |
|---|---|---|
| `google/gemma-4-31B-it`, `google/gemma-3-27b-it` | Gemma Terms of Use | Use restrictions. Among the strongest multilingual options at this size |
| `meta-llama/Llama-3.3-70B-Instruct` | Llama 3.3 Community | Use restrictions + acceptable-use policy |
| `CohereLabs/aya-expanse-32b` | **CC-BY-NC-4.0** | ⚠ **The one that hurts** — purpose-built for multilingual coverage, exactly the right size, and **this exclusion does not loosen however Q-04-02 is answered**: non-commercial is incompatible with government production |
| `aisingapore/Gemma-SEA-LION-v4-27B-IT` | Gemma Terms of Use | Also targets South-**East** Asian languages; Nepali is not in its focus set |
| `zai-org/GLM-4.5-Air` | MIT | Licence fine — excluded on **size** (106B) |

### ⚠ Provider independence is claimed but only partly demonstrated

The router fans out across Together, Groq, Novita, Fireworks, DeepInfra and others, so the evidence
is independence from *any* single vendor rather than from OpenAI alone: `gpt-oss-20b` is offered by
**eight** and `gpt-oss-120b` by **eleven** (router catalogue, 2026-08-20).

**But only one route has been exercised** — the router selected Groq for the successful probes. The
alternatives are OpenAI-compatible and need no code change, but **none has been probed**, since each
needs its own account. **Do not read the fan-out count as a measurement.**

## What is not yet true

- ⚠ **The model ids in `.env.open` are placeholders for *quality*.** The probe measured licences,
  structured-output behaviour and reasoning overheads across the shortlist. **None of that is an
  accuracy result** — capability is not quality, and conflating them is the easiest overstatement
  available here.
- ⚠ **Transcription is not served by this configuration at all.** The router returns **404** for
  `/v1/audio/transcriptions`, verified for three model ids while `/v1/models` and
  `/v1/chat/completions` return 200 on the same token. So *"the open configuration runs the whole
  system"* is **false for audio** and true for text.
  ⭐ **The consequence runs in our favour:** the one path the open provider cannot serve is the one
  path that does not run — voice transcription is switched off on cost grounds — so **the open
  configuration covers every model call this system actually makes.**
- ⚠ **The accuracy comparison is one column short**, and the open candidate's perfect SEAH
  false-alarm rate is uninterpretable without recall. Both are in
  [`model-benchmarks.md`](model-benchmarks.md) §4 and §5, not restated here. **Until that column
  lands, no model here may be selected on the evidence that exists.**
- ⚠ **The repository default is still the proprietary configuration**, deliberately. An open base URL
  with unvalidated model ids is a repository that cannot serve one request on a fresh clone — weaker
  evidence, not stronger. The flip is one line per task, once the open column exists.
- ⚠ **Configurable provider is not knowable jurisdiction.** The router selects a partner **per
  request** unless the model id pins one (`openai/gpt-oss-120b:groq`). Production must pin; CI need
  not, since it sends synthetic data only. This registry makes the *choice* configurable; it does not
  make the *location of execution* knowable ([privacy assessment](privacy-assessment.md) F-17).
- ⚠ **Grievance text still reaches the provider unredacted.** Switching providers is not a privacy
  control.

## Related

- [`00_compliance_status.md`](00_compliance_status.md) — the indicator-by-indicator assessment
- [`model-benchmarks.md`](model-benchmarks.md) — what the models score
- [`vllm-deployment.md`](vllm-deployment.md) — self-hosting, designed and costed
- [`privacy-assessment.md`](privacy-assessment.md) — where grievance text goes, leg by leg
- [`docs/services/06_llm_service.md`](../services/06_llm_service.md) · [`docs/deployment/11_llm_pipeline_policy.md`](../deployment/11_llm_pipeline_policy.md) — the two surfaces
