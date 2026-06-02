# Spec 9: REST-based Webchat (Option B)

## Purpose

Create a **Rasa-free** version of the webchat that talks directly to the orchestrator via REST, without Socket.IO, providing a cleaner long-term architecture.

This will live in a separate folder (e.g. `channels/REST_webchat`) so the existing `channels/webchat` can continue to run until migration is complete.

---

## Scope

- Copy the current webchat assets to a new folder (e.g. `channels/REST_webchat/`).
- Replace Socket.IO-based communication with direct HTTP calls to the orchestrator:
  - `POST /message` for sending user input.
  - Optional: `GET /health` for UI-level health checks.
- Preserve:
  - The current UI behavior (chat widget, launcher, file upload, quick replies).
  - File upload behavior (still via Flask `/upload-files`); only the bot conversation backend changes.

---

## Target Architecture

- **Frontend**: `channels/REST_webchat/`
  - `app.js` (or equivalent) calls `fetch("http://<orchestrator-host>:8000/message", ...)` for each message.
  - Renders responses from the orchestrator’s `messages[]` array.
- **Backend**: Orchestrator only (no Rasa, no Socket.IO needed for chat):
  - `POST /message` is the single entry point for conversation.
  - `messages[]`, `next_state`, `expected_input_type` drive the UI.
- **Files**:
  - Still uploaded to Flask endpoint (`FILE_UPLOAD_CONFIG.URL`), as today.

---

## Implementation Plan

### 1. Create REST_webchat Folder

- Copy existing webchat folder:
  ```bash
  cp -r channels/webchat channels/REST_webchat
  ```
- Adjust HTML entry point (e.g. `index.html`) only as needed to reference the new JS bundle path (if bundling is used).

### 2. Replace Socket.IO with REST in app.js

In `channels/REST_webchat/app.js`:

- Remove or no-op Socket.IO-specific code:
  - `initializeWebSocket`, `socket`, `socket.emit`, `io(WEBSOCKET_CONFIG.URL, ...)`, etc.
- Implement a REST-based `safeSendMessage`:

```js
const ORCHESTRATOR_URL = "http://localhost:8000/message"; // or via nginx

async function restSendMessage(message, additionalData = {}) {
  const userId = window.getSessionId(); // reuse existing session id logic

  const payload = {
    user_id: userId,
    text: "",
    payload: null,
    channel: "webchat-rest"
  };

  if (message.startsWith("/")) {
    payload.payload = message;
  } else {
    payload.text = message;
  }

  // Optionally include metadata (e.g., province/district)
  if (additionalData && Object.keys(additionalData).length > 0) {
    payload.metadata = additionalData;
  }

  const resp = await fetch(ORCHESTRATOR_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!resp.ok) {
    console.error("Orchestrator error:", await resp.text());
    uiActions.showError("Sorry, there was an error. Please try again.");
    return;
  }

  const data = await resp.json();
  handleOrchestratorResponse(data);
}

window.safeSendMessage = restSendMessage;
```

### 3. Rendering Responses

Add a helper to render orchestrator responses in `app.js` or a new module:

```js
function handleOrchestratorResponse(response) {
  const { messages, next_state, expected_input_type } = response;

  if (!Array.isArray(messages)) return;

  messages.forEach((m) => {
    if (m.text) {
      uiActions.appendMessage(m.text, "received");
    }
    if (m.buttons && m.buttons.length > 0) {
      // Render quick replies / buttons using existing UI helpers
      eventHandlers.renderQuickReplies(m.buttons);
    }
    if (m.custom) {
      // Handle custom payloads like grievance_id_set (update window.grievanceId)
      eventHandlers.handleCustomPayload(m.custom);
    }
  });

  // Optionally use next_state / expected_input_type to adjust UI (e.g. disable input when done)
}
```

You can reuse or lightly adapt existing helpers in `modules/eventHandlers.js` and `uiActions.js` to handle buttons and custom payloads.

### 4. Intro / Initial Message

The existing webchat sends an `/introduce{...}` command on startup. In REST_webchat:

- Keep the same behavior, but call `restSendMessage(initialMessage)` instead of `socket.emit`:

```js
function sendIntroduceMessage() {
  const { province, district } = getUrlParams();
  const flaskSessionId = window.flaskSessionId || window.getSessionId();
  const initialMessage =
    province && district
      ? `/introduce{"province": "${province}", "district": "${district}", "flask_session_id": "${flaskSessionId}"}`
      : `/introduce{"flask_session_id": "${flaskSessionId}"}`;

  restSendMessage(initialMessage);
}
```

### 5. File Uploads

Leave file upload logic unchanged (still hitting Flask) but ensure:

- When grievance ID is set via orchestrator `json_message`/`custom`, you update `window.grievanceId` in your `handleCustomPayload` so uploads continue to work.

### 6. Utterances file (frontend-only copy)

