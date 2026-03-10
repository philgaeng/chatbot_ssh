# Spec 12: Robust File Upload Flow

## Purpose

Make file attachment in the REST webchat robust and non-blocking: users can add files anytime during a grievance flow without interrupting the chatbot. The bot remembers where the user was and restores that state when the user returns to the chat.

---

## Requirements (Draft)

1. **Attach button** is enabled as soon as `grievance_id` is provided by the backend.
2. **Users can always add files** — they do not need to wait for a specific message or prompt.
3. **Bot remembers state** — before the user enters the file upload flow, we snapshot the current conversation state; when they return, we restore it.
4. **File upload** is handled by the chatbot UI as implemented (upload → processing → poll → "File is saved in the database").
5. **After upload completes** — show a message: "Files uploaded. You can add more files or go back to the chat." with two buttons: **Add more files** | **Go back to chat**.
6. **Go back to chat** — restores the UI to the state before file upload, so the user can continue the conversation where they left off.
7. **Non-interrupting** — the user can add files anytime without losing their place in the flow.

---

## Current Behaviour (Reference)

- Attach button is always visible; grievance check happens only when user tries to upload.
- File upload flow: select files → preview → send (Enter or submit) → "Files uploaded successfully. Processing..." → poll `/file-status/{file_id}` → "File is saved in the database".
- No explicit "file upload mode" — upload happens inline; user can keep typing.
- Orchestrator session (state, active_loop, slots) is unchanged when user attaches files; we never send a payload for "attach" action.

---

## Decisions (resolved)

### Resolved decisions (Q1–Q10)

| #       | Decision                                                                                                                                                                                       |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Q1**  | Keep button always visible; **disable** (greyed out) until `grievance_id` is set; tooltip "Start a grievance first" when disabled.                                                             |
| **Q2**  | Consider a distinct file-upload emphasis (e.g. colour / UI) — recommendation in spec below.                                                                                                    |
| **Q3**  | All in-chat (no modal). Mobile-first; use colours/UI to distinguish flow. "Add more files" = re-open picker for another round.                                                                 |
| **Q4**  | Snapshot **frontend only**: last bot message text, last quick replies. On "Go back" we **re-send/show** the last bot message so the user sees where they were. Orchestrator session unchanged. |
| **Q5**  | No orchestrator call on "Go back". Restore from snapshot: show transition message + last bot message + original quick replies.                                                                 |
| **Q6**  | **Lock** message input until upload + "File is saved" completes, then show "Add more / Go back" buttons.                                                                                       |
| **Q7**  | **Stack**: each upload round adds a new "Files uploaded" message with buttons.                                                                                                                 |
| **Q8**  | Status-check users **can** attach files once the grievance is retrieved (same `grievance_id` behaviour).                                                                                       |
| **Q9**  | Rely on **button enabled** when grievance_id exists. Orchestrator can still prompt "add files" after grievance creation if none attached yet.                                                  |
| **Q10** | **C)** Replace previous quick replies with "Add more" \| "Go back"; on "Go back" restore **both** the last bot message and original quick replies.                                             |

---

## Exit file-upload flow (Go back to chat)

**Agreed behaviour:** When the user clicks **Go back to chat** we send:

1. **One transition message** — files are uploaded and we are going back to the flow (friendly, clear).
2. **The latest response from the bot** — re-display the last bot message and its quick replies so the user sees where they were and can continue.

### Suggested transition messages (pick one or adapt)

- **Option A (short):**  
  _"Your files are uploaded. Here’s where we left off."_

Then immediately below: show the **last bot message** (from snapshot) and the **original quick replies** (e.g. [Yes] [No] for category review). No orchestrator call; session is unchanged.

### Optional: Nepali

If the UI is bilingual, add a short Nepali line for the same transition (e.g. _"तपाईंको फाइलहरू सेव भयो। यहाँ हामी रोक्यौ।"_ or similar — to be confirmed by a native speaker).

---

## Open point: exit-flow clarification

- **Order in the chat:** After the user clicks "Go back to chat", the sequence in the thread will be:  
  `… → [Files uploaded. Add more | Go back] → [Transition message] → [Last bot message] [Original quick replies]`.  
  The "Files uploaded" bubble stays in history; we do not remove it. **Confirm this is the desired order.** Confirm
- **Re-displaying the last bot message:** We append it as a **new** bot bubble (same text + same buttons as in the snapshot), so the user sees it again in context. **Confirm we do not need to remove or collapse any earlier duplicate of that message.** Confirm

---

## Proposed Architecture

### Frontend (REST_webchat)

