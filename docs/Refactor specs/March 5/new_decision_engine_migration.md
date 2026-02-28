# GRM Chatbot — Replace Rasa Flow Engine (Keep Existing States/Fields/Actions)

## Goal

Move the deterministic flow logic out of Rasa while **keeping the existing**:

- state names
- field/slot names
- action names + their business logic (as-is, just called from outside Rasa)

Rasa can be removed entirely later, but the first target is: **same behavior, less Rasa pain**.

---

## What stays the same

- Conversation structure (all existing states)
- Collected fields / slot keys
- Validation rules (where possible)
- Action names and their semantics (e.g., `action_create_complaint`, `action_check_status`, etc.)
- use oof rasa_chatbot/actions/utils/utterance_mapping_rasa.py as a reference for all the utterances

---

## What changes

- Rasa stories/rules/forms are replaced by a **deterministic state machine** (wizard engine).
- A small backend service (FastAPI recommended) becomes the “brain”:
  - loads the flow definition
  - stores session state + collected fields
  - calls actions as normal Python functions
  - returns the next bot message + expected input

GRMS API integration is not built yet → implement a **stub action** for now.

---

## Target Architecture (minimal)

Channel (web test now / WhatsApp later)
→ Orchestrator API (state machine)
→ Session Store (DB)
→ Action Layer (your existing actions)
→ Queue (optional but recommended)
→ GRMS Adapter (stub now, real API later)

---

## Work to do (high level)

### 1) Export / represent the Rasa flow outside Rasa

Create a single source of truth for the flow using your existing names.

**Deliverable:** `flow.json` (or `flow.yaml`) that contains:

- `states`
- prompts/messages per state
- expected input type per state
- field/slot to store (`store_as`)
- transition to next state (deterministic)
- which action to call (if any) at state entry/exit

> No need to redesign the flow—just serialize what already exists.

---

### 2) Implement Orchestrator service

**Deliverable:** FastAPI app with one endpoint.

`POST /message`
Input:

- `user_id`
- `message_id`
- `text` OR `payload` (button selection)
- `channel` (optional)

Output:

- `messages[]` (text + optional choices)
- `next_state`
- `expected_input_type`

Core logic:

- load session (`state + slots`)
- run state handler
- validate input, update slots
- call action if required
- pick next state
- return response

---

### 3) Session persistence

Store per user:

- `state`
- `slots` (JSON dict using your current slot names)
- timestamps
- message dedupe (by `message_id`)

DB: Postgres (preferred) or SQLite for dev.

---

### 4) Action layer compatibility

Wrap each existing Rasa action so it can be called as a normal function, without Rasa dispatcher objects.

**Deliverable:** `actions/registry.py`

- `call_action(action_name, slots, context) -> ActionResult`
- ActionResult can include:
  - slot updates
  - messages
  - events (optional)
  - side-effect results

Keep action names identical to Rasa.

---

### 5) Optional queue for fragile calls (recommended)

For things that may fail due to connectivity (future GRMS submit, optional LLM calls):

- enqueue job
- immediate user response: “received, processing”
- retry later

Can start without a queue and add once needed.

---

### 6) GRMS integration placeholder

Since GRMS API is not built:

- implement a stub action matching your intended action name
- store payloads locally for testing

Example:

- `action_submit_to_grms` writes the canonical payload JSON to DB and returns `status=PENDING_INTEGRATION`

---

## Migration approach (safe)

1. **Keep names identical** (states, slots, actions).
2. Build orchestrator + run with a simple web test harness.
3. Replay known conversation paths to verify identical outputs.
4. Integrate WhatsApp after orchestrator is stable.

---

---

## Acceptance criteria

- For the same inputs, the new orchestrator produces:
  - the same sequence of states
  - the same slot keys filled
  - the same actions invoked (by name)
- Idempotent handling of duplicate inbound messages (message_id dedupe)
- No dependency on Rasa stories/rules/forms at runtime

---
