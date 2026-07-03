# Agent runbook — HR-07: Webchat robustness

**Branch:** `hardening/hr-07-webchat` off `integration/seah-claude` · **Spec:** [`../05-webchat-robustness-spec.md`](../05-webchat-robustness-spec.md) · Read [`README.md`](README.md) common rules first. All work in `channels/REST_webchat/` (+ hash generation only).

⚠️ **This is the live complainant channel used for SEAH reports. Smallest possible diffs. No refactors, no cleanup, no touching the `window.*` architecture.**

## Mission

Four surgical fixes: persist the session ID so first-time complainants survive a refresh, lock the composer against double-sends, pin the two unpinned CDN scripts with SRI, and remove the one interpolating `innerHTML`.

## Steps

1. **Understand session handling first:** read `app.js` session functions (`getSessionId` ~200-204, `handleClearSessionCommand` ~846, socket room join ~496-505) AND `backend/orchestrator/session_store.py` + `main.py` session-id handling — confirm the server accepts the `temp_`-prefixed IDs as durable keys (it receives them today, so persisting the same string is the compatible move; do not invent a new ID format).
2. **Persist at startup:** one `localStorage.setItem` in `getSessionId()`'s fallback branch. Verify both regimes converge: fresh visit → refresh keeps ID; `/clear_session` still rotates it.
3. **Send lock** per spec §2: `isSending` guard around the text-submit path (`handleMessageSubmit` → `safeSendMessage` ~914). Find where the orchestrator response is processed to clear the flag; add the ~15 s failsafe timeout. Reuse existing disable mechanics (`setInputLocked`) if they fit without side effects on the upload flow.
4. **SRI:** resolve exact current versions — socket.io is already pinned (`4.7.4`); exifr is floating (`@7`) and **must be pinned to the exact resolved version** before hashing. Generate: `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`. Add `integrity` + `crossorigin="anonymous"` to both tags in `index.html`. Load the page and confirm no SRI console errors.
5. **Banner:** replace the `innerHTML` at `app.js` ~301 with `textContent` + `createElement("strong")` composition. Trigger the filed banner and confirm identical rendering.
6. **Static checks:** `grep -n "innerHTML" app.js modules/*.js` (only the safe clear at `uiActions.js` ~212 remains); both CDN tags carry integrity.
7. **Execute the full manual regression sweep** from spec §Manual against the local stack (`http://localhost:8080`) — all seven items including EN/NE switch, upload, voice note, map pin, SEAH route + close controls, status check. Record every result (pass/fail + date) in `../PROGRESS.md`. If ANY regression appears, revert the offending change rather than patching forward.

## Constraints

- Exactly four changes. The voice-chunk race, i18n leaks, dead code, and map-modal localization are **out of scope** — log them in PROGRESS deviations if you're tempted.
- No build tooling, no module restructuring, no new files.
- `channels/webchat/` (legacy folder) — do not touch.

## Done means

All HR-07 checklist boxes ticked in `../PROGRESS.md`, static greps clean, the seven-item manual regression sweep fully recorded with a date.