| Component        | Behaviour                                                                                                                                                                                                      |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Attach button    | Always visible; **disabled** (greyed out) until `window.grievanceId` is set; tooltip "Start a grievance first" when disabled.                                                                                  |
| File upload flow | Select → preview → send → **lock input** → upload → poll → "File is saved" → show "Add more / Go back" buttons.                                                                                                |
| Post-upload      | Append message "Files uploaded. You can add more files or go back to the chat." with buttons: **Add more files** \| **Go back to chat**. Replace any previous quick replies with these two until user chooses. |
| State snapshot   | When user selects files (before upload), snapshot: `lastBotMessageText`, `lastBotQuickReplies`.                                                                                                                |
| Go back to chat  | (1) Append **transition message** (e.g. "Your files are uploaded. Here's where we left off."). (2) Append **last bot message** + **original quick replies** from snapshot. No orchestrator call. Unlock input. |
| Multiple rounds  | Each upload round stacks a new "Files uploaded" message with [Add more][Go back].                                                                                                                              |

### Backend (orchestrator / file server)

- No change. File upload and status polling as today.
- Orchestrator does not receive any "attach" or "file_upload_started" payload.

### Data flow

```
User in grievance_review, sees "Do you want to review categories?" [Yes][No]
    ↓
User clicks attach, selects files
    → Snapshot: lastMessage="Do you want...", quickReplies=[Yes, No]
    → (No API call)
    ↓
User sends (Enter) → handleFileUpload → lock input → upload → poll → "File is saved"
    ↓
Append "Files uploaded. Add more or go back." [Add more files][Go back to chat]
    (Previous quick replies replaced by these two)
    ↓
User clicks "Go back to chat"
    → Append transition: "Your files are uploaded. Here's where we left off."
    → Append last bot message + original quick replies from snapshot
    → Unlock input
    → User sees "Do you want to review categories?" [Yes][No] again
    → User clicks Yes/No → POST /message → normal flow continues
```

### Q2 follow-up: file-upload emphasis (mobile, in-chat)

- All interactions stay **in the chat** (no modal). Options to distinguish the file-upload phase:
  - **Colour:** e.g. a light border or background on the "Files uploaded. Add more | Go back" bubble, or a distinct colour for file-related messages.
  - **Copy:** Short label above the input while in upload flow, e.g. "Adding files — send to upload or go back to chat when done."
  - **Input state:** Input is locked until "File is saved" + buttons shown; that already signals "upload in progress."
- **Recommendation:** Locked input + clear "Add more / Go back" buttons is enough for robustness; optional subtle colour for the post-upload bubble if the design wants a visual cue. Agreed a different color may confuse the user

---

## Implementation status

| Item | Status | Notes |
|------|--------|-------|
| **Q1** Attach button disabled until grievance_id | Done | Button uses `grievanceId` + `grievanceCreatedInDb`; tooltip "Start a grievance first" when no grievance |
| **Q4/Q5** State snapshot, Go back (no orchestrator call) | Done | `takeFileUploadSnapshot()`, `handleGoBackToChat()` in app.js |
| **Q6** Lock input during upload | Done | `setInputLocked(true)` before upload, unlock when batch complete |
| **Q7** Stack: each round adds "Files uploaded" message | Done | `showPostUploadMessageAndUnlock()` appends message + [Add more][Go back] |
| **Q8** Status-check users can attach | Done | `open_upload_modal` sets grievanceId + grievanceCreatedInDb |
| **Q10** Replace quick replies with Add more \| Go back | Done | `replaceQuickReplies()` in uiActions.js; eventHandlers handle `__add_more_files__`, `__go_back_to_chat__` |
| Post-upload message | Done | "Files uploaded. You can add more files or go back to the chat." |
| Transition message (Go back) | Done | "Your files are uploaded. Here's where we left off." (Option A) |
| Failure flow: Add more \| Go back | Done | `showFailureMessageAndUnlock()` on FAILURE |
| Bilingual (Nepali) for post-upload / transition | N/A | Chat is English-only; Nepali in utterance_mapping is for testing. REST webchat uses hardcoded EN. |
| Confirm exit-flow (chat order, re-display) | Done | Confirmed: order is `… → [Files uploaded] → [Transition] → [Last bot message] [Original replies]` |

---

## Next Steps

1. **Confirm** the two exit-flow points above (chat order, re-display as new bubble) — **Confirmed.**
2. **Bilingual support**: Not needed — chat is English-only (Nepali in utterance_mapping is for testing). REST_webchat can keep hardcoded EN.
3. **Test** scenarios: mid-form attach, lock during upload, multiple upload rounds, go back → transition + last message + quick replies, then continue conversation.
