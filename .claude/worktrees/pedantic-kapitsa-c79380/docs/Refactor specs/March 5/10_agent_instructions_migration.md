# Agent Instructions 10.A–10.E

Instructions for agents responsible for implementing the updated specs that cover **all forms and flows** (new grievance, contact, OTP, submit, grievance review, status check), plus Celery integration and server scripts.

**Execution order**: 10.B and 10.D can inform each other; 10.C depends on 10.B; 10.A depends on 10.B, 10.C, and 10.D; **10.E** depends on 10.A–10.D. **Recommended**: 10.B → 10.C → 10.D → 10.A → 10.E.

---

## Overview

| Agent | Spec | Responsibility |
|-------|------|----------------|
| **10.A** | [01_orchestrator.md](01_orchestrator.md) | Orchestrator: FastAPI app, session store, state machine, wire all states and transitions |
| **10.B** | [02_action_layer.md](02_action_layer.md) | Action Layer: adapters, registry, wire all actions for all forms |
| **10.C** | [03_form_loop.md](03_form_loop.md) | Form Loop: run_form_turn, _ASK_ACTIONS_BY_SLOT, support all forms |
| **10.D** | [04_flow_logic.md](04_flow_logic.md) | Flow Logic: transitions, routing, payload→intent, initial session |
| **10.E** | [02_action_layer.md](02_action_layer.md) Celery section | Celery integration, action verification, launch_servers_celery.sh, stop_servers_celery.sh |

---

## Agent 10.A: Orchestrator

### Mission

Implement the orchestrator so it drives **all flows** defined in [01_orchestrator.md](01_orchestrator.md): new grievance (form_grievance → contact_form → otp_form → submit_grievance → grievance_review → done) and status check (status_check_form with form_status_check_1/2/otp/skip).

### Spec Reference

**Primary spec**: [01_orchestrator.md](01_orchestrator.md)

### Context

- **Depends on**: 10.B (action registry, adapters), 10.C (form loop), 10.D (transitions, payload mapping)
- **Files**: `orchestrator/main.py`, `orchestrator/session_store.py`, `orchestrator/state_machine.py`
- **Config**: `orchestrator/config/flow.yaml` – load states, transitions, forms at startup

### Tasks

1. **Wire all states in state_machine.py**
   - `intro`, `main_menu` – already done
   - `form_grievance` – run form loop; on form_complete → `contact_form` (not `done`)
   - `contact_form` – run form loop for form_contact; on form_complete → `otp_form`
   - `otp_form` – run form loop for form_otp; on form_complete → `submit_grievance` (grievance) or next status-check step (status check)
   - `submit_grievance` – run `action_submit_grievance`; on submit_complete → `grievance_review`
   - `grievance_review` – run form loop for form_grievance_complainant_review; on review_complete → `done`
   - `status_check_form` – run form loop for form_status_check_1/2/otp/skip; on form_complete → done or next form per story_route/story_step
   - `done` – flow ends

2. **Implement routing for status_check_form**
   - When form_status_check_1 completes: route to form_otp (phone), form_status_check_2 (grievance ID), or form_status_check_skip
   - When form_otp completes (status check): route to form_status_check_2
   - When form_status_check_2 completes: route to action_status_check_request_follow_up or action_skip_status_check_outro
   - When form_status_check_skip completes: run action_skip_status_check_outro → done

3. **Ensure session structure supports all flows**
   - session.state, session.active_loop, session.requested_slot
   - session.slots with all slots used by form_contact, form_otp, form_grievance_complainant_review, form_status_check_*

4. **Load form config from flow.yaml**
   - Forms section defines validation_action and required_slots per form
   - Use config to resolve form instance and active_loop for each state

### Deliverables

- Updated `orchestrator/state_machine.py` with handlers for contact_form, otp_form, submit_grievance, grievance_review
- Status_check_form logic that chains form_status_check_1 → form_otp/form_status_check_2/form_status_check_skip as per routing map in 04_flow_logic.md
- All transitions from flow.yaml implemented

### Cross-Agent Dependencies

- **10.B**: Must have invoke_action for all actions (action_ask_complainant_*, action_ask_otp_*, action_submit_grievance, action_status_check_*, etc.)
- **10.C**: Must have run_form_turn and form instances for form_contact, form_otp, form_grievance_complainant_review, form_status_check_1/2/skip
- **10.D**: Use PAYLOAD_TO_INTENT, Initial Session structure, Routing Map from 04_flow_logic.md