**Purpose:** Centralize all user-facing strings in REST_webchat so copy is maintained in one place. The frontend handles some flows without orchestrator calls (e.g. file upload “Go back”, errors), so these messages live in the frontend.

**File:** `channels/REST_webchat/utterances.js`

**Structure:** Same en/ne pattern as `utterance_mapping_rasa.py` for consistency:

```js
// utterances.js
const LANG = "en"; // or "ne" when bilingual

export const U = {
  errors: {
    connection: { en: "Sorry, there seems to be a connection issue...", ne: "..." },
    timeout: { en: "...", ne: "..." },
  },
  file_upload: {
    post_upload: { en: "Files uploaded. You can add more files...", ne: "..." },
    transition: { en: "Your files are uploaded. Here's where we left off.", ne: "..." },
    failure: { en: "One or more files could not be saved...", ne: "..." },
    buttons: { add_more: { en: "Add more files", ne: "..." }, go_back: { en: "Go back to chat", ne: "..." } },
    no_grievance: { en: "To attach files, first start a grievance...", ne: "..." },
    voice_detected: { en: "Voice recordings detected...", ne: "..." },
    oversized: { en: "Some files are too large and will be skipped:", ne: "..." },
    processing_long: { en: "File processing is taking longer than expected...", ne: "..." },
    processing: { en: "Processing files...", ne: "..." },
    file_saved: { en: "File is saved in the database.", ne: "..." },
    // ...
  },
  task_status: {
    classification_done: { en: "We've finished analyzing your grievance...", ne: "..." },
    // ...
  },
};

export function get(keyPath, lang = LANG) {
  const keys = keyPath.split(".");
  let v = U;
  for (const k of keys) v = v?.[k];
  return (typeof v === "object" && v?.[lang]) ? v[lang] : (v?.en ?? String(v ?? ""));
}
```

**Usage:** `import { get } from "./utterances.js";` then `get("file_upload.post_upload")` or `get("errors.connection")`. All hardcoded strings in `app.js`, `eventHandlers.js`, and `uiActions.js` should be moved to `utterances.js` and referenced via `get(...)`.

**Default language:** `DEFAULT_LANG = "ne"` (Nepali); English (`en`) is for testing. To switch language, call `get(keyPath, "en")` or pass lang from URL/settings.

---

## Testing Plan

### 1. Manual browser tests (REST_webchat)

- **Happy path – new grievance**
  - Open REST_webchat page in a browser.
  - Start chat, confirm intro / language selection appears.
  - Choose English (payload `/set_english`) and verify main menu.
  - Choose "New grievance" (payload `/new_grievance`) and verify grievance form prompt.
  - Enter grievance text and continue until details are submitted (payload `/submit_details`).
  - Confirm the flow ends with `next_state == "done"` and a clear completion message.

- **File upload flow**
  - In the same session, start a new grievance and progress until a `grievance_id` is issued via custom payload.
  - Attach one or more files and send.
  - Confirm:
    - Files are POSTed to `FILE_UPLOAD_CONFIG.URL`.
    - `client_type` is `webchat-rest`, and `grievance_id` / session IDs are populated.
    - Upload status and any transcription messages appear in the chat.

- **Status check entry flow**
  - Start a new session.
  - Go through intro → language selection (`/set_english`).
  - Choose "Check status" (payload `/check_status`) from the main menu.
  - Verify the UI shows the status-check form and any expected buttons or prompts.

- **Resilience / error UX**
  - Stop the orchestrator temporarily and try sending a message.
  - Confirm an appropriate error appears in the chat (using `uiActions.showError`) and the widget does not hard-crash.

### 2. API-level tests (orchestrator)

- **Reuse existing tests in `tests/orchestrator/test_orchestrator_api.py`:**
  - `test_health_endpoint` – validates `GET /health`.
  - `test_full_happy_path_flow` – intro → `/set_english` → `/new_grievance` → free-text grievance → `/submit_details` with state assertions.
  - `test_status_check_entry_flow` – intro → `/set_english` → `/check_status` with assertions on `next_state` and presence of buttons.

These API tests should continue to pass as-is and serve as the backend contract that REST_webchat relies on.

---

## Checklist

- [x] `channels/REST_webchat/` created and wired to orchestrator REST API
- [x] `channels/REST_webchat/utterances.js` created; all frontend-only copy moved from app.js, eventHandlers.js, uiActions.js
- [x] Socket.IO removed or no-op in REST_webchat (no dependency on Rasa)
- [x] `safeSendMessage` uses `fetch` to call `POST /message`
- [x] Orchestrator responses rendered correctly (text, buttons, custom payloads)
- [x] Intro `/introduce` path implemented via REST
- [x] File uploads adapted for REST_webchat and grievance ID coming from orchestrator custom payloads
- [x] Manual E2E test: intro → language → new grievance → grievance text → submit (browser) – validated 2026-02-27; file upload flow not yet exercised
