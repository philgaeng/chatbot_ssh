# Running this system on open models

> **Audience:** a DPG reviewer, or anyone who wants to run this grievance system without depending
> on a proprietary model provider.
> **Status (2026-08-18):** the *mechanism* is built, tested and pinned. The *model choices* are not
> yet measured — see [What is not yet true](#what-is-not-yet-true), and read that section before
> quoting anything here as evidence.
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

## What is not yet true

A configuration page that overstates its position is worth less than none, so:

- ⚠ **The model ids in `.env.open` are placeholders.** They are plausible — openly-licensed, served
  by the router, multilingual — but this system has **not** been measured on them.
  Nepali classification quality, translation quality and ASR word-error rate are all unmeasured.
  [DPG-22 and DPG-23](../sprints/2026-08-llm/03-open-models-spec.md) own those numbers, and they are
  currently gated on **Q-19: there is no LLM budget**.
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