---

## Agent 10.B: Action Layer

### Mission

Extend the action registry and adapters so they support **all actions** required by every form and flow in [02_action_layer.md](02_action_layer.md).

### Spec Reference

**Primary spec**: [02_action_layer.md](02_action_layer.md)

### Context

- **Depends on**: Existing Rasa actions in `rasa_chatbot/actions/`
- **Files**: `orchestrator/adapters/dispatcher.py`, `orchestrator/adapters/tracker.py`, `orchestrator/action_registry.py`
- **Interface**: CollectingDispatcher, SessionTracker must match what Rasa actions expect

### Tasks

1. **Ensure CollectingDispatcher and SessionTracker support all slots**
   - Slots for form_contact, form_otp, form_grievance_complainant_review, form_status_check_* (see slots table in 02_action_layer.md)
   - No changes to interface; only ensure tracker passes correct slots to actions

2. **Register all regular actions in action_registry.py**
   - Intro/menu: action_introduce, action_set_english, action_set_nepali, action_main_menu
   - Grievance: action_start_grievance_process, action_ask_grievance_new_detail
   - Status check: action_start_status_check
   - Contact: action_ask_complainant_location_consent, action_ask_complainant_province, action_ask_complainant_district, action_ask_complainant_municipality_temp, action_ask_complainant_municipality_confirmed, action_ask_complainant_village_temp, action_ask_complainant_village_confirmed, action_ask_complainant_ward, action_ask_complainant_address_temp, action_ask_complainant_address_confirmed, action_ask_complainant_consent, action_ask_complainant_full_name, action_ask_complainant_email_temp, action_ask_complainant_email_confirmed
   - OTP: action_ask_otp_consent, action_ask_otp_input, action_ask_complainant_phone
   - Status check: action_ask_status_check_method, action_ask_status_check_grievance_id_selected, action_ask_status_check_complainant_full_name, action_ask_status_check_retrieve_grievances, action_ask_form_status_check_skip_valid_province_and_district, action_ask_form_status_check_skip_complainant_district, action_ask_form_status_check_skip_complainant_municipality_temp, action_ask_form_status_check_skip_complainant_municipality_confirmed
   - Grievance review: action_ask_form_grievance_complainant_review_grievance_classification_consent, action_ask_form_grievance_complainant_review_grievance_categories_status, action_ask_form_grievance_complainant_review_grievance_cat_modify, action_ask_form_grievance_complainant_review_grievance_summary_status, action_ask_form_grievance_complainant_review_grievance_summary_temp
   - Submit/completion: action_submit_grievance, action_status_check_request_follow_up, action_skip_status_check_outro

3. **Handle Rasa action class names and execute_action**
   - Rasa actions use `execute_action` (or `run`); ensure registry calls the correct method
   - Map action names to classes in `rasa_chatbot.actions` (check `__init__.py` for imports)

4. **events_to_slot_updates**
   - Must correctly extract SlotSet events for all slot names used across forms

### Deliverables

- Updated `orchestrator/action_registry.py` with all actions listed in 02_action_layer.md
- Verify: invoke_action for action_ask_complainant_province, action_ask_otp_consent, action_ask_status_check_method, etc. returns events and dispatcher.messages

### Remaining Work (see 02_action_layer.md)

- [ ] Verify all ask actions from form_loop _ASK_ACTIONS_BY_SLOT and _ASK_ACTIONS_BY_FORM_SLOT are registered
- [ ] Verify form_status_check_skip complainant_* delegates work in skip flow context
- [ ] Verify action_submit_grievance, action_skip_status_check_outro are registered for orchestrator

### Cross-Agent Dependencies

- **10.C**: Form loop will call invoke_action for ask actions; registry must resolve all action names in _ASK_ACTIONS_BY_SLOT and _ASK_ACTIONS_BY_FORM_SLOT
- **10.A**: Orchestrator calls invoke_action for action_start_grievance_process, action_start_status_check, action_submit_grievance, action_status_check_*

---

## Agent 10.C: Form Loop

### Mission

Extend the form loop so it supports **all forms** and uses the complete `_ASK_ACTIONS_BY_SLOT` and `_ASK_ACTIONS_BY_FORM_SLOT` mappings defined in [03_form_loop.md](03_form_loop.md).

