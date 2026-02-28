# Scoped Refactor: Overview and Decisions

## Scope

Build the **Orchestrator + Action Layer** to cover all forms and flows, replacing Rasa's form handling:

1. **New grievance flow** (primary path):
   ```
   intro + main_menu → form_grievance → contact_form → otp_form → submit_grievance → grievance_review → done
   ```

2. **Status check flow** (parallel path):
   ```
   main_menu → status_check_form (form_status_check_1 → form_status_check_2 or form_otp or form_status_check_skip) → done
   ```

**Success criterion**: Same behavior as Rasa for each flow, validated via curl or test harness.  
**Status**: ✅ All flows implemented by Agents 10.A–10.D (orchestrator, action layer, form loop, flow logic).

---

## Achievements (Agents 10.A–10.D)

### 10.A – Orchestrator
- **State machine** wires all states: intro → main_menu → form_grievance → contact_form → otp_form → submit_grievance → grievance_review → done
- **Status check** routes: form_status_check_1 → form_otp | form_status_check_2 | form_status_check_skip; form_status_check_2 → action_status_check_request_follow_up; form_status_check_skip → action_skip_status_check_outro
- **Form instances**: ValidateFormGrievance, ValidateFormContact, ValidateFormOtp, ValidateFormStatusCheck1/2, ValidateFormSkipStatusCheck, ValidateFormGrievanceComplainantReview
- **Payload mapping**: set_english, set_nepali, new_grievance, start_status_check, route_status_check_phone, route_status_check_grievance_id, submit_details, add_more_details, restart, skip, affirm, deny

### 10.B – Action Layer
- **Action registry** for all forms: action_introduce, action_main_menu, action_start_grievance_process, action_start_status_check, action_submit_grievance; contact ask actions (action_ask_complainant_*); OTP (action_ask_otp_consent, action_ask_otp_input); status check (action_ask_status_check_method, action_ask_status_check_grievance_id_selected, etc.); grievance review (action_ask_form_grievance_complainant_review_*); action_status_check_request_follow_up, action_skip_status_check_outro
- **events_to_slot_updates** for SlotSet events
- Adapters (CollectingDispatcher, SessionTracker) unchanged; support all slots

### 10.C – Form Loop
- **_ASK_ACTIONS_BY_SLOT** for grievance, contact, OTP, status check, grievance review (50+ slot→action mappings)
- **_ASK_ACTIONS_BY_FORM_SLOT** for shared slots (form_status_check_skip complainant_*, form_status_check_1 complainant_phone)
- **get_form(active_loop)** lazy-loads all 7 forms
- **run_form_turn** supports any form; uses _get_ask_action(active_loop, slot) for form-specific overrides

### 10.D – Flow Logic
- **PAYLOAD_TO_INTENT** in state_machine.py; **Routing map** for status_check_form (form_status_check_1/otp/2/skip chaining)
- **Initial session** with default slots; transitions aligned with flow.yaml

---

## Overall Progress

| Component | Spec | Status |
|-----------|------|--------|
| Orchestrator | [01_orchestrator.md](01_orchestrator.md) | ✅ Done |
| Action Layer | [02_action_layer.md](02_action_layer.md) | ✅ Done |
| Form Loop | [03_form_loop.md](03_form_loop.md) | ✅ Done |
| Flow Logic | [04_flow_logic.md](04_flow_logic.md) | ✅ Done |
| Agent Specs | [05_agent_specs.md](05_agent_specs.md) | ✅ Done |
| Test Spec | [06_test_spec.md](06_test_spec.md) | ✅ Done |

---

## Components

| Component | Spec | Purpose |
|-----------|------|---------|
| Orchestrator | [01_orchestrator.md](01_orchestrator.md) | FastAPI app, POST /message, session store, state machine |
| Action Layer | [02_action_layer.md](02_action_layer.md) | CollectingDispatcher, SessionTracker, action registry |
| Form Loop | [03_form_loop.md](03_form_loop.md) | Orchestrator drives extract → validate → ask |
| Flow Logic | [04_flow_logic.md](04_flow_logic.md) | States, transitions, actions for all forms and flows |
| Webchat Integration | [07_webchat_integration.md](07_webchat_integration.md) | Plan to connect existing webchat to orchestrator |
| Agent Instructions 10 | [10_agent_instructions.md](10_agent_instructions.md) | Instructions for agents 10.A–10.D (orchestrator, action layer, form loop, flow logic) |

