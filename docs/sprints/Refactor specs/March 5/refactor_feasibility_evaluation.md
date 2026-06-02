# GRM Chatbot Refactor: Feasibility Evaluation

**Document purpose**: Evaluate the feasibility of migrating from Rasa to a deterministic state machine / FastAPI orchestrator, as proposed in `new_decision_engine_migration.md`.  
**Timeline constraint**: 2 weeks implementation.  
**Date**: February 24, 2025.

---

## Executive Summary

| Area | Feasibility | Effort (rough) | Risk |
|------|-------------|----------------|------|
| New decision engine | Medium–High | 4–6 days | Medium |
| Action layer adaptation | High | 5–7 days | High |
| Frontend integration | Medium | 1–2 days | Low |
| API choice (FastAPI vs current) | Low | 0.5 days | Low |

**Verdict**: Feasible in 2 weeks only with scope reduction and parallel work. The refactor is reasonable strategically, but the current codebase’s depth of Rasa-specific customizations makes it **risky to complete fully in 2 weeks** without dropping features or doing phased delivery.

---

## 1. Current System Snapshot

### 1.1 Rasa Components

| Component | Count/Details |
|-----------|----------------|
| Slots | ~90+ slots in `domain.yml` |
| Actions | ~130 actions |
| Forms | 12 forms (e.g. `form_grievance`, `form_contact`, `form_otp`, `form_status_check_1/2`, etc.) |
| Intents | ~80+ (with NLU training) |
| Stories | Multiple flows (grievance filing, status check, sensitive issues, modify flows) |
| Rules | ~17 rules for form completion + intents |

### 1.2 Action Customizations (Critical for Migration)

**Location**: `rasa_chatbot/actions/`

- **Base mixins** (`base_mixins.py`, ~620 lines):
  - `ActionCommonMixin`: logging, helpers, constants
  - `LanguageHelpersMixin`: language detection, skip detection (fuzzy), validation helpers
  - `SensitiveContentHelpersMixin`: keyword-based sensitive content detection
  - `ActionFlowHelpersMixin`: `get_next_action_for_form()` (central routing), reset_slots, grievance helpers
  - `ActionMessagingHelpersMixin`: email, SMS, recap preparation

- **Base classes** (`base_classes.py`):
  - `BaseAction`: `run()` → `execute_action()`, language initialization
  - `BaseFormValidationAction`: extends Rasa `FormValidationAction` with custom slot extraction, skip handling, boolean/category slot handling

- **Form-specific logic**:
  - `form_contact.py`: 600+ lines, province/district/municipality/village/address validation and chaining
  - `form_grievance.py`: grievance description, sensitive content branching
  - `form_otp.py`: OTP consent, input, resend, skip flows
  - `form_status_check.py` / `form_status_check_skip.py`: phone/grievance ID retrieval, name matching, location-based routing
  - `form_grievance_complainant_review.py`: category/summary review, modify flows
  - `form_sensitive_issues.py`: nickname, phone, extra details
  - `form_story_main_route_step.py`: story routing

### 1.3 Utterance System

- **File**: `utterance_mapping_rasa.py` (~1200 lines)
- **Structure**: `form_name → action_name → utterances[index][en|ne]` + `buttons`
- **Languages**: English (en), Nepali (ne)

### 1.4 Integration Points

- **Frontend webchat** → Rasa Socket.IO (port 5005), event `complainant_uttered`
- **REST webhook**: `POST /webhooks/rest/webhook`
- **Flask backend** (port 5001): file uploads, `/accessible-socket.io` for Celery status updates
- **Celery**: LLM classification → sends results back to Rasa as user message (WebSocket)
- **Database**: PostgreSQL (grievances, complainants, files, etc.)

---

## 2. Complexity by Work Package

### 2.1 Coding the New Decision Engine

**Scope**: Implement a deterministic state machine that replaces Rasa stories, rules, and form orchestration.

**Complexity**: **Medium–High**

**Reasons**:

1. **Flow structure**: The current flow is driven by `get_next_action_for_form()` in `base_mixins.py`. The routing map is nested: `story_main → form_name → story_route → story_step`. This can be serialized into `flow.json` / `flow.yaml` without redesigning logic.

2. **Sensitive-issues branching**: `grievance_sensitive_issue` and other slots change which form runs next (e.g. `form_sensitive_issues` vs `form_contact`). The orchestrator must handle these conditionals explicitly.

