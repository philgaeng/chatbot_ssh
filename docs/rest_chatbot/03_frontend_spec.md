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
- `expected_input_type` — **`buttons`** or **`text`** (see §10 Composer input mode)

Frontend caches:

- last bot text
- last quick replies
- `lastOrchestratorNextState`
- `lastExpectedInputType` — drives composer mode after each orchestrator turn (new)

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
- `#grievance-filed-banner` shows *Grievance filed* + reference id from **submit** (`grievance_filed` event) through `grievance_review` and `done`, until session reset or file-another.
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

## 10) Composer Input Mode (buttons vs text)

### 10.1 Problem

Users often type into the composer when the bot expects a **quick-reply button** tap (main menu, Yes/No, location method, etc.). The textarea staying active and looking identical to “please type” steps causes confusion.

### 10.2 Modes

The composer has three modes. **Locked** always wins over the other two.

| Mode | CSS class on `#form` | Textarea | Send button | When |
|------|----------------------|----------|-------------|------|
| `text` | `composer-mode-text` | enabled | enabled | Bot expects free text (forms, skip-able fields, open chat) |
| `buttons` | `composer-mode-buttons` | disabled | disabled | Bot expects a quick-reply only (no free text) |
| `locked` | `composer-mode-locked` | disabled | disabled | Upload in progress, map picker suppression, voice next-step handoff, etc. |

`setInputLocked(true)` in existing code maps to **`locked`**. Unlocking must **restore** the last non-locked mode (`text` or `buttons`), not blindly enable text.

### 10.3 Primary signal: `expected_input_type` (backend-aligned)

Orchestrator `POST /message` response includes `expected_input_type`:

- `"buttons"` → composer mode **`buttons`**
- `"text"` → composer mode **`text`**

Store on `window.lastExpectedInputType` in `handleOrchestratorResponse`.

**Backend derivation (target — replace hardcoded state list):** at end of `run_flow_turn`, derive from the **outgoing turn** (`dispatcher.messages`), not only `next_state`:

```text
buttons_on_turn = union of all message.buttons on this response
has_skip = any payload in (/skip, /affirm_skip)
if buttons_on_turn and not has_skip → expected_input_type = "buttons"
else → expected_input_type = "text"
```

Rationale:

- Yes/No review steps (`grievance_review`, bool/category slots) emit buttons without Skip → **buttons**
- Contact/address/email asks with Skip → **text** (even with buttons visible)
- Intro / main menu / location method → **buttons** (no skip on turn)
- Open chat with no buttons → **text**

Keep the existing early return for pure menu states if needed; the message-based rule should subsume most of the `next_state in (...)` tuple in `state_machine.py`.

**Frontend safeguard (keep):** if visible quick-reply payloads include `/skip` or `/affirm_skip`, force mode **`text`** even if backend mislabels a turn (belt-and-suspenders).

Payload constants: `BUTTON_SKIP` in `backend/actions/utils/mapping_buttons.py`.

### 10.4 Confirmed product rules (2026-06)

| Rule | Decision |
|------|----------|
| Yes/No without Skip | **Block typing** (buttons mode) |
| Post-upload local buttons | **Block typing** |
| Nepali copy | Ship draft strings from agent brief; no product review gate |
| Backend + frontend alignment | **Yes** — fix `expected_input_type` derivation in orchestrator |
| Quick-reply pulse/highlight | **P2 only** if field testing shows residual confusion (see §10.11) |

### 10.5 Local-only quick replies (no orchestrator turn)

These flows must set composer mode explicitly when showing buttons:

| Flow | Mode | Notes |
|------|------|-------|
| Post-upload (`Add more` / `Go back` / voice follow-ups) | `buttons` | Navigation only |
| Post-upload restore (`handleGoBackToChat`) | restore from `fileUploadSnapshot.lastExpectedInputType` | extend snapshot |
| User sends typed message (`handleMessageSubmit`) | `text` until next bot turn | existing quick-reply clear stays |
| Session reset / file another | `text` | default after clear |
| `next_state === "done"` with no buttons | `text` | optional; low traffic |

### 10.6 Visual design

Make enabled vs disabled unmistakable on small screens.

**Text mode (`composer-mode-text`)**

- Textarea: **2–3px solid** border using `var(--primary-color)`; optional soft outer glow (`box-shadow: 0 0 0 3px rgba(primary, 0.15)`)
- Placeholder (i18n `composer.placeholder_text`): e.g. *“Please type your answer here”*
- Optional hint line below textarea (`#composer-hint`, i18n `composer.hint_text`): *“Type your answer below”*
- Send button: normal active styling

