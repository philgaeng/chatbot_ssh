# LLM Service Spec

## 1) Scope

Shared LLM utility/service layer used by async task pipelines and chatbot workflows.

Implementation:

- `backend/services/LLM_services.py`

## 2) Capabilities

### Audio transcription

- `transcribe_audio_file(file_path, language_code)`
- uses OpenAI Whisper transcription API

### Contact extraction

- `extract_contact_info(...)`
- `extract_all_contact_info(...)`

Extracts structured contact/location data from natural-language inputs.

### Grievance classification + summarization

- `classify_and_summarize_grievance(...)`

Returns structured output:

- `grievance_summary`
- `grievance_categories`
- `grievance_categories_alternative`
- `follow_up_question`

### Sensitive-content detection

- `detect_sensitive_content_llm(text, language_code)`

Specialized to detect sexual/gender harassment indicators; intentionally excludes non-target categories like land disputes.

### Translation

- `translate_grievance_to_english_LLM(...)`
- `translate_grievance_to_english(grievance_id)`

Produces English normalized copies and metadata for storage.

## 3) Configuration Dependencies

Environment/config inputs:

- `OPENAI_API_KEY`
- model names configured in code paths (`whisper-1`, `gpt-*`)
- category dictionaries from `backend/config/constants.py`

## 4) Error and Fallback Behavior

- Missing client/config returns structured failure/fallback payloads in many functions.
- Parse failures are logged and return defensive empty objects/default structures.
- Callers should treat service outputs as best-effort and validate required fields before persistence.

## 5) Typical Callers

- Celery tasks in `backend/task_queue/registered_tasks.py`
- voice grievance orchestration
- classification/review-related chatbot flows