### Spec Reference

**Primary spec**: [03_form_loop.md](03_form_loop.md)

### Context

- **Depends on**: 10.B (action registry for ask actions)
- **Files**: `orchestrator/form_loop.py`
- **Forms**: form_grievance, form_contact, form_otp, form_status_check_1, form_status_check_2, form_status_check_skip, form_grievance_complainant_review

### Tasks

1. **Implement complete _ASK_ACTIONS_BY_SLOT**
   - Add all slot → action mappings from 03_form_loop.md (grievance, contact, OTP, status check, grievance review)
   - Ensure every slot used by any form has an ask action

2. **Implement _ASK_ACTIONS_BY_FORM_SLOT for shared slots**
   - Slots that appear in multiple forms (e.g. complainant_municipality_temp in form_contact vs form_status_check_skip) must map to different ask actions
   - Lookup: check (active_loop, requested_slot) first; fall back to slot-only lookup

3. **Support all form validation classes**
   - Lazy-load or import: ValidateFormContact, ValidateFormOtp, ValidateFormStatusCheck1, ValidateFormStatusCheck2, ValidateFormStatusCheckSkip, ValidateFormGrievanceComplainantReview
   - run_form_turn must accept any of these form instances and call required_slots, extract_<slot>, validate_<slot> correctly

4. **Handle form-specific behavior**
   - form_otp: otp_consent and otp_input use different ask actions; otp_status drives re-prompt
   - form_status_check_1: required_slots is dynamic (story_route, status_check_grievance_id_selected, complainant_phone)
   - form_status_check_2: required_slots depends on status_check_retrieve_grievances
   - form_status_check_skip: uses form-specific ask actions for shared location slots

5. **Resolve ask action by (active_loop, slot) when needed**
   - When active_loop is form_status_check_skip and requested_slot is complainant_district, use action_ask_form_status_check_skip_complainant_district
   - When active_loop is form_contact and requested_slot is complainant_district, use action_ask_complainant_district

### Deliverables

- Updated `orchestrator/form_loop.py` with full _ASK_ACTIONS_BY_SLOT and _ASK_ACTIONS_BY_FORM_SLOT
- Lazy form getters or factory for all forms (ValidateFormContact, ValidateFormOtp, ValidateFormStatusCheck1, ValidateFormStatusCheck2, ValidateFormStatusCheckSkip, ValidateFormGrievanceComplainantReview)
- run_form_turn works for any of these forms

### Cross-Agent Dependencies

- **10.B**: All ask action names in _ASK_ACTIONS_BY_SLOT must be registered in action_registry
- **10.A**: Orchestrator will call run_form_turn with form instance and session; form_loop returns (messages, slot_updates, completed)

---

## Agent 10.D: Flow Logic

### Mission

Define and document the **flow logic** (transitions, payload mapping, initial session, routing) so 10.A can implement it correctly. Update [04_flow_logic.md](04_flow_logic.md) if needed, and ensure consistency with `flow.yaml` and `base_mixins` routing.

### Spec Reference

**Primary spec**: [04_flow_logic.md](04_flow_logic.md)

### Context

- **Depends on**: Understanding of Rasa flows in `rasa_chatbot/actions/base_classes/base_mixins.py` (get_next_action_for_form)
- **Files**: `orchestrator/config/flow.yaml`, `orchestrator/state_machine.py`
- **Documents**: 04_flow_logic.md is the source of truth for states, transitions, payload mapping

### Tasks

1. **Verify and document PAYLOAD_TO_INTENT**
   - Ensure all payloads used by Rasa (domain.yml, stories) are in PAYLOAD_TO_INTENT
   - Add any missing: route_status_check_phone, route_status_check_grievance_id, etc.
   - Sync with state_machine.PAYLOAD_TO_INTENT (or derive from 04_flow_logic)

2. **Verify Initial Session structure**
   - Slots needed for intro, main_menu, form_grievance
   - Ensure defaults (complainant_province, complainant_district, language_code) are set
   - Add slots for contact_form, otp_form, status_check if needed for initial session (usually filled as flow progresses)

