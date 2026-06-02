# Spec 8: Webchat Socket.IO Bridge (Option A)

## Purpose

Implement a Socket.IO bridge between the existing webchat (`channels/webchat`) and the orchestrator so the current UI can use the new decision engine with minimal changes.

This is a **transition solution**, not the long-term target, but it allows fast end-to-end testing and rollout.

---

## Scope

- Add a Socket.IO server (or layer) that:
  - Receives `complainant_uttered` from webchat.
  - Calls the orchestrator’s conversation logic (`run_flow_turn` / `POST /message`).
  - Emits `bot_uttered` events compatible with existing webchat handlers.
- Keep `channels/webchat` code **as unchanged as possible**, apart from `WEBSOCKET_CONFIG.URL` pointing to the new endpoint.
- Deploy behind nginx on the same `/socket.io/` path currently used for Rasa.

---

## Responsibilities

### Bridge Server

- **Transport**: Socket.IO (server-side)
- **Inbound events**:
  - `complainant_uttered` with payload:
    ```json
    {
      "message": "string",
      "session_id": "string",
      "metadata": { "optional": "data" }
    }
    ```
  - Map to orchestrator request:
    - `user_id = session_id`
    - If `message` starts with `/`: `payload = message`, `text = ""`
    - Else: `text = message`, `payload = null`
    - `channel = "webchat"` (optional)
- **Outbound events**:
  - For each `message` from the orchestrator response, emit:
    ```json
    {
      "text": "string?",
      "buttons": [ { "title": "string", "payload": "string" } ]?,
      "custom": { "data": {...} }?
    }
    ```
  - Event name: `bot_uttered` (to match existing handlers).

---

## Implementation Sketch (implemented)

### 1. Server Placement

- Option 1: In-process with FastAPI (e.g., `python-socketio` + ASGI integration).
- Option 2: Separate process/module (e.g., `socketio` server that calls orchestrator via HTTP).

For simplicity and reuse of `run_flow_turn`, Option 1 (in-process) is preferred if the stack allows it.

### 2. Concrete implementation

- **Bridge module**: `orchestrator/socket_server.py`
  - Uses `socketio.AsyncServer(async_mode="asgi")` and `socketio.ASGIApp(sio)` to expose a Socket.IO endpoint.
  - Handles `complainant_uttered`:
    - Reads `{ message, session_id, metadata }`.
    - Maps `message`:
      - If `message` starts with `/` ⇒ `text = ""`, `payload = message`.
      - Else ⇒ `text = message`, `payload = None`.
    - Loads / creates session via `get_session` / `create_session` and `slot_defaults` from `load_config()`.
    - Calls `run_flow_turn(session=session, text=text, payload=payload, domain=_DOMAIN)`.
    - Persists via `save_session(session)`.
    - Emits one `bot_uttered` per orchestrator message, normalising keys:
      - `text` → `text`
      - `buttons` → `buttons`
      - `json_message` / `custom` → `custom`.
  - Exposes `app = socket_app` so it can be run directly as an ASGI app.

- **Combined ASGI app**: `orchestrator/main.py`
  - Existing FastAPI app remains on `/message` and `/health`.
  - Adds a combined Starlette app:
    - `asgi = Starlette(routes=[Mount("/socket.io", app=socket_app), Mount("/", app=app)])`
  - Recommended run command (HTTP + Socket.IO on one port):
    ```bash
    uvicorn orchestrator.main:asgi --host 0.0.0.0 --port 8082
    ```