3. **Form completion vs. form transitions**: Rasa uses `active_loop` and rules for form completion. The new engine must model “form X complete → run action_next_action → go to form Y” explicitly.

4. **Intent mapping**: Today NLU maps text to intents (e.g. `/new_grievance`, `/check_status`, `skip`, `affirm`, `deny`). Without Rasa, the orchestrator needs:
   - Button payloads (already used: `/new_grievance`, etc.)
   - Text matching for skip/affirm/deny (you already have `is_skip_instruction` and similar logic)

**Deliverables**:

- `flow.json` or `flow.yaml` (states, transitions, expected input types)
- Orchestrator logic (state handler, transition resolution)
- Session store interface (state + slots per user)

**Estimated effort**: 4–6 days (assuming flow export + orchestrator implementation).

---

### 2.2 Adjusting the Action Layer

**Scope**: Make existing actions callable as plain Python functions without `Tracker`, `CollectingDispatcher`, or Rasa events.

**Complexity**: **High**

**Reasons**:

1. **Rasa SDK coupling**:
   - `Tracker`: slots, `latest_message`, `sender_id`, `active_loop`
   - `CollectingDispatcher`: `utter_message(text=..., buttons=...)`
   - `FormValidationAction`: `extract_*` and `validate_*` per slot

2. **Required abstractions**:
   - **Context**: `{ slots: dict, user_id: str, language_code: str, ... }` instead of `Tracker`
   - **Output**: `ActionResult` = `{ slot_updates: dict, messages: list, next_action?: str }` instead of `dispatcher.utter_message()` + `SlotSet` events

3. **Slot extraction and validation**:
   - Current forms use `extract_*` + `validate_*`. Validation often calls `dispatcher.utter_message()` for error prompts.
   - Migration options:
     - **A**: Keep validation logic, replace dispatcher with “return messages in ActionResult”
     - **B**: Move validation into the orchestrator and have actions assume pre-validated input

4. **`requested_slot` and skip flow**:
   - Rasa tracks `requested_slot` and `skip_validation_needed`. The orchestrator must manage equivalent state (e.g. “current slot”, “skip confirmation pending”).

5. **Shared helpers**:
   - `helpers_repo`, `db_manager`, `Messaging`, `location_validator`, `keyword_detector`, etc. remain valid; they do not depend on Rasa.
   - `get_utterance_base` / `get_buttons_base` can stay as-is; only the caller (orchestrator vs. action) changes.

6. **Async and Celery**:
   - `action_retrieve_classification_results` triggers Celery and waits for WebSocket delivery. The orchestrator needs a similar “wait for classification” state and integration with the existing Celery/WebSocket path.

**Deliverables**:

- `actions/registry.py`: `call_action(action_name, slots, context) -> ActionResult`
- Adapters per action (or a generic wrapper) that:
  - Build context from slots + session
  - Call existing business logic
  - Convert `ActionResult` back into orchestrator updates

**Estimated effort**: 5–7 days (more if every form/action is wrapped manually).

---

### 2.3 Frontend Integration

**Scope**: Point the webchat at the new orchestrator instead of Rasa.

**Complexity**: **Medium (Low if API is compatible)**

**Current frontend behavior**:

- Connects to Rasa via Socket.IO (`/socket.io/` on port 5005)
- Emits `complainant_uttered` with `{ message, session_id }`
- Expects `bot_uttered`-style responses (text + optional buttons)
- Sends `rasa_session_id` / `flask_session_id` for file uploads and Celery

**Options**:

1. **New orchestrator exposes a Rasa-compatible Socket.IO API**  
   - Same events (`complainant_uttered` / `bot_uttered`), same payload shape.  
   - Frontend changes: minimal (URL/port only).

2. **New orchestrator exposes REST-only**  
   - `POST /message` with `{ user_id, message_id, text, payload?, channel? }`  
   - Frontend must be updated to use REST instead of Socket.IO, or you add a small Socket.IO → REST bridge.

3. **WebSocket on Flask**  
   - Reuse `/accessible-socket.io` or add a new WebSocket endpoint.  
   - Requires frontend changes to connect to Flask and use the new protocol.

**Recommendation**: Keep a Rasa-compatible Socket.IO interface on the orchestrator to minimize frontend work.

**Estimated effort**: 1–2 days (mostly config and endpoint wiring if the API is compatible).

---

### 2.4 API Choice: FastAPI vs. Current Stack

**Scope**: Choose between FastAPI and the current Flask/Rasa setup for the orchestrator.

