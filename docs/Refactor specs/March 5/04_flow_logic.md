# Spec 4: Flow Logic

## Purpose

Define the exact states, transitions, and action invocations for the grievance details flow.

---

## Flow Diagram

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
    | SlotSet: grievance_id, complainant_id, story_main, grievance_sensitive_issue
    v
[form_grievance]
    |
    | requested_slot = grievance_new_detail
    | Run action_ask_grievance_new_detail (first prompt)
    v
<-- user input (text or payload)
    |
    | extract_grievance_new_detail -> validate_grievance_new_detail
    | Apply slot updates
    |
    +-- grievance_new_detail != "completed" -> re-ask (action_ask_grievance_new_detail)
    |       -> stay in form_grievance
    |
    +-- grievance_new_detail == "completed" -> [done]
```

---

## States

| State | active_loop | requested_slot | Description |
|-------|-------------|----------------|-------------|
| intro | null | null | Language selection |
| main_menu | null | null | Menu (File grievance, Check status, Exit) |
| form_grievance | form_grievance | grievance_new_detail | Collecting grievance details |
| done | null | null | Form complete |

---

## Transitions

### intro
- **Trigger**: Session created (new user)
- **Action**: Run `action_introduce`
- **Next**: Wait for language selection; on `/set_english` or `/set_nepali` → main_menu

### main_menu
- **Trigger**: language_code set
- **Action**: Run `action_main_menu`
- **Next**: Wait for choice; on `/new_grievance` → run `action_start_grievance_process` → form_grievance

### start_grievance → form_grievance
- **Trigger**: User selected /new_grievance
- **Action**: Run `action_start_grievance_process`
- **Input**: Tracker with default slots (complainant_province, complainant_district from defaults; language_code from session)
- **Output**: SlotSet events; dispatcher has json_message for grievance_id_set
- **Next**: Run `action_ask_grievance_new_detail` for first prompt

### form_grievance (loop)
- **Trigger**: User sends message (text or payload)
- **Actions**: extract_grievance_new_detail, validate_grievance_new_detail
- **Branch**:
  - `grievance_new_detail == "completed"` → done
  - Else → Run `action_ask_grievance_new_detail`, stay in form_grievance

### done
- **Trigger**: required_slots returns []
- **Action**: None (flow ends)
- **Response**: Optional "Grievance details saved" or similar

---

## Initial Session (intro)

```python
{
  "state": "intro",
  "active_loop": None,
  "requested_slot": None,
  "slots": {
    "language_code": None,  # Set by set_english/set_nepali
    "complainant_province": "<DEFAULT_PROVINCE>",
    "complainant_district": "<DEFAULT_DISTRICT>",
    "story_main": None,
    "grievance_id": None,
    "complainant_id": None,
    "grievance_sensitive_issue": False,
    "grievance_description": None,
    "grievance_new_detail": None,
    "grievance_description_status": None,
    "requested_slot": None,
    "skip_validation_needed": None,
    "skipped_detected_text": None
  }
}
```

---

## Payload → Intent Mapping

| User sends | Intent for latest_message |
|------------|---------------------------|
| `/set_english` | set_english |
| `/set_nepali` | set_nepali |
| `/new_grievance` | new_grievance |
| `/submit_details` | submit_details |
| `/add_more_details` | add_more_details |
| `/restart` | restart |
| `/skip` | skip |
| `/affirm_skip` | affirm |
| `/deny_skip` | deny |
| Free text | intent_slot_neutral or "" |

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
- [x] main_menu: action_main_menu; new_grievance → action_start_grievance_process → form_grievance
- [x] form_grievance: form loop; grievance_new_detail=="completed" → done
- [x] Payload → intent mapping (all payloads from table)
- [x] Initial session: state=intro, language_code=None, defaults for province/district
