# Spec 3: Form Loop

## Purpose

Reproduce Rasa's form-filling behavior: the orchestrator drives `required_slots` → `extract_*` → `validate_*` → apply updates → ask for next slot or complete.

## Implementation (orchestrator/form_loop.py)

| Component | Description |
|-----------|-------------|
| `run_form_turn(form, session, user_input, domain)` | Returns `(messages, slot_updates, completed)` |
| `_get_ask_action(active_loop, slot)` | Lookup: _ASK_ACTIONS_BY_FORM_SLOT first, else _ASK_ACTIONS_BY_SLOT |
| `get_form(active_loop)` | Lazy form factory for all 7 forms |
| `_first_empty(required, slots)` | First empty slot in required list |

---

## Form: form_grievance (ValidateFormGrievance)

**Required slots** (from `required_slots()`):
- If `grievance_sensitive_issue`: `["sensitive_issues_follow_up", "grievance_new_detail"]` – **excluded in spike**
- If `grievance_new_detail == "completed"`: `[]` (form complete)
- Else: `["grievance_new_detail"]`

**For spike**: Only `["grievance_new_detail"]` or `[]`.

---

## Per-Turn Flow

1. **Get required slots**:
   ```python
   form = ValidateFormGrievance()
   required = await form.required_slots(domain_slots, dispatcher, tracker, domain)
   ```

2. **Find next empty slot**:
   ```python
   next_slot = first_empty_slot(required, session_slots)
   if next_slot is None:
       # Form complete -> transition to done
       return complete
   ```

3. **If we have user input** (this turn):
   - Set `tracker._latest_message = {"text": text, "intent": {"name": derived_intent}}`
   - Set `tracker._requested_slot = next_slot` (and `requested_slot` in slots)
   - Call `extract_<slot_name>(dispatcher, tracker, domain)`:
     ```python
     raw = await form.extract_grievance_new_detail(dispatcher, tracker, domain)
     slot_value = raw.get("grievance_new_detail") if raw else None
     ```
   - If `slot_value` is not None: call `validate_<slot_name>(slot_value, dispatcher, tracker, domain)`:
     ```python
     slot_updates = await form.validate_grievance_new_detail(slot_value, dispatcher, tracker, domain)
     ```
   - Apply `slot_updates` to session.
   - `dispatcher.messages` now contains any error/confirmation messages.

4. **If no user input** (e.g. first ask) **or after validation we need to re-ask**:
   - Run `action_ask_grievance_new_detail` to send the prompt.
   - Set `expected_input_type` for next turn.

5. **Determine next requested_slot**:
   - Re-call `required_slots` with updated tracker.
   - Next empty slot becomes `requested_slot` for next turn.

---

## Slot Extraction Details

`extract_grievance_new_detail` uses `_handle_slot_extraction` which:
- Reads `tracker.latest_message["text"]` and `["intent"]["name"]`
- Handles skip, payloads (`/submit_details` → `submit_details`), free text
- May set `skip_validation_needed`, `skipped_detected_text` for confirmation
- Returns `Dict[slot_name, value]` or `{}`

**Intent derivation** (orchestrator):
- If `payload` starts with `/`: strip `/` and use as intent (e.g. `/submit_details` → `submit_details`)
- Else: `intent_slot_neutral` or empty

---

## Validation Details

`validate_grievance_new_detail` handles:
- `restart` → clear grievance, set `grievance_description_status: "restart"`
- `add_more_details` → set `grievance_new_detail: None`, `grievance_description_status: "add_more_details"`
- `submit_details` → set `grievance_new_detail: "completed"`, persist grievance, **stub** `_trigger_async_classification`
- Free text → update `grievance_description`, check sensitive content (**excluded in spike**), set `grievance_description_status: "show_options"`
- Returns `Dict[slot_name, value]`

---

## Form Completion

When `required_slots` returns `[]`:
- Set `active_loop = None`, `state = "done"`.
- No further form loop turns.

---

## Ask Action

After validation (or when first entering form), run `action_ask_grievance_new_detail`:
- Uses `grievance_description_status` to pick utterance (initial, restart, add_more_details, show_options + buttons).
- Dispatcher collects messages; orchestrator returns them in response.

---

## Deliverables

- `orchestrator/form_loop.py` – `run_form_turn(form, session, user_input, domain) -> (messages, slot_updates, completed)`
- `get_form(active_loop)` – lazy form factory for all forms

---

## Implementation Status (done)