3. **Document routing map for status_check**
   - From base_mixins: form_status_check_1 + route_status_check_phone → form_otp
   - form_status_check_1 + route_status_check_grievance_id → form_status_check_2 or form_story_step
   - form_status_check_1 + skip → form_status_check_skip
   - form_otp + route_status_check_phone → form_status_check_2
   - form_status_check_skip → action_skip_status_check_outro
   - Ensure 04_flow_logic.md and flow.yaml are aligned

4. **Condition helpers**
   - Define what form_complete, submit_complete, review_complete mean for each form/state
   - form_complete: required_slots() returns []
   - submit_complete: action_submit_grievance succeeds
   - review_complete: form_grievance_complainant_review required_slots returns []

5. **Cross-check flow.yaml**
   - flow.yaml states and transitions should match 04_flow_logic.md
   - If flow.yaml is missing transitions (e.g. contact_form → otp_form), add them or document the gap

### Deliverables

- Updated or verified [04_flow_logic.md](04_flow_logic.md) with complete Payload → Intent mapping
- Clear routing map for status_check (form_status_check_1 → form_otp | form_status_check_2 | form_status_check_skip; form_status_check_2 → action_status_check_*; etc.)
- Sync flow.yaml with 04_flow_logic where needed
- Document condition logic (form_complete, submit_complete, review_complete) for 10.A

### Cross-Agent Dependencies

- **10.A**: Orchestrator uses 04_flow_logic as the source of truth for transitions and routing
- **10.C**: Form loop uses required_slots() to determine form_complete; no direct dependency on 10.D

---

## Agent 10.E: Celery Integration and Server Scripts

### Mission

Ensure Celery is used properly in the REST orchestrator stack: resolve the import chain so the action registry can load without Celery/Redis when desired, and provide `launch_servers_celery.sh` and `stop_servers_celery.sh` that start/stop the full REST stack **including** Redis and Celery workers (for LLM grievance classification).

### Spec Reference

**Primary spec**: [02_action_layer.md](02_action_layer.md) – Celery Integration section (lines 171–205), Remaining Work (lines 257–260)

### Context

- **Depends on**: 10.A, 10.B, 10.C, 10.D (full orchestrator and action layer)
- **Import chain**: `form_grievance` imports `classify_and_summarize_grievance_task` from `backend.task_queue.registered_tasks` at module load time; that loads `celery_app` → requires Celery installed
- **Current behavior**: `form_loop` stubs `_trigger_async_classification` so Celery task is not called; but the **import** still fails if Celery is not installed
- **Base scripts**: `scripts/rest_api/launch_servers.sh` (orchestrator + backend only), `scripts/rest_api/stop_servers.sh`

### Tasks

#### 1. Celery import chain (Option A – recommended)

- Move `classify_and_summarize_grievance_task` import **inside** `_trigger_async_classification` in `rasa_chatbot/actions/forms/form_grievance.py`
- Catch `ImportError` and gracefully stub or skip the task when Celery/Redis is not available
- Result: action registry can load in REST-only envs (no Celery installed); when Celery *is* installed and workers run, classification works

#### 2. Form loop: real Celery vs stub

- When Celery is available: **do not** stub `_trigger_async_classification` in `form_loop.py`; let it call the real task
- Add an env flag (e.g. `ENABLE_CELERY_CLASSIFICATION=1`) or config so orchestrator can choose stub vs real
- Document in 02_action_layer.md

#### 3. Verify all actions

- Run form_loop for `form_contact`, `form_otp`, `form_status_check_skip`, `form_grievance_complainant_review` with valid sessions
- Confirm no `Unknown action` errors (requires Celery installed for grievance-related imports, or after Option A)
- Add a pytest or script under `tests/orchestrator/` or `orchestrator/scripts/` that invokes first ask for each form

#### 4. Form-specific delegates (form_status_check_skip)

- `form_status_check_skip` complainant_* slots map to shared contact action classes (e.g. `ActionAskComplainantDistrict`)
- Confirm utterances from `action_ask_form_status_check_skip_complainant_district` etc. are appropriate in status-check context (check `utterance_mapping_rasa` for form_status_check section)
- If utterances are wrong, add form-specific ask actions or utterance overrides

#### 5. Create `scripts/rest_api/launch_servers_celery.sh`

Based on `scripts/rest_api/launch_servers.sh`, add:

**Stack scope**: Include Postgres, both webchats (via nginx), backend, orchestrator, Redis, Celery workers. **Do NOT** include Rasa or Rasa actions (REST stack replaces them).

