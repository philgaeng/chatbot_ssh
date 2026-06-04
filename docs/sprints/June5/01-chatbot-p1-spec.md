# Chatbot P1 — implementation spec

**Sprint:** June5  
**Tickets:** CB-03, CB-04, CB-05, CB-07  
**Brief:** [voice-notes-and-ux-feature-brief.md](../voice-notes-and-ux-feature-brief.md)

---

## Touch map (files you will change)

| Layer | Path | Role |
|-------|------|------|
| Webchat UI | `channels/REST_webchat/index.html` | Persistent Close Browser / Close Session buttons |
| Webchat app | `channels/REST_webchat/app.js` | Post-upload quick replies, filed banner, file-another CTA, orchestrator calls |
| Webchat modules | `channels/REST_webchat/modules/eventHandlers.js` | `clear_window`, `close_browser_tab`, `/nav_*` payloads |
| Webchat modules | `channels/REST_webchat/modules/uiActions.js` | Message append, UI state |
| i18n | `channels/REST_webchat/utterances.js` | `file_upload.*`, button labels |
| Config | `channels/REST_webchat/config.js` | Endpoints (reference only unless new routes) |
| Flow | `backend/orchestrator/state_machine.py` | `done`, post-submit, SEAH vs standard |
| Actions | `backend/actions/action_outro.py` | Grievance outro messages after submit |
| Actions | `backend/actions/action_submit_grievance.py` | Submit + recap (reference for grievance_id in messages) |
| Utterances (server) | `backend/actions/utils/utterance_mapping_rasa.py` | Bot text for outro / file step if server-driven |
| Docs | `docs/rest_chatbot/02_flow_spec.md`, `03_frontend_spec.md` | Update after implementation |

**Mirror (if production still serves legacy path):** `channels/webchat/app.js`, `index.html` — keep in sync or document single canonical channel.

**Read-only reference**

- `docs/rest_chatbot/01_backend_spec.md` — `POST /message`, upload API
- `backend/api/routers/files.py` — `POST /upload-files`
- `tests/orchestrator/test_orchestrator_api.py` — flow regression patterns

---

## CB-03 — Close / exit consolidation

### Goal

One close control per workflow; **no behavior change** to existing actions.

### Locked decisions

| Workflow | Show | Hide |
|----------|------|------|
| Standard grievance | **Close session** | Close browser |
| SEAH (and equivalent sensitive paths) | **Close browser** | Close session |

### Current implementation (audit first)

- Header buttons: `channels/REST_webchat/index.html` lines ~51–56 (`persistent-close-browser`, `persistent-close-session`).
- Post-upload buttons built in `channels/REST_webchat/app.js` (~889–906) — may expose both `close_browser` and `close_session` / `clear_session`.
- Handlers: `channels/REST_webchat/modules/eventHandlers.js` — `clear_window`, `close_browser_tab`, `/nav_close_browser_tab`.

### Tasks

1. Detect **SEAH vs standard** on the client (slot/custom from orchestrator response, or `next_state` / story flag — align with `ENABLE_SEAH_DEDICATED_FLOW` and `form_seah_*` states in `state_machine.py`).
2. Toggle visibility of the two persistent header buttons (CSS `hidden` or conditional render in JS).
3. Filter post-upload quick replies so only the allowed close action appears for the active workflow.
4. Remove redundant bot prompts that ask to “close both” or duplicate exit choices (grep `close_browser`, `clear_session` in actions + utterances).

### Acceptance criteria

- [ ] Standard path: user never sees Close browser in header or end-of-flow buttons.
- [ ] SEAH path: user never sees Close session in header or end-of-flow buttons.
- [ ] Close session still resets session id (`handleClearSessionCommand` / equivalent).
- [ ] Close browser still attempts tab close with fallback message.

---

## CB-04 — File another grievance

### Goal

After filing, user can start a new grievance without closing the browser tab.

### Tasks

1. Add quick reply / button **File another grievance** when `next_state === "done"` (and optionally after `grievance_review` completion) in `app.js` post-submit UI.
2. On click: call orchestrator with `/introduce{...}` (same payload as startup in `app.js` `DOMContentLoaded`) or `/new_grievance` per `state_machine.py` menu transition — **must** clear `window.grievanceId`, cached orchestrator state, and rotate session if product requires fresh session.
3. Remove or replace copy that tells users to close the tab (search outro actions in `action_outro.py` and utterance keys).

