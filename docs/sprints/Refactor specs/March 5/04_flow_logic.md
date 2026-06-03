# Spec 4: Flow Logic

## Purpose

Define the exact states, transitions, and action invocations for all forms and flows.

---

## Flow Diagram: New Grievance (Full Path)

```
[intro]
    | action_introduce (language selection)
    v
<-- user selects language (set_english / set_nepali)
    |
    v
[main_menu]
    | action_main_menu (File grievance | Check status | Exit)
    v
<-- user selects /new_grievance
    |
    v
action_start_grievance_process
    | SlotSet: grievance_id, complainant_id, story_main="new_grievance", grievance_sensitive_issue
    v
[form_grievance]
    | requested_slot = grievance_new_detail
    | Run action_ask_grievance_new_detail
    v
<-- user input (text or payload) -> extract -> validate
    |
    +-- grievance_new_detail != "completed" -> re-ask, stay in form_grievance
    +-- grievance_new_detail == "completed" (form_complete) -> [contact_form]
    |
    v
[contact_form]
    | Slots: complainant_location_consent, complainant_province, complainant_district, municipality, village, ward, address, complainant_consent, complainant_full_name, complainant_email_*
    v
<-- user input -> extract -> validate (validate_form_contact)
    |
    +-- form_complete -> [otp_form]
    v
[otp_form]
    | Slots: complainant_phone, otp_consent, otp_input, otp_status
    v
<-- user input -> extract -> validate (validate_form_otp)
    |
    +-- form_complete -> [submit_grievance]
    v
action_submit_grievance
    | Persist complainant, finalize grievance
    v
[grievance_review]
    | Form: form_grievance_complainant_review (classification consent, categories, summary)
    v
<-- user input -> extract -> validate
    |
    +-- review_complete -> [done]
```

---

## Flow Diagram: Grievance Details Only (Current Implementation)

```
[intro] -> [main_menu] -> [form_grievance] -> [done]
```

(Contact, OTP, submit, and grievance_review are not yet wired in state_machine.)

---

---

## Flow Diagram: Status Check (Phone Route)

```
[main_menu]
    v
<-- user selects /start_status_check
    |
    v
action_start_status_check
    | SlotSet: story_main="status_check"
    v
[status_check_form] (form_status_check_1)
    | requested_slot = story_route
    v
<-- user selects route_status_check_phone
    |
    | requested_slot = complainant_phone
    v
<-- user enters phone -> validate -> retrieve grievances
    |
    +-- form_complete -> [otp_form] (status check context)
    v
[otp_form]
    | complainant_phone already set; otp_consent, otp_input, otp_status
    v
<-- user input -> validate_form_otp
    |
    +-- form_complete -> [form_status_check_2]
    v
[form_status_check_2]
    | status_check_retrieve_grievances, status_check_complainant_full_name, status_check_grievance_id_selected
    v
<-- user input -> validate_form_status_check_2
    |
    +-- form_complete -> form_story_step -> action_status_check_request_follow_up | action_skip_status_check_outro
    v
[done]
```

---

## Flow Diagram: Status Check (Grievance ID Route)

```
[status_check_form] (form_status_check_1)
    | requested_slot = story_route
    v
<-- user selects route_status_check_grievance_id
    |
    | requested_slot = status_check_grievance_id_selected
    v
<-- user enters grievance ID -> validate
    |
    +-- form_complete -> [form_status_check_2]  (orchestrator)
    |   (Rasa: form_status_check_1 → form_story_step, then form_status_check_2 depending on flow)
    v
[form_status_check_2] — grievance ID already set; form validates quickly
    |
    +-- form_complete -> action_status_check_request_follow_up -> [done]
```

---

## Flow Diagram: Status Check (Skip Path)

```
Within status_check_form: user selects /skip
    |
    v
form_status_check_skip
    | valid_province_and_district, complainant_district, complainant_municipality_*
    v
<-- user input -> validate_form_status_check_skip
    |
    +-- form_complete -> action_skip_status_check_outro
    v
[done]
```

---

## States

| State | active_loop | requested_slot | Description |
|-------|-------------|----------------|-------------|
| intro | null | null | Language selection |
| main_menu | null | null | Menu (File grievance, Check status, Exit) |
| form_grievance | form_grievance | grievance_new_detail | Collecting grievance details |
| contact_form | form_contact | complainant_* | Collecting contact and location |
| otp_form | form_otp | complainant_phone, otp_* | Collecting phone and OTP verification |
| submit_grievance | null | null | Running action_submit_grievance |
| grievance_review | form_grievance_complainant_review | grievance_* | Post-submission classification review |
| status_check_form | form_status_check_1/2/otp/skip | varies | Status check via ID or phone |
| done | null | null | Flow complete |

