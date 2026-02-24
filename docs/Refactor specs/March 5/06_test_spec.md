# Test Spec: Scoped Refactor

Test specification for the orchestrator + action layer proof-of-concept. Covers unit, integration, and end-to-end tests.

**Test framework**: pytest (or reuse existing project test setup)  
**Location**: `tests/orchestrator/` (or `orchestrator/tests/`)

---

## Overall Test Progress

| Category | Spec Section | Status |
|----------|--------------|--------|
| Action Layer | [1. Action Layer](#1-action-layer) | ⬜ Not started |
| Form Loop | [2. Form Loop](#2-form-loop) | ⬜ Not started |
| Session Store | [3. Session Store](#3-session-store) | ⬜ Not started |
| Config Loader | [4. Config Loader](#4-config-loader) | ⬜ Not started |
| Orchestrator API | [5. Orchestrator API](#5-orchestrator-api) | ⬜ Not started |
| Flow Transitions | [6. Flow Transitions](#6-flow-transitions) | ⬜ Not started |
| End-to-End | [7. End-to-End](#7-end-to-end) | ⬜ Not started |

---

## 1. Action Layer

### 1.1 CollectingDispatcher

| Test | Description | Checklist |
|------|-------------|-----------|
| utter_message text | Append text-only message to messages list | [ ] |
| utter_message buttons | Append message with buttons | [ ] |
| utter_message json_message | Append custom json_message (grievance_id_set) | [ ] |
| Multiple messages | Multiple utter_message calls → multiple entries in list | [ ] |

### 1.2 SessionTracker

| Test | Description | Checklist |
|------|-------------|-----------|
| get_slot | Returns correct value for existing slot | [ ] |
| get_slot missing | Returns None for unknown slot | [ ] |
| latest_message | Returns provided dict or {} | [ ] |
| active_loop | Returns {"name": x} when set, None when not | [ ] |
| sender_id | Returns sender_id | [ ] |
| slots | Returns slots dict (reference, not copy) | [ ] |

### 1.3 Action Registry

| Test | Description | Checklist |
|------|-------------|-----------|
| invoke_action action_introduce | Runs, returns events, dispatcher has messages | [ ] |
| invoke_action action_set_english | Sets language_code slot | [ ] |
| invoke_action action_set_nepali | Sets language_code slot | [ ] |
| invoke_action action_main_menu | Shows menu with buttons | [ ] |
| invoke_action action_start_grievance_process | json_message with grievance_id_set, SlotSet events | [ ] |
| invoke_action action_ask_grievance_new_detail | Utterance for grievance prompt (varies by grievance_description_status) | [ ] |
| invoke_action unknown | Raises or returns gracefully | [ ] |

### 1.4 events_to_slot_updates

| Test | Description | Checklist |
|------|-------------|-----------|
| SlotSet events | Extracts slot name and value from Rasa event format | [ ] |
| Empty events | Returns {} | [ ] |
| Multiple SlotSets | All slots in dict | [ ] |

**Reference**: `orchestrator/scripts/verify_action_layer.py`

---

## 2. Form Loop

### 2.1 run_form_turn

| Test | Description | Checklist |
|------|-------------|-----------|
| First ask (no user input) | Calls action_ask_grievance_new_detail, returns messages, completed=False | [ ] |
| Free text input | Extracts and validates, updates grievance_description, re-asks with show_options | [ ] |
| Payload /submit_details | Sets grievance_new_detail="completed", completed=True | [ ] |
| Payload /add_more_details | Sets grievance_new_detail=None, grievance_description_status="add_more_details" | [ ] |
| Payload /restart | Clears grievance, grievance_description_status="restart" | [ ] |
| Skip handling | Handles skip intent, sets slot to SKIP_VALUE where applicable | [ ] |
| skip_validation_needed | When user says "skip" with fuzzy match, shows confirmation, handles /affirm_skip | [ ] |

### 2.2 required_slots

| Test | Description | Checklist |
|------|-------------|-----------|
| grievance_new_detail empty | Returns ["grievance_new_detail"] | [ ] |
| grievance_new_detail == "completed" | Returns [] (form complete) | [ ] |

**Reference**: `orchestrator/scripts/verify_form_loop.py`

---

## 3. Session Store

### 3.1 Operations

| Test | Description | Checklist |
|------|-------------|-----------|
| get_session new user | Returns None | [ ] |
| create_session | Creates session with state=intro, default slots | [ ] |
| save_session | Persists to store | [ ] |
| get_session after save | Returns saved session | [ ] |
| Session isolation | Different user_ids get different sessions | [ ] |

---

## 4. Config Loader

### 4.1 load_config

| Test | Description | Checklist |
|------|-------------|-----------|
| Loads flow.yaml | Returns dict with states, transitions | [ ] |
| Loads slot_defaults | Returns complainant_province, complainant_district, etc. | [ ] |
| Missing config | Handles gracefully (defaults or error) | [ ] |

---

## 5. Orchestrator API

### 5.1 POST /message

| Test | Description | Checklist |
|------|-------------|-----------|
| Request format | Accepts user_id, text, payload (optional) | [ ] |
| Response format | Returns messages[], next_state, expected_input_type | [ ] |
| New user | Creates session, returns intro messages | [ ] |
| Invalid request | Returns 4xx with clear error | [ ] |

### 5.2 GET /health

| Test | Description | Checklist |
|------|-------------|-----------|
| Returns 200 | Health check succeeds | [ ] |

---

## 6. Flow Transitions

| Test | Description | Checklist |
|------|-------------|-----------|
| intro → main_menu | After set_english or set_nepali, next_state=main_menu | [ ] |
| main_menu → form_grievance | After new_grievance, grievance_id set, next_state=form_grievance | [ ] |
| form_grievance → form_grievance | After free text, re-ask; next_state=form_grievance | [ ] |
| form_grievance → done | After submit_details, next_state=done | [ ] |

---

## 7. End-to-End

### 7.1 Full Flow (Happy Path)

| Step | Action | Expected | Checklist |
|------|--------|----------|-----------|
| 1 | POST /message (new user, no payload) | intro messages (language selection) | [ ] |
| 2 | POST /message payload=/set_english | main_menu messages | [ ] |
| 3 | POST /message payload=/new_grievance | grievance_id in custom message, grievance prompt | [ ] |
| 4 | POST /message text="My complaint is..." | show_options with buttons | [ ] |
| 5 | POST /message payload=/submit_details | completed, next_state=done | [ ] |

### 7.2 Curl Commands (Manual)

```bash
# 1. Intro
curl -X POST http://localhost:8000/message -H "Content-Type: application/json" \
  -d '{"user_id": "e2e-test-1", "text": ""}'

# 2. Set English
curl -X POST http://localhost:8000/message -H "Content-Type: application/json" \
  -d '{"user_id": "e2e-test-1", "payload": "/set_english"}'

# 3. New grievance
curl -X POST http://localhost:8000/message -H "Content-Type: application/json" \
  -d '{"user_id": "e2e-test-1", "payload": "/new_grievance"}'

# 4. Grievance text
curl -X POST http://localhost:8000/message -H "Content-Type: application/json" \
  -d '{"user_id": "e2e-test-1", "text": "My complaint is about delayed services"}'

# 5. Submit
curl -X POST http://localhost:8000/message -H "Content-Type: application/json" \
  -d '{"user_id": "e2e-test-1", "payload": "/submit_details"}'
```

### 7.3 E2E Test Script

| Test | Description | Checklist |
|------|-------------|-----------|
| e2e_full_flow | Automated: run steps 1–5, assert messages at each step | [ ] |
| e2e_restart | Add_more_details then restart, then submit | [ ] |

---

## 8. Regression (Optional)

Compare orchestrator output with Rasa for same inputs:

| Test | Description | Checklist |
|------|-------------|-----------|
| Same messages intro | Orchestrator intro ≈ Rasa action_introduce output | [ ] |
| Same messages main_menu | Orchestrator main_menu ≈ Rasa action_main_menu output | [ ] |
| Same slot sequence | For given inputs, slots match Rasa tracker | [ ] |

---

## 9. Test File Structure

```
tests/orchestrator/
├── conftest.py           # fixtures: domain, sample session, dispatcher, tracker
├── test_adapters.py      # CollectingDispatcher, SessionTracker
├── test_action_registry.py
├── test_form_loop.py
├── test_session_store.py
├── test_config_loader.py
├── test_orchestrator_api.py  # FastAPI TestClient
└── test_e2e_flow.py
```

Or reuse `orchestrator/scripts/verify_*.py` as pytest tests.

---

## 10. Dependencies

- **pytest** (or unittest)
- **pytest-asyncio** for async tests
- **httpx** or **TestClient** (FastAPI) for API tests
- **unittest.mock** or **pytest-mock** for patching db_manager, Celery
