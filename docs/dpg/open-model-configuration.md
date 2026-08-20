# Running this system on open models

> **Audience:** a DPG reviewer, or anyone who wants to run this grievance system without depending
> on a proprietary model provider.
> **Status (2026-08-20):** the *mechanism* is built, tested and pinned, and the endpoint has now been
> **probed** — see [The open endpoint, probed](#the-open-endpoint-probed--dpg-21-2026-08-20). The
> *model choices* are still not measured for **quality**: capability (what a model can be told) is a
> different question from accuracy (what it gets right), and only the first has been answered.
> Read [What is not yet true](#what-is-not-yet-true) before quoting anything here as evidence.
> Owner: [`docs/sprints/2026-08-llm/02-llm-agnostic-spec.md`](../sprints/2026-08-llm/02-llm-agnostic-spec.md) DPG-16.

---

## The claim, and what backs it

**Every model this system calls is a configuration value.** There are nine model call sites across
two independent LLM surfaces — the chatbot intake path and the ticketing case-analysis path — and
none of them names a model, a provider or an endpoint. All nine resolve through one registry,
[`backend/config/llm_config.py`](../../backend/config/llm_config.py), which both surfaces import and
neither owns.

What backs it, in order of how hard it is to argue with:

| Evidence | Where |
|---|---|
| One environment change moves **both** surfaces — both clients are constructed in a single test and asserted onto the same endpoint | `tests/ticketing/test_llm_client.py::test_one_env_change_moves_both_surfaces` |
| No model name exists outside the registry — AST-parsed, not grepped, across `backend/` and `ticketing/` | `tests/backend/test_llm_config_pins.py` |
| No client is constructed outside the two factories | same file |
| `.env.example` and the registry agree in **both** directions — undocumented variables and stale ones both fail the build | same file |
| The two configurations declare the same variables and differ only in values | same file |

## How to switch

Two committed files differ only in values. Neither contains a secret; both are templates.

```bash
# open weights, via Hugging Face Inference Providers
cp .env.open env.local.llm && $EDITOR env.local.llm     # set LLM_API_KEY=hf_…

# or today's default
cp .env.openai env.local.llm && $EDITOR env.local.llm   # set LLM_API_KEY=sk-…
```

Append the block to `env.local` and restart the services that call models
(`celery_llm`, `backend`, `ticketing_api`, `grm_celery`). **Nothing else changes**: no code, no
image rebuild, no migration, no compose edit. `diff .env.openai .env.open` is the whole delta, and
it is the answer to indicator 4.

## What the registry declares

| Group | Variables | Notes |
|---|---|---|
| Endpoint | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES` | `LLM_API_KEY` empty ⇒ **no client is built**, and each call site takes its documented fallback rather than 401-ing per request |
| ASR endpoint | `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_TIMEOUT` | Falls back to the chat endpoint field by field. Separate because transcription commonly runs elsewhere and is far slower |
| Models | `MODEL_CLASSIFY`, `MODEL_EXTRACT`, `MODEL_TRANSLATE`, `MODEL_DETECT`, `MODEL_ASR`, `MODEL_TICKET_TRANSLATE`, `MODEL_TICKET_FINDINGS`, `MODEL_TICKET_FINDINGS_SEAH` | Eight task keys. `MODEL_TICKET_TRANSLATE` empty ⇒ follows `MODEL_TRANSLATE` |
| Deadlines | `TIMEOUT_CLASSIFY`, `TIMEOUT_TICKET` | Per task; 0 ⇒ the endpoint's |
| Structured output | `LLM_STRUCTURED_OUTPUT` + `STRUCTURED_*` per task | See below |
| Deprecated | `OPENAI_API_KEY`, `OPENAI_CLASSIFICATION_TIMEOUT` | Still honoured; one warning each |

### Structured output is a per-model property, and that is measured

`json_schema` constrains generation to a grammar, so a reply is guaranteed parseable. Support is a
property of the **(endpoint, model) pair** — not of the endpoint, which is what the sprint plan
originally assumed. Measured against the live provider on 2026-08-18, one request per cell:

| Model | `json_schema` | `json_object` |
|---|---|---|
| `gpt-5-nano` | ✅ | ✅ |
| `gpt-4o-mini` | ✅ | ✅ |
| `gpt-3.5-turbo` | **400** | ✅ |
| `gpt-4` | **400** | **400** |

So each task declares its own capability, `LLM_STRUCTURED_OUTPUT` is the endpoint ceiling, and the
effective mode is the weaker of the two. The ladder degrades — `json_schema` → `json_object` →
`prompt` — and the rung used is logged per call. An endpoint with no JSON mode at all still works.

## The deployment ladder

| Tier | `LLM_BASE_URL` | Status |
|---|---|---|
| **T1** — hosted open weights | `https://router.huggingface.co/v1` | ✅ Supported. The configuration in `.env.open` |
| **T2** — self-hosted vLLM | `http://<private-ip>:8000/v1` | ⏸ Designed, **parked** — no owner for GPU running costs (Q-03/Q-05). Documented and costed by DPG-25, not deployed |
| **T3** — on-prem | `http://localhost:8000/v1` | Same as T2, inside DOR infrastructure |
| — | `https://api.openai.com/v1` | Today's default, and the benchmark comparison |

**The code is identical at every tier.** Only these variables change.

## The open endpoint, probed — DPG-21 (2026-08-20)

`scripts/ops/llm_smoke.py` is a committed, re-runnable probe. It resolves the endpoint from the same
registry the product uses, asks each model six questions — one request per cell — and prints a
`ModelProfile` tuple to paste into `backend/config/llm_config.py`. A reviewer can run it themselves:

```bash
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
  run --rm --no-deps -v "$PWD:/app" -w /app \
  -e LLM_BASE_URL=https://router.huggingface.co/v1 -e LLM_API_KEY="$HF_TOKEN" \
  backend python -m scripts.ops.llm_smoke --candidates --json report.json
```

### What it found — the full shortlist, measured

Second pass, 2026-08-20, paced (see the rate-limit note below). Six probes per model, one request
per cell.

| Model | Licence *(from the model card, at probe time)* | chat | `json_object` | `json_schema` | `temperature` | `max_tokens` | Probe latency |
|---|---|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | **0.73 s** |
| `openai/gpt-oss-120b` | apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | **0.68 s** |
| `Qwen/Qwen3.5-27B` | apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | 20.48 s |
| `Qwen/Qwen3.5-35B-A3B` | apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | 9.35 s |
| `Qwen/Qwen3.5-9B` | apache-2.0 | ✅ | ✅ | ⚠ **accepted, not honoured** | ✅ | ✅ | 23.78 s |
| `swiss-ai/Apertus-70B-Instruct-2509` | apache-2.0 | ❌ **"Your request was blocked"** | — | — | — | — | 0.42 s |
| `microsoft/phi-4` | mit | ✅ | ✅ | ✅ | ✅ | ✅ | 1.77 s |
| *audio / transcription* | — | ❌ **404 — the router serves no `/v1/audio/*` route at all** (see below) | | | | | |

*(Probe latency is the `json_schema` request on a **one-sentence** prompt — not a benchmark number.
It is here because the spread is three orders of magnitude and that is a finding in itself.)*

### ⭐ Three things this cost six requests each and was worth it

**1. `Qwen/Qwen3.5-9B` accepts `json_schema` and ignores it.** HTTP 200, well-formed JSON, and
**not one of the fields the schema declares required**. This is the failure DPG-13's degradation
ladder exists for, caught in the wild — and it is invisible to any probe that asks for *some JSON*
and calls a successful parse a pass. The probe schema requires a `district` field the prompt never
mentions, precisely so "returned JSON" and "was constrained" can be told apart. The model is pinned
to `json_object` in `_PROFILES`, which is the strongest rung it actually applies.

⚠ **Had this not been measured, a fresh clone pointed at that model would have produced malformed
output under load and nothing would have explained why.**

**2. ⚠ `swiss-ai/Apertus-70B-Instruct-2509` refused the request outright** — *"Your request was
blocked."* The prompt was the benchmark's flagship item: construction dust entering a house, children
falling ill. **A content filter that blocks a grievance about children's health is disqualifying for
a grievance system**, whatever the model's quality, and it would fail closed on exactly the reports
that matter most. That is a shame — Apertus was the strongest *DPG story* in the shortlist (fully
open weights **and** open training data, built for low-resource language coverage). It gets no
`_PROFILES` entry; an unmeasured model takes the conservative default rather than a guess. See the
[follow-up](../sprints/2026-08-llm/followups/apertus-content-filter-blocks-a-grievance.md).

**3. ⚠ Latency varies by 30×, and the slow end is not survivable.** `gpt-oss` answers a one-sentence
probe in **0.7 s**; `Qwen3.5-9B` takes **23.8 s** and emits 2,048 completion tokens to do it. The
real classification prompt is ~20,700 characters before the complaint is added. **Against a 30-second
interactive budget, the Qwen family is a serious risk and `gpt-oss` has enormous headroom** — and
that is a selection input, not a footnote, because latency here is pass/fail rather than a table row.

### ⚠ And a correction worth carrying: the router rate-limits and calls it a credit failure

The first pass reported six of seven candidates as unmeasurable, on the strength of
*"You have depleted your monthly included credits"* (HTTP 402). **That was wrong.** Probing the same
models **one at a time**, seconds later, every one passed. It is a short-window rate limit whose
message is about the month. The probe now backs off and retries account-level refusals — never model
refusals, because a 400 on `json_schema` is the answer and not an obstacle — and paces itself between
models. [The write-up](../sprints/2026-08-llm/followups/hf-router-rate-limit-reads-as-credit-exhaustion.md).

**Licences were verified for all seven**, including Apertus, because model-card lookups are free.

### The candidate shortlist, and what the licence filter excluded

The list lives in [`scripts/ops/llm_candidates.json`](../../scripts/ops/llm_candidates.json) as
**data**, deliberately: the licence limb of the filter is provisional
([`00_compliance_status.md`](00_compliance_status.md) consultant-Q5), so if restricted-use open
weights turn out to satisfy indicator 4, widening the field is an edit to one file rather than a
redesign.

**Excluded on licence, not on quality** — worth naming, because on a low-resource language this
exclusion may be costing real accuracy:

| Model | Licence | Note |
|---|---|---|
| `google/gemma-4-31B-it`, `google/gemma-3-27b-it` | Gemma Terms of Use | Bespoke community licence with use restrictions. Among the strongest multilingual options at this size |
| `meta-llama/Llama-3.3-70B-Instruct` | Llama 3.3 Community | Use restrictions + acceptable-use policy |
| `CohereLabs/aya-expanse-32b` | **CC-BY-NC-4.0** | ⚠ The one that hurts. Aya is *purpose-built* for multilingual coverage and is exactly the right size — but non-commercial is incompatible with a government production deployment **however consultant-Q5 is answered**, so unlike the rows above this exclusion does not loosen |
| `aisingapore/Gemma-SEA-LION-v4-27B-IT` | Gemma Terms of Use | Inherits Gemma terms. Also targets South-**East** Asian languages; Nepali is not in its focus set |
| `zai-org/GLM-4.5-Air` | MIT | Licence is fine — excluded on **size** (106B, far outside the 24 GB limb). Recorded so a later reader knows it was considered |

### ⚠ Provider independence is claimed but only partly demonstrated

The router's value for indicator 4 is that it fans out across Together, Groq, Novita, Fireworks,
DeepInfra and others, so the evidence is independence from *any single vendor* rather than from
OpenAI alone. `openai/gpt-oss-20b` is offered by **eight** of them and `openai/gpt-oss-120b` by
**eleven**, read from the router's own catalogue on 2026-08-20.

**What has actually been exercised is one route** — the router selected Groq for the successful
probes. The alternative base URLs in the sprint spec (Together, Fireworks, DeepInfra, Groq direct,
OpenRouter) are OpenAI-compatible and the code needs no change to use them, but **none has been
probed**, because each needs its own account. Do not read the fan-out count as a measurement.

## What is not yet true

A configuration page that overstates its position is worth less than none, so:

- ⚠ **The model ids in `.env.open` are still placeholders for *quality*.** DPG-21 (2026-08-20)
  measured the **whole shortlist**: licences confirmed from the model cards, `json_schema` honoured
  by five of six reachable candidates and *silently ignored* by the sixth, reasoning overheads
  measured, and every result landed in `_PROFILES`. None of that is an accuracy result.
  **Capability is not quality**, and conflating them is the easiest overstatement available here.
- ⚠ **Transcription is not served by this configuration at all.** The router returns **404** for
  `/v1/audio/transcriptions` — verified for three model ids, with `/v1/models` and
  `/v1/chat/completions` both returning 200 on the same token. So *"the open configuration runs the
  whole system"* is **false for audio** and true for text. Nothing breaks today because voice is
  switched off, and it would break the day it is switched on
  ([follow-up](../sprints/2026-08-llm/followups/the-open-config-has-no-working-asr-endpoint.md)).
  Nepali classification quality, translation quality and ASR word-error rate are all unmeasured.
  [DPG-22 and DPG-23](../sprints/2026-08-llm/03-open-models-spec.md) own those numbers. ✅ **Funded as of
  2026-08-20** (Q-19 — a few hundred USD, owner-paid, shared with the pilot's own inference), so the
  measurements are scheduled rather than blocked. ⚠ **Until they land, nothing here may be cited as a
  measured result** — placeholders that acquire a funding date are still placeholders.
- ⚠ **The repository default is still the proprietary configuration**, deliberately. An open base
  URL combined with proprietary model ids is a repository that cannot serve one request on a fresh
  clone — weaker evidence than an honest default, not stronger. The flip is one line per task in the
  registry, once DPG-23 reports (Q-10).
- ⚠ **Configurable provider is not the same as knowable jurisdiction.** The Hugging Face router
  selects a partner **per request** unless the model id pins one (`openai/gpt-oss-120b:groq`).
  Production must pin; CI need not, because it sends synthetic data only. This registry makes the
  *choice* configurable; it does not make the *location of execution* knowable
  ([privacy assessment](privacy-assessment.md) F-17).
- ⚠ **Grievance text still reaches the provider unredacted.** Switching providers is not a privacy
  control. Redaction at the model-call boundary is
  [Sprint 3](../sprints/2026-08-llm/04-pii-redaction-spec.md), and it hooks the same chokepoint this
  sprint created.
- ⚠ **Voice transcription is not live**, for lack of budget, so the ASR path is correct-by-signature
  and unit-tested but has no field evidence and no WER baseline (DPG-22).

## Related

- [`00_compliance_status.md`](00_compliance_status.md) — the indicator-by-indicator briefing
- [`privacy-assessment.md`](privacy-assessment.md) — where grievance text goes, leg by leg
- [`dependency-licenses.md`](dependency-licenses.md) — 153 packages, dispositioned
- [`docs/services/06_llm_service.md`](../services/06_llm_service.md) — the chatbot surface
- [`docs/deployment/11_llm_pipeline_policy.md`](../deployment/11_llm_pipeline_policy.md) — the ticketing surface
