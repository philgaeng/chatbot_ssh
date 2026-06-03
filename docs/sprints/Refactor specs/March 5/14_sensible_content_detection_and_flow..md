# Sensitive Content Detection and Flow

## 1. Overview

This spec describes the **sensitive content detection flow**: how we detect when a user’s grievance text refers to sexual or oppressive behaviour, and how we route them into the sensitive-issues form (anonymous filing, follow-up options). The goal is to make detection **fast** and **reliable** even when the LLM is slow or unavailable.

**Out of scope for this doc:** The content of the sensitive-issues form itself (follow-up, phone, nickname, etc.) stays as in `form_sensitive_issues.py`; we only change **when** and **how** we set `grievance_sensitive_issue` and how we plug that into the orchestrator.

---

## 2. Current Flow (As-Is)

### 2.1 Where detection happens

| Location | What happens |
|----------|----------------|
| **form_grievance.py** `validate_grievance_new_detail` (lines 279–295) | When the user submits **free text** (not a payload like `/submit_details`), we call `self.detect_sensitive_content(dispatcher, slot_value)`. If it returns a result, we set `grievance_sensitive_issue: True` and related slots and return; otherwise we set `grievance_sensitive_issue: False`. |
| **form_grievance.py** `required_slots` (lines 173–176) | If `grievance_sensitive_issue` is truthy, we return `["sensitive_issues_follow_up", "grievance_new_detail"]`, so the form keeps running and the next slot asked is `sensitive_issues_follow_up`. |
| **base_mixins.py** `SensitiveContentHelpersMixin.detect_sensitive_content` | Calls `self.helpers.detect_sensitive_content(slot_value, self.language_code)` (keyword-based). If `detected` and `action_required`, returns slot updates including `grievance_sensitive_issue: True`, category, level, message, confidence. |
| **helpers_repo.py** / **keyword_detector.py** | Keyword/regex detection (sexual_assault, harassment, land_issues, violence) with levels (critical/high/medium/low) and thresholds. No LLM. |

So today, **sensitive detection is synchronous and keyword-only** at the moment the user adds text. The **heavy** Celery task is `classify_and_summarize_grievance_task` (summary + categories + follow-up questions); it does **not** set `grievance_sensitive_issue` and runs only after the user clicks “Submit details”.

### 2.2 Rasa flow

- When `form_grievance` “completes” with `grievance_sensitive_issue: True`, **stories** transition to `form_sensitive_issues` (separate form).
- Slots like `sensitive_issues_follow_up`, `complainant_phone`, etc. are validated by `ValidateFormSensitiveIssues`; ask actions live in `form_sensitive_issues.py`.

### 2.3 Orchestrator flow (state_machine, form_loop, action_registry)

- **state_machine.py**: When `form_grievance` completes (`run_form_turn` returns `completed=True`), we always go to **contact_form**. There is **no** branch on `grievance_sensitive_issue` and **no** `form_sensitive_issues` state.
- **form_loop.py**: Only runs one form per state (e.g. `ValidateFormGrievance` for `form_grievance`). It does **not** load `ValidateFormSensitiveIssues`. The ask-action map `_ASK_ACTIONS_BY_SLOT` / `_ASK_ACTIONS_BY_FORM_SLOT` does **not** include `sensitive_issues_follow_up` or any other sensitive-issues ask actions.
- **action_registry.py**: Does **not** register `action_ask_sensitive_issues_follow_up`, `action_ask_sensitive_issues_new_detail`, etc.
- **session_store.py**: Default for `grievance_sensitive_issue` is `False`.

So in the **orchestrator**, the sensitive-issues subflow is **not** implemented: even if `ValidateFormGrievance.required_slots` returned `["sensitive_issues_follow_up", "grievance_new_detail"]`, the form loop would have no extract/validate for those slots (they belong to `ValidateFormSensitiveIssues`) and no ask action for `sensitive_issues_follow_up`. So we must either add a proper `form_sensitive_issues` state and form run, or unify the flow in a different way.

---

## 3. Gaps Summary