### Acceptance criteria

- [ ] CTA visible at end of successful standard + SEAH submit paths.
- [ ] Second grievance receives new `grievance_id` after submit.
- [ ] No stale file-upload lock from previous grievance.

---

## CB-05 — Attachment step copy rewrite

### Goal

Friendlier attachment messaging; encourage photos, documents, and photos of handwritten complaints.

### Tasks

1. Find current strings: `utterances.js` keys under `file_upload` (e.g. `no_grievance`, `post_upload`, `failure`); grep `not attached` in repo.
2. Replace harsh “no file” wording with supportive copy (EN + NE).
3. Add/expand **invitation** copy when upload opens:  
   *"You can now attach pictures or other documents related to your grievance. These will be reviewed by our officer. You may also attach a photo of a handwritten complaint."*
4. If server emits attachment prompts, update matching keys in `utterance_mapping_rasa.py` or form ask actions.

### Acceptance criteria

- [ ] EN and NE strings present and used by `get()` in `app.js`.
- [ ] Voice-detected path (`file_upload.voice_detected`) still works if unchanged.

---

## CB-07 — Post-submit success messaging + filed banner

### Goal

Three clear messages after filing + persistent top-of-chat banner with grievance number.

Users must never see a single “recap wall” bubble that mixes success, ID, details, SMS, and timeline (legacy `create_confirmation_message` in chat). SMS/email may still use the full recap text.

### Two phases (standard grievance)

| Phase | When | Chat messages | Banner |
|-------|------|---------------|--------|
| **A — Filed** | Immediately after `action_submit_grievance` (OTP/contact complete), **before** categorization review | Three separate bubbles (see below) | **Show** — stays visible through review |
| **B — Review complete** | After complainant finishes `grievance_review` (`action_grievance_outro`) | Same three-bubble pattern (reference UX in manual QA) | **Still visible** |

Phase A is the fix for the post-OTP screenshot (one long confirmation). Phase B is the post–“Validate summary” screenshot (already correct).

Orchestrator state after Phase A is `grievance_review` (not `done`). The banner must **not** wait for `done`.

### Message sequence (locked) — each phase uses three separate `utter_message` calls

| # | Content |
|---|---------|
| 1 | Explicit **success** — grievance filed |
| 2 | **Grievance number** (`grievance_id`) prominent (own bubble) |
| 3 | Follow-up may continue (categorization review, attachments, contact) but filing is **already complete** |

Phase A message 3 should mention that **categorization / summary review** may follow. Phase B message 3 focuses on **attachments** (existing outro copy).

### Banner (locked)

- Placement: `#grievance-filed-banner` between chat header and `#messages` in `index.html`.
- Copy: status **Grievance filed** + grievance number (EN + NE via `utterances.js`).
- **Show:** on `grievance_filed` custom event from server (emit from `action_submit_grievance` and SEAH submit) and whenever client already knows `grievance_id` in post-filed states (`grievance_review`, `done`).
- **Hide:** session reset, file another grievance, clear session.

### Tasks

1. **Server — submit:** Replace in-chat `create_confirmation_message` with three utterances in `action_submit_grievance.py`; keep full recap for SMS only. Emit `json_message` `event_type: grievance_filed` with `grievance_id`.
2. **Server — outro:** Keep `action_grievance_outro` three messages after review (Phase B).
3. **Client:** Show banner on `grievance_filed` and for `next_state` in `grievance_review` \| `done` when `window.grievanceId` is set; do not require `done` only.
4. Coordinate attachment copy with **CB-05** (no “not yet filed” wording).

### Acceptance criteria

- [ ] Banner visible from **submit** (Phase A) through review until session reset or file another.
- [ ] Phase A: three separate chat messages after OTP/submit (no recap wall).
- [ ] Phase B: three messages after review confirm (unchanged UX target).
- [ ] SEAH path: equivalent success + id + banner on submit.

---

## Testing checklist (P1)

- [ ] Manual: new grievance → attach file → done → file another → second id.
- [ ] Manual: SEAH intake — only Close browser shown.
- [ ] Manual: standard intake — only Close session shown.
- [ ] `tests/orchestrator/test_orchestrator_api.py` updated if outro message count changes.

---

## Out of scope (P1)

- Voice note recording (CB-01, P2)
- Map pin, EXIF, dust path (P2)
- Ticketing portal changes