---

## Transitions

### intro
- **Trigger**: Session created (new user)
- **Action**: Run `action_introduce`
- **Next**: On `/set_english` or `/set_nepali` → main_menu

### main_menu
- **Trigger**: language_code set
- **Action**: Run `action_main_menu`
- **Next**: On `/new_grievance` → run `action_start_grievance_process` → form_grievance; on `/start_status_check` → run `action_start_status_check` → status_check_form

### form_grievance (loop)
- **Trigger**: User sends message (text or payload)
- **Actions**: extract_grievance_new_detail, validate_grievance_new_detail
- **Branch**: `grievance_new_detail == "completed"` → contact_form; else → re-ask, stay in form_grievance

### contact_form (loop)
- **Trigger**: User sends message
- **Actions**: extract_*/validate_* for complainant_* slots (validate_form_contact)
- **Branch**: form_complete → otp_form; else → re-ask, stay in contact_form

### otp_form (loop)
- **Trigger**: User sends message
- **Actions**: extract_*/validate_* for complainant_phone, otp_consent, otp_input, otp_status (validate_form_otp)
- **Branch** (grievance flow): form_complete → submit_grievance
- **Branch** (status check): form_complete → form_status_check_2

### submit_grievance
- **Trigger**: otp_form complete (grievance flow)
- **Action**: Run `action_submit_grievance`
- **Next**: submit_complete → grievance_review

### grievance_review (loop)
- **Trigger**: User sends message
- **Actions**: extract_*/validate_* for form_grievance_complainant_review slots
- **Branch**: review_complete → done

### status_check_form (loop)
- **Trigger**: User sends message
- **Forms**: form_status_check_1, form_status_check_2, form_otp, form_status_check_skip (depending on story_route and story_step)
- **Branch**: form_complete or skip → done or next form (action_status_check_request_follow_up, action_skip_status_check_outro)

### done
- **Trigger**: Flow complete
- **Action**: None (flow ends)

---

## Initial Session (intro)

```python
{
  "state": "intro",
  "active_loop": None,
  "requested_slot": None,
  "slots": {
    # Intro / main_menu
    "language_code": None,  # Set by set_english/set_nepali
    "complainant_province": "<DEFAULT_PROVINCE>",   # Required for form_status_check_skip
    "complainant_district": "<DEFAULT_DISTRICT>",   # Required for form_status_check_skip
    # Grievance flow
    "story_main": None,
    "grievance_id": None,
    "complainant_id": None,
    "grievance_sensitive_issue": False,
    "grievance_description": None,
    "grievance_new_detail": None,
    "grievance_description_status": None,
    # Status check flow (filled as flow progresses)
    "story_route": None,       # route_status_check_phone | route_status_check_grievance_id | SKIP_VALUE
    "story_step": None,
    # Form loop
    "requested_slot": None,
    "skip_validation_needed": None,
    "skipped_detected_text": None
  }
}
```

**Slots filled during flow**: `story_route`, `story_step`, `complainant_phone`, `otp_*`, `status_check_*`, `contact_form` slots — none needed for initial session. `contact_form` and `otp_form` slots are filled when those forms run.

---

## Payload → Intent Mapping

**Source of truth**: `orchestrator/state_machine.PAYLOAD_TO_INTENT` — keep in sync.

| User sends (payload or text starting with /) | Intent for latest_message |
|---------------------------------------------|---------------------------|
| `/set_english` | set_english |
| `/set_nepali` | set_nepali |
| `/new_grievance` | new_grievance |
| `/start_status_check`, `/check_status` | start_status_check |
| `/route_status_check_phone` | route_status_check_phone |
| `/route_status_check_grievance_id` | route_status_check_grievance_id |
| `/submit_details` | submit_details |
| `/add_more_details` | add_more_details |
| `/restart` | restart |
| `/skip` | skip |
| `/affirm_skip` | affirm |
| `/deny_skip` | deny |
| Other payloads, free text | intent_slot_neutral |

**Note**: Payloads used by Rasa (domain.yml, NLU) that affect routing must be in this table. `route_status_check_phone` and `route_status_check_grievance_id` set the `story_route` slot via `validate_story_route`. The `/skip` payload maps to intent `skip`; when user skips within status check, `story_route` is set to SKIP_VALUE (e.g. `slot_skipped`) by the validation form.

---

## Condition Helpers (for 10.A)

| Condition | Meaning | Implementation |
|-----------|---------|----------------|
| **form_complete** | Form has no remaining required slots | `await form.required_slots(domain_slots, dispatcher, tracker, domain)` returns `[]` |
| **submit_complete** | Grievance submitted successfully | `action_submit_grievance` runs without error; slots persisted |
| **review_complete** | Post-submission review done | `form_grievance_complainant_review.required_slots()` returns `[]` |

