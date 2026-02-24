# Agent Specs: Scoped Refactor

Agent specifications for building the orchestrator + action layer. Each agent can work independently with the context provided below.

**Execution order**: Config Extraction (1) → Action Layer (2) → Form Loop (3) → Orchestrator (4) → Tests (see [06_test_spec.md](06_test_spec.md))  
*(1 and 2 can run in parallel; 3 needs 2; 4 needs 1, 2, 3)*

---

## Overall Progress

| Agent | Spec | Status |
|-------|------|--------|
| Config Extraction | [Agent 1](#agent-1-config-extraction) | ✅ Done |
| Action Layer | [Agent 2](#agent-2-action-layer) | ✅ Done |
| Form Loop | [Agent 3](#agent-3-form-loop) | ✅ Done |
| Orchestrator | [Agent 4](#agent-4-orchestrator) | ✅ Done |

---

## Agent 1: Config Extraction

### Mission
Define the orchestrator YAML schema and build an extraction script that reads Rasa YAMLs and produces our format. Orchestrator loads only from our YAML at runtime.

### Context
- **Input**: `rasa_chatbot/domain.yml`, `rasa_chatbot/data/stories/stories.yml`, `rasa_chatbot/data/rules/rules.yml` (if exists)
- **Output**: `orchestrator/config/flow.yaml`, `orchestrator/config/slots.yaml` (or combined)
- **Decisions**: See [00_overview_and_questions.md](00_overview_and_questions.md)

### Tasks

- [x] **1.1** Define `flow.yaml` schema for this spike:
  - states: intro, main_menu, form_grievance, done
  - transitions: state + intent/condition → next_state + action
  - form_grievance: form name, required slots reference

- [x] **1.2** Define `slots.yaml` schema (or embed in flow.yaml):
  - slot names and types needed for form_grievance flow
  - defaults (language_code, complainant_province, complainant_district)

- [x] **1.3** Write extraction script `orchestrator/scripts/extract_config.py`:
  - Load domain.yml (PyYAML or rasa.shared)
  - Extract slots used by form_grievance
  - Extract flow structure from stories for intro → main_menu → form_grievance
  - Output our YAML format

- [x] **1.4** Add `orchestrator/config/` with initial flow.yaml and slots.yaml (manual or script output)

### Deliverables
- `orchestrator/config/flow.yaml`
- `orchestrator/config/slots.yaml` (or equivalent)
- `orchestrator/scripts/extract_config.py`

### Reference
- [01_orchestrator.md](01_orchestrator.md) – config dependency
- [04_flow_logic.md](04_flow_logic.md) – states, transitions
- [00_overview_and_questions.md](00_overview_and_questions.md) – decision on YAML as source

---

## Agent 2: Action Layer

### Mission
Build CollectingDispatcher, SessionTracker, and action registry so existing Rasa actions run without Rasa's Tracker/Dispatcher.

### Context
- **Location**: `orchestrator/adapters/`, `orchestrator/action_registry.py`
- **Actions to support**: action_introduce, action_set_english, action_set_nepali, action_main_menu, action_start_grievance_process, action_ask_grievance_new_detail
- **Form**: ValidateFormGrievance (required_slots, extract_grievance_new_detail, validate_grievance_new_detail) – invoked directly, not via registry run()

### Tasks

- [x] **2.1** Implement `orchestrator/adapters/dispatcher.py`:
  - CollectingDispatcher class
  - `utter_message(text=..., buttons=..., json_message=..., response=...)`
  - Append to self.messages list
  - Handle json_message for grievance_id_set

- [x] **2.2** Implement `orchestrator/adapters/tracker.py`:
  - SessionTracker class
  - get_slot, sender_id, slots, latest_message, active_loop
  - Match interface used by base_mixins, base_classes, form_grievance

- [x] **2.3** Implement `orchestrator/action_registry.py`:
  - invoke_action(action_name, dispatcher, tracker, domain) -> List[dict]
  - Map action names to class instances (action_introduce, etc.)
  - events_to_slot_updates(events) -> dict
  - Import from rasa_chatbot.actions

- [x] **2.4** Verify: Call action_start_grievance_process with adapters; dispatcher.messages and return events are correct

### Deliverables
- `orchestrator/adapters/dispatcher.py`
- `orchestrator/adapters/tracker.py`
- `orchestrator/action_registry.py`

### Reference
- [02_action_layer.md](02_action_layer.md)
- `rasa_chatbot/actions/forms/form_grievance.py`
- `rasa_chatbot/actions/base_classes/base_classes.py`
- `rasa_chatbot/actions/generic_actions.py` (action_introduce, action_main_menu, action_set_english, action_set_nepali)

---

## Agent 3: Form Loop

### Mission
Implement the form loop driver: required_slots → extract_* → validate_* → apply updates → ask for next slot or complete.

### Context
- **Depends on**: Agent 2 (dispatcher, tracker, action registry)
- **Form**: ValidateFormGrievance
- **Slot**: grievance_new_detail only (sensitive content excluded)

### Tasks

- [x] **3.1** Implement `orchestrator/form_loop.py`:
  - run_form_turn(form, slot_name, user_input, session, domain) -> (messages, slot_updates, completed)
  - Get required_slots from form
  - Find next empty slot
  - If user input: call extract_*, validate_*; apply slot_updates
  - If first ask or re-ask: call action_ask_grievance_new_detail
  - Return completed=True when required_slots returns []

- [x] **3.2** Handle requested_slot, skip_validation_needed, skipped_detected_text in session/tracker

- [x] **3.3** Stub _trigger_async_classification in ValidateFormGrievance (or mock) – no Celery call

- [x] **3.4** Verify: Simulate form turn with text "/submit_details"; slot_updates and messages match expected

### Deliverables
- `orchestrator/form_loop.py`

### Reference
- [03_form_loop.md](03_form_loop.md)
- `rasa_chatbot/actions/forms/form_grievance.py`
- `rasa_chatbot/actions/base_classes/base_classes.py` (_handle_slot_extraction)

---

## Agent 4: Orchestrator

### Mission
Build the FastAPI app, session store, and state machine. Wire intro → main_menu → form_grievance → done. Expose POST /message.

### Context
- **Depends on**: Agents 1, 2, 3
- **Package**: `orchestrator/` at repo root
- **Config**: Load from orchestrator YAML (Agent 1 output)

### Tasks

- [x] **4.1** Implement `orchestrator/session_store.py`:
  - In-memory store: get_session, save_session, create_session
  - Session structure: user_id, state, active_loop, requested_slot, slots, updated_at
  - Initial session: state=intro, slots from [04_flow_logic.md](04_flow_logic.md)

- [x] **4.2** Implement `orchestrator/main.py` (or `orchestrator/app.py`):
  - FastAPI app
  - POST /message: parse request, load session, run flow logic
  - Return messages, next_state, expected_input_type

- [x] **4.3** Implement flow logic in request handler or `orchestrator/state_machine.py`:
  - intro: run action_introduce; on set_english/set_nepali → main_menu
  - main_menu: run action_main_menu; on new_grievance → action_start_grievance_process → form_grievance
  - form_grievance: call form_loop.run_form_turn; on completed → done
  - done: no further actions

- [x] **4.4** Load config from flow.yaml, slots.yaml at startup

- [x] **4.5** Add GET /health endpoint

- [x] **4.6** Verify: curl POST /message for full flow (intro → lang → menu → new_grievance → grievance text → submit_details → done)

### Deliverables
- `orchestrator/main.py`
- `orchestrator/session_store.py`
- `orchestrator/state_machine.py` (or inline)
- `orchestrator/requirements.txt` (fastapi, uvicorn, pyyaml, etc.)

### Reference
- [01_orchestrator.md](01_orchestrator.md)
- [04_flow_logic.md](04_flow_logic.md)
- [00_overview_and_questions.md](00_overview_and_questions.md)