- [x] required_slots called with dispatcher, tracker, domain
- [x] extract_<slot> / validate_<slot> called generically via `hasattr` + `getattr` (or grievance-specific fallback)
- [x] slot_updates applied to session
- [x] Ask action resolved via `_get_ask_action(active_loop, slot)` – checks _ASK_ACTIONS_BY_FORM_SLOT first, then _ASK_ACTIONS_BY_SLOT
- [x] completed=True when required_slots returns []
- [x] requested_slot, skip_validation_needed handled
- [x] After validation: `next_slot_to_ask = _first_empty(required_after, slots)` (may differ from next_slot)
- [x] `get_form(active_loop)` – lazy-loads ValidateFormGrievance, ValidateFormContact, ValidateFormOtp, ValidateFormStatusCheck1, ValidateFormStatusCheck2, ValidateFormSkipStatusCheck, ValidateFormGrievanceComplainantReview

---

---

## Form: form_contact (ValidateFormContact)

**Required slots** (from `required_slots()`):
- Location: complainant_location_consent, complainant_province, complainant_district, complainant_municipality_temp, complainant_municipality_confirmed, complainant_village_temp, complainant_village_confirmed, complainant_ward, complainant_address_temp, complainant_address_confirmed, complainant_address
- Contact: complainant_consent, complainant_full_name, complainant_email_temp, complainant_email_confirmed

**Ask actions** (slot → action):
- complainant_location_consent → action_ask_complainant_location_consent
- complainant_province → action_ask_complainant_province
- complainant_district → action_ask_complainant_district
- complainant_municipality_temp → action_ask_complainant_municipality_temp, complainant_municipality_confirmed → action_ask_complainant_municipality_confirmed
- complainant_village_temp → action_ask_complainant_village_temp, complainant_village_confirmed → action_ask_complainant_village_confirmed
- complainant_ward → action_ask_complainant_ward
- complainant_address_temp → action_ask_complainant_address_temp, complainant_address_confirmed → action_ask_complainant_address_confirmed
- complainant_consent → action_ask_complainant_consent
- complainant_full_name → action_ask_complainant_full_name
- complainant_email_temp → action_ask_complainant_email_temp, complainant_email_confirmed → action_ask_complainant_email_confirmed

---

## Form: form_otp (ValidateFormOtp)

**Required slots** (from `required_slots()`):
- complainant_phone, otp_consent, otp_input, otp_status

**Ask actions**:
- complainant_phone → action_ask_complainant_phone (or form_otp first-ask flow)
- otp_consent → action_ask_otp_consent
- otp_input → action_ask_otp_input

**Special behavior**: OTP generation and SMS sending occur in `action_ask_otp_input`. Slot `otp_status` drives re-prompt (invalid_format, invalid_otp, resend, etc.).

---

## Form: form_status_check_1 (ValidateFormStatusCheck1)

**Required slots** (dynamic, from `required_slots()`):
- If story_route=SKIP or list_grievance_id=SKIP or status_check_grievance_id_selected=SKIP → []
- If story_route=route_status_check_grievance_id → [story_route, status_check_grievance_id_selected]
- If story_route=route_status_check_phone → [story_route, complainant_phone]
- Else → [story_route]

**Ask actions**:
- story_route → action_ask_status_check_method
- status_check_grievance_id_selected → action_ask_status_check_grievance_id_selected
- complainant_phone → action_ask_form_status_check_1_complainant_phone (or action_ask_complainant_phone)

---

## Form: form_status_check_2 (ValidateFormStatusCheck2)

**Required slots** (dynamic):
- If route=phone and not status_check_retrieve_grievances → [status_check_retrieve_grievances]
- Else: [status_check_complainant_full_name, status_check_grievance_id_selected] or [status_check_grievance_id_selected]

**Ask actions**:
- status_check_retrieve_grievances → action_ask_status_check_retrieve_grievances
- status_check_complainant_full_name → action_ask_status_check_complainant_full_name

---

## Form: form_status_check_skip (ValidateFormSkipStatusCheck)

*Note: Actual class is `ValidateFormSkipStatusCheck` in `form_status_check_skip.py`.*

**Required slots** (dynamic):
- If valid_province_and_district=SKIP → []
- If valid_province_and_district=False → [valid_province_and_district, complainant_district, complainant_municipality_temp, complainant_municipality_confirmed]
- Else → [valid_province_and_district, complainant_municipality_temp, complainant_municipality_confirmed]

**Ask actions**:
- valid_province_and_district → action_ask_form_status_check_skip_valid_province_and_district
- complainant_district → action_ask_form_status_check_skip_complainant_district
- complainant_municipality_temp → action_ask_form_status_check_skip_complainant_municipality_temp
- complainant_municipality_confirmed → action_ask_form_status_check_skip_complainant_municipality_confirmed