| # | Gap | Impact |
|---|-----|--------|
| G1 | **No LLM-based sensitive detection** | Keyword-only detection can miss paraphrases, euphemisms, or mixed language. |
| G2 | **Heavy task is not for sensitivity** | `classify_and_summarize_grievance_task` is slow and does not set `grievance_sensitive_issue`. We cannot rely on it for routing to the sensitive form. |
| G3 | **Orchestrator skips form_sensitive_issues** | After `form_grievance` completes, we always go to `contact_form`. No state or form run for sensitive issues. |
| G4 | **Orchestrator missing sensitive-issues actions/slots** | No ask actions for `sensitive_issues_follow_up`, etc., and no extract/validate for those slots in the grievance form loop. |
| G5 | **Keyword fallback should be stronger** | When LLM is unavailable, we should maximise recall (and control precision via UX) by expanding patterns and coverage. |
| G6 | **helpers_repo return shape** | `base_mixins` expects `confidence` in the detection dict; `helpers_repo.detect_sensitive_content` does not return `confidence`. `level` may be an enum and should be serializable (string). |

---

## 4. Proposed Direction

### 4.1 New lightweight Celery task: `detect_sensitive_content_task`

- **Purpose:** Answer a single yes/no: does this text (in the given language) contain content related to the user reporting **sexual or gender harassment** (sensitive_content)? Land issues and violence are high_priority for ADB but must **not** set `grievance_sensitive_issue`; the prompt should target only sensitive_content.
- **Input:** e.g. `{ "text": str, "language_code": str, "grievance_id": str?, "session_id": str? }`.
- **Output:** Same shape as **helpers_repo.py** / **keyword_detector.py** so one code path can consume either source:
  ```json
  {
    "detected": true | false,
    "level": "high" | "medium" | "low",
    "message": "excerpt of the text (or empty when not detected)"
  }
  ```
  Routing: `grievance_sensitive_issue = result.detected` (and optionally only when `level` is high/critical if we want to filter by severity). Task status for frontend can be separate.
- **Prompt (conceptual):**  
  “Does this text in {language} contain any content related to the user reporting sexual or gender harassment? (Do not flag land issues or violence.) Respond with a JSON object only: `{\"detected\": true or false, \"level\": \"high\" or \"medium\" or \"low\", \"message\": \"short excerpt of the relevant part of the text, or empty string if not detected\"}`.”
- **Why a separate task:** Kept minimal (one boolean + level + excerpt, no follow-up questions) so it can return **quickly** and we can use the result for routing before or right after “Submit details”.

### 4.2 When to run the lightweight task (decided: B)

- **Chosen: B) On every text addition (background).**  
  Each time the user adds grievance text (in `validate_grievance_new_detail`), fire `detect_sensitive_content_task` in the background and store the result in session/DB. On “Submit details”, use the latest stored result if available; otherwise fall back to keyword. Rationale: users rarely add multiple chunks, so the timelapse while they type or before they press Submit is enough for the LLM to finish in many cases.
- **Where to store the task result (decided):** Persist in **session/DB** so the orchestrator can read it on the next turn (e.g. when handling “Submit details” or the next message).
- **REST UX:** Show a short “Checking…” when the user presses Submit details; by then the background task will often have completed. If not, use keyword result for routing.

### 4.3 Inline (keyword) detection: make it cover “as many cases as possible”

When the LLM is not available (or times out), we rely on `helpers_repo.detect_sensitive_content` → `keyword_detector.detect_sensitive_content`. To improve coverage:

- **Expand patterns:** Add synonyms, euphemisms, and mixed-language variants (e.g. Romanised Nepali, common transliterations) for **sensitive_content** categories (see 4.3.1).
- **Consider lowering thresholds or adding “medium” as action_required** for borderline cases (with UX that allows “No, I meant something else”).
- **Fix** the interface: `helpers_repo` should return `confidence` and ensure `level` is a string (e.g. `result.level.value` if it’s an enum). **Decided: OK.**

#### 4.3.1 ADB: two distinct detection buckets (decided)

- **Sensitive content (→ special flow):** Gender and **sexual harassment** only. When detected, we trigger the **sensitive-issues form** (anonymous filing, follow-up, etc.). This is what “sensitive_content” means for routing.
- **High priority (→ usual flow):** **Land issues** and **violence**. Used so ADB officers can follow up on these grievances; the flow remains the **usual** one (no sensitive-issues form). Do not route these into `form_sensitive_issues`.

So the keyword detector (and the lightweight LLM task) should clearly separate: (1) sexual/gender harassment → set `grievance_sensitive_issue` and route to sensitive form; (2) land_issues / violence → may set a “high_priority” or similar flag for ADB but do **not** set `grievance_sensitive_issue`.

### 4.4 Orchestrator: support form_sensitive_issues (decided: same pattern as other flows)

To close G3 and G4:

