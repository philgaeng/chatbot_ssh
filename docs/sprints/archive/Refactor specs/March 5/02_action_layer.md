# Spec 2: Action Layer

## Purpose

Provide thin adapters so existing Rasa actions run with the orchestrator, without Rasa's Tracker and Dispatcher at runtime.

---

## Components

### 1. CollectingDispatcher

**Interface** (match Rasa's `CollectingDispatcher` surface used by our actions):

```python
class CollectingDispatcher:
    def __init__(self):
        self.messages = []  # List of {text?, buttons?, json_message?, custom?}

    def utter_message(self, text=None, buttons=None, json_message=None, response=None, **kwargs):
        # Append to self.messages
        # Handle: text, buttons, json_message (for grievance_id_set), response (utter template - resolve or skip for spike)
        pass
```

**Used by**:
- `action_start_grievance_process`: `utter_message(json_message={"data": {"grievance_id": ..., "event_type": "grievance_id_set"}})`
- `action_ask_grievance_new_detail`: `utter_message(text=..., buttons=...)`
- `ValidateFormGrievance` validate/extract: `utter_message(text=..., buttons=...)` for errors, skip confirmation, etc.

---

### 2. SessionTracker

**Interface** (match Rasa Tracker surface used by our actions):

```python
class SessionTracker:
    def __init__(self, slots: dict, sender_id: str, latest_message: dict = None,
                 active_loop: str = None, requested_slot: str = None):
        self._slots = slots
        self._sender_id = sender_id
        self._latest_message = latest_message or {}
        self._active_loop = active_loop
        self._requested_slot = requested_slot

    def get_slot(self, key: str) -> Any:
        return self._slots.get(key)

    @property
    def sender_id(self) -> str:
        return self._sender_id

    @property
    def slots(self) -> dict:
        return self._slots

    @property
    def latest_message(self) -> dict:
        return self._latest_message

    @property
    def active_loop(self):
        return {"name": self._active_loop} if self._active_loop else None
```

**Slots used across forms**:

| Form | Key Slots |
|------|-----------|
| form_grievance | grievance_id, complainant_id, story_main, grievance_sensitive_issue, grievance_description, grievance_new_detail, grievance_description_status, requested_slot, skip_validation_needed, skipped_detected_text |
| form_contact | complainant_location_consent, complainant_province, complainant_district, complainant_municipality_temp/confirmed, complainant_village_temp/confirmed, complainant_ward, complainant_address_temp/confirmed, complainant_consent, complainant_full_name, complainant_email_temp/confirmed |
| form_otp | complainant_phone, otp_consent, otp_input, otp_status, otp_number, otp_resend_count |
| form_grievance_complainant_review | grievance_classification_consent, grievance_categories_status, grievance_cat_modify, grievance_summary_status, grievance_summary_temp |
| form_status_check_1 | story_route, status_check_grievance_id_selected, complainant_phone |
| form_status_check_2 | status_check_retrieve_grievances, status_check_complainant_full_name, status_check_grievance_id_selected, list_grievance_id |
| form_status_check_skip | valid_province_and_district, complainant_province, complainant_district, complainant_municipality_temp/confirmed |

Plus shared: `language_code`, `story_main`, `flask_session_id`.

---

### 3. Action Registry

**Interface**:

```python
def invoke_action(action_name: str, dispatcher: CollectingDispatcher,
                  tracker: SessionTracker, domain: dict) -> List[dict]:
    """
    Invoke action by name. Returns list of events (SlotSet, FollowupAction, etc.).
    dispatcher.messages contains any utterances the action sent.
    """
```

**Actions in scope** (regular actions):
- `action_introduce` – language selection
- `action_set_english`, `action_set_nepali` – set language_code
- `action_main_menu` – menu: File grievance, Check status, Exit
- `action_start_grievance_process` – start grievance flow, set grievance_id, complainant_id, story_main
- `action_start_status_check` – start status check flow, set story_main="status_check"
- `action_ask_grievance_new_detail` – ask for grievance_new_detail
- `action_ask_complainant_*` – ask for contact slots (location_consent, province, district, full_name, email_*, etc.)
- `action_ask_otp_consent`, `action_ask_otp_input` – OTP prompts
- `action_ask_status_check_method`, `action_ask_status_check_grievance_id_selected`, `action_ask_status_check_complainant_full_name`, `action_ask_status_check_retrieve_grievances` – status check prompts
- `action_ask_form_status_check_skip_*` – status check skip prompts (valid_province_and_district, complainant_*)
- `action_ask_form_grievance_complainant_review_*` – grievance review prompts
- `action_submit_grievance` – finalize grievance submission
- `action_status_check_request_follow_up`, `action_skip_status_check_outro` – status check completion
- `validate_form_*` – form validation; invoked via form loop (required_slots, extract_*, validate_*), not via `run()`

**Note**: Form validation actions don't have a single `run()` entry point. The orchestrator calls `required_slots`, `extract_<slot>`, `validate_<slot>` directly. The registry is used for regular actions only.

---

### 4. Event Parsing

Convert action return value (`List[Dict]`) to slot updates:

```python
def events_to_slot_updates(events: List[dict]) -> dict:
    """Extract SlotSet events -> {slot_name: value}"""
```

Rasa events: `{"event": "slot", "name": "x", "value": y}` or `SlotSet("x", y)` → `{"x": y}`.

---

## Integration with Existing Code

- **Actions** stay in `rasa_chatbot/actions/`. No changes to action code.
- **Adapters** live in `orchestrator/adapters/` (or `action_layer/`).
- **Registry** imports action classes and instantiates them; calls `run()` for regular actions.
- **Domain** loaded from `rasa_chatbot/domain.yml` or passed as dict.

---

## Dependencies

- Existing: `rasa_chatbot.actions.forms.form_grievance.ActionStartGrievanceProcess`
- Existing: `rasa_chatbot.actions.forms.form_grievance.ActionAskGrievanceNewDetail`
- Existing: `rasa_chatbot.actions.forms.form_grievance.ValidateFormGrievance`
- Existing: `backend.services.database_services.postgres_services.db_manager`
- Existing: `actions.utils.utterance_mapping_rasa` (get_utterance_base, get_buttons_base)
- **Celery chain**: `form_grievance` imports `classify_and_summarize_grievance_task` from `backend.task_queue.registered_tasks`, which loads Celery at module import time. See Celery Integration section.

---

## Deliverables

- `orchestrator/adapters/dispatcher.py` – CollectingDispatcher
- `orchestrator/adapters/tracker.py` – SessionTracker
- `orchestrator/action_registry.py` – invoke_action, events_to_slot_updates

---

## Checklist

- [x] CollectingDispatcher: utter_message(text, buttons, json_message) collects to list
- [x] SessionTracker: get_slot, sender_id, slots, latest_message, active_loop
- [x] Action registry: invoke_action for action_introduce, action_set_english, action_set_nepali, action_main_menu, action_start_grievance_process, action_ask_grievance_new_detail
- [x] Action registry: all ask actions (form_contact, form_otp, form_status_check_*, form_grievance_complainant_review), action_submit_grievance, action_status_check_*, action_skip_status_check_outro
- [x] events_to_slot_updates: SlotSet → dict
- [x] Verify: action_start_grievance_process runs with adapters, returns correct events and messages
- [x] form_loop _ASK_ACTIONS_BY_SLOT and _ASK_ACTIONS_BY_FORM_SLOT expanded per 03_form_loop; _get_ask_action resolves form-specific overrides

---

## Celery Integration (Implemented – Agent 10.E)

### Issue (Resolved)

`rasa_chatbot.actions.forms.form_grievance` imports `classify_and_summarize_grievance_task` from `backend.task_queue.registered_tasks` at **module load time**. That module imports `celery_app`, which requires Celery to be installed.

The action registry lazy-loads actions on first `invoke_action`; any grievance-related action (e.g. `action_start_grievance_process`, `action_ask_grievance_new_detail`) triggers import of `form_grievance` → `registered_tasks` → `celery_app` → `celery`. If Celery is not installed (or Redis/Celery worker is not running), the import fails with `ModuleNotFoundError: No module named 'celery'`.

### What Uses Celery

| Component | Celery usage |
|-----------|--------------|
| `ValidateFormGrievance._trigger_async_classification` | Calls `classify_and_summarize_grievance_task.delay(...)` when grievance form completes, for LLM classification |
| `form_loop` | Stubs `_trigger_async_classification` for spike; does not call actual Celery task |

### Requirements

- `requirements_rest.txt` includes `celery==5.5.2` – REST stack expects Celery.
- For REST-only envs without Celery workers, the *import* still fails if Celery is not installed.

### Celery Integration (Implemented – Agent 10.E)

1. **Option A – Defer task import** ✅  
   `classify_and_summarize_grievance_task` is imported **inside** `_trigger_async_classification` in `form_grievance.py`, with `ImportError` caught. In REST-only envs without Celery, the task is skipped and slots indicate skip status.  
   - Result: Action registry loads without Celery installed.

2. **Form loop env flag – `ENABLE_CELERY_CLASSIFICATION`**  
   Set `ENABLE_CELERY_CLASSIFICATION=1` (or `true`, `yes`) before starting the orchestrator to use the real Celery task when the grievance form completes. Otherwise, `form_loop` stubs `_trigger_async_classification` and classification is skipped.  
   - Requires Redis and Celery workers running (e.g. via `scripts/rest_api/launch_servers_celery.sh`).

---

## Action Registry: Ask Actions Required by Form Loop

The form loop (`orchestrator/form_loop.py`) uses `_ASK_ACTIONS_BY_SLOT` and `_ASK_ACTIONS_BY_FORM_SLOT` to resolve ask actions. **Every action name in those mappings must be registered in `action_registry.py`** or `invoke_action` will raise.

**Contract**: form_loop calls `invoke_action(action_name)`; action_registry must resolve each action name to an action instance. If any action is missing, form_contact, form_otp, form_status_check_skip, or form_grievance_complainant_review will fail at runtime.

### Ask Actions (from form_loop _ASK_ACTIONS_BY_SLOT + _ASK_ACTIONS_BY_FORM_SLOT)

*Registered = ✓ as of current action_registry.py. If verification fails, update the table.*

| Action Name | Form(s) | Registered |
|-------------|---------|------------|
| action_ask_grievance_new_detail | form_grievance | ✓ |
| action_ask_complainant_location_consent | form_contact | ✓ |
| action_ask_complainant_province | form_contact | ✓ |
| action_ask_complainant_district | form_contact | ✓ |
| action_ask_complainant_municipality_temp | form_contact | ✓ |
| action_ask_complainant_municipality_confirmed | form_contact | ✓ |
| action_ask_complainant_village_temp | form_contact | ✓ |
| action_ask_complainant_village_confirmed | form_contact | ✓ |
| action_ask_complainant_ward | form_contact | ✓ |
| action_ask_complainant_address_temp | form_contact | ✓ |
| action_ask_complainant_address_confirmed | form_contact | ✓ |
| action_ask_complainant_consent | form_contact | ✓ |
| action_ask_complainant_full_name | form_contact | ✓ |
| action_ask_complainant_email_temp | form_contact | ✓ |
| action_ask_complainant_email_confirmed | form_contact | ✓ |
| action_ask_complainant_phone | form_otp (fallback for form_status_check_1) | ✓ |
| action_ask_otp_consent | form_otp | ✓ |
| action_ask_otp_input | form_otp | ✓ |
| action_ask_status_check_method | form_status_check_1 | ✓ |
| action_ask_status_check_grievance_id_selected | form_status_check_1 | ✓ |
| action_ask_status_check_complainant_full_name | form_status_check_2 | ✓ |
| action_ask_status_check_retrieve_grievances | form_status_check_2 | ✓ |
| action_ask_form_status_check_skip_valid_province_and_district | form_status_check_skip | ✓ |
| action_ask_form_status_check_skip_complainant_district | form_status_check_skip | ✓ |
| action_ask_form_status_check_skip_complainant_municipality_temp | form_status_check_skip | ✓ |
| action_ask_form_status_check_skip_complainant_municipality_confirmed | form_status_check_skip | ✓ |
| action_ask_form_status_check_1_complainant_phone | form_status_check_1 | ✓ |
| action_ask_form_grievance_complainant_review_grievance_classification_consent | form_grievance_complainant_review | ✓ |
| action_ask_form_grievance_complainant_review_grievance_categories_status | form_grievance_complainant_review | ✓ |
| action_ask_form_grievance_complainant_review_grievance_cat_modify | form_grievance_complainant_review | ✓ |
| action_ask_form_grievance_complainant_review_grievance_summary_status | form_grievance_complainant_review | ✓ |
| action_ask_form_grievance_complainant_review_grievance_summary_temp | form_grievance_complainant_review | ✓ |

### Remaining Work

- [x] **Agent 10.B**: All actions above registered in `action_registry.py` (intro, grievance, contact, OTP, status check, status check skip, grievance review, submit, status_check_*)
- [x] **Agent 10.E**: **Verify** all actions: pytest `tests/orchestrator/test_form_loop.py` – `test_form_contact_first_ask`, `test_form_otp_first_ask`, `test_form_status_check_skip_first_ask`, `test_form_grievance_complainant_review_first_ask` confirm first ask works with no `Unknown action` errors
- [x] **Agent 10.E**: **Form-specific delegates**: form_status_check_skip complainant_* use shared contact action classes (ActionAskComplainantDistrict etc.); utterances from `action_ask_commons` match form_status_check_skip context ("Please provide your district name or Skip")
- [x] **Agent 10.E**: **Celery integration**: lazy import in `form_grievance._trigger_async_classification`; action registry loads without Celery/Redis; `ENABLE_CELERY_CLASSIFICATION=1` enables real Celery task

---

## Action-to-Form Mapping Summary

| Form | Ask Actions (slot → action) | Validation Action |
|------|-----------------------------|-------------------|
| form_grievance | grievance_new_detail → action_ask_grievance_new_detail | validate_form_grievance |
| form_contact | complainant_location_consent → action_ask_complainant_location_consent, complainant_province → action_ask_complainant_province, complainant_district → action_ask_complainant_district, complainant_municipality_temp → action_ask_complainant_municipality_temp, complainant_village_temp → action_ask_complainant_village_temp, complainant_ward → action_ask_complainant_ward, complainant_address_temp → action_ask_complainant_address_temp, complainant_full_name → action_ask_complainant_full_name, complainant_email_temp → action_ask_complainant_email_temp, etc. | validate_form_contact |
| form_otp | complainant_phone → action_ask_complainant_phone (or form_otp flow), otp_consent → action_ask_otp_consent, otp_input → action_ask_otp_input | validate_form_otp |
| form_status_check_1 | story_route → action_ask_status_check_method, status_check_grievance_id_selected → action_ask_status_check_grievance_id_selected, complainant_phone → action_ask_form_status_check_1_complainant_phone | validate_form_status_check_1 |
| form_status_check_2 | status_check_retrieve_grievances → action_ask_status_check_retrieve_grievances, status_check_complainant_full_name → action_ask_status_check_complainant_full_name | validate_form_status_check_2 |
| form_status_check_skip | valid_province_and_district → action_ask_form_status_check_skip_valid_province_and_district, complainant_* → action_ask_form_status_check_skip_complainant_* | validate_form_status_check_skip |
| form_grievance_complainant_review | grievance_classification_consent → action_ask_form_grievance_complainant_review_grievance_classification_consent, etc. | validate_form_grievance_complainant_review |
