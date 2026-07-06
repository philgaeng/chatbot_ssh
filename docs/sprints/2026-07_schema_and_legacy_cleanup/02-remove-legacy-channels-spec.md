# CL-02 — Remove legacy channels (accessible + monitoring-gsheet)

> Workstream: legacy-channels · Branch `cleanup/cl-02-channels` · Independent of CL-01.
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §2. ⚠️ **Naming trap:** `accessible`/`voice`-named backend is REST_webchat's LIVE infra — never delete by name-match.

---

## Goal

Completely remove the two dead frontends `channels/accessible/` and `channels/monitoring-gsheet/` and the backend that **exclusively** serves them, while leaving REST_webchat's live voice/socket/upload infrastructure fully intact.

## The one rule that governs this ticket

> Delete only what the audit lists as **exclusive** to these two channels. Everything named "accessible"/"voice"/"socket" that REST_webchat also uses **stays**. When in doubt, grep for a REST_webchat caller before deleting.

## Steps

1. **Re-verify exclusivity** (line numbers drift): for each item in AUDIT §2c, grep the whole repo for importers/callers and confirm none live in `channels/REST_webchat/`, `ticketing/`, or `backend/orchestrator/`. Confirm the AUDIT §2d "must stay" set still has REST_webchat callers (esp. `app.js` connecting `/accessible-socket.io`, and `voiceChunkUpload.js`/`config.js` hitting `/upload-voice-chunk`).

2. **Delete the frontends:** `channels/accessible/`, `channels/monitoring-gsheet/`.

3. **Delete the exclusive backend:**
   - `backend/api/routers/voice_grievance.py`
   - `backend/services/accessible/` (whole dir)
   - `backend/api/routers/gsheet.py`
   - `backend/api/gsheet_monitoring_api.py`
   - `backend/api/app.py` (dead Flask rollback artifact — confirm again it is launched nowhere; only `uvicorn backend.api.fastapi_app:app` runs)

4. **Un-wire in `backend/api/fastapi_app.py`:** remove `voice_grievance` + `gsheet` from the import (~:45) and their `include_router(...)` (~:122-123). **KEEP** `files.router` (~:120), the websocket imports (~:46), and `app.mount("/accessible-socket.io", socketio_app)` (~:128). App must still start and REST_webchat status/upload must still work.

5. **nginx cleanup:** in all four `deployment/nginx/webchat_rest_compose_{wsl,prod,prod.tls,aws}.conf`, remove `location /gsheet-get-grievances`. **KEEP** `/accessible-socket.io`, `/upload-voice-chunk`, `/upload-voice-complete`.

6. **Env + misc:** remove `GSHEET_BEARER_TOKEN` (`backend/utils/env.grm.example`, `docs/deployment/12_environment_urls.md`, `deployment_environment_urls.*.yaml`, and the two deleted files). Drop `.claudeignore:19,22`. Update docs that describe these channels (`docs/services/08_gsheet_monitoring_service.md`, `docs/deployment/06_integrations.md`, `04_backend.md:58-60`, `README.md`, `docs/README.md`, CLAUDE.md service-boundary lines) — delete or mark retired.

7. **Do NOT touch the DB.** `grievance_voice_recordings`/`grievance_transcriptions` are shared voice infra — they stay (owned by the public stream per CL-01).

## Verification (acceptance)

- [ ] App boots: `uvicorn backend.api.fastapi_app:app` imports cleanly with the routers removed (no `ImportError` from the deleted modules).
- [ ] `grep -rn "voice_grievance\|gsheet_monitoring\|services.accessible\|api.app import\|from backend.api import app" backend/ channels/` returns nothing live.
- [ ] **REST_webchat still works** (the whole point): on the running stack, exercise the recording button (voice-chunk upload → `/upload-voice-complete`) and confirm the Socket.IO `file_status_update`/`task_status` events still arrive over `/accessible-socket.io`. (Browser step — if no automation, drive the endpoints directly and confirm 200 + socket emit; record what was verified vs pending-human.)
- [ ] `pytest tests/` unaffected (no test imported the removed modules; if any did, it targeted dead code — remove/adjust and note it).
- [ ] nginx configs still valid (`nginx -t` if available) with only the gsheet block removed.

## Constraints

- Deletion only — no refactors of the surviving voice/socket/upload code.
- Never remove anything in AUDIT §2d. If a "delete" target turns out to have a live REST_webchat/ticketing caller, STOP and log it — the audit may have drifted.
- `channels/webchat/` (older legacy folder) is out of scope here unless separately confirmed.

## Done means

Both channels + their exclusive backend removed; `fastapi_app.py` un-wired but REST_webchat voice/socket/upload verified intact; nginx/env/docs cleaned; no dead imports; [`PROGRESS.md`](PROGRESS.md) updated with what was verified live vs pending a human browser check.
