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
| Phase 2 Flows | [Agent 5](#agent-5-phase-2-flows) | ✅ Done |
| Webchat Socket Bridge | [Agent 6](#agent-6-webchat-socket-bridge) | ⬜ Pending |
| REST Webchat | [Agent 7](#agent-7-rest-webchat) | ⬜ Pending |
| Agents 10.A–10.D | [10_agent_instructions.md](10_agent_instructions.md) | ⬜ Pending |

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

---

## Agent 5: Phase 2 Flows

### Mission
Extend the orchestrator, action layer, and form loop to support additional flows (status check, contact + OTP, grievance review) using the same patterns as the grievance details flow.
**Status**: Completed (status check, contact + OTP, and grievance review flows implemented and wired into orchestrator; initial tests in place).

### Context
- **Depends on**: Agents 1–4 (existing infrastructure)
- **New flows**:
  - Status check (via phone or grievance ID)
  - Contact information collection
  - OTP verification
  - Grievance classification review

---

### Agent 5A – Status Check Flow

#### Mission
Extend the orchestrator, action layer, and form loop to support a **status check flow** (via phone or grievance ID) using the same patterns as the existing grievance details flow.

#### Context / Constraints
- **Depends on**: Agents 1–4 infrastructure (orchestrator, action registry, form loop patterns, config conventions).
- **Assume**:
  - Flow configuration lives in `orchestrator/config/flow.yaml` and slots in `slots.yaml`.
  - State machine transitions are implemented in `orchestrator/state_machine.py`.
  - Actions are registered in `orchestrator/action_registry.py`.
- Keep naming, structure, and error-handling consistent with the grievance details flow.

#### Goals
- **Add a complete status check path** (both via phone and via grievance ID) that:
  - Can be entered from the appropriate starting state/intents.
  - Collects any required identifiers (phone or grievance ID) via forms.
  - Calls the appropriate status lookup actions.
  - Surfaces the result back to the user and returns to a stable end state.

#### Tasks
- **Flow & state machine**
  - Add the status-check states and transitions in `flow.yaml` and `state_machine.py`.
  - Support branching between “check by phone” vs “check by grievance ID” (based on user input or prior context).
- **Actions & forms**
  - Register and wire status-related actions in `action_registry.py` (e.g., lookup-by-phone, lookup-by-id).
  - Define and integrate any required forms in the form loop for collecting identifiers and confirming results.
- **Validation & error cases**
  - Handle “no matching grievance found”, multiple matches, and backend errors with clear user-facing messages.
  - Ensure the flow can gracefully fall back or exit if the user abandons the status-check.

#### Deliverables
- Updated status-check related sections in:
  - `orchestrator/config/flow.yaml`
  - `orchestrator/config/slots.yaml` (if new slots are needed)
  - `orchestrator/state_machine.py`
  - `orchestrator/action_registry.py`
- Minimal tests or test stubs for this flow in `tests/orchestrator/` (coordinate with Agent 5C to avoid duplication).

---

### Agent 5B – Contact + OTP + Grievance Review Flows

#### Mission
Extend the orchestrator, action layer, and form loop to support **contact information collection**, **OTP verification**, and **post-submission grievance review/classification** as separate but connected flows, using the same patterns as the grievance details flow.

#### Context / Constraints
- **Depends on**: Agents 1–4 infrastructure and naming patterns; Agent 5A does not block you except where you share config conventions.
- **Assume**:
  - States will include at least `contact_form`, `otp_form`, `submit_grievance`, and `grievance_review`.
  - There is (or will be) a `form_grievance_complainant_review` form to reuse/extend.
- Design the flows so they can be invoked from the main grievance submission flow or other entry points without tight coupling.

#### Goals
- **Contact + OTP flow**
  - Collect and validate contact information.
  - Trigger and verify an OTP.
  - Only allow continuation when OTP is successfully validated (with timeout / retry behavior as needed).
- **Grievance review flow**
  - Integrate a review step after grievance submission using `form_grievance_complainant_review`.
  - Optionally display or incorporate classification results if available.

#### Tasks
- **Flow & states**
  - Add states: `contact_form`, `otp_form`, `submit_grievance`, `grievance_review` into `flow.yaml` and `state_machine.py`.
  - Define transitions between these states and back to the main flow (success, failure, user cancellation).
- **Forms & actions**
  - Wire contact and OTP forms into the form loop (form definitions, required slots, validations).
  - Register and implement contact/OTP-related actions and any submission/review actions in `action_registry.py`.
  - Integrate `form_grievance_complainant_review` after submission, ensuring it can handle:
    - Cases where classification is present.
    - Cases where classification is missing or delayed.
- **User experience & edge cases**
  - Define behavior for wrong OTP, expired OTP, and maximum retries.
  - Ensure the user can correct contact info and re-request OTP.
  - Make review optional if the user skips or if required data is missing.

#### Deliverables
- Updated flow and slot configuration:
  - `orchestrator/config/flow.yaml`
  - `orchestrator/config/slots.yaml`
- Extended orchestration and actions:
  - `orchestrator/state_machine.py`
  - `orchestrator/action_registry.py`
- Minimal tests or test stubs for these flows in `tests/orchestrator/` (coordinate with Agent 5C).

---

### Agent 5C – Tests and E2E Flows for New Features

#### Mission
Design and implement **unit, integration, and end-to-end tests** for the new status check, contact + OTP, and grievance review flows so that behavior is well-specified and stable, mirroring existing Rasa behavior.

#### Context / Constraints
- **Depends on**: The APIs, states, and config shapes defined by Agents 5A and 5B.
- You can:
  - Start by defining test cases, fixtures, and expected behaviors based on current Rasa flows.
  - Implement tests incrementally as the other agents finalize interfaces.
- Follow existing testing patterns under `tests/orchestrator/`.

#### Goals
- **Unit-level** coverage for:
  - New adapters (e.g., status lookup, OTP sender/validator, contact persistence, classification).
  - Any new utility or mapping logic introduced by Agents 5A and 5B.
- **Integration-level** coverage for:
  - Orchestrator API paths that initiate or interact with the new flows.
  - Form loop behavior for status, contact, OTP, and grievance review forms.
- **E2E** coverage that:
  - Mirrors the current Rasa bot flows for status check, contact+OTP, and grievance review.
  - Ensures correct transitions, slot filling, and final responses.

#### Tasks
- **Test design**
  - Define test matrices for:
    - Status check by phone vs by grievance ID (success, not found, error).
    - Contact+OTP flows (success, wrong OTP, expired OTP, max retries).
    - Grievance review with and without classification results.
- **Test implementation**
  - Add pytest modules for new adapters, forms, and orchestrator API paths under `tests/orchestrator/`.
  - Implement E2E-style tests that simulate user journeys through:
    - Status check flow.
    - Contact + OTP + submit grievance flow.
    - Post-submission grievance review flow.
- **Infrastructure**
  - Reuse and extend existing fixtures, factories, and helpers instead of creating parallel ones.
  - Ensure tests are stable, deterministic, and fast enough for CI.

#### Deliverables
- New or updated tests under `tests/orchestrator/`, including:
  - Adapter/form/API tests for the new flows.
  - E2E tests covering:
    - Status check.
    - Contact + OTP.
    - Grievance review (with/without classification).
- Clear test names and structure that map back to the flows and states defined by Agents 5A and 5B.

### Deliverables
- Updated `orchestrator/config/flow.yaml` and `slots.yaml`
- Extended `orchestrator/state_machine.py`
- Extended `orchestrator/action_registry.py`
- New or updated tests under `tests/orchestrator/`

---

## Agent 6: Webchat Socket Bridge

### Mission
Implement the **Socket.IO bridge** (Option A, short-term) so that the existing `channels/webchat` client can talk to the orchestrator without major frontend changes.

### Context
- **Spec**: See [08_webchat_socket_bridge.md](08_webchat_socket_bridge.md)
- **Frontend**: `channels/webchat` (unchanged except for config URL)
- **Backend**:
  - Bridge listens for `complainant_uttered`
  - Bridge calls orchestrator conversation logic (`run_flow_turn` / `POST /message`)
  - Bridge emits `bot_uttered` compatible with existing event handlers
- This is a **transition agent**; the long-term target is REST_webchat (Spec 9).

### Tasks

- [ ] **6.1** Create bridge module
  - Implement `orchestrator/socket_server.py` (or equivalent) using `python-socketio` or Starlette websockets.
  - Define `complainant_uttered` handler that:
    - Reads `{ message, session_id, metadata }`
    - Maps to orchestrator call:
      - `user_id = session_id`
      - `text` or `payload` derived from `message` (commands start with `/`)
    - Calls `run_flow_turn(session, text, payload, domain)` directly (preferred) or `POST /message`.
    - Saves updated session via `save_session`.
    - Emits `bot_uttered` events for each orchestrator `messages[]` entry.

- [ ] **6.2** Wire bridge into app startup
  - Ensure the bridge starts alongside the FastAPI app (or as a companion ASGI app).
  - Expose it on a configurable host/port and path `/socket.io/`.

- [ ] **6.3** Update webchat config
  - In `channels/webchat/config.js`, change `WEBSOCKET_CONFIG.URL` to point to the bridge host/port.
  - Keep `path: '/socket.io/'` and `transports: ['websocket']` unchanged.

- [ ] **6.4** Update nginx (or reverse proxy)
  - Add or adjust a `location ~* ^/socket\.io/` block that proxies to the bridge.
  - Preserve WebSocket upgrade headers.

- [ ] **6.5** Tests / verification
  - Manual:
    - Start orchestrator + bridge.
    - Open existing webchat.
    - Run through: intro → language → new grievance → grievance text → submit details.
  - Optional:
    - Add a small integration test that emits `complainant_uttered` via a Socket.IO client and asserts `bot_uttered` responses.

### Deliverables
- `orchestrator/socket_server.py` (or equivalent bridge module)
- Updated orchestrator startup wiring to include the Socket.IO bridge
- Updated `channels/webchat/config.js` with new `WEBSOCKET_CONFIG.URL`
- Updated nginx (or reverse proxy) config routing `/socket.io/` to the bridge
- Short test note or script documenting how to verify the bridge end-to-end

---

## Agent 7: REST Webchat

### Mission
Implement the **REST-based webchat** (Option B, long-term) in a separate folder (`channels/REST_webchat`) that talks directly to the orchestrator `POST /message` endpoint, with no dependency on Rasa or Socket.IO.

### Context
- **Spec**: See [09_rest_webchat.md](09_rest_webchat.md)
- **Current webchat**: `channels/webchat` uses Socket.IO → Rasa; REST_webchat should:
  - Reuse as much UI and file-upload logic as possible.
  - Replace the transport layer with `fetch` calls to the orchestrator.
- **Backend**: Orchestrator already exposes `POST /message` and `GET /health`.

### Tasks

- [ ] **7.1** Create REST_webchat folder
  - Copy existing webchat:
    ```bash
    cp -r channels/webchat channels/REST_webchat
    ```
  - Adjust any build/HTML entry points so they reference the REST_webchat bundle instead of the Socket.IO one.

- [ ] **7.2** Replace Socket.IO client logic
  - In `channels/REST_webchat/app.js`:
    - Remove or no-op `initializeWebSocket`, `socket`, `socket.emit`, `io(...)`.
    - Implement `restSendMessage(message, additionalData)` that:
      - Derives `user_id` from `window.getSessionId()` (reuse existing session logic).
      - Maps commands (`/introduce`, `/new_grievance`, etc.) to `payload`, and free text to `text`.
      - Calls orchestrator `POST /message` via `fetch`.
      - Calls a new `handleOrchestratorResponse(response)` helper to render replies.
    - Set `window.safeSendMessage = restSendMessage`.

- [ ] **7.3** Render orchestrator responses
  - Implement `handleOrchestratorResponse` (in `app.js` or a new module) that:
    - Iterates over `response.messages[]`.
    - For each message:
      - If `text`, call `uiActions.appendMessage(text, "received")`.
      - If `buttons`, render quick replies using existing UI helpers (e.g. `eventHandlers.renderQuickReplies`).
      - If `custom`/`json_message`, pass to a new `eventHandlers.handleCustomPayload` that:
        - Detects grievance ID events and updates `window.grievanceId`.
        - Handles any other custom payloads you define.
    - Optionally uses `next_state` / `expected_input_type` to adjust UI (e.g. disabling input when `next_state == "done"`).

- [ ] **7.4** Intro / initial message
  - Keep the existing `/introduce{...}` behavior, but:
    - Replace any `socket.emit` with `restSendMessage(initialMessage)`.
    - Ensure `province`, `district`, and `flask_session_id` are still passed in the payload as today.

- [ ] **7.5** File uploads
  - Confirm that:
    - File uploads still go to Flask (`FILE_UPLOAD_CONFIG.URL`) as before.
    - `window.grievanceId` is set based on orchestrator custom payloads so uploads have the correct `grievance_id`.
  - Adjust only where necessary (e.g. if any Rasa-specific fields were sent along).

- [ ] **7.6** Testing & validation
  - Manual:
    - Open REST_webchat page.
    - Walk through intro → language selection → new grievance → grievance text → submit.
    - Attach files and confirm they appear in the back office with the correct grievance.
  - Optional automated:
    - Add browser tests (Playwright/Cypress) that simulate the main happy-path flows using REST_webchat.

### Deliverables
- `channels/REST_webchat/` folder with:
  - REST-based `app.js` (or equivalent entry point).
  - Updated `config.js` (no WEBSOCKET_CONFIG dependency or only for file server, if desired).
  - Any updated `eventHandlers.js` / `uiActions.js` helpers tailored for REST responses.
- Minimal documentation on how to run and test REST_webchat locally.


