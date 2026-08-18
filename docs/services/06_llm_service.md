# LLM Service Spec

## 1) Scope

Shared LLM utility/service layer used by async task pipelines and chatbot workflows.

Implementation:

- `backend/services/LLM_services.py` — the capabilities below
- `backend/services/llm_client.py` — **the only place this surface constructs a client** (DPG-11).
  Lazy, cached, built from the shared registry. It names no model and no endpoint.
- `backend/config/llm_config.py` — **the only place any model name or endpoint is declared**, for
  this surface *and* the ticketing one (DPG-17)

⚠ **Do not construct an `OpenAI(...)` here or anywhere else in `backend/`.** Until 2026-08-18 this
module built one at import (swallowing the failure into `client = None`, which is why five
functions carry five different guards) *and* a second one inside `classify_and_summarize_grievance`
that shadowed it. Both are gone; a test fails if a third appears
(`tests/backend/test_llm_config_pins.py`).

## 2) Capabilities

### Audio transcription

- `transcribe_audio_file(file_path, language_code)`
- model: `whisper-1`, resolved from configuration (see §3)

⚠ **Not verified end-to-end — and it demonstrably did not work until 2026-08-18.** The call passed
`language_code=…` to `client.audio.transcriptions.create`. The OpenAI SDK's parameter is `language`,
and `Transcriptions.create` declares its parameters explicitly with no `**kwargs`, so **every call on
this path raised `TypeError`**, was logged, and re-raised. Verified against the pinned
`openai==1.70.0` in-container, not inferred (DPG-14.3).

Corrected to `language=…` and pinned by `tests/backend/test_llm_services.py::test_transcribe_request_binds_against_the_real_openai_signature`,
which binds the request the code sends against the installed SDK signature — a mock accepts any
keyword, which is why a mock-only assertion could not have caught this.

**What can honestly be claimed: the signature is now correct and unit-tested. Not that transcription
works.** Voice transcription is not live (Q-13.2 — no LLM budget for it), so no field evidence exists
or can exist, and there is no Nepali WER baseline until DPG-22.

### Contact extraction

- `extract_contact_info(...)`
- `extract_all_contact_info(...)`

Extracts structured contact/location data from natural-language inputs.

### Grievance classification + summarization

- `classify_and_summarize_grievance(...)`
- model: `gpt-5-nano` — **a deliberate cost choice** (Q-13.1), not the drift it looks like. This is
  the primary AI path in the product, and it is the baseline DPG-23 benchmarks the open models against.

Returns structured output:

- `grievance_summary`
- `grievance_categories`
- `grievance_categories_alternative`
- `follow_up_question`

**Measured 2026-08-18** (DPG-14.1, three live calls with a realistic Nepali grievance, in-container):

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `finish_reason` | `stop` | `stop` | `stop` |
| Prompt tokens | 4,259 | ~4,259 | ~4,259 |
| Completion tokens | 3,087 | 2,222 | 2,157 |
| — of which **reasoning** | **2,880** | **2,048** | **1,984** |
| Server processing | **20.5 s** | 15.2 s | 14.0 s |

Two things follow, and both matter more than the model name:

1. **No truncation.** `finish_reason` was `stop` on every run, so the suspicion behind DPG-14.1 —
   that a length limit was silently producing malformed JSON which `parse_llm_response` swallowed
   into `{}` — is **not** what is happening. Recorded as a corrected non-finding.
2. ⚠ **Latency sits on top of the retrieve step's 20-second poll deadline**
   (`CLASSIFICATION_POLL_MAX_SECONDS`, `backend/actions/grievance_intake/classification.py`). One of
   three successful runs exceeded it. When that happens the complainant is shown the empty-classification
   path even though the model succeeded and the row is filled moments later. See **D-30**.
   The reasoning tokens are why: 92% of the completion budget on run 1 was invisible reasoning, and the
   prompt is 20,725 characters because the full category catalogue and its dictionary are injected.

### Sensitive-content detection

> ⚠ **There are THREE SEAH signals, not one, and only the second is on this page.** Documented here
> 2026-08-18 (DPG-19b) because Q-14's fail-open decision rests on the first one existing, and no
> spec said so:
>
> | Signal | Where | Model? |
> |---|---|---|
> | **Deterministic keyword detector**, scored | `backend/shared_functions/keyword_detector.py` → slot validation, **inside the conversation** | none |
> | **This function**, async via Celery | `detect_sensitive_content_llm` | yes |
> | **The classification's categories** | `classify_and_summarize_grievance` returns categories; the review step keeps any containing `"gender"` (`form_grievance_complainant_review.py::detect_sensitive_categories`) | yes, the same call |
>
> So an LLM outage degrades a second pass and leaves the deterministic one running — which is what
> makes fail-open defensible (Q-14). ⚠ **If the keyword path ever stops running independently,
> fail-open stops being justified.**

- `detect_sensitive_content_llm(text, language_code)`

Specialized to detect sexual/gender harassment indicators; intentionally excludes non-target categories like land disputes.

### Translation

- `translate_grievance_to_english_LLM(...)`
- `translate_grievance_to_english(grievance_id)`

Produces English normalized copies and metadata for storage.

## 3) Configuration Dependencies

