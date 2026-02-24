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

**Slots used by form_grievance flow**:
- `grievance_id`, `complainant_id`, `story_main`, `grievance_sensitive_issue`
- `grievance_description`, `grievance_new_detail`, `grievance_description_status`
- `requested_slot`, `skip_validation_needed`, `skipped_detected_text`
- `complainant_province`, `complainant_district`, `complainant_office` (from defaults or prior)
- `language_code` (default "en" for spike)
- `flask_session_id` (optional for spike)

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

**Actions in scope**:
- `action_introduce` – regular Action (language selection)
- `action_set_english`, `action_set_nepali` – regular Action (set language_code)
- `action_main_menu` – regular Action (menu: File grievance, Check status, Exit)
- `action_start_grievance_process` – regular Action
- `action_ask_grievance_new_detail` – regular Action (ask for grievance_new_detail)
- `validate_form_grievance` – form validation; invoked via form loop, not directly via registry for `run()`

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
- [x] events_to_slot_updates: SlotSet → dict
- [x] Verify: action_start_grievance_process runs with adapters, returns correct events and messages
