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
| File upload robustness (REST webchat) | [Agent 12](#agent-12-file-upload-robustness-rest-webchat) | ⬜ Pending |
| Agents 10.A–10.D | [10_agent_instructions.md](10_agent_instructions.md) | ⬜ Pending |
| Backend: Flask → FastAPI (8A–8D) | [Agent 8A](#agent-8a-fastapi-skeleton--grievance-api) → [8B](#agent-8b-file-server-router) / [8C](#agent-8c-socketio-asgi-app) → [8D](#agent-8d-voice-gsheet-deprecation-tests) / [11_flask_to_fastapi_migration.md](11_flask_to_fastapi_migration.md) | ⬜ Pending |

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

---

## Agent 12: File Upload Robustness (REST webchat)

### Mission

Implement the **robust file upload flow** in `channels/REST_webchat` so users can add files anytime during a grievance flow without losing their place. The bot remembers the last bot message and quick replies; when the user returns from file upload, we show a transition message and re-display that state. No backend or orchestrator changes.

### Context

- **Spec:** [12_file_upload_robustness.md](12_file_upload_robustness.md) — requirements, resolved decisions (Q1–Q10), exit flow, data flow, proposed architecture.
- **Location:** `channels/REST_webchat/` only (`app.js`, `modules/eventHandlers.js`, `modules/uiActions.js`, `index.html`, `styles.css`).
- **Backend / orchestrator:** No changes. File upload and `/file-status` polling remain as today; no new API or payloads.

### Tasks

- [ ] **12.1 Attach button enablement**
  - In `app.js`: Keep the attach button always visible. **Disable** it (greyed out, not clickable) when `window.grievanceId` is null/undefined.
  - When disabled, set a `title` (tooltip) on the button: "Start a grievance first" (or equivalent).
  - When `window.grievanceId` is set (e.g. from `handleCustomPayload` / `json_message`), enable the button and clear the tooltip.
  - Use existing `uiActions.setGrievanceId` (or equivalent) so that when the orchestrator sends grievance_id, the button becomes enabled; add a single place that updates the button disabled state and tooltip whenever grievanceId changes (e.g. after each `handleOrchestratorResponse` or in `setGrievanceId` callback).

- [ ] **12.2 State snapshot**
  - When the user selects files (e.g. in `handleFileSelection` or when `selectedFiles.length` becomes > 0 before upload), take a **snapshot** of:
    - Last bot message text (e.g. `window.lastBotMessageText` or the last received message in the chat).
    - Last bot quick replies (e.g. `window.lastBotQuickReplies` — array of `{ title, payload }`).
  - Store in module-level variables or a small object (e.g. `fileUploadSnapshot`) so it is available when the user later clicks "Go back to chat".
  - Ensure the snapshot is taken **before** the user sends (Enter) to upload, so it captures the state "before file upload flow". If needed, snapshot when the file preview is first shown (user has selected files but not yet submitted).

- [ ] **12.3 Lock message input during upload**
  - From when the user submits the form with files selected until the upload completes and "File is saved in the database" (and optionally until the "Add more / Go back" message is shown), **lock** the message input and send button (disabled, optionally greyed out).
  - Unlock when: (a) upload fails (show error, unlock), or (b) file status polling returns SUCCESS for all files and the post-upload message + buttons are shown.

- [ ] **12.4 Post-upload message and buttons**
  - After "File is saved in the database" (or equivalent success message), append a **bot message**:  
    `"Files uploaded. You can add more files or go back to the chat."`  
    with two quick-reply style buttons: **Add more files** | **Go back to chat**.
  - **Replace** any existing quick replies in the UI with only these two (so the user does not see the previous bot’s buttons until they click "Go back to chat").
  - Stack: if the user clicks "Add more files" and uploads again, append another "Files uploaded. You can add more files or go back to the chat." message with the same two buttons (do not replace the previous such message).

- [ ] **12.5 "Add more files" button**
  - When the user clicks **Add more files**, re-open the file picker (programmatic click on the file input) and/or ensure the attachment preview area is ready for a new selection. No orchestrator call. User can select new files and send again; then lock → upload → poll → success → append another post-upload message with [Add more][Go back].

- [ ] **12.6 "Go back to chat" button**
  - When the user clicks **Go back to chat**:
    1. Append a **transition message** as a bot message:  
       *"Your files are uploaded. Here's where we left off."*  
       (Use this exact string unless the spec is updated.)
    2. Append the **last bot message** (from snapshot) as a new bot bubble.
    3. Restore the **original quick replies** from the snapshot (e.g. [Yes] [No]) so they appear under that last bot message.
    4. **Unlock** the message input and send button.
  - Do **not** call the orchestrator. The session is unchanged; the next user message or quick-reply click will send the next `POST /message` as usual.

- [ ] **12.7 Persist snapshot across "Add more files" rounds**
  - If the user clicks "Add more files" and uploads again, keep using the **same** snapshot (the last bot message and quick replies from before they first entered the file upload flow). Do not overwrite the snapshot with the "Files uploaded. Add more or go back" message. When they finally click "Go back to chat", restore from that original snapshot.

- [ ] **12.8 Edge cases**
  - No grievance_id: button disabled and tooltip as in 12.1; if somehow upload is attempted, keep current error message in chat.
  - Upload failure: unlock input, show error, do not show "Add more / Go back" (user can try again or continue chatting).
  - Snapshot missing (e.g. user refreshed mid-upload): on "Go back to chat", if snapshot is empty, still unlock input and optionally append a short message like "You can continue below." so the user is not stuck.

### Deliverables

- Updated `channels/REST_webchat/app.js`: attach button enable/disable and tooltip, snapshot on file selection, lock/unlock input during upload, post-upload message + [Add more files][Go back to chat], "Go back to chat" handler (transition message + restore last bot message + quick replies), "Add more files" re-open picker.
- Updated `channels/REST_webchat/modules/uiActions.js` (or equivalent): any helpers needed to append a bot message, set quick replies, or update the attach button state from a single place when grievanceId changes.
- Updated `channels/REST_webchat/modules/eventHandlers.js` (if needed): e.g. handler for the "Go back to chat" and "Add more files" button payloads that calls into app.js logic.
- Updated `channels/REST_webchat/styles.css` (if needed): disabled state for the attach button (greyed out), and optionally locked state for the message input.
- No changes to orchestrator, backend, or `utterance_mapping_rasa.py` unless a product decision adds server-side transition text later.

### Reference

- **Spec:** [12_file_upload_robustness.md](12_file_upload_robustness.md) — full requirements, data flow, exit-flow wording, and confirmation on chat order and re-display.
- **Current implementation:** `channels/REST_webchat/app.js` (handleFileUpload, handleMessageSubmit, pollFileStatus, updateFileStatus), `handleOrchestratorResponse`, `eventHandlers.handleCustomPayload`, `uiActions.setGrievanceId`, quick reply rendering.

---

## Agent 8: Backend Flask → FastAPI Migration (split into 8A–8D)

The migration is split into **four agents** so that (1) each has a focused scope, (2) **8B** (file server) and **8C** (Socket.IO) can run in parallel after **8A**, and (3) **8D** (voice, gsheet, deprecation, tests) runs last with the full backend in place.

**Spec:** [11_flask_to_fastapi_migration.md](11_flask_to_fastapi_migration.md) – URL surface, components, design choices, phases. All agents preserve the same URLs and response shapes.

**Execution order:**
```
8A (skeleton + grievance)  →  8B (file server)  →  8D (voice, gsheet, deprecation, tests)
                         ↘  8C (Socket.IO)   ↗
```
- **8A** must complete first (FastAPI app + grievance router).
- **8B** and **8C** can run in parallel; 8B may stub `emit_status_update_accessible` until 8C provides the real Socket.IO app (then 8B or 8C wires the call).
- **8D** runs after 8B (and ideally 8C) so all routers exist for tests and cutover.

---

### Agent 8A: FastAPI skeleton + Grievance API

#### Mission
Create the FastAPI backend app and migrate the grievance API so the app is runnable with uvicorn and grievance endpoints match current Flask behaviour. This is the foundation for 8B, 8C, and 8D.

#### Context
- **Spec:** [11_flask_to_fastapi_migration.md](11_flask_to_fastapi_migration.md) – Phases 1 and 2, URL surface for grievance.
- **Current:** Grievance routes live in `backend/api/app.py` (inline); `send_status_update_notifications` uses `Messaging` in-process.
- **Constraints:** Same paths (`/api/grievance/...`), same response JSON. Reuse `GrievanceDbManager`, `Messaging`.

#### Tasks
- [ ] **8A.1** Create `backend/api/fastapi_app.py` (or `main_fastapi.py`). Add `CORSMiddleware` (same policy as Flask). Add `GET /health` → 200. Verify run with `uvicorn backend.api.fastapi_app:app --port 5001`.
- [ ] **8A.2** Create `backend/api/routers/grievance.py`. Implement:
  - `POST /api/grievance/{grievance_id}/status` (body: status_code, optional notes, created_by); call `update_grievance_status` and `send_status_update_notifications`.
  - `GET /api/grievance/{grievance_id}` (grievance, current_status, status_history, files).
  - `GET /api/grievance/statuses`.
- [ ] **8A.3** Use Pydantic for request/response where helpful; preserve response structure. Include router in app (no prefix; paths already have `/api/grievance`). Test with curl or TestClient vs Flask.

#### Deliverables
- `backend/api/fastapi_app.py` with CORS, `GET /health`, and grievance router.
- `backend/api/routers/grievance.py` with same URL surface and behaviour as Flask grievance routes.

---

### Agent 8B: File server router

#### Mission
Migrate all file-server routes from `FileServerAPI` (`backend/api/channels_api.py`) to a FastAPI router. Preserve URLs and behaviour; wire or stub `emit_status_update_accessible` for task-status updates (real emit provided by 8C).

#### Context
- **Spec:** [11_flask_to_fastapi_migration.md](11_flask_to_fastapi_migration.md) – Phase 3, file server URL surface.
- **Current:** `channels_api.FileServerAPI` – upload-files, files, download, file-status, grievance-review, task-status, generate-ids, test-db, test-upload. Uses `FileServerCore`, Celery, and `emit_status_update_accessible` from `websocket_utils`.
- **Depends on:** 8A (FastAPI app exists). May stub `emit_status_update_accessible` (no-op or log) until 8C mounts Socket.IO; then 8B or 8C connects the file router to the real emit.

#### Tasks
- [ ] **8B.1** Create `backend/api/routers/files.py`. Implement all routes from `FileServerAPI` with same paths: `GET /`, `GET /test-db`, `POST /generate-ids`, `POST /upload-files`, `GET /files/{grievance_id}`, `GET /download/{file_id}`, `GET /file-status/{file_id}`, `GET /grievance-review/{grievance_id}`, `POST /grievance-review/{grievance_id}`, `GET /files/{filename}`, `POST /test-upload`, `POST /task-status`.
- [ ] **8B.2** For `POST /upload-files`: use FastAPI `File()`, `UploadFile`, `Form()` for `grievance_id` and optional fields; reuse `FileServerCore` and Celery task. For `POST /task-status`: call a shared `emit_status_update_accessible(grievance_id, status, task_data)` – stub if 8C not done, or wire to 8C’s helper once available.
- [ ] **8B.3** Include router in FastAPI app. Test: REST webchat upload and file listing with correct `grievance_id`.

#### Deliverables
- `backend/api/routers/files.py` with same URL surface as `FileServerAPI`; `emit_status_update_accessible` either stubbed or wired to 8C’s Socket.IO helper.

---

### Agent 8C: Socket.IO ASGI app

#### Mission
Implement the Socket.IO ASGI app for `/accessible-socket.io` and mount it in the FastAPI app. Provide `emit_status_update_accessible` so the file router (8B) can push status updates to clients. Match current Flask-SocketIO events and room behaviour.

#### Context
- **Spec:** [11_flask_to_fastapi_migration.md](11_flask_to_fastapi_migration.md) – Phase 4, Socket.IO URL and events.
- **Current:** `backend/api/websocket_utils.py` – path `/accessible-socket.io`, Redis message queue, events: connect, join, disconnect, status_update, another_event, join_room; `emit_status_update_accessible` used by file server.
- **Depends on:** 8A (FastAPI app to mount into). Can run in parallel with 8B; 8B will wire to this agent’s emit helper once both are done.

#### Tasks
- [ ] **8C.1** Create a `python-socketio` ASGI app (e.g. `backend/api/websocket_fastapi.py`). Use Redis as message queue if current app uses `SOCKETIO_REDIS_URL`. Implement handlers: `connect`, `join`, `disconnect`, `status_update`, `another_event`, `join_room`, error handler. Match payload and room behaviour (re-emit to room, etc.).
- [ ] **8C.2** Expose `emit_status_update_accessible(grievance_id, status, task_data)` (or same signature as Flask) so the file router can emit to the correct room. Document how 8B should import/call it.
- [ ] **8C.3** Mount the Socket.IO ASGI app in the FastAPI app at `/accessible-socket.io` (e.g. `app.mount("/accessible-socket.io", socket_asgi_app)`). Path must match nginx and clients. Test with accessible UI or a Socket.IO client.

#### Deliverables
- Socket.IO ASGI app (e.g. `backend/api/websocket_fastapi.py`) with same events and `emit_status_update_accessible`; mounted at `/accessible-socket.io`.

---

### Agent 8D: Voice, gsheet, deprecation, tests

#### Mission
Add the remaining routers (voice, gsheet), switch production to the FastAPI backend (scripts and docs), and add or adjust tests for the FastAPI app. Runs after 8A, 8B, and ideally 8C so the full backend is in place.

#### Context
- **Spec:** [11_flask_to_fastapi_migration.md](11_flask_to_fastapi_migration.md) – Phases 5 and 6, checklist.
- **Current:** Voice in `backend/services/accessible/voice_grievance.py` (Flask blueprint); gsheet in `backend/api/gsheet_monitoring_api.py`. Startup via `launch_servers_celery.sh` (or similar).
- **Depends on:** 8A (app), 8B (file router). Prefer 8C done so tests can cover Socket.IO.

#### Tasks
- [x] **8D.1 Voice router** – Create `backend/api/routers/voice_grievance.py`. Routes: `POST /accessible-file-upload`, `GET /grievance-status/{grievance_id}`, `POST /submit-grievance`. Reuse logic from `voice_grievance.py`; replace Flask with FastAPI (Pydantic, `File`, `Form`, path params). Include in app.
- [x] **8D.2 Gsheet router** – Create `backend/api/routers/gsheet.py` (or add `APIRouter` in existing gsheet module). Route: `GET /gsheet-get-grievances` with Bearer auth; reuse auth and data logic. Include in app.
- [x] **8D.3 Deprecate Flask for production** – Update `scripts/rest_api/launch_servers_celery.sh` (or equivalent) to run FastAPI backend with uvicorn (e.g. port 5001). Add comment/README in `backend/api/` that live backend is FastAPI; keep `app.py` for reference. Update [BACKEND.md](../../BACKEND.md) and deployment/nginx notes.
- [x] **8D.4 Tests** – Add or adjust tests using `TestClient(backend.api.fastapi_app.app)` for: health, grievance endpoints, upload-files (or key file routes), and optionally Socket.IO connect/emit. Ensure REST webchat file upload and grievance_id flow work against FastAPI backend.

#### Deliverables
- `backend/api/routers/voice_grievance.py`, `backend/api/routers/gsheet.py` with same URL surface as current Flask.
- Startup scripts and docs updated to uvicorn; Flask deprecated for production.
- Tests for FastAPI backend; REST webchat verified against it.

---

### Reference (all Agent 8 sub-agents)
- **Spec:** [11_flask_to_fastapi_migration.md](11_flask_to_fastapi_migration.md) – URL surface, components, phases, checklist.
- **Backend overview:** [BACKEND.md](../../BACKEND.md). **Orchestrator:** [01_orchestrator.md](01_orchestrator.md).


