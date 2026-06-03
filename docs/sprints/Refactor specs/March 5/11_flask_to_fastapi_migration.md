# Spec 11: Migrate Backend from Flask to FastAPI

## Purpose

Migrate the current Flask backend (`backend/api/app.py` and its blueprints) to FastAPI so the project uses a single stack. This simplifies troubleshooting, improves integration between the orchestrator (conversation) and file/grievance APIs (e.g. user interacts with the bot when adding files), and allows new features (e.g. Messaging API) to be built once on FastAPI.

**Context:** The orchestrator is already FastAPI ([01_orchestrator.md](01_orchestrator.md)). This spec covers only the **backend** (files, grievance CRUD, Socket.IO, gsheet, voice). After migration, both can be served from one ASGI app or remain separate processes; deployment and nginx can stay on the same URL paths.

**Implementation:** The work is split across **Agent 8A–8D** in [05_agent_specs_spike.md](05_agent_specs_spike.md): 8A (skeleton + grievance), 8B (file server), 8C (Socket.IO), 8D (voice, gsheet, deprecation, tests). 8A first; 8B and 8C can run in parallel; 8D last.

---

## Current Flask Backend (Source of Truth)

### Entry point

- **File:** `backend/api/app.py`
- **Run:** `python backend/api/app.py` (Werkzeug + Flask-SocketIO) or gunicorn with gevent/eventlet for production.

### Components to migrate

| Component | Location | Role |
|-----------|----------|------|
| **File server API** | `backend/api/channels_api.py` (`FileServerAPI`) | Upload files, list/download files, task-status, grievance-review, generate-ids, test-db. |
| **Grievance API** | `backend/api/app.py` (inline routes) | `POST /api/grievance/<id>/status`, `GET /api/grievance/<id>`, `GET /api/grievance/statuses`; calls `send_status_update_notifications` (uses `Messaging` in-process). |
| **Socket.IO** | `backend/api/websocket_utils.py` | Path `/accessible-socket.io`; Redis message queue; events: `connect`, `join`, `disconnect`, `status_update`, `another_event`, `join_room`; `emit_status_update_accessible` used by file server. |
| **Voice / accessible** | `backend/services/accessible/voice_grievance.py` (`voice_grievance_bp`) | `POST /accessible-file-upload`, `GET /grievance-status/<id>`, `POST /submit-grievance`. |
| **Gsheet monitoring** | `backend/api/gsheet_monitoring_api.py` | `GET /gsheet-get-grievances` (Bearer auth). |
| **Health** | `backend/api/app.py` | `GET /health` → `'OK', 200`. |

### URL surface (must be preserved)

Clients (REST webchat, nginx, accessible UI) depend on these paths. Do not change them.

- `GET /health`
- `POST /upload-files`
- `GET /files/<grievance_id>`, `GET /download/<file_id>`, `GET /file-status/<file_id>`, `GET /files/<filename>`
- `GET /grievance-review/<grievance_id>`, `POST /grievance-review/<grievance_id>`
- `POST /task-status`
- `POST /generate-ids`, `GET /test-db`, `POST /test-upload`
- `POST /api/grievance/<grievance_id>/status`, `GET /api/grievance/<grievance_id>`, `GET /api/grievance/statuses`
- `POST /accessible-file-upload`, `GET /grievance-status/<grievance_id>`, `POST /submit-grievance`
- `GET /gsheet-get-grievances`
- Socket.IO at path `/accessible-socket.io`

---

## Target: FastAPI Backend

### Design choices

1. **One FastAPI app** for the backend (no Flask). Use `APIRouter` for each former blueprint; include with appropriate prefixes where needed.
2. **Same URL paths** as above so nginx and frontends stay unchanged.
3. **Socket.IO:** Use `python-socketio` ASGI app (same approach as orchestrator’s `Mount("/socket.io", app=socket_app)`). Mount at `/accessible-socket.io`. Keep Redis as message queue if used today.
4. **Shared services:** Keep using `FileServerCore`, `GrievanceDbManager`, `Messaging` (or future Messaging API client) as plain Python; inject or instantiate in FastAPI dependency or router code.
5. **Orchestrator:** Can remain a separate uvicorn process (current setup) or be mounted under the same ASGI app (e.g. under `/message`). This spec does not require merging them; only the backend is migrated.

### Capability mapping (Flask → FastAPI)

| Flask | FastAPI |
|-------|---------|
| `@app.route`, Blueprint | `APIRouter`, `@router.get` / `@router.post` |
| `request.get_json()`, `request.form`, `request.files` | Pydantic bodies, `File()`, `UploadFile`, `Form()` |
| `jsonify(...)` | Return dict or Pydantic model; FastAPI serializes JSON |
| `request.args`, path params | Query/path parameters (typed) |
| CORS | `CORSMiddleware` |
| Flask-SocketIO | `python-socketio` ASGI app mounted with `Mount("/accessible-socket.io", app=socket_app)` |
| Run | `uvicorn backend.api.fastapi_app:app` (or chosen module) |

---

## Implementation Plan

### Phase 1: FastAPI app skeleton and routing

- Create `backend/api/fastapi_app.py` (or `backend/api/main_fastapi.py`) as the ASGI application.
- Add CORS middleware.
- Add `GET /health`.
- Wire one router (e.g. grievance-only) and verify with a single endpoint. Run with `uvicorn backend.api.fastapi_app:app --port 5001` and keep Flask runnable in parallel during migration.

### Phase 2: Migrate grievance API

- New module: `backend/api/routers/grievance.py` (or equivalent). Implement:
  - `POST /api/grievance/{grievance_id}/status`
  - `GET /api/grievance/{grievance_id}`
  - `GET /api/grievance/statuses`