**Buttons mode (`composer-mode-buttons`)**

- Textarea: `disabled`, grey background (`#f0f2f5`), muted text (`#888`), `cursor: not-allowed`
- Border: 1px neutral grey (no blue emphasis)
- Placeholder (i18n `composer.placeholder_buttons`): e.g. *“Please use the buttons above”*
- Hint (`composer.hint_buttons`): *“Choose one of the options above”*
- Send button: `disabled`
- Do **not** steal focus into the textarea when opening the widget in buttons mode

**Locked mode**

- Reuse buttons-mode greys; hint may show upload/processing copy from existing `voice-status-banner` (no duplicate)

**Quick-reply emphasis (buttons mode only, optional P2)**

- Slightly stronger quick-reply container style (e.g. light blue panel behind `.quick-replies`) so buttons read as the primary action

### 10.7 Implementation surface

| File | Change |
|------|--------|
| `channels/REST_webchat/modules/uiActions.js` | Add `setComposerMode(mode)`, `getComposerMode()`, skip-aware helper; refactor `setInputLocked` to set/clear `locked` and restore previous mode |
| `channels/REST_webchat/app.js` | Read `expected_input_type` in `handleOrchestratorResponse`; call `applyComposerModeAfterTurn()`; extend `fileUploadSnapshot`; fix unlock paths |
| `channels/REST_webchat/utterances.js` | `composer.*` strings (`en` / `ne`) |
| `channels/REST_webchat/styles.css` | `.composer-mode-text`, `.composer-mode-buttons`, `#composer-hint`, textarea states |
| `channels/REST_webchat/index.html` | Optional `#composer-hint` element + `aria-describedby` on `#message-input` |

### 10.8 Accessibility

- `aria-disabled="true"` on textarea in buttons/locked modes
- `aria-describedby="composer-hint"` when hint is visible
- Invalid-send tooltip must not fire on disabled textarea click (ignore submit when mode is `buttons`)

### 10.9 Backend validation (defense in depth)

Button-only turns already reject stray free text in many forms via `_handle_boolean_and_category_slot_extraction` (returns `{slot_name: None}` unless input starts with `/affirm`, `/deny`, `/skip`, or another `/` payload).

**Do not add per-form `extract_buttons` / `validate_buttons` methods** — that duplicates `get_buttons()` and the existing extractors.

**Do add one shared helper** on `BaseFormValidationAction` (optional small refactor, not blocking frontend UX):

```python
@staticmethod
def is_action_payload(message_text: str) -> bool:
    return bool((message_text or "").strip().startswith("/"))
```

Use only where a validator needs an explicit early reject + re-prompt; bool/category paths already enforce slash payloads.

Orchestrator `expected_input_type` should **not** call form validators — it only inspects **outgoing** `dispatcher.messages[].buttons` for the turn (see §10.3).

### 10.10 Verification scenarios

1. **Intro / main menu** — textarea grey/disabled; blue quick replies are only path
2. **Address with Skip** — textarea blue/enabled; user can type or tap Skip
3. **Yes/No confirm** (no Skip) — textarea disabled once backend/heuristic marks buttons mode
4. **File upload** — locked during upload; after success, buttons mode for Add more / Go back
5. **Go back to chat** — restores prior text/buttons mode from snapshot
6. **Language `ne`** — placeholders and hints in Nepali
7. **High-contrast** — borders/hints remain visible (`body.high-contrast` rules)

### 10.11 Confidence / P2 pulse

Design confidence with **backend message-derived `expected_input_type` + frontend disable/visuals + skip safeguard: ~92%**.

Ship **without** quick-reply pulse/highlight as P1. Add pulse (subtle animation or light panel on `.quick-replies` in buttons mode) only if pilot users still tap the greyed textarea.

---

## 11) UI Controls and Error Handling

Persistent controls:

- close browser button (`window.close()` fallback message if blocked)
- close session button (state reset + new session id)

Input UX:

- Enter sends (only when composer mode is `text` and not `locked`)
- Shift+Enter adds newline
- tooltip shown when user tries to send empty message with no files (text mode only)

Error UX:

- connection errors from orchestrator API failures
- upload API and poll errors
- long-processing notification when polling max attempts is reached

---

## 12) Agent implementation brief

See **`docs/rest_chatbot/agents/composer-input-mode.md`** for step-by-step implementation and test checklist.
