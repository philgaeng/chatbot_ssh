# Test Spec: Scoped Refactor

Test specification for the orchestrator + action layer proof-of-concept. Covers unit, integration, and end-to-end tests.

**Test framework**: pytest (or reuse existing project test setup)  
**Location**: `tests/orchestrator/` (or `orchestrator/tests/`)

---

## Overall Test Progress

| Category | Spec Section | Status |
|----------|--------------|--------|
| Action Layer | [1. Action Layer](#1-action-layer) | ✅ Done |
| Form Loop | [2. Form Loop](#2-form-loop) | ✅ Done |
| Session Store | [3. Session Store](#3-session-store) | ✅ Done |
| Config Loader | [4. Config Loader](#4-config-loader) | ⬜ Not started |
| Orchestrator API | [5. Orchestrator API](#5-orchestrator-api) | ✅ Done |
| Flow Transitions | [6. Flow Transitions](#6-flow-transitions) | ✅ Done |
| End-to-End | [7. End-to-End](#7-end-to-end) | ✅ Done |
| Extended Flows (10.A–10.D) | [8. Extended Flows](#8-extended-flows) | ⬜ Pending |

---

## 1. Action Layer

### 1.1 CollectingDispatcher

| Test | Description | Checklist |
|------|-------------|-----------|
| utter_message text | Append text-only message to messages list | [x] |
| utter_message buttons | Append message with buttons | [x] |
| utter_message json_message | Append custom json_message (grievance_id_set) | [x] |
| Multiple messages | Multiple utter_message calls → multiple entries in list | [x] |

### 1.2 SessionTracker

| Test | Description | Checklist |
|------|-------------|-----------|
| get_slot | Returns correct value for existing slot | [x] |
| get_slot missing | Returns None for unknown slot | [x] |
| latest_message | Returns provided dict or {} | [x] |
| active_loop | Returns {"name": x} when set, None when not | [x] |
| sender_id | Returns sender_id | [x] |
| slots | Returns slots dict (reference, not copy) | [x] |

### 1.3 Action Registry

| Test | Description | Checklist |
|------|-------------|-----------|
| invoke_action action_introduce | Runs, returns events, dispatcher has messages | [x] |
| invoke_action action_set_english | Sets language_code slot | [x] |
| invoke_action action_set_nepali | Sets language_code slot | [x] |
| invoke_action action_main_menu | Shows menu with buttons | [x] |
| invoke_action action_start_grievance_process | json_message with grievance_id_set, SlotSet events | [x] |
| invoke_action action_ask_grievance_new_detail | Utterance for grievance prompt (varies by grievance_description_status) | [x] |
| invoke_action action_start_status_check | Sets story_main="status_check", resets status slots | [ ] |
| invoke_action action_ask_complainant_* | Contact ask actions return messages | [ ] |
| invoke_action action_ask_otp_consent, action_ask_otp_input | OTP ask actions return messages | [ ] |
| invoke_action action_submit_grievance | Persists complainant, finalizes grievance | [ ] |
| invoke_action action_status_check_request_follow_up | Status check completion messages | [ ] |
| invoke_action action_skip_status_check_outro | Status check skip outro messages | [ ] |
| invoke_action action_ask_form_grievance_complainant_review_* | Grievance review ask actions | [ ] |
| invoke_action unknown | Raises or returns gracefully | [x] |

### 1.4 events_to_slot_updates

| Test | Description | Checklist |
|------|-------------|-----------|
| SlotSet events | Extracts slot name and value from Rasa event format | [x] |
| Empty events | Returns {} | [x] |
| Multiple SlotSets | All slots in dict | [x] |

**Reference**: `orchestrator/scripts/verify_action_layer.py`

---

## 2. Form Loop

### 2.1 run_form_turn

| Test | Description | Checklist |
|------|-------------|-----------|
| First ask (no user input) | Calls action_ask_grievance_new_detail, returns messages, completed=False | [x] |
| Free text input | Extracts and validates, updates grievance_description, re-asks with show_options | [x] |
| Payload /submit_details | Sets grievance_new_detail="completed", completed=True | [x] |
| Payload /add_more_details | Sets grievance_new_detail=None, grievance_description_status="add_more_details" | [x] |
| Payload /restart | Clears grievance, grievance_description_status="restart" | [x] |
| Skip handling | Handles skip intent, sets slot to SKIP_VALUE where applicable | [x] |
| skip_validation_needed | When user says "skip" with fuzzy match, shows confirmation, handles /affirm_skip | [x] |

### 2.2 required_slots

| Test | Description | Checklist |
|------|-------------|-----------|
| grievance_new_detail empty | Returns ["grievance_new_detail"] | [x] |
| grievance_new_detail == "completed" | Returns [] (form complete) | [x] |

### 2.3 Extended Forms (form_contact, form_otp, form_status_check_*, form_grievance_complainant_review)

| Test | Description | Checklist |
|------|-------------|-----------|
| run_form_turn form_contact | First ask for complainant_location_consent | [ ] |
| run_form_turn form_otp | First ask for complainant_phone or otp_consent | [ ] |
| run_form_turn form_status_check_1 | First ask for story_route | [ ] |
| run_form_turn form_status_check_2 | First ask for status_check_retrieve_grievances or status_check_complainant_full_name | [ ] |
| run_form_turn form_status_check_skip | First ask for valid_province_and_district | [ ] |
| run_form_turn form_grievance_complainant_review | First ask for grievance_classification_consent | [ ] |
| _get_ask_action form_status_check_skip complainant_district | Returns action_ask_form_status_check_skip_complainant_district | [ ] |
| _get_ask_action form_contact complainant_district | Returns action_ask_complainant_district | [ ] |
| get_form(active_loop) | Lazy-loads all 7 forms by name | [ ] |

**Reference**: `orchestrator/scripts/verify_form_loop.py`

---

## 3. Session Store

### 3.1 Operations

| Test | Description | Checklist |
|------|-------------|-----------|
| get_session new user | Returns None | [x] |
| create_session | Creates session with state=intro, default slots | [x] |
| save_session | Persists to store | [x] |
| get_session after save | Returns saved session | [x] |
| Session isolation | Different user_ids get different sessions | [x] |

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
| Request format | Accepts user_id, text, payload (optional) | [x] |
| Response format | Returns messages[], next_state, expected_input_type | [x] |
| New user | Creates session, returns intro messages | [x] |
| Invalid request | Returns 4xx with clear error | [x] |

### 5.2 GET /health

| Test | Description | Checklist |
|------|-------------|-----------|
| Returns 200 | Health check succeeds | [x] |

---

## 6. Flow Transitions

| Test | Description | Checklist |
|------|-------------|-----------|
| intro → main_menu | After set_english or set_nepali, next_state=main_menu | [x] |
| main_menu → form_grievance | After new_grievance, grievance_id set, next_state=form_grievance | [x] |
| form_grievance → form_grievance | After free text, re-ask; next_state=form_grievance | [x] |
| form_grievance → contact_form | After submit_details, next_state=contact_form | [ ] |
| contact_form → otp_form | After form_contact complete, next_state=otp_form | [ ] |
| otp_form → submit_grievance | After form_otp complete (grievance flow), next_state=submit_grievance | [ ] |
| submit_grievance → grievance_review | After action_submit_grievance, next_state=grievance_review | [ ] |
| grievance_review → done | After form_grievance_complainant_review complete, next_state=done | [ ] |
| main_menu → status_check_form | After start_status_check, next_state=status_check_form | [ ] |
| status_check form_status_check_1 → form_otp | After route_status_check_phone, active_loop=form_otp | [ ] |
| status_check form_status_check_1 → form_status_check_2 | After route_status_check_grievance_id, active_loop=form_status_check_2 | [ ] |
| status_check form_status_check_1 → form_status_check_skip | After skip, active_loop=form_status_check_skip | [ ] |
| status_check form_otp → form_status_check_2 | After form_otp complete (status check), active_loop=form_status_check_2 | [ ] |
| status_check form_status_check_2 → done | After form complete, action_status_check_request_follow_up, next_state=done | [ ] |
| status_check form_status_check_skip → done | After form complete, action_skip_status_check_outro, next_state=done | [ ] |

---

## 7. End-to-End

### 7.1 Full Flow (Happy Path)

| Step | Action | Expected | Checklist |
|------|--------|----------|-----------|
| 1 | POST /message (new user, no payload) | intro messages (language selection) | [x] |
| 2 | POST /message payload=/set_english | main_menu messages | [x] |
| 3 | POST /message payload=/new_grievance | grievance_id in custom message, grievance prompt | [x] |
| 4 | POST /message text="My complaint is..." | show_options with buttons | [x] |
| 5 | POST /message payload=/submit_details | next_state=contact_form, active_loop=form_contact (full flow) | [ ] |

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
| e2e_full_flow | Automated: run steps 1–5, assert messages at each step | [x] |
| e2e_restart | Add_more_details then restart, then submit | [ ] |
| e2e_new_grievance_full | intro → lang → new_grievance → grievance text → submit → contact_form → ... → done | [ ] |
| e2e_status_check_phone | intro → lang → start_status_check → route_status_check_phone → phone → otp → done | [ ] |
| e2e_status_check_grievance_id | intro → lang → start_status_check → route_status_check_grievance_id → grievance_id → done | [ ] |

---

## 8. Extended Flows (Agents 10.A–10.D)

Tests for the full new grievance path and status check paths implemented by Agents 10.A–10.D.

### 8.1 New Grievance Flow (Full Path)

| Test | Description | Checklist |
|------|-------------|-----------|
| form_grievance → contact_form | After submit_details, next_state=contact_form, active_loop=form_contact | [ ] |
| contact_form first ask | First slot complainant_location_consent, action_ask_complainant_location_consent | [ ] |
| contact_form slot progression | Location slots then contact slots (province, district, municipality, etc.) | [ ] |
| contact_form → otp_form | After all contact slots filled, next_state=otp_form | [ ] |
| otp_form first ask | complainant_phone or otp_consent depending on story_main | [ ] |
| otp_form → submit_grievance | After otp_status valid, next_state=submit_grievance | [ ] |
| submit_grievance | action_submit_grievance runs, next_state=grievance_review | [ ] |
| grievance_review first ask | grievance_classification_consent | [ ] |
| grievance_review → done | After review slots complete, next_state=done | [ ] |

### 8.2 Status Check Flow (Phone Route)

| Test | Description | Checklist |
|------|-------------|-----------|
| main_menu → status_check_form | intent=start_status_check, next_state=status_check_form | [ ] |
| form_status_check_1 first ask | story_route, action_ask_status_check_method | [ ] |
| form_status_check_1 route_status_check_phone | story_route set, active_loop→form_otp | [ ] |
| form_otp in status check | complainant_phone slot, OTP flow | [ ] |
| form_otp complete → form_status_check_2 | active_loop=form_status_check_2 | [ ] |
| form_status_check_2 → done | action_status_check_request_follow_up, next_state=done | [ ] |

### 8.3 Status Check Flow (Grievance ID Route)

| Test | Description | Checklist |
|------|-------------|-----------|
| form_status_check_1 route_status_check_grievance_id | story_route set, active_loop→form_status_check_2 | [ ] |
| form_status_check_2 status_check_grievance_id_selected | Collect grievance ID, validate format | [ ] |
| form_status_check_2 → done | action_status_check_request_follow_up | [ ] |

### 8.4 Status Check Flow (Skip Path)

| Test | Description | Checklist |
|------|-------------|-----------|
| form_status_check_1 skip | story_route=SKIP, active_loop→form_status_check_skip | [ ] |
| form_status_check_skip valid_province_and_district | First ask for valid_province_and_district | [ ] |
| form_status_check_skip → done | action_skip_status_check_outro, next_state=done | [ ] |

### 8.5 Payload → Intent Mapping

| Test | Description | Checklist |
|------|-------------|-----------|
| route_status_check_phone | payload /route_status_check_phone → intent route_status_check_phone | [ ] |
| route_status_check_grievance_id | payload /route_status_check_grievance_id → intent route_status_check_grievance_id | [ ] |
| start_status_check | payload /start_status_check or /check_status → intent start_status_check | [ ] |

### 8.6 Test File Structure (Extended)

```
tests/orchestrator/
├── test_action_registry.py   # extend: action_start_status_check, action_submit_grievance, contact/otp/review actions
├── test_form_loop.py         # extend: run_form_turn for form_contact, form_otp, form_status_check_*, _get_ask_action
├── test_orchestrator_api.py  # extend: flow transitions for contact_form, otp_form, status_check_form
├── test_e2e_flow.py          # extend: e2e_new_grievance_full, e2e_status_check_phone, e2e_status_check_grievance_id
└── conftest.py               # extend: fixtures for contact/otp/status_check session states
```

---

## 9. Regression (Optional)

Compare orchestrator output with Rasa for same inputs:

| Test | Description | Checklist |
|------|-------------|-----------|
| Same messages intro | Orchestrator intro ≈ Rasa action_introduce output | [ ] |
| Same messages main_menu | Orchestrator main_menu ≈ Rasa action_main_menu output | [ ] |
| Same slot sequence | For given inputs, slots match Rasa tracker | [ ] |

---

## 10. Test File Structure

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

## 11. Dependencies

- **pytest** (or unittest)
- **pytest-asyncio** for async tests
- **httpx** or **TestClient** (FastAPI) for API tests
- **unittest.mock** or **pytest-mock** for patching db_manager, Celery