**Every model name, endpoint, timeout, retry count and structured-output mode this service uses is
declared in one file: [`backend/config/llm_config.py`](../../backend/config/llm_config.py) (DPG-17).**
This spec deliberately does not restate them — a second list is a list that drifts, and the model
names in this product had already been copied into four modules before that registry existed.

- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_TIMEOUT` / `LLM_MAX_RETRIES` / `LLM_STRUCTURED_OUTPUT`
- `ASR_BASE_URL` / `ASR_API_KEY` / `ASR_TIMEOUT` — the transcription endpoint, which may be a
  different provider or machine
- `MODEL_CLASSIFY`, `MODEL_EXTRACT`, `MODEL_TRANSLATE`, `MODEL_DETECT`, `MODEL_ASR` — per-task,
  each defaulting to the model this service used before the registry existed
- `TIMEOUT_CLASSIFY` — classification's own budget (default 120 s); `OPENAI_CLASSIFICATION_TIMEOUT`
  is honoured as a deprecated alias, with one warning
- `OPENAI_API_KEY` — deprecated alias for `LLM_API_KEY` / `ASR_API_KEY`; honoured, warned about once
- category dictionaries from `backend/config/constants.py`

The same registry is read by the ticketing surface (`ticketing/clients/llm_client.py`), so one
`LLM_BASE_URL` change moves both. That is the DPG indicator-4 property, and it is pinned by a test
rather than asserted here — `tests/backend/test_llm_config.py`, `tests/backend/test_llm_config_pins.py`.

### Structured output — schemas, and the ladder that degrades them

Seven of the nine call sites produce JSON. Each declares a Pydantic model
(`backend/services/llm_schemas.py`, `ticketing/clients/llm_schemas.py`), and the request carries a
**strict `json_schema`** wherever the model supports it — generation is then constrained to the
grammar, so the reply is *guaranteed* parseable rather than probably parseable.

⚠ **Support is a property of the (endpoint, model) pair, not of the endpoint.** Measured against the
live provider, 2026-08-18, one request per cell:

| Model | `json_schema` | `json_object` |
|---|---|---|
| `gpt-5-nano` | ✅ | ✅ |
| `gpt-4o-mini` | ✅ | ✅ |
| `gpt-3.5-turbo` | **400** | ✅ |
| `gpt-4` | **400** | **400** — no JSON mode at all |

So each task declares its own capability in the registry, `LLM_STRUCTURED_OUTPUT` is the endpoint's
ceiling, and the effective mode is the weaker of the two. The ladder degrades — `json_schema` →
`json_object` → `prompt` — and never guesses upward; the rung used is logged per call.

**What this closed.** Two call sites — classification and translation, the primary AI path and the
English record — sent *no* `response_format` and asked for "strict JSON" in the prompt. A malformed
reply was absorbed by `parse_llm_response` into `{}`, which is exactly what a successful *empty*
classification looks like. It now raises `LLMResponseParseError`, the caller's own error contract
fires, and the log records the response **length, not its content**.

⚠ **Categories are validated against the live catalogue, not a frozen enum.** The taxonomy is
admin-configurable and resynced into `public.grievance_classification_taxonomy`; a `Literal[...]` of
today's categories would require a code change per category and break the resync. A value outside the
catalogue is **logged, not rejected** — a mis-named category is not a reason to discard a
complainant's classification.

## 4) Error and Fallback Behavior

- Missing client/config returns structured failure/fallback payloads in many functions. **Three
  different idioms** — raise, sentinel dict, `None` — one per function, pinned as they are by
  `tests/backend/test_llm_services.py`. Unifying them is a behaviour change nobody has scheduled.
- ⚠ **A failure payload is not a result.** Callers must check: the classification failure dict is
  **truthy**, and a task that only guarded `if not values:` stored it as a success —
  `grievance_classification_status = LLM_generated` with an empty summary (fixed 2026-08-18,
  DPG-15/D-32). Use `is_failed_classification()` / `is_empty_extraction()` from
  `backend/config/classification_status.py`.
- ⚠ **Never write an empty extraction over stored data.** An outage once overwrote a complainant's
  phone number with `""` (D-33). Losing the enrichment is recoverable; losing the number is not.
- Parse failures now **raise** `LLMResponseParseError` rather than returning `{}` — a malformed
  reply and an empty result were previously the same value (DPG-13).

### Degraded mode

Intake never waits on a model. The grievance row is written to Postgres first, classification is a
Celery task, and the retrieve step polls with a 20-second deadline. Verified by pointing
`LLM_BASE_URL` at a dead port and driving the real tasks against the real database.

`GET /health/llm` (backend API) reports the configured endpoint **host** — never the key —
reachability, and whether a key is configured. Reachability is a **network** property: a 401 counts
as reachable, because a wrong key and a dead host are different problems.

⚠ **It is deliberately not part of any container health check**, and a test reads the compose files
to keep it that way. An LLM outage degrades classification; it must never restart the chatbot.

⚠ Known gaps, logged not fixed: `LLM_failed` is unreachable because nothing retries (D-34), so a
failed classification sits at `pending` and the retrieve step waits its full 20 seconds.

## 5) Typical Callers

- Celery tasks in `backend/task_queue/registered_tasks.py`
- voice grievance orchestration
- classification/review-related chatbot flows
