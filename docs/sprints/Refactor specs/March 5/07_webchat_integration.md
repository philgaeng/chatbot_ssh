# Spec 7: Webchat Integration with Orchestrator

## Purpose

Describe how to plug the existing webchat (`channels/webchat`) into the new orchestrator, replacing Rasa as the primary conversation engine while preserving the current UX as much as possible.

---

## Current Webchat Behavior (Today)

- **Code**: `channels/webchat/app.js`, `config.js`, `modules/*`, `index.html`
- **Transport**: Socket.IO to the Rasa server
  - `WEBSOCKET_CONFIG.URL`: `http://localhost:8082` (or nginx proxy → Rasa)
  - `WEBSOCKET_CONFIG.OPTIONS.path`: `/socket.io/`
  - Uses `io(WEBSOCKET_CONFIG.URL, { path, transports: ['websocket'] })`
- **Events**:
  - Sends user messages via:
    - `socket.emit("complainant_uttered", { message, session_id, ... })`
  - Receives bot messages via Rasa’s SocketIO channel (`bot_uttered`, handled in `eventHandlers.setupSocketEventHandlers`)
- **Session**:
  - Uses `socket.id` and `SESSION_CONFIG.STORAGE_KEY` (`rasa_session_id`) for session identification
- **Initial message**:
  - On first connection, sends an `/introduce{...}` command (with `province`, `district`, `flask_session_id`) via `safeSendMessage(initialMessage)`
- **Files**:
  - Uploads via `FILE_UPLOAD_CONFIG.URL` (`http://localhost:5001/upload-files`), independent of Rasa

Goal: **Keep the UI and file-upload logic the same**, but switch the bot “brain” from Rasa to the orchestrator.

---

## Strategy: Two-Track Integration

We will:

- **Track A (Option A / Spec 8)**: Implement a Socket.IO bridge so the existing `channels/webchat` can talk to the orchestrator with minimal changes. This is for fast validation and rollout.
- **Track B (Option B / Spec 9)**: In parallel, implement a new REST-based webchat in `channels/REST_webchat` that talks directly to `POST /message`. This is the long-term, Rasa-free client.

Once REST_webchat is stable and deployed, we can decommission the Socket.IO bridge and the original Socket.IO-based webchat.

---

## Target Integration Architecture (Summary)

### Option A: Orchestrator Socket.IO Bridge (see 08_webchat_socket_bridge.md)

Add a Socket.IO endpoint to the orchestrator that mimics the minimal Rasa SocketIO protocol the webchat expects:

- **Server**: Orchestrator process (FastAPI + Socket.IO)
- **Endpoint**:
  - URL: `http://<host>:<port>` (same host as orchestrator or via nginx)
  - Path: `/socket.io/` (keep consistent with current config)
- **Events**:
  - **Inbound**: `complainant_uttered`
    - Payload: `{ message: string, session_id: string, metadata?: object }`
    - Behavior: On receive, call orchestrator `POST /message` with:
      - `user_id = session_id`
      - `text = message` OR `payload` if the message starts with `/`
      - `channel = "webchat"`
  - **Outbound**: `bot_uttered`
    - Payload: `{ text?: string, buttons?: [...], custom?: {...} }`
    - Built from orchestrator `messages[]` in the `POST /message` response

**Webchat change**: only `WEBSOCKET_CONFIG.URL` (and possibly port) needs to change to point to the orchestrator Socket.IO server. Event names and payloads stay the same.

### Option B: Direct REST from Webchat (see 09_rest_webchat.md)

Alternate (more invasive) approach: change `safeSendMessage` to call `POST /message` via `fetch` and render responses directly, **removing Socket.IO entirely**. This would require:

- Replacing `socket.emit("complainant_uttered", ...)` with `fetch("/message", ...)`
- Rewriting event-handling code in `modules/eventHandlers.js` to handle HTTP responses instead of Socket.IO events

This is more refactor work on the frontend and is better suited as a later step.

---

## Integration Plan (Option A)

### 1. Orchestrator: Socket.IO Layer

**New module** (suggested): `orchestrator/socket_server.py` or integrated in `main.py` using `python-socketio` or Starlette WebSocket routes.

Responsibilities:

- Start a Socket.IO server on the same host as FastAPI, same or different port
- On `complainant_uttered`:
  - Read `{ message, session_id, metadata }`
  - Map to orchestrator request:
    - `user_id = session_id`
    - If `message` starts with `/`: set `payload = message`, `text = ""`
    - Else: `text = message`, `payload = null`
  - Call `POST /message` internally (reuse orchestrator `run_flow_turn` instead of HTTP where possible)
  - Emit `bot_uttered` back to the client for each message in the orchestrator response:
    - `text` → `bot_uttered.text`
    - `buttons` → `bot_uttered.buttons`
    - `custom` / `json_message` → `bot_uttered.custom`

### 2. Webchat: Config Update

Update `channels/webchat/config.js` to point to the orchestrator Socket.IO server instead of Rasa:

- **Before**:
  ```js
  const WEBSOCKET_CONFIG = {
      URL: `http://localhost:8082`, // Rasa / nginx
      OPTIONS: {
          path: '/socket.io/',
          transports: ['websocket']
      }
  };
  ```

- **After** (example):
  ```js
  const WEBSOCKET_CONFIG = {
      URL: `http://localhost:8002`, // Orchestrator Socket.IO bridge
      OPTIONS: {
          path: '/socket.io/',
          transports: ['websocket']
      }
  };
  ```

No changes required in `app.js` for message sending, since it already uses:

- `safeSendMessage(message)` → `socket.emit("complainant_uttered", { message, session_id, ... })`

Event handlers in `modules/eventHandlers.js` should already be listening for `bot_uttered` and can be reused as-is if the orchestrator bridge emits `bot_uttered` with the same shape as Rasa.

### 3. Nginx / Deployment

Add or update nginx configuration to proxy the new Socket.IO endpoint, similar to the existing Rasa websocket proxy:

- **Location block** (example):
  ```nginx
  location ~* ^/socket\.io/ {
      proxy_pass http://localhost:8002;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection \"upgrade\";
      proxy_set_header Host $host;
      proxy_read_timeout 600s;
  }
  ```

This allows the webchat to continue using `/socket.io/` while you swap the backend from Rasa to the orchestrator.

---

## Integration Plan (Step-by-Step)

1. **Implement Socket.IO bridge on orchestrator side** (or companion process):
   - Ingest `complainant_uttered` events
   - Call orchestrator `run_flow_turn` / `POST /message`
   - Emit `bot_uttered` responses
2. **Update `WEBSOCKET_CONFIG.URL`** in `channels/webchat/config.js` to the new Socket.IO server
3. **Update nginx** to route `/socket.io/` to the orchestrator Socket.IO server
4. **Smoke-test webchat**:
   - Load the webchat page
   - Ensure intro / language selection appears
   - Run through the grievance flow; verify messages and buttons behave as in the curl and pytest tests
5. **Gradual migration** (optional):
   - Run Rasa and orchestrator in parallel for a time, but route webchat only to orchestrator
   - Keep status check and other flows validated before fully disabling Rasa for webchat

---

## Checklist

- [ ] Orchestrator: Socket.IO bridge implemented
- [ ] Webchat `WEBSOCKET_CONFIG.URL` updated to orchestrator
- [ ] Nginx (or other proxy) routes `/socket.io/` to orchestrator Socket.IO
- [ ] Manual webchat test: intro → language → new grievance → grievance text → submit details
- [ ] Optional: Webchat tests automated (e.g. with Playwright or Cypress) for the main flows

