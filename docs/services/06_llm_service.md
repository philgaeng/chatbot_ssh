# LLM Service Spec

## 1) Scope

Shared LLM utility/service layer used by async task pipelines and chatbot workflows.

Implementation:

- `backend/services/LLM_services.py`

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

## 4) Error and Fallback Behavior

- Missing client/config returns structured failure/fallback payloads in many functions.
- Parse failures are logged and return defensive empty objects/default structures.
- Callers should treat service outputs as best-effort and validate required fields before persistence.

## 5) Typical Callers

- Celery tasks in `backend/task_queue/registered_tasks.py`
- voice grievance orchestration
- classification/review-related chatbot flows