- **state_machine.py:** When `form_grievance` completes, **if** `grievance_sensitive_issue` is True, transition to a new state (e.g. `form_sensitive_issues`) and run `form_sensitive_issues` (same semantics as Rasa: ask `sensitive_issues_follow_up`, then complainant_phone, etc.). When that form completes, then transition to `contact_form`.
- **form_loop.py:** Register `form_sensitive_issues` in `get_form()`; add ask-action mappings for `sensitive_issues_follow_up`, `sensitive_issues_new_detail`, `sensitive_issues_nickname`, `form_sensitive_issues_complainant_phone` (and any other slots asked by the sensitive-issues form). Use the **same pattern as the other flows** (same form class, same slots, same ask actions as Rasa).
- **action_registry.py:** Register all ask actions (and any other actions) used by the sensitive-issues form so that `invoke_action` can run them.
- **Payloads and intents (action item):** Verify that payloads used by the sensitive-issues form (`/not_sensitive_content`, `/add_more_details`, `/anonymous`, `/skip`) are present in `PAYLOAD_TO_INTENT` (or equivalent) in the orchestrator so user replies are correctly interpreted.

Slots and domain for the sensitive-issues form stay aligned with `form_sensitive_issues.py` and `domain.yml` (e.g. `sensitive_issues_follow_up`, `complainant_phone`, etc.).

---

## 5. Decisions (from Open Questions)

| # | Decision |
|---|----------|
| 1 | **When to run task:** **B** — On every text addition (background). People rarely add more details, so the timelapse is enough to get detection ready before Submit. |
| 2 | **Where to store result:** **B** — Persist in session/DB so the orchestrator can read it on the next turn. |
| 3 | **REST UX:** Show a short “Checking…” when the user presses Submit details; by then the LLM will often have already run. |
| 4 | **Orchestrator form_sensitive_issues:** Use the same pattern as the other flows (same form class, same slots, same ask actions as Rasa). |
| 5 | **Payloads/intents:** Verify that `/not_sensitive_content`, `/add_more_details`, `/anonymous`, `/skip` are in `PAYLOAD_TO_INTENT` (or equivalent). |
| 6 | **ADB – two buckets:** (1) **Sensitive content** = gender/sexual harassment only → triggers sensitive-issues form. (2) **High priority** = land issues, violence → for ADB follow-up but **usual flow** (no sensitive form). Keyword detector and LLM task must only set `grievance_sensitive_issue` for (1). |
| 7 | **helpers_repo:** Add `confidence` to the return dict and ensure `level` is a string (e.g. `result.level.value`). |

---

## 6. References

- **Form (sensitive-issues):** `rasa_chatbot/actions/forms/form_sensitive_issues.py` — keep as-is for behaviour; orchestrator will call it.
- **Form (grievance):** `rasa_chatbot/actions/forms/form_grievance.py` — `required_slots` (173–176), `validate_grievance_new_detail` (279–288), `_trigger_async_classification` (140–150).
- **Detection (mixin):** `rasa_chatbot/actions/base_classes/base_mixins.py` — `SensitiveContentHelpersMixin.detect_sensitive_content`.
- **Detection (keyword):** `backend/shared_functions/keyword_detector.py`, `backend/shared_functions/helpers_repo.py`.
- **Orchestrator:** `orchestrator/state_machine.py`, `orchestrator/form_loop.py`, `orchestrator/action_registry.py`, `orchestrator/session_store.py`.
- **Heavy task:** `backend/task_queue/registered_tasks.py` — `classify_and_summarize_grievance_task` (does not set `grievance_sensitive_issue`).
- **Config:** `orchestrator/config/slots.yaml`, `orchestrator/scripts/extract_config.py` — `grievance_sensitive_issue` is already a slot.

---

## 7. Implementation (Done)

The following was implemented (Agent 9, March 2025).

### 7.1 Lightweight Celery task and LLM

- **`backend/services/LLM_services.py`**: Added `detect_sensitive_content_llm(text, language_code)` — single LLM call returning `{ "detected", "level", "message" }` for **sexual or gender harassment only**; prompt explicitly says do not flag land issues or violence.
- **`backend/task_queue/registered_tasks.py`**: Added `detect_sensitive_content_task(text, language_code, grievance_id?, session_id?)`. Calls the LLM helper and persists the result (see store below). Registered as LLM task; exported in `__all__`.

### 7.2 Store and trigger on text addition