```python
import socketio
from orchestrator.state_machine import run_flow_turn
from orchestrator.session_store import get_session, save_session, create_session
from orchestrator.config_loader import load_config

sio = socketio.AsyncServer(async_mode=\"asgi\")
app = socketio.ASGIApp(sio)  # or mounted into FastAPI

@sio.event
async def complainant_uttered(sid, data):
    message = data.get(\"message\", \"\")
    session_id = data.get(\"session_id\", sid)

    # Map to orchestrator input
    text = \"\"
    payload = None
    if message.startswith(\"/\"):
        payload = message
    else:
        text = message

    session = get_session(session_id) or create_session(session_id, slot_defaults)

    messages, next_state, expected_input_type = await run_flow_turn(
        session=session,
        text=text,
        payload=payload,
        domain=domain,
    )

    save_session(session)

    # Emit bot_uttered for each message
    for m in messages:
        out = {}
        if \"text\" in m:
            out[\"text\"] = m[\"text\"]
        if \"buttons\" in m:
            out[\"buttons\"] = m[\"buttons\"]
        if \"json_message\" in m or \"custom\" in m:
            out[\"custom\"] = m.get(\"json_message\") or m.get(\"custom\")
        await sio.emit(\"bot_uttered\", out, to=sid)
```

---

## Webchat Changes (current)

- In `channels/webchat/config.js`:
  - `WEBSOCKET_CONFIG` is already compatible with the bridge:
    ```js
    const WEBSOCKET_CONFIG = {
      URL: `http://localhost:8082`, // Orchestrator Socket.IO bridge (local)
      OPTIONS: {
        path: '/socket.io/',
        transports: ['websocket']
      }
    };
    ```
  - For remote deployments, only `URL` changes to your nginx host (e.g. `https://chat.example.org`); `path` and `transports` stay the same.
- No changes to:
  - `safeSendMessage` in `app.js` (still calls `socket.emit("complainant_uttered", ...)`).
  - `eventHandlers.setupSocketEventHandlers` (still listens to `bot_uttered`).

---

## Nginx / Deployment (target)

Example nginx location (adapt to your existing config):

```nginx
location ~* ^/socket\.io/ {
    proxy_pass http://localhost:8082;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 600s;
}
```

This allows gradual cutover: point webchat to the orchestrator bridge while Rasa is still running for other channels.

---

## Tests

### Manual verification

1. **Start orchestrator + bridge**:
   - `uvicorn orchestrator.main:asgi --port 8082`
2. **Run existing webchat**:
   - Confirm `WEBSOCKET_CONFIG.URL` points at the same host/port as the bridge.
3. **Happy-path flow**:
   - Open webchat, then run:
     - Intro greeting appears.
     - Choose language (English / Nepali buttons).
     - Select “New grievance”.
     - Enter grievance text.
     - Submit details until confirmation.
   - At each step, verify:
     - `complainant_uttered` is sent with `{ message, session_id }`.
     - `bot_uttered` responses mirror the behavior of `/message` (texts, buttons).
4. **Slash command sanity checks**:
   - In webchat, send `/restart`, `/submit_details`, and another known payload.
   - Confirm they are handled correctly via the `payload` path (no free-text intent parsing).

### Automated / integration tests (future)

- **Socket.IO client test (Python)**:
  - Use an async Socket.IO test client (e.g. `python-socketio` client) that:
    - Connects to `ws://localhost:8082/socket.io/`.
    - Emits a `complainant_uttered` event with a fixed `session_id` and message.
    - Awaits one or more `bot_uttered` events.
    - Asserts that:
      - A message is received.
      - Its `text` matches an expected intro string, and/or buttons contain expected payloads.
    - Optionally, compares the Socket.IO response to the `/message` HTTP response for the same logical turn.
- **Web UI tests (optional)**:
  - Add Playwright/Cypress tests for:
    - Happy-path grievance flow via webchat.
    - At least one slash command (`/restart`) path.

## Checklist

- [x] Socket.IO bridge module implemented (and wired to `run_flow_turn`)
- [x] `WEBSOCKET_CONFIG` in `channels/webchat/config.js` compatible with bridge
- [ ] Nginx (or equivalent) routes `/socket.io/` to bridge
- [x] Manual test: intro → language → new grievance → grievance text → submit details works via webchat
- [ ] Optional: Automated webchat tests added (e.g., Playwright/Cypress or Socket.IO client tests)

