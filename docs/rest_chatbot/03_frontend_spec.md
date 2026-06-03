# REST Webchat Frontend Spec

## 1) Scope

This spec documents `channels/REST_webchat` behavior:

- UI shell and widget behavior
- session/language handling
- orchestrator request/response contract
- quick replies + custom payload handling
- file upload UX and polling
- websocket task-status integration

## 2) File Layout

- `channels/REST_webchat/index.html` - widget markup and Socket.IO client script load
- `channels/REST_webchat/app.js` - application orchestration and API calls
- `channels/REST_webchat/config.js` - endpoint and session config
- `channels/REST_webchat/utterances.js` - frontend-local i18n copy
- `channels/REST_webchat/modules/eventHandlers.js` - button/custom payload behavior
- `channels/REST_webchat/modules/uiActions.js` - UI rendering/state helpers
- `channels/REST_webchat/styles.css` - visual styling
- `channels/REST_webchat/ui_config.js` - theme constants

## 3) Configuration Contract (`config.js`)

Current defaults:

- Orchestrator endpoint: `/message`
- File upload endpoint: `/upload-files`
- Session localStorage key: `rasa_session_id`
- Socket transport: websocket
- Socket path/namespace used in app: `/accessible-socket.io`

Deployment assumption:

- Reverse proxy routes same-origin paths to orchestrator/API services.

## 4) Session and Language

### 4.1 Session id strategy

`window.getSessionId()` returns:

- existing id from localStorage key `rasa_session_id`, or
- generated temp id: `temp_<timestamp>_<random>`

Session reset action:

- `handleClearSessionCommand()` resets frontend state and rotates session id.

### 4.2 Language strategy

Supported languages in UI copy:

- `en`
- `ne`

Resolution order:

1. URL param `lang`
2. localStorage `rest_webchat_lang`
3. fallback `en`

Language slash commands:

- `/set_english`
- `/set_nepali`

## 5) Startup Behavior

On `DOMContentLoaded`:

1. initialize language
2. initialize UI references
3. setup Socket.IO task status room subscription
4. send introductory message (`/introduce{...}`)
5. register event listeners

Intro payload contains:

- `flask_session_id`
- optional URL context: `province`, `district`
- optional QR token `t`

## 6) Orchestrator Messaging Contract

Outbound request (`restSendMessage`):

- `user_id`
- `message_id` (null by default)
- `text` or `payload`
- `channel: "webchat-rest"`
- optional `metadata`

Inbound response (`handleOrchestratorResponse`):

- `messages[]`
  - `text`
  - `buttons`
  - `custom`
  - `json_message`
- `next_state`
- `expected_input_type`

Frontend caches:

- last bot text
- last quick replies
- `lastOrchestratorNextState`

These are used for post-upload restore and end-of-flow button behavior.

## 7) Quick Replies and Custom Payloads

Quick replies:

- rendered as button blocks
- previous quick reply groups are replaced/cleared to avoid stale choices

Custom payload handlers include:

- `grievance_id_set` -> set grievance id
- `grievance_saved_in_db` -> enable upload state
- `open_upload_modal` -> open file picker
- `clear_window` -> clear session
- `close_browser_tab` -> attempt tab close

Local-only quick reply payloads:

- `__add_more_files__`
- `__go_back_to_chat__`
- `__file_another_grievance__` (restart intake from `done` without closing tab)

These do not call orchestrator.

Post-submit UX (June5 P1):

- `close_controls_mode` on `/message` response: `session` (Close session only) or `browser` (SEAH / sensitive — Close browser only).
- `#grievance-filed-banner` shows reference id from submit until session reset or file-another.
- Orchestrator outro emits three text messages (success → reference → follow-up/attachments).

## 8) File Upload UX and API Flow

### 8.1 Preconditions

Upload requires `window.grievanceId`.

If not present:

- frontend sends translated helper message telling user to first create grievance.

### 8.2 Upload process

1. User selects files
2. frontend validates/flags oversized files
3. optional image compression for very large image uploads
4. `POST /upload-files` with multipart payload
5. if accepted, poll `GET /file-status/{file_id}`

Payload includes:

- `grievance_id`
- `client_type=webchat-rest`
- `rasa_session_id`
- `flask_session_id`
- `files[]`

### 8.3 Locking and completion behavior

During upload:

- message input + send button are locked

On successful completion:

- show post-upload helper copy
- show quick replies:
  - add more files
  - go back to chat
  - end-of-flow close/clear actions when `next_state == done`

On failure:

- show failure copy
- keep recovery quick replies
- unlock input

## 9) WebSocket Behavior

Client connection:

- namespace: `/accessible-socket.io`
- path: `/accessible-socket.io`
- room: current session id

Events handled:

- `task_status`

Specific handling exists for task:

- `classify_and_summarize_grievance_task` on `SUCCESS` to display summary/categories output to user.

## 10) UI Controls and Error Handling

Persistent controls:

- close browser button (`window.close()` fallback message if blocked)
- close session button (state reset + new session id)

Input UX:

- Enter sends
- Shift+Enter adds newline
- tooltip shown when user tries to send empty message with no files

Error UX:

- connection errors from orchestrator API failures
- upload API and poll errors
- long-processing notification when polling max attempts is reached
