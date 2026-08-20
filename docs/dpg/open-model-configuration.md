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

### What it found

| Model | Licence *(from the model card, at probe time)* | chat | `json_object` | `json_schema` | `temperature` | `max_tokens` | Served by |
|---|---|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | groq |
| `openai/gpt-oss-120b` | apache-2.0 | ✅ | ✅ | ✅ | ⚠ blocked | ⚠ blocked | — |
| `Qwen/Qwen3.5-27B` | apache-2.0 | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | — |
| `Qwen/Qwen3.5-35B-A3B` | apache-2.0 | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | — |
| `Qwen/Qwen3.5-9B` | apache-2.0 | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | — |
| `swiss-ai/Apertus-70B-Instruct-2509` | apache-2.0 | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | — |
| `microsoft/phi-4` | mit | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | ⚠ blocked | — |
| *audio / transcription* | — | ⚠ Not measured — no audio subset exists ([followup](../sprints/2026-08-llm/followups/no-audio-subset-for-asr-benchmark.md)) | | | | | |

> ⚠ **`⚠ blocked` is a billing state, not a model property.** The Hugging Face account exhausted its
> monthly included inference credits partway through the run (HTTP 402). Those cells measure the
> wallet and say nothing about the models. They are marked, not left blank and not rendered as ❌ —
> because the first version of the probe *did* render them as ❌, and *"depleted your monthly
> included credits"* came out looking exactly like *"this model does not support `temperature`"*.
> That is the failure `docs/models/01_seah_detection_benchmark.md` §6.1 makes a standing rule about,
> and `tests/backend/test_llm_smoke.py` now pins the distinction.
>
> **Licences were still verified for every candidate**, because model-card lookups are free.

### The two facts this bought, which were not free

1. **`json_schema` is genuinely honoured by `gpt-oss`, not merely accepted.** The probe schema
   requires a `district` field the prompt never mentions, so a provider that silently drops
   `response_format` returns a reply without it. That is the whole difference between "returned
   JSON" and "was constrained", and asking for *some JSON* cannot tell them apart. Everything on the
   `json_schema` rung of DPG-13's ladder therefore works on the open configuration too.
2. ⚠ **`gpt-oss` reasons, and the registry did not know.** Unrecognised ids fall through to
   `DEFAULT_PROFILE`, whose `reasoning_overhead` is **0** — and `.env.open` ships `gpt-oss-20b` as the
   default open model. A token cap consumed entirely by the reasoning phase returns
   `finish_reason: length` with **empty content**: not an error, not a truncation anyone notices,
   just nothing. That is D-40, and the repository's own open configuration was one long ticket
   timeline away from it. A measured 1,000-token floor is now in `_PROFILES`, pinned by
   `tests/backend/test_llm_config.py`.

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
  established that `gpt-oss` **can be driven correctly** — permissive licence confirmed from the
  model card, `json_schema` honoured rather than merely accepted, reasoning overhead measured and
  landed in `_PROFILES`. None of that is an accuracy result. **Capability is not quality**, and
  conflating them is the easiest overstatement available here.
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