- **`backend/sensitive_detection_store.py`**: New module. `set_result(session_id, grievance_id, result)` and `get_result(session_id, grievance_id)`. In-memory store keyed by session/grievance; docstring notes Redis or DB for production if Celery runs in a separate process.
- **`rasa_chatbot/actions/forms/form_grievance.py`**:
  - On **free-text** grievance input: description is updated and options shown; **no** synchronous keyword check for routing. Instead `_trigger_detect_sensitive_content_task(...)` is fired in a daemon thread (same pattern as `_trigger_async_classification`).
  - On **Submit details**: `_get_sensitive_issue_slots_on_submit()` reads from the store; if no stored result, runs keyword detection on the full grievance description. Slot `grievance_sensitive_issue` (and related slots) are set only from stored result or keyword (keyword only sets them for sensitive_content — see 7.4).

### 7.3 helpers_repo and keyword detector (two buckets)

- **`backend/shared_functions/helpers_repo.py`**: `detect_sensitive_content` now returns **`confidence`** (from `result.confidence`) and **`level`** as a string (`result.level.value` when enum). Error fallback uses `action_required: False`, `confidence: 0.0`.
- **`backend/shared_functions/keyword_detector.py`**: **SENSITIVE_CONTENT_CATEGORIES** = `sexual_assault`, `harassment`; **HIGH_PRIORITY_CATEGORIES** = `land_issues`, `violence`. **`action_required`** is set only when the highest match is in sensitive_content and level is CRITICAL or HIGH. Land and violence are still detected but do **not** set `action_required`, so they do not route to the sensitive-issues form.

### 7.4 Orchestrator: form_sensitive_issues

- **`orchestrator/state_machine.py`**:
  - When **form_grievance** completes: if `session["slots"].get("grievance_sensitive_issue")` is True, next state is **form_sensitive_issues** and the sensitive-issues form is run; when that form completes, transition to **contact_form**. If False, transition directly to **contact_form**.
  - New state **form_sensitive_issues**: runs `ValidateFormSensitiveIssues`; on completion goes to **contact_form** and runs the contact form first ask.
  - **PAYLOAD_TO_INTENT**: added `not_sensitive_content`, `anonymous` (add_more_details and skip were already present).
- **`orchestrator/form_loop.py`**:
  - **get_form()**: added **form_sensitive_issues** (lazy-load `ValidateFormSensitiveIssues`).
  - **_ASK_ACTIONS_BY_SLOT**: added `sensitive_issues_follow_up`, `sensitive_issues_new_detail`, `sensitive_issues_nickname`.
  - **_ASK_ACTIONS_BY_FORM_SLOT**: added `("form_sensitive_issues", "complainant_phone")` → `action_ask_form_sensitive_issues_complainant_phone`.
  - Extract/validate: when `active_loop` is set, form-specific method names are tried (e.g. `extract_form_sensitive_issues_complainant_phone`, `validate_form_sensitive_issues_complainant_phone`).
- **`orchestrator/action_registry.py`**: Registered the four sensitive-issues ask actions: `action_ask_sensitive_issues_follow_up`, `action_ask_sensitive_issues_new_detail`, `action_ask_sensitive_issues_nickname`, `action_ask_form_sensitive_issues_complainant_phone`.

### 7.5 Other changes

- **`rasa_chatbot/actions/forms/form_sensitive_issues.py`**: `required_slots` now returns `required_slots` instead of `domain_slots`.

### 7.6 Tests

- **`tests/test_sensitive_content_detection.py`**: Keyword path — sexual_assault/harassment sets `action_required`; land_issues and violence do not. helpers_repo returns `confidence` and string `level`. Sensitive detection store get/set/clear.
- **`tests/orchestrator/test_orchestrator_api.py`**: E2E test `test_sensitive_content_flow_goes_to_form_sensitive_issues` (sensitive text → Submit details → expect **form_sensitive_issues**). Requires full env (e.g. socketio) to run.

---

## 8. Next Steps (remaining / future)

1. **REST UX:** Optional: show a short "Checking…" when the user presses Submit details (frontend/orchestrator).
2. **Keyword coverage:** Optionally expand patterns (synonyms, euphemisms, mixed-language) for sensitive_content categories to improve recall when LLM is unavailable.

3. **Store in production:** If Celery workers run in a separate process, back the sensitive detection store with Redis or a DB table keyed by `session_id` / `grievance_id`.
4. **"Checking…" and task status:** Optional frontend handling to show that sensitive check is in progress and/or to consume websocket status from the lightweight task if desired.