1. **Redis**: ensure Redis is running (start if needed, or check `scripts/database/` / project convention)
2. **Celery workers**:
   - Start Celery `default` queue worker (concurrency 2)
   - Start Celery `llm_queue` worker (concurrency 6) – used by `classify_and_summarize_grievance_task`
3. **Order**: Postgres → Redis → Orchestrator → Backend → Celery default → Celery llm_queue
4. **PIDs**: `logs/celery_default.pid`, `logs/celery_llm_queue.pid`
5. **Logs**: `logs/celery_default.log`, `logs/celery_llm_queue.log`
6. **Venv**: use `$BASE_DIR/rasa-env/bin/celery` or `$BASE_DIR/.venv/bin/celery` if present, else `celery`
7. **Summary**: print Celery worker status and URLs (orchestrator, backend, Flower if desired)

Reuse patterns from `scripts/servers/launch_servers.sh` or `scripts/local/launch_servers.sh` for `start_celery_worker`, `cleanup_celery_worker`, `wait_for_worker_ready`.

#### 6. Create `scripts/rest_api/stop_servers_celery.sh`

Based on `scripts/rest_api/stop_servers.sh`, add:

1. Stop `orchestrator_rest_api`, `backend_rest_api` (existing)
2. Stop Celery workers: read `logs/celery_default.pid`, `logs/celery_llm_queue.pid`, send TERM, wait, force kill if needed
3. Fallback: `pkill -f "celery.*worker"` if PID files missing
4. Remove PID files after stop
5. Print note: "Orchestrator, backend, and Celery workers stopped. Postgres and Redis (if used elsewhere) are not stopped."

### Deliverables

- Updated `rasa_chatbot/actions/forms/form_grievance.py` – lazy import of `classify_and_summarize_grievance_task`, graceful fallback
- Optional: env/config to enable/disable real Celery in form_loop
- `scripts/rest_api/launch_servers_celery.sh` – REST stack + Redis + Celery workers
- `scripts/rest_api/stop_servers_celery.sh` – stop orchestrator, backend, Celery workers
- Verification script or pytest: run form_loop first ask for form_contact, form_otp, form_status_check_skip, form_grievance_complainant_review
- Updated [02_action_layer.md](02_action_layer.md) Remaining Work: mark Celery integration and verification items as done when complete

### Cross-Agent Dependencies

- **10.A–10.D**: Must be complete; 10.E assumes full orchestrator, action registry, and form loop
- **Redis**: `launch_servers_celery.sh` assumes Redis is available (start manually or via project script)

### Reference

- `scripts/rest_api/launch_servers.sh` – base REST launcher
- `scripts/rest_api/stop_servers.sh` – base stop script
- `scripts/servers/launch_servers.sh` – Celery worker startup pattern (`start_celery_worker`, `cleanup_celery_worker`)
- `scripts/local/stop_servers.sh` – Celery stop pattern
- `backend.task_queue.registered_tasks` – `classify_and_summarize_grievance_task`
- `rasa_chatbot/actions/forms/form_grievance.py` – `_trigger_async_classification`

---

## Execution Checklist

| Step | Agent | Prerequisite | Output |
|------|-------|--------------|--------|
| 1 | 10.D | — | flow.yaml synced, 04_flow_logic.md complete, routing map documented |
| 2 | 10.B | — | action_registry with all actions, adapters support all slots |
| 3 | 10.C | 10.B | form_loop with _ASK_ACTIONS_BY_SLOT, _ASK_ACTIONS_BY_FORM_SLOT, support all forms |
| 4 | 10.A | 10.B, 10.C, 10.D | state_machine with all states, transitions, routing; full flow works |
| 5 | 10.E | 10.A–10.D | Celery integration, launch_servers_celery.sh, stop_servers_celery.sh, action verification |

---

## Shared Reference

- [00_overview_and_questions.md](00_overview_and_questions.md) – forms/flows inventory, scope
- [02_action_layer.md](02_action_layer.md) – Celery Integration, Remaining Work (lines 171–205, 257–260)
- [06_test_spec.md](06_test_spec.md) – test patterns; extend for new flows
- `rasa_chatbot/actions/` – existing Rasa actions
- `rasa_chatbot/actions/base_classes/base_mixins.py` – get_next_action_for_form routing
