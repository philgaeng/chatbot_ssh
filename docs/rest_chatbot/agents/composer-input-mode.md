# Agent brief: Composer input mode (buttons vs text)

**Goal:** Reduce user confusion when quick-reply buttons are shown by disabling and visually de-emphasizing the textarea unless free text is expected (e.g. Skip-able form fields).

**Spec:** `docs/rest_chatbot/03_frontend_spec.md` §10–§11  
**Primary code:** `channels/REST_webchat/` + **`backend/orchestrator/state_machine.py`** (`expected_input_type` derivation only)

**Product decisions (locked):** Yes/No without Skip → block typing; post-upload buttons → block typing; Nepali draft copy OK; no pulse P1.

---

## Step 0 — Backend: align `expected_input_type` (`state_machine.py`)

Add a helper near the end of `run_flow_turn` (before `return`):

```python
_SKIP_PAYLOADS = frozenset({"/skip", "/affirm_skip"})

def _buttons_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out = []
    for m in messages or []:
        for b in m.get("buttons") or []:
            if b.get("payload"):
                out.append(b)
    return out

def _derive_expected_input_type(messages: List[Dict[str, Any]]) -> str:
    buttons = _buttons_from_messages(messages)
    if not buttons:
        return "text"
    if any((b.get("payload") or "") in _SKIP_PAYLOADS for b in buttons):
        return "text"
    return "buttons"
```

Replace the current block:

```python
expected = "buttons" if next_state in (...) else "text"
if next_state in form_states and session.get("requested_slot"):
    expected = "text"
```

with:

```python
expected = _derive_expected_input_type(dispatcher.messages)
```

Keep the early `introduce` return that uses `"buttons"` if it still applies; otherwise message-based rule covers it.

**No new `extract_buttons` / `validate_buttons` on form classes** — bool/category extractors already require `/` payloads. Optional: `BaseFormValidationAction.is_action_payload()` static helper for DRY (see spec §10.9).

---

## Context

- Orchestrator already returns `expected_input_type`: `"buttons"` | `"text"` on every `POST /message` response (`backend/orchestrator/main.py`).
- The REST webchat **does not use this field yet** — `handleOrchestratorResponse` in `app.js` ignores it.
- `uiActions.setInputLocked()` only handles upload/processing; it does not distinguish buttons-only turns from text turns.

---

## Implementation steps

### Step 1 — i18n (`utterances.js`)

Add under `U.composer`:

```javascript
composer: {
  placeholder_text: {
    en: "Please type your answer here",
    ne: "कृपया यहाँ आफ्नो जवाफ टाइप गर्नुहोस्",
  },
  placeholder_buttons: {
    en: "Please use the buttons above",
    ne: "कृपया माथिका बटनहरू प्रयोग गर्नुहोस्",
  },
  hint_text: {
    en: "Type your answer below",
    ne: "तल आफ्नो जवाफ टाइप गर्नुहोस्",
  },
  hint_buttons: {
    en: "Choose one of the options above",
    ne: "माथिका विकल्पहरूमध्ये एक छान्नुहोस्",
  },
},
```

Use `get("composer.placeholder_text")` etc. Review Nepali copy with product if unsure.

### Step 2 — Markup (`index.html`)

Inside `#form.composer`, after the textarea:

```html
<p id="composer-hint" class="composer-hint" aria-live="polite"></p>
```

On `#message-input`, add `aria-describedby="composer-hint"`.

Remove the hardcoded English placeholder from HTML; set it from JS when mode changes.

### Step 3 — Composer mode API (`uiActions.js`)

Add module state:

```javascript
let composerMode = "text";       // "text" | "buttons"
let composerLocked = false;      // upload / explicit lock
const SKIP_PAYLOADS = new Set(["/skip", "/affirm_skip"]);
```

**`export function setComposerMode(mode)`** (`mode` is `"text"` | `"buttons"`)

- Store `composerMode`
- If `composerLocked`, return early (only update stored mode for restore later)
- Apply CSS classes on `#form`: remove `composer-mode-text` / `composer-mode-buttons`, add the active one
- Update `#message-input`: `disabled`, placeholder, classes (`composer-input--active` / `composer-input--buttons-only`)
- Update `#composer-hint` text from i18n
- Update send button `disabled` when `mode === "buttons"`

**Refactor `setInputLocked(locked)`**

- `locked === true` → `composerLocked = true`, disable input + send, add `composer-mode-locked` on form
- `locked === false` → `composerLocked = false`, remove `composer-mode-locked`, call `setComposerMode(composerMode)` to restore

**`export function getComposerMode()`** — return current mode (for snapshots)

