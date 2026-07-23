# HR-07 — Webchat Robustness (session persistence, send lock, SRI, banner XSS)

> Workstream E · Branch `hardening/hr-07-webchat` · Independent.
> All paths under `channels/REST_webchat/`. Evidence: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §2.5 + REST_webchat review. Re-locate line numbers before editing. **This is the live complainant channel — smallest possible diffs, no refactors.**

## Problems (verified)

1. **Session ID never persisted on first visit** — `window.getSessionId` (`app.js:200-204`) returns `localStorage.getItem(key) || tempSessionId`; the only `setItem` on `rasa_session_id` is in `handleClearSessionCommand` (`app.js:846`). Fresh user + mid-conversation refresh ⇒ new `temp_…` ID ⇒ conversation orphaned. Every first-time complainant loses their session on refresh.
2. **Double-send** — no composer lock for in-flight text; `window.safeSendMessage(message)` is fire-and-forget (`app.js:914`). (Quick replies and uploads are already guarded.)
3. **Unpinned CDN scripts on a PII/SEAH-collecting page** — `cdn.socket.io/4.7.4/socket.io.min.js` (`index.html:21`) and `cdn.jsdelivr.net/npm/exifr@7` (`index.html:152`) have **no `integrity` attribute** (Leaflet already has SRI — `index.html:11-12,151`).
4. **One interpolating `innerHTML`** — `app.js:301`: `` grievanceFiledBannerText.innerHTML = `${label} <strong>${grievanceId}</strong>` `` with server-supplied `grievanceId` (untrusted per threat model). Everything else already renders via `textContent`.

## Change

1. **Persist session at startup**: in `getSessionId()`'s fallback branch, `localStorage.setItem(key, tempSessionId)` before returning (drop the `temp_` prefix or keep it — must remain compatible with whatever the orchestrator session store accepts; check `session_store.py` key handling). Result: refresh keeps the same session ID both before and after the first `/clear_session`. Also verify the Socket.IO room join (`app.js:496-505`) uses the now-stable ID.
2. **In-flight send lock**: guard `handleMessageSubmit` with an `isSending` flag (set before `safeSendMessage`, cleared in its completion/error paths — make the call awaitable or clear on the response handler). Disable the send button + Enter path while locked; re-enable on response or after a hard timeout (~15 s) so a lost response can't brick the composer. Reuse the existing `setInputLocked` mechanics from the upload path where possible.
3. **SRI**: pin exifr to an exact version (`exifr@7.x.y` — resolve the current concrete version) and add `integrity` + `crossorigin="anonymous"` to both scripts. Generate hashes: `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`. Verify the exact URLs stay byte-stable (versioned paths, not `@7` floating — floating tags cannot be SRI-pinned).
4. **Banner XSS**: replace `app.js:301` with `textContent` composition (`label` text node + `<strong>` element whose `textContent = grievanceId`). Visual output identical.

**Out of scope** (logged for Tier-2, do not do now): voice-chunk ordering race, i18n leaks, map-picker localization, dead `updateTaskStatus` code.

## Tests (acceptance)

No JS test infra exists for this channel and this ticket does not add one — verification is a scripted manual pass plus one static check:

- [ ] Static: `grep -n "innerHTML" app.js modules/*.js` ⇒ only the safe clear (`uiActions.js:212`) remains.
- [ ] Static: both CDN `<script>` tags have `integrity` + `crossorigin`; versions exact.

## Manual verification (execute all, record in PROGRESS — this is the channel's regression suite)

Run against the local compose stack (`http://localhost:8080` per DOCKER.md):
- [ ] **Fresh-visit persistence**: clear site data → load webchat → answer 2–3 intake turns → hard refresh ⇒ same `rasa_session_id` in localStorage (DevTools), conversation continues server-side (next message doesn't restart intro).
- [ ] **Clear-session flow**: `/clear_session` still issues a fresh ID and starts over.
- [ ] **Send lock**: type a message, press Enter twice fast ⇒ one user bubble, one orchestrator turn (check network tab: one `POST /message`). Composer re-enables after the reply; after a simulated dead backend (stop orchestrator), composer re-enables after the timeout with the error banner.
- [ ] **SRI**: page loads cleanly (no console SRI errors); temporarily corrupt one hash ⇒ script refuses to load (then restore).
- [ ] **Banner**: complete a grievance ⇒ filed banner shows the ID bold, renders as text (inspect DOM: no parsed HTML); no visual change.
- [ ] **Full regression sweep** (nothing else broke): EN + NE language switch, quick replies, file upload (image), voice note record/send, map pin flow, SEAH route entry + persistent close controls, status-check flow.