**Complexity**: **Low**

**Considerations**:

| Factor | FastAPI | Keep Flask |
|--------|---------|------------|
| New code | New service | Extend existing Flask app |
| Async | Native | Requires careful use of eventlet/gevent |
| Typing & validation | Strong (Pydantic) | Manual |
| Learning curve | Low if team knows async Python | None |
| Deployment | Extra service (or same host, different port) | Same as today |

**Recommendation**: Use **FastAPI** for the orchestrator as a dedicated service. It fits the “small backend brain” idea and keeps orchestration separate from Flask (file uploads, WebSocket for Celery). Flask stays for file handling and existing integrations.

**Estimated effort**: ~0.5 days (project setup, basic routing).

---

## 3. Phased Migration (Recommended for 2 Weeks)

Given the 2-week constraint, a phased approach reduces risk:

### Phase 1 (Week 1): Core engine + single flow

1. **Day 1–2**: Export `flow.json` for one path (e.g. “new grievance, EN, no sensitive content”).
2. **Day 2–3**: Implement FastAPI orchestrator with `POST /message` and in-memory session store.
3. **Day 3–4**: Action registry + adapters for the main grievance flow (e.g. `action_start_grievance_process` → `form_grievance` steps → `form_contact` → `form_otp` → `action_submit_grievance`).
4. **Day 5**: Connect webchat to orchestrator (Socket.IO compatibility layer or REST + minimal frontend changes).
5. **Day 5–6**: End-to-end test of one path.

### Phase 2 (Week 2): Broaden coverage

1. Extend `flow.json` to status check and sensitive-issues flows.
2. Add adapters for remaining actions used in those flows.
3. Add Postgres (or Redis) session store.
4. Add `message_id` deduplication.
5. Regression tests against known conversation paths.

### Deferred (post–2 weeks)

- Full parity with all Rasa rules and intents
- WhatsApp integration
- Optional queue for fragile calls
- GRMS stub (per spec)

---

## 4. Risk Overview

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Action wrapping takes longer than estimated | High | Delays Phase 2 | Prioritize critical actions; stub others |
| Celery/classification integration breaks | Medium | Blocks grievance flow | Test Celery + WebSocket path early |
| State machine misses edge cases | Medium | Wrong next state | Reuse `get_next_action_for_form` logic verbatim |
| Frontend Socket.IO incompatibility | Low | Extra frontend work | Design Rasa-compatible response format from day 1 |
| Session store performance | Low | Slowness under load | Start with Postgres; optimize if needed |

---

## 5. Agent Specs (For Implementation)

If you proceed, these specs can be handed to different agents:

### Agent A: Flow Export

- **Input**: `domain.yml`, `stories.yml`, `rules.yml`, `base_mixins.py` (routing_map)
- **Output**: `flow.json` or `flow.yaml` with states, transitions, `store_as`, `expected_input_type`, actions
- **Reference**: `utterance_mapping_rasa.py` for prompts/messages

### Agent B: Orchestrator Service

- **Stack**: FastAPI
- **Endpoints**: `POST /message`, `GET /health`
- **Logic**: Load session → run state handler → validate input → update slots → call action → resolve next state → persist session
- **Session**: In-memory first; Postgres/Redis in Phase 2

### Agent C: Action Registry and Adapters

- **File**: `actions/registry.py`
- **Contract**: `call_action(action_name, slots, context) -> ActionResult`
- **Tasks**: Create context builder (slots → Tracker-like), adapter per action or generic wrapper, map `ActionResult` to slot updates + messages

### Agent D: Frontend Integration

- **Task**: Add config for orchestrator URL; ensure request/response format matches what webchat expects
- **Optional**: Implement Socket.IO compatibility layer on the orchestrator

---

## 6. Conclusion and Recommendation

The migration is **technically feasible** and aligns well with the goal of simplifying maintenance by removing Rasa stories, rules, and forms. The main difficulty is the **rich action and form layer** built on top of Rasa’s Tracker and Dispatcher.

**Recommendation**:

1. **Do the refactor**, but in phases as above.
2. **Target 2 weeks** for: flow export, orchestrator, action registry for the main grievance flow, and one working path end-to-end.
3. **Extend coverage** in the following weeks: status check, sensitive issues, full regression.
4. **Keep Rasa running in parallel** until the new engine has been validated on key flows.

**Realistic outcome for 2 weeks**: A working orchestrator with the core grievance flow migrated and the foundation for status check and sensitive-issues flows in place.