- Use Pydantic models for request/response where helpful; keep `send_status_update_notifications` logic (in-process `Messaging` for now; can switch to Messaging API later).
- Include router in the FastAPI app with no prefix (paths already include `/api/grievance`).
- Test: same behaviour as Flask for these three endpoints.

### Phase 3: Migrate file server (channels_api)

- New module: `backend/api/routers/files.py` (or keep class-based structure with `APIRouter`). Implement all routes from `FileServerAPI`:
  - `/upload-files`, `/files/<grievance_id>`, `/download/<file_id>`, `/file-status/<file_id>`, `/grievance-review/<grievance_id>` (GET/POST), `/files/<filename>`, `/task-status`, `/generate-ids`, `/test-db`, `/test-upload`.
- File upload in FastAPI: `File()`, `UploadFile`, `Form()` for `grievance_id` and optional fields. Reuse `FileServerCore` and task invocation (e.g. Celery) as-is.
- `emit_status_update_accessible`: either call into a shared Socket.IO emit helper used by the ASGI Socket.IO app, or keep a reference to the socket server and emit from the router (pattern depends on how `python-socketio` is set up).
- Include router; preserve path prefixes (none for these routes in current app).
- Test: upload flow and file listing from REST webchat.

### Phase 4: Socket.IO ASGI app

- Create or adapt a `python-socketio` ASGI app for the same events and path `/accessible-socket.io`. Use Redis as message queue if currently used.
- Implement handlers: `connect`, `join`, `disconnect`, `status_update`, `another_event`, `join_room` (and error handler). Match current payload and room behaviour.
- Expose a function equivalent to `emit_status_update_accessible` so the file router can trigger status updates to the correct room.
- In the FastAPI app, mount the Socket.IO ASGI app: `app.mount("/accessible-socket.io", socket_asgi_app)` (or use a Starlette `Mount` if the app is built with Starlette routing). Ensure the mount path matches exactly what nginx and clients use.
- Test: accessible UI or any client that uses Socket.IO for status updates.

### Phase 5: Voice and gsheet routers

- **Voice:** `backend/api/routers/voice_grievance.py` (or equivalent). Routes: `POST /accessible-file-upload`, `GET /grievance-status/<grievance_id>`, `POST /submit-grievance`. Reuse existing business logic from `backend/services/accessible/voice_grievance.py`; replace Flask `request`/`jsonify` with FastAPI.
- **Gsheet:** `backend/api/routers/gsheet.py` (or keep in gsheet_monitoring_api with an `APIRouter`). Route: `GET /gsheet-get-grievances` with Bearer auth. Reuse existing auth and data logic.
- Include both routers in the FastAPI app.
- Test: voice flow and gsheet endpoint.

### Phase 6: Deprecate Flask backend

- Update startup scripts (e.g. `scripts/rest_api/launch_servers_celery.sh`) and docs to run the FastAPI backend (uvicorn) instead of Flask for the backend port (e.g. 5001).
- Keep `backend/api/app.py` (Flask) in the repo for reference or rollback; add a comment or README that the live backend is FastAPI.
- Update [BACKEND.md](../../BACKEND.md) and any deployment/nginx notes to reference the FastAPI app and `uvicorn` command.

---

## Deliverables

- `backend/api/fastapi_app.py` – FastAPI app with CORS, health, and all routers mounted.
- `backend/api/routers/` (or equivalent) – grievance, files, voice_grievance, gsheet (each with an `APIRouter`).
- Socket.IO ASGI app (e.g. in `backend/api/websocket_fastapi.py` or alongside existing `websocket_utils.py`) mounted at `/accessible-socket.io`.
- Same URL surface and response shapes as the current Flask backend.
- Startup/docs updated to use uvicorn for the backend; Flask entry point deprecated for production.

---

## Checklist

- [ ] FastAPI app created; `GET /health` returns 200.
- [ ] Grievance API (3 endpoints) migrated and tested.
- [ ] File server routes (upload-files, files, download, file-status, grievance-review, task-status, generate-ids, test-db, test-upload) migrated and tested.
- [ ] Socket.IO ASGI app mounted at `/accessible-socket.io`; events and `emit_status_update_accessible` behaviour preserved.
- [ ] Voice routes (accessible-file-upload, grievance-status, submit-grievance) migrated and tested.
- [ ] Gsheet route (gsheet-get-grievances) migrated and tested.
- [ ] REST webchat file upload and grievance_id flow work against FastAPI backend.
- [ ] Scripts and docs updated to run FastAPI backend; Flask marked deprecated for production.

---

## Dependencies

- **Existing:** [01_orchestrator.md](01_orchestrator.md) (orchestrator already FastAPI). [BACKEND.md](../../BACKEND.md) (API overview, Flask vs FastAPI).
- **Libraries:** FastAPI, uvicorn, python-socketio (ASGI mode), Pydantic. Remove or stop using Flask/Flask-SocketIO for the backend once migration is verified.
- **No change** to orchestrator, Rasa SDK actions, or REST webchat frontend beyond ensuring they still call the same backend URLs.

---

## Notes

- **Messaging API:** This spec does not add the Messaging API; it only migrates the current in-process `Messaging` usage into the FastAPI backend. Adding `POST /api/messaging/send-sms` (and similar) is a follow-up.
- **Orchestrator mount:** Optionally, the same ASGI app can mount the orchestrator (e.g. at `/`) so one process serves both; that can be a separate small step after this spec is done.
- **Tests:** Add or adjust tests in `tests/` to call the FastAPI app (e.g. `TestClient(backend.api.fastapi_app.app)`) for the migrated endpoints.