---

## Decisions (Answered)

### 1. Sensitive content detection
**Decision**: Exclude for spike. Treat sensitive content as normal text; validate adapter pattern first.

### 2. Celery classification
**Decision**: Stub for spike. No Celery call; orchestrator transitions to "done" directly.

### 3. Database
**Decision**: Use real DB as built. Essential for a meaningful proof-of-concept.

### 4. Domain / config source
**Decision**: Use our own YAML structure from the start. Extract all data from Rasa YAMLs into our format.

- Define orchestrator YAML schema (`flow.yaml`, slots) as the source of truth.
- Add an extraction step/script that reads `domain.yml` (and stories/rules if needed) and produces our YAML.
- Orchestrator loads only from our YAML. No dependency on Rasa format at runtime.
- When Rasa is removed, we keep the same structure – no rework.

**Flow**:
```
Rasa YAMLs (domain.yml, stories, rules)
        ↓
  [extraction script]
        ↓
Orchestrator YAMLs (flow.yaml, slots, etc.)
        ↓
  Orchestrator loads at startup
```

### 5. Language
**Decision**: Use `get_utterance` from the beginning – support both en and ne from the start.

### 6. Package location
**Decision**: `orchestrator/` at repo root – clear separation from Rasa and backend.

### 7. Intro / main menu
**Decision**: Include. Easier to design without Rasa form constraints.

---

---

## Forms and Flows Inventory

### Forms (from flow.yaml and Rasa)

| Form | Validation Action | Required Slots (or dynamic) | Ask Actions | Flow(s) |
|------|-------------------|-----------------------------|-------------|---------|
| `form_grievance` | validate_form_grievance | grievance_new_detail | action_ask_grievance_new_detail | New grievance |
| `form_contact` | validate_form_contact | complainant_location_consent, complainant_province, complainant_district, complainant_municipality_*, complainant_village_*, complainant_ward, complainant_address_*, complainant_consent, complainant_full_name, complainant_email_* | action_ask_complainant_* | New grievance |
| `form_otp` | validate_form_otp | complainant_phone, otp_consent, otp_input, otp_status | action_ask_otp_consent, action_ask_otp_input | New grievance, Status check (phone route) |
| `form_grievance_complainant_review` | validate_form_grievance_complainant_review | grievance_classification_consent, grievance_categories_status, grievance_cat_modify, grievance_summary_* | action_ask_form_grievance_complainant_review_* | New grievance (post-submit) |
| `form_status_check_1` | validate_form_status_check_1 | story_route, status_check_grievance_id_selected or complainant_phone | action_ask_status_check_method, action_ask_status_check_grievance_id_selected, etc. | Status check |
| `form_status_check_2` | validate_form_status_check_2 | status_check_retrieve_grievances, status_check_complainant_full_name, status_check_grievance_id_selected | action_ask_status_check_retrieve_grievances, action_ask_status_check_complainant_full_name | Status check |
| `form_status_check_skip` | validate_form_status_check_skip | valid_province_and_district, complainant_district, complainant_municipality_* | action_ask_form_status_check_skip_* | Status check (when user skips OTP or grievance ID) |
| `form_status_check_modify` | validate_form_status_check_modify | (modify flows) | action_ask_modify_* | Status check (modify) |

### Flow Paths

| Flow | Entry | Forms / States | Exit |
|------|-------|----------------|------|
| **New grievance** | main_menu + /new_grievance | form_grievance → contact_form → otp_form → submit_grievance → grievance_review | done |
| **Status check (phone)** | main_menu + /start_status_check | form_status_check_1 (story_route=phone) → form_otp → form_status_check_2 → form_story_step / action_status_check_* | done |
| **Status check (grievance ID)** | main_menu + /start_status_check | form_status_check_1 (story_route=id) → form_status_check_2 (or form_story_step) → action_status_check_* | done |
| **Status check (skip)** | Within status check | form_status_check_skip → action_skip_status_check_outro | done |

---

## Out of Scope (This Spike)

- form_sensitive_issues, sensitive content branching
- form_contact_modify, form_location_modify, form_grievance_modify (modify flows)
- form_story_main, form_story_route, form_story_step (Rasa legacy)
- Celery classification trigger (stub)
- Message deduplication (message_id)
- Persistent session store (Postgres/Redis)