**Per form**:
- **form_grievance**: form_complete when `grievance_new_detail` is filled/validated
- **form_contact**: form_complete when complainant_* slots (location, name, email) are filled
- **form_otp**: form_complete when complainant_phone, otp_consent, otp_input, otp_status are filled
- **form_status_check_1**: form_complete when story_route + (status_check_grievance_id_selected or complainant_phone) are filled
- **form_status_check_2**: form_complete when status_check_grievance_id_selected is set
- **form_status_check_skip**: form_complete when valid_province_and_district, complainant_district, complainant_municipality_* are filled
- **form_grievance_complainant_review**: review_complete when grievance_classification_consent, grievance_categories_status, grievance_cat_modify, grievance_summary_status, grievance_summary_temp are filled

---

## Stubbed Behavior

- `_trigger_async_classification`: No-op; return `{}` (no slot updates from classification).
- Sensitive content: Excluded; treat as normal text (no `grievance_sensitive_issue` branching).

---

## Deliverables

- Logic implemented in orchestrator's request handler (or `state_machine.py`)
- Clear mapping from state + user input → action(s) → next state

---

## Checklist

- [x] intro: action_introduce; set_english/set_nepali → main_menu
- [x] main_menu: action_main_menu; new_grievance → action_start_grievance_process → form_grievance; start_status_check → status_check_form
- [x] form_grievance: form loop; grievance_new_detail=="completed" → contact_form
- [x] contact_form: form loop; form_complete → otp_form (wired in state_machine)
- [x] otp_form: form loop; form_complete → submit_grievance (grievance) or form_status_check_2 (status check) (wired in state_machine)
- [x] submit_grievance, grievance_review (wired in state_machine)
- [x] status_check_form: form loop for form_status_check_1, form_otp, form_status_check_2, form_status_check_skip; routing by story_route
- [x] Payload → intent mapping (all payloads from table; sync with state_machine.PAYLOAD_TO_INTENT)
- [x] Initial session: state=intro, language_code=None, defaults for province/district

---

## Routing Map (status_check)

Orchestrator `state_machine.py` and Rasa `base_mixins.get_next_action_for_form` use equivalent routing. The orchestrator maps `story_route` from slots; SKIP_VALUE (e.g. `slot_skipped`) is set when user chooses skip.

### New grievance
| From | To |
|------|-----|
| form_grievance | form_contact |
| form_contact | form_otp |
| form_otp | submit_grievance |

### Status check (by active_loop + story_route)

| active_loop | story_route | Next |
|-------------|-------------|------|
| form_status_check_1 | route_status_check_phone | form_otp |
| form_status_check_1 | route_status_check_grievance_id | form_status_check_2 |
| form_status_check_1 | SKIP_VALUE (skip) | form_status_check_skip |
| form_otp | (any) | form_status_check_2 |
| form_status_check_2 | — | action_status_check_request_follow_up → done |
| form_status_check_skip | — | action_skip_status_check_outro → done |

### Orchestrator vs Rasa
- **Orchestrator** (state_machine): form_status_check_1 + route_status_check_grievance_id → form_status_check_2 → action_status_check_request_follow_up. No form_story_step.
- **Rasa** (base_mixins): form_status_check_1 + route_status_check_grievance_id → form_story_step (collects story_step); form_status_check_2 → form_story_step; form_story_step + story_step → action_status_check_request_follow_up | form_status_check_modify. The orchestrator skips form_story_step and always runs action_status_check_request_follow_up.

The orchestrator must use `active_loop` and `story_route` (from slots) to select the next form/action after form_complete.

---

## flow.yaml Alignment

The `orchestrator/config/flow.yaml` defines states and linear transitions. It does **not** model conditional branching inside `status_check_form` or `otp_form` (grievance vs status_check). That logic lives in `state_machine.run_flow_turn`.

| flow.yaml | 04_flow_logic | Notes |
|-----------|---------------|-------|
| otp_form → submit_grievance (form_complete) | otp_form → submit_grievance (grievance flow) | flow.yaml assumes grievance; state_machine branches on story_main |
| (no status_check internal transitions) | status_check_form: form_status_check_1 → form_otp/form_status_check_2/form_status_check_skip | flow.yaml treats status_check_form as single state; internal routing in state_machine |
| contact_form → otp_form | ✓ | Aligned |
| form_grievance → contact_form | ✓ | Aligned |

**Action**: flow.yaml is correct as a linear view; 10.A uses state_machine.py for branching. No flow.yaml changes needed for status_check.
