# Agent prompt — Chatbot P1 (June5)

You are implementing **Chatbot P1** for the Nepal GRM REST webchat. Work only the four tickets below.

---

## Read first (in order)

1. `docs/sprints/June5/01-chatbot-p1-spec.md` — full spec (authoritative)
2. `docs/sprints/voice-notes-and-ux-feature-brief.md` — locked decisions for CB-03, CB-04, CB-05, CB-07
3. `docs/rest_chatbot/03_frontend_spec.md` and `docs/rest_chatbot/02_flow_spec.md` — existing behavior

---

## Mission

Deliver **CB-03, CB-04, CB-05, CB-07** with minimal diff. Do not start voice notes, map pin, or dust path (P2).

| ID | Summary |
|----|---------|
| **CB-03** | Standard flow: **Close session** only. SEAH: **Close browser** only. Same button behavior as today. |
| **CB-04** | **File another grievance** CTA after submit; clean restart without closing tab. |
| **CB-05** | Rewrite attachment copy (EN + NE); encourage photos, docs, handwritten complaint photo. |
| **CB-07** | Three post-file messages (success → grievance # → follow-ups OK) + top **filed** banner with id. |

---

## You may edit

- `channels/REST_webchat/` — `index.html`, `app.js`, `utterances.js`, `modules/eventHandlers.js`, `modules/uiActions.js`
- `backend/orchestrator/state_machine.py` — only if needed for outro / done / SEAH detection
- `backend/actions/action_outro.py`, `backend/actions/action_submit_grievance.py` — outro messages
- `backend/actions/utils/utterance_mapping_rasa.py` — if server-side strings change
- `tests/orchestrator/test_orchestrator_api.py` — update if message flow changes
- `docs/rest_chatbot/` — short update when behavior changes

**Mirror** `channels/webchat/` only if this repo still deploys it; otherwise note in PROGRESS.

---

## Do not edit

- `ticketing/`, `channels/ticketing-ui/`
- `docker-compose.yml`, `.env`, `requirements.txt` (unless user asks)
- Unrelated refactors

---

## Implementation hints

**CB-03:** Header buttons in `index.html` (`persistent-close-browser`, `persistent-close-session`). Post-upload buttons in `app.js` (~889–906). Handlers in `eventHandlers.js` (`/nav_close_browser_tab`, clear session). Detect SEAH via orchestrator state/custom payload.

**CB-04:** Add quick reply when `next_state === "done"`. Reset `window.grievanceId`, call `/introduce` or `/new_grievance` per `state_machine.py`. Remove tab-close instructions from outro copy.

**CB-05:** Keys under `file_upload` in `utterances.js`; grep `not attached` / `no_grievance`.

**CB-07:** Extend `action_grievance_outro` / submit path for three messages; banner in `app.js` until session reset.

---

## Progress protocol (required)

After each ticket, update `docs/sprints/June5/PROGRESS.md` → **Agent: Chatbot P1**:

- Set ticket status: `in_progress` → `done` (or `blocked` with reason)
- Fill Agent/date, commit hash, Notes
- Check verification boxes for that ticket when manually verified

---

## Definition of done

- [ ] All four tickets `done` in PROGRESS.md
- [ ] CB-03: standard vs SEAH close buttons verified manually
- [ ] CB-04: second grievance gets new id
- [ ] CB-05: EN + NE strings in use
- [ ] CB-07: banner + three messages on standard submit
- [ ] No linter errors in touched files
- [ ] Deviations logged in PROGRESS → **Deviations from spec**

---

## Report back

When finished, summarize:

1. Files changed (paths)
2. How SEAH vs standard is detected
3. Utterance keys added/changed
4. Anything blocked for product (open spec items)

Do not commit unless the user asks.