---

## Form: form_grievance_complainant_review (ValidateFormGrievanceComplainantReview)

**Required slots** (from flow.yaml): grievance_classification_consent, grievance_categories_status, grievance_cat_modify, grievance_summary_status, grievance_summary_temp

**Ask actions**:
- grievance_classification_consent → action_ask_form_grievance_complainant_review_grievance_classification_consent
- grievance_categories_status → action_ask_form_grievance_complainant_review_grievance_categories_status
- grievance_cat_modify → action_ask_form_grievance_complainant_review_grievance_cat_modify
- grievance_summary_status → action_ask_form_grievance_complainant_review_grievance_summary_status
- grievance_summary_temp → action_ask_form_grievance_complainant_review_grievance_summary_temp

---

## _ASK_ACTIONS_BY_SLOT (complete mapping)

The form loop uses `_ASK_ACTIONS_BY_SLOT` to map each requested_slot to the correct ask action. Full mapping:

```python
_ASK_ACTIONS_BY_SLOT = {
    # Grievance flow
    "grievance_new_detail": "action_ask_grievance_new_detail",
    # Contact form
    "complainant_location_consent": "action_ask_complainant_location_consent",
    "complainant_province": "action_ask_complainant_province",
    "complainant_district": "action_ask_complainant_district",
    "complainant_municipality_temp": "action_ask_complainant_municipality_temp",
    "complainant_municipality_confirmed": "action_ask_complainant_municipality_confirmed",
    "complainant_village_temp": "action_ask_complainant_village_temp",
    "complainant_village_confirmed": "action_ask_complainant_village_confirmed",
    "complainant_ward": "action_ask_complainant_ward",
    "complainant_address_temp": "action_ask_complainant_address_temp",
    "complainant_address_confirmed": "action_ask_complainant_address_confirmed",
    "complainant_consent": "action_ask_complainant_consent",
    "complainant_full_name": "action_ask_complainant_full_name",
    "complainant_email_temp": "action_ask_complainant_email_temp",
    "complainant_email_confirmed": "action_ask_complainant_email_confirmed",
    # OTP form
    "complainant_phone": "action_ask_complainant_phone",
    "otp_consent": "action_ask_otp_consent",
    "otp_input": "action_ask_otp_input",
    # Status check flow
    "story_route": "action_ask_status_check_method",
    "status_check_grievance_id_selected": "action_ask_status_check_grievance_id_selected",
    "status_check_complainant_full_name": "action_ask_status_check_complainant_full_name",
    "status_check_retrieve_grievances": "action_ask_status_check_retrieve_grievances",
    "valid_province_and_district": "action_ask_form_status_check_skip_valid_province_and_district",
    # Grievance review
    "grievance_classification_consent": "action_ask_form_grievance_complainant_review_grievance_classification_consent",
    "grievance_categories_status": "action_ask_form_grievance_complainant_review_grievance_categories_status",
    "grievance_cat_modify": "action_ask_form_grievance_complainant_review_grievance_cat_modify",
    "grievance_summary_status": "action_ask_form_grievance_complainant_review_grievance_summary_status",
    "grievance_summary_temp": "action_ask_form_grievance_complainant_review_grievance_summary_temp",
}
```

**Form-specific overrides** (when slot appears in multiple forms):
```python
# form_status_check_skip uses different ask actions for shared location slots
# form_status_check_1 uses action_ask_form_status_check_1_complainant_phone for complainant_phone
_ASK_ACTIONS_BY_FORM_SLOT = {
    ("form_status_check_skip", "valid_province_and_district"): "action_ask_form_status_check_skip_valid_province_and_district",
    ("form_status_check_skip", "complainant_district"): "action_ask_form_status_check_skip_complainant_district",
    ("form_status_check_skip", "complainant_municipality_temp"): "action_ask_form_status_check_skip_complainant_municipality_temp",
    ("form_status_check_skip", "complainant_municipality_confirmed"): "action_ask_form_status_check_skip_complainant_municipality_confirmed",
    ("form_status_check_1", "complainant_phone"): "action_ask_form_status_check_1_complainant_phone",
}
```

**Lookup**: `_get_ask_action(active_loop, slot)` checks `(active_loop, slot)` in _ASK_ACTIONS_BY_FORM_SLOT first, else falls back to _ASK_ACTIONS_BY_SLOT.get(slot). Implemented in `orchestrator/form_loop.py`.

---

## Remaining Work

- [ ] End-to-end test of form_contact, form_otp, form_status_check_skip, form_grievance_complainant_review flows
- [ ] Verify all ask actions are registered in action_registry (see 02_action_layer.md)
