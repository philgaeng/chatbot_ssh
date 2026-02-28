# Spec 1: Orchestrator

## Purpose

Lightweight FastAPI service that receives user input, drives the state machine, invokes actions via the Action Layer, and returns bot messages.

---

## API

### POST /message

**Request**:
```json
{
  "user_id": "string",
  "message_id": "string (optional, for future dedupe)",
  "text": "string (user message)",
  "payload": "string (optional, button payload e.g. /submit_details)",
  "channel": "string (optional)"
}
```

**Response**:
```json
{
  "messages": [
    { "text": "string" },
    { "buttons": [{"title": "string", "payload": "string"}] },
    { "custom": { "data": {...} } }
  ],
  "next_state": "string",
  "expected_input_type": "text|buttons|custom"
}
```

---

## Session Store (In-Memory)

**Structure**:
```python
{
  "user_id": str,
  "state": str,           # e.g. "form_grievance", "done"
  "active_loop": str,     # form name or null
  "requested_slot": str,  # current slot being collected
  "slots": dict,          # all slot values
  "updated_at": datetime
}
```

**Operations**:
- `get_session(user_id) -> Session | None`
- `save_session(session)`
- `create_session(user_id) -> Session` (initial state)

---

## State Machine (All Flows)

| State | Description | Flow(s) |
|-------|-------------|---------|
| `intro` | Language selection; run action_introduce | All |
| `main_menu` | Menu; run action_main_menu | All |
| `form_grievance` | Collect grievance_new_detail | New grievance |
| `contact_form` | Collect complainant contact and location | New grievance |
| `otp_form` | Collect phone and verify OTP | New grievance, Status check (phone) |
| `submit_grievance` | Finalize submission; run action_submit_grievance | New grievance |
| `grievance_review` | Post-submission classification review | New grievance |
| `status_check_form` | Status check via ID or phone (form_status_check_1/2/otp/skip) | Status check |
| `done` | Flow ends | All |

**Transitions** (from flow.yaml):
- `intro` + set_english/set_nepali → `main_menu`
- `main_menu` + new_grievance → `form_grievance`
- `main_menu` + start_status_check → `status_check_form`
- `form_grievance` + form_complete → `contact_form`
- `contact_form` + form_complete → `otp_form`
- `otp_form` + form_complete → `submit_grievance` (grievance flow) or `status_check_form` (status check flow, active_loop = form_status_check_2)
- `submit_grievance` + submit_complete → `grievance_review`
- `grievance_review` + review_complete → `done`
- `status_check_form` + form_complete (or skip) → `done` (or intermediate form transitions per route)

---

## Flow per Request

1. Load or create session for `user_id`.
2. Parse input: use `payload` if present, else `text`. Derive intent for payloads (e.g. `/submit_details` → `submit_details`).
3. Build `latest_message` for tracker: `{"text": text, "intent": {"name": derived_intent}}`.
4. If state is `intro`: run `action_introduce`; on language selection apply slot updates, transition to `main_menu`.
5. If state is `main_menu`: run `action_main_menu`; on `/new_grievance` run `action_start_grievance_process` → `form_grievance`; on `/start_status_check` run `action_start_status_check` → `status_check_form`.
6. If state is `form_grievance`: run form loop (see [03_form_loop.md](03_form_loop.md)); on form_complete → `contact_form`.
7. If state is `contact_form`: run form loop for form_contact; on form_complete → `otp_form`.
8. If state is `otp_form`: run form loop for form_otp; on form_complete → `submit_grievance` (if story_main = new_grievance) or `status_check_form` with active_loop = form_status_check_2 (if story_main = status_check).
9. If state is `submit_grievance`: run `action_submit_grievance`; on submit_complete → `grievance_review`.
10. If state is `grievance_review`: run form loop for form_grievance_complainant_review; on review_complete → `done`.
11. If state is `status_check_form`: run form loop for form_status_check_1/2/otp/skip as dictated by story_route and story_step; on complete → `done` or intermediate form.
12. Apply slot updates to session.
13. Persist session.
14. Return `messages`, `next_state`, `expected_input_type`.

---

## Dependencies

- Action registry (invoke actions)
- Config (load from orchestrator YAML, extracted from Rasa domain/stories)

---

## Deliverables

- `orchestrator/main.py` – FastAPI app
- `orchestrator/session_store.py` – in-memory session store
- `orchestrator/state_machine.py` – state and transition logic (or inline in main)

---

## Checklist

- [x] POST /message endpoint implemented
- [x] GET /health endpoint
- [x] In-memory session store (get, save, create)
- [x] Flow: intro → main_menu → form_grievance → contact_form → otp_form → submit_grievance → grievance_review → done
- [x] Flow: intro → main_menu → status_check_form (form_status_check_1/2/otp/skip) → done
- [x] Config loaded from orchestrator YAML
- [x] Response format: messages, next_state, expected_input_type

---

## Implementation Status by Flow

| Flow | States Implemented | Forms in Orchestrator |
|------|-------------------|------------------------|
| **New grievance (full)** | intro, main_menu, form_grievance, contact_form, otp_form, submit_grievance, grievance_review, done | form_grievance, form_contact, form_otp, form_grievance_complainant_review |
| **Status check** | intro, main_menu, status_check_form, done | form_status_check_1, form_otp, form_status_check_2, form_status_check_skip |

**Status check routing** (per `story_route` and `active_loop`):
- form_status_check_1 + route_status_check_phone → form_otp
- form_status_check_1 + route_status_check_grievance_id → form_status_check_2
- form_status_check_1 + skip → form_status_check_skip
- form_otp (status check) → form_status_check_2
- form_status_check_2 → action_status_check_request_follow_up → done
- form_status_check_skip → action_skip_status_check_outro → done

All flows use the same orchestration pattern:
- Dedicated state(s) to enter each form
- Shared form loop driver (`run_form_turn`)
- Slot → ask action mapping in `_ASK_ACTIONS_BY_SLOT` (see [03_form_loop.md](03_form_loop.md))
