# Spec 3: Form Loop

## Purpose

Reproduce Rasa's form-filling behavior: the orchestrator drives `required_slots` → `extract_*` → `validate_*` → apply updates → ask for next slot or complete.

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

- `orchestrator/form_loop.py` – `run_form_turn(form, slot_name, user_input, session, domain) -> (messages, slot_updates, completed)`

---

## Checklist

- [x] required_slots called with dispatcher, tracker, domain
- [x] extract_grievance_new_detail called when user input present
- [x] validate_grievance_new_detail called with extracted value
- [x] slot_updates applied to session
- [x] action_ask_grievance_new_detail called for first ask and re-ask
- [x] completed=True when required_slots returns []
- [x] requested_slot, skip_validation_needed handled
