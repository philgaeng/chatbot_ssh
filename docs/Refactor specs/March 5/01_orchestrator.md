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

## State Machine (Grievance Details Flow)

| State | Description |
|-------|-------------|
| `intro` | Language selection; run action_introduce |
| `main_menu` | Menu; run action_main_menu |
| `form_grievance` | Collect grievance_new_detail |
| `done` | Form complete; flow ends |

**Transitions**:
- `intro` + user selects language → `main_menu`
- `main_menu` + user selects /new_grievance → run `action_start_grievance_process` → `form_grievance`
- `form_grievance` + user input → form loop (extract → validate) → stay in `form_grievance` or → `done` when form completes
- `done` → no further transitions (flow complete)

---

## Flow per Request

1. Load or create session for `user_id`.
2. Parse input: use `payload` if present, else `text`. Derive intent for payloads (e.g. `/submit_details` → `submit_details`).
3. Build `latest_message` for tracker: `{"text": text, "intent": {"name": derived_intent}}`.
4. If state is `intro`: run `action_introduce`; on language selection apply slot updates, transition to `main_menu`.
5. If state is `main_menu`: run `action_main_menu`; on `/new_grievance` run `action_start_grievance_process`, transition to `form_grievance`.
6. If state is `form_grievance`: run form loop (see [03_form_loop.md](03_form_loop.md)).
7. Apply slot updates to session.
8. Persist session.
9. Return `messages`, `next_state`, `expected_input_type`.

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
- [x] Flow: intro → main_menu → form_grievance → done
- [x] Config loaded from orchestrator YAML
- [x] Response format: messages, next_state, expected_input_type