**`export function resolveComposerModeFromTurn(expectedInputType, quickReplies)`**

```javascript
const hasSkip = (quickReplies || []).some((b) =>
  SKIP_PAYLOADS.has(b.payload)
);
if (hasSkip) return "text";
if (expectedInputType === "buttons") return "buttons";
return "text";
```

Trust backend after Step 0; skip safeguard handles mislabels only.

### Step 4 — Wire orchestrator (`app.js`)

In `handleOrchestratorResponse`:

```javascript
const { messages = [], next_state, expected_input_type, close_controls_mode } = response || {};
// ... existing logic ...

window.lastExpectedInputType =
  typeof expected_input_type === "string" ? expected_input_type : "text";

// After messages.forEach (quick replies rendered):
const mode = uiActions.resolveComposerModeFromTurn(
  window.lastExpectedInputType,
  window.lastBotQuickReplies
);
uiActions.setComposerMode(mode);
```

In `resetFrontendState` and after session clear: `uiActions.setComposerMode("text")`.

**Launcher focus:** in `setupEventListeners`, only `messageInput.focus()` when `uiActions.getComposerMode() === "text"` and not locked.

**`handleMessageSubmit`:** at top, if composer is buttons-only or locked, `preventDefault` and return (belt-and-suspenders).

### Step 5 — Local flows (`app.js`)

| Location | Action |
|----------|--------|
| `takeFileUploadSnapshot` | Add `lastExpectedInputType: window.lastExpectedInputType` |
| `showPostUploadMessageAndUnlock` | After `replaceQuickReplies`, `setComposerMode("buttons")` then `setInputLocked(false)` |
| `showFailureMessageAndUnlock` | Same as post-upload |
| `handleGoBackToChat` | After restore quick replies, `setComposerMode(snapshot.lastExpectedInputType === "buttons" ? "buttons" : "text")` with skip re-check on restored buttons |
| `handleVoiceNextStep` | Keep lock during send; on unlock restore via last expected type |

### Step 6 — Styles (`styles.css`)

```css
#form.composer-mode-text #message-input {
  border: 2px solid var(--primary-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color) 18%, transparent);
}

#form.composer-mode-buttons #message-input,
#form.composer-mode-locked #message-input {
  border: 1px solid #d0d0d0;
  background: #f0f2f5;
  color: #888;
  box-shadow: none;
}

.composer-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.35;
  color: #54656f;
  padding: 0 4px;
}

#form.composer-mode-text .composer-hint {
  color: var(--primary-color);
  font-weight: 500;
}

#form.composer-mode-buttons .composer-hint {
  color: #888;
}
```

Add `body.high-contrast` overrides if existing patterns require thicker borders.

Optional: `.composer-mode-buttons .quick-replies` light panel background.

### Step 7 — Manual test checklist

Run REST webchat locally (see `docs/claude-tickets/DOCKER.md` or project docker docs for orchestrator + static channel).

- [ ] Fresh load → intro buttons → textarea disabled, grey, hint says use buttons
- [ ] File a grievance → reach contact field with Skip → textarea blue, can type
- [ ] Tap Skip on a skippable field → flow continues
- [ ] Main menu / location method → buttons only
- [ ] Upload file mid-flow → locked; after done → Add more/Go back, textarea disabled
- [ ] Go back to chat → composer mode matches pre-upload step
- [ ] `/set_nepali` → composer copy in Nepali
- [ ] Enter key does not submit in buttons mode
- [ ] Send tooltip does not appear when clicking send in buttons mode

---

## Out of scope (unless explicitly requested)

- `channels/webchat/` (legacy socket client)
- Changing quick-reply button labels or orchestrator utterances
- Per-form `extract_buttons` / `validate_buttons` (redundant — see spec §10.9)
- Quick-reply pulse/highlight (P2 only if pilot shows residual confusion)

---

## Alternative approaches (product options)

If disabling the textarea feels too harsh in user testing:

1. **Hint-only** — keep textarea enabled but show a prominent banner; lower implementation risk, weaker guardrail.
2. **Hide textarea** — collapse composer to a single-line “Tap a button above” bar in buttons mode; strongest signal, more layout work.
3. **Pulse quick replies (P2)** — animate or panel-highlight `.quick-replies` in buttons mode; ~3–5% extra clarity; ship only if P1 insufficient.
4. **Backend `allows_free_text` boolean** — explicit per-turn flag instead of inferring from skip; unnecessary once message-derived `expected_input_type` lands.

**Ship P1:** backend message-derived `expected_input_type` + disable + visual modes. **Skip pulse** unless field test fails.
