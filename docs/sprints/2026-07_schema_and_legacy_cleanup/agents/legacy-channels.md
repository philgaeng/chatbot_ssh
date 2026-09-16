# Agent runbook — CL-02: Remove legacy channels

**Branch:** `cleanup/cl-02-channels` off the agreed base · **Model:** Opus (high effort — deletion-safety on a live channel) · **Spec:** [`../02-remove-legacy-channels-spec.md`](../02-remove-legacy-channels-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §2 first.

⚠️ **Naming trap:** backend named `accessible`/`voice`/`socket` is REST_webchat's LIVE infrastructure. Delete ONLY the audit's "exclusive" set. Never delete by name-match.

## Mission

Completely remove `channels/accessible/` + `channels/monitoring-gsheet/` and the backend that exclusively serves them, leaving REST_webchat's voice/socket/upload paths fully intact.

## Steps

1. **Re-verify exclusivity** (AUDIT §2c): for each delete target, grep the repo for importers/callers; confirm none in `channels/REST_webchat/`, `ticketing/`, `backend/orchestrator/`. Confirm the §2d "must stay" set still has REST_webchat callers (`app.js` → `/accessible-socket.io`; `voiceChunkUpload.js`/`config.js` → `/upload-voice-chunk`).
2. **Delete frontends:** `channels/accessible/`, `channels/monitoring-gsheet/`.
3. **Delete exclusive backend:** `backend/api/routers/voice_grievance.py`, `backend/services/accessible/` (whole dir), `backend/api/routers/gsheet.py`, `backend/api/gsheet_monitoring_api.py`, `backend/api/app.py` (dead Flask artifact — re-confirm it's launched nowhere).
4. **Un-wire `backend/api/fastapi_app.py`:** remove `voice_grievance` + `gsheet` from import (~:45) and their `include_router` (~:122-123). **KEEP** `files.router` (~:120), websocket imports (~:46), `app.mount("/accessible-socket.io", …)` (~:128).
5. **nginx:** remove `location /gsheet-get-grievances` in all four `webchat_rest_compose_*.conf`. KEEP `/accessible-socket.io`, `/upload-voice-chunk`, `/upload-voice-complete`.
6. **Env/misc:** remove `GSHEET_BEARER_TOKEN` (env.grm.example, `12_environment_urls.md`, `deployment_environment_urls.*.yaml`); drop `.claudeignore:19,22`; update/mark-retired the channel docs (`08_gsheet_monitoring_service.md`, `06_integrations.md`, `04_backend.md`, READMEs, CLAUDE.md boundary lines).
7. **Do NOT touch the DB** — `grievance_voice_recordings`/`grievance_transcriptions` stay (CL-01 owns them).

## Verify (acceptance)
- App imports clean: `uvicorn backend.api.fastapi_app:app` starts with routers removed (no ImportError).
- `grep -rn "voice_grievance\|gsheet_monitoring\|services.accessible\|backend.api.app\|from backend.api import app" backend/ channels/` → nothing live.
- **REST_webchat still works**: exercise the recording button (voice-chunk → `/upload-voice-complete`) + confirm Socket.IO `file_status_update`/`task_status` over `/accessible-socket.io`. Browser step → if no automation, drive the endpoints directly (200 + socket emit) and record live-verified vs pending-human.
- `pytest tests/` unaffected; nginx configs valid (`nginx -t` if available).

## Constraints
- Deletion only, no refactor of surviving code. Never remove AUDIT §2d. If a delete target has a live caller, STOP + log. `channels/webchat/` out of scope.

## Done means
Both channels + exclusive backend removed; `fastapi_app.py` un-wired but REST_webchat voice/socket/upload verified intact; nginx/env/docs cleaned; no dead imports; PROGRESS updated (live-verified vs pending-human).
