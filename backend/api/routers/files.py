"""
File server API router. Same URL surface and behaviour as FileServerAPI in channels_api.py.
Uses FileServerCore and Celery; emit_status_update_accessible is stubbed until 8C wires the Socket.IO helper.
"""

import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

# In-memory store for file upload failures (key: file_id, value: {error, timestamp})
# So GET /file-status/{file_id} can return FAILURE when the Celery task failed. TTL 1 hour.
_FILE_FAILURES: Dict[str, Dict[str, Any]] = {}
_FILE_FAILURE_TTL_SEC = 3600

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from backend.config.constants import MAX_FILE_SIZE
from backend.config.database_constants import get_task_status_codes
from backend.services.database_services.postgres_services import db_manager
from backend.services.file_server_core import FileServerCore
from backend.shared_functions.utterance_mapping_server import get_utterance
from backend.task_queue.registered_tasks import process_file_upload_task
from werkzeug.utils import secure_filename

status_codes = get_task_status_codes()
SUCCESS = status_codes["SUCCESS"]
FAILED = status_codes["FAILED"]
RETRYING = status_codes["RETRYING"]
STARTED = status_codes["STARTED"]

# Core instance (same as Flask backend)
from backend.config.constants import ALLOWED_EXTENSIONS

_upload_folder = os.getenv("UPLOAD_FOLDER", "uploads")
file_server_core = FileServerCore(
    upload_folder=_upload_folder,
    allowed_extensions=ALLOWED_EXTENSIONS,
)

router = APIRouter()

# --- Emit stub: 8C can replace this with the real Socket.IO emit ---
_emit_status_update_accessible: Optional[Callable[[str, str, dict], None]] = None


def get_emit_status_update_accessible() -> Callable[[str, str, dict], None]:
    """Return the emit function for task-status updates. Stub logs until 8C wires real emit."""
    if _emit_status_update_accessible is not None:
        return _emit_status_update_accessible

    def _stub_emit(session_id: str, status: str, message: dict) -> None:
        import logging
        logging.getLogger(__name__).debug(
            "emit_status_update_accessible (stub) session_id=%s status=%s message=%s",
            session_id, status, message,
        )

    return _stub_emit


def set_emit_status_update_accessible(fn: Callable[[str, str, dict], None]) -> None:
    """Call from 8C to wire the real Socket.IO emit. e.g. files.set_emit_status_update_accessible(real_emit)."""
    global _emit_status_update_accessible
    _emit_status_update_accessible = fn


# --- Helpers (mirror channels_api) ---


def _get_language_code(request: Request) -> str:
    return request.query_params.get("language", "en")


def _extract_session_type_from_grievance_id(grievance_id: str) -> str:
    if not grievance_id or "-" not in grievance_id:
        return "unknown"
    suffix = grievance_id.split("-")[-1]
    if len(suffix) == 1:
        if suffix == "A":
            return "accessible"
        if suffix == "B":
            return "bot"
    return "unknown"


def _validate_files(
    core: FileServerCore,
    files: List[UploadFile],
    grievance_id: str,
) -> tuple:
    """Returns (uploaded_files, oversized_files, wrong_extensions_list)."""
    uploaded_files = []
    oversized_files = []
    wrong_extensions_list = []

    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            content = file.file.read()
            file_size = len(content)
            file.file.seek(0)

            if file_size > MAX_FILE_SIZE:
                oversized_files.append(filename)
                continue
            ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else None
            if not ext:
                wrong_extensions_list.append({"file_name": filename, "extension": "None"})
                continue
            if ext not in core.allowed_extensions:
                wrong_extensions_list.append({"file_name": filename, "extension": ext})
                continue

            file_id = str(uuid.uuid4())
            grievance_dir = os.path.join(core.upload_folder, grievance_id)
            os.makedirs(grievance_dir, exist_ok=True)
            file_path = os.path.join(grievance_dir, filename)
            with open(file_path, "wb") as f:
                f.write(content)

            metadata = core.get_file_metadata(file_path)
            file_data = {
                "file_id": file_id,
                "file_name": filename,
                "file_path": file_path,
                "file_size": file_size,
                **metadata,
            }
            uploaded_files.append(file_data)

    return uploaded_files, oversized_files, wrong_extensions_list


# --- Routes (same paths as FileServerAPI) ---


@router.get("/")
def health_check():
    """Health check for file server."""
    return JSONResponse({"status": "ok", "message": "File server is running"})


@router.get("/test-db")
def test_db():
    """Test database connectivity."""
    try:
        file_server_core.log_event(event_type=STARTED, details={})
        connection = db_manager.get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'grievances'"
        )
        tables_count = cursor.fetchone()[0]
        grievance_count = 0
        if tables_count > 0:
            cursor.execute("SELECT COUNT(*) FROM grievances")
            grievance_count = cursor.fetchone()[0]
        test_id = db_manager.generate_id(type="grievance_id")
        connection.close()

        file_server_core.log_event(
            event_type=SUCCESS,
            details={
                "tables_exist": tables_count > 0,
                "grievance_count": grievance_count,
                "test_grievance_id": test_id,
            },
        )
        return JSONResponse({
            "status": SUCCESS,
            "message": "Database connection successful",
            "tables_exist": tables_count > 0,
            "grievance_count": grievance_count,
            "test_grievance_id": test_id,
        })
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        return JSONResponse(
            {"status": FAILED, "message": f"Database connection error: {str(e)}"},
            status_code=500,
        )


@router.post("/generate-ids")
async def generate_ids(request: Request):
    """Generate grievance_id and complainant_id."""
    try:
        file_server_core.log_event(
            event_type=STARTED, details={"method": "POST", "endpoint": "/generate-ids"}
        )
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        if not body:
            body = {}
        province = body.get("province", "KO")
        district = body.get("district", "JH")
        grievance_id = db_manager.generate_id(
            type="grievance_id", province=province, district=district
        )
        complainant_id = db_manager.generate_id(
            type="complainant_id", province=province, district=district
        )
        file_server_core.log_event(
            event_type=SUCCESS,
            details={
                "grievance_id": grievance_id,
                "complainant_id": complainant_id,
                "province": province,
                "district": district,
            },
        )
        return JSONResponse({
            "status": SUCCESS,
            "grievance_id": grievance_id,
            "complainant_id": complainant_id,
            "province": province,
            "district": district,
        })
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        return JSONResponse(
            {"status": FAILED, "message": f"Failed to generate IDs: {str(e)}"},
            status_code=500,
        )


@router.post("/upload-files")
async def upload_files(
    request: Request,
    grievance_id: str = Form(...),
    rasa_session_id: Optional[str] = Form(None),
    flask_session_id: Optional[str] = Form(None),
    language: Optional[str] = Query(None),
    files: List[UploadFile] = File(..., alias="files[]"),
):
    """Handle file uploads for a grievance. Reuses FileServerCore and Celery task."""
    language_code = language or _get_language_code(request)
    file_server_core.log_event(event_type=STARTED, details={"method": "POST", "endpoint": "/upload-files"})
    source = _extract_session_type_from_grievance_id(grievance_id)
    file_server_core.log_event(
        event_type=STARTED,
        details={
            "grievance_id": grievance_id,
            "source": source,
            "rasa_session_id": rasa_session_id,
            "flask_session_id": flask_session_id,
        },
    )

    try:
        if not grievance_id:
            file_server_core.log_event(event_type=FAILED, details={"error": "No grievance_id provided"})
            error_message = get_utterance("file_server", "upload_files", 1, language_code)
            return JSONResponse({"error": error_message}, status_code=400)

        if not files:
            file_server_core.log_event(event_type=FAILED, details={"error": "No files in files[] list"})
            error_message = get_utterance("file_server", "upload_files", 4, language_code)
            return JSONResponse({"error": error_message}, status_code=400)

        uploaded_files, oversized_files, wrong_extensions_list = _validate_files(
            file_server_core, files, grievance_id
        )

        if not uploaded_files:
            file_server_core.log_event(event_type=FAILED, details={"error": "All files were invalid"})
            return JSONResponse(
                {
                    "error": "All files were invalid",
                    "wrong_extensions_list": wrong_extensions_list,
                    "oversized_files": oversized_files,
                    "max_file_size": MAX_FILE_SIZE,
                },
                status_code=400,
            )

        file_data = uploaded_files[0]
        result = process_file_upload_task.delay(
            grievance_id=grievance_id,
            file_data=file_data,
            session_id=flask_session_id,
        )

        return JSONResponse(
            {
                "status": STARTED,
                "flask_session_id": flask_session_id,
                "message": "Files are being processed - those listed in oversized_files and wrong_extensions_list will be ignored",
                "files": [f["file_id"] for f in uploaded_files],
                "oversized_files": oversized_files,
                "wrong_extensions_list": wrong_extensions_list,
                "max_file_size": MAX_FILE_SIZE,
                "task_id": result.id,
            },
            status_code=202,
        )
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        error_message = get_utterance("file_server", "upload_files", 6, language_code)
        return JSONResponse(
            {"error": error_message, "detail": str(e)},
            status_code=500,
        )


@router.get("/files/{item}")
def get_files_or_file(item: str, request: Request):
    """GET /files/{grievance_id} lists files; GET /files/{filename} serves file. Same path in Flask (list registered first)."""
    # If it looks like a grievance_id (e.g. GR-...), treat as list; else try serve by filename
    looks_like_grievance_id = item.startswith("GR-") and "-" in item
    if looks_like_grievance_id:
        try:
            language_code = _get_language_code(request)
            session_type = _extract_session_type_from_grievance_id(item)
            file_server_core.log_event(
                event_type=STARTED,
                details={"grievance_id": item, "session_type": session_type},
            )
            files = db_manager.get_grievance_files(item)
            file_server_core.log_event(
                event_type=SUCCESS,
                details={"grievance_id": item, "file_count": len(files), "session_type": session_type},
            )
            return JSONResponse({"files": files})
        except Exception as e:
            file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
            language_code = _get_language_code(request)
            error_message = get_utterance("file_server", "get_files", 1, language_code)
            return JSONResponse({"error": error_message}, status_code=500)
    # Serve file by name from upload_folder
    try:
        language_code = _get_language_code(request)
        file_server_core.log_event(event_type=STARTED, details={"file_name": item})
        path = os.path.join(file_server_core.upload_folder, item)
        if not os.path.isfile(path):
            return JSONResponse({"error": "File not found"}, status_code=404)
        file_server_core.log_event(event_type=SUCCESS, details={"file_name": item})
        return FileResponse(path, filename=item)
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        return JSONResponse({"error": str(e)}, status_code=404)


@router.get("/download/{file_id}")
def download_file(file_id: str, request: Request):
    """Download a specific file."""
    try:
        language_code = _get_language_code(request)
        file_server_core.log_event(event_type=STARTED, details={"file_id": file_id})
        file_data = db_manager.file.get_file_by_id(file_id)
        if file_data and os.path.exists(file_data["file_path"]):
            file_server_core.log_event(
                event_type=SUCCESS,
                details={"file_id": file_id, "file_name": file_data["file_name"]},
            )
            return FileResponse(
                file_data["file_path"],
                filename=file_data["file_name"],
                media_type="application/octet-stream",
            )
        return JSONResponse({"error": "File not found"}, status_code=404)
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        return JSONResponse({"error": "Internal server error"}, status_code=500)


def _prune_expired_file_failures() -> None:
    """Remove file failure entries older than TTL."""
    now = time.time()
    expired = [fid for fid, v in _FILE_FAILURES.items() if (now - v.get("timestamp", 0)) > _FILE_FAILURE_TTL_SEC]
    for fid in expired:
        del _FILE_FAILURES[fid]


@router.get("/file-status/{file_id}")
def get_file_status(file_id: str, request: Request):
    """Get the processing status of a file."""
    try:
        language_code = _get_language_code(request)
        file_server_core.log_event(event_type=STARTED, details={"file_id": file_id})
        _prune_expired_file_failures()
        if file_id in _FILE_FAILURES:
            failure = _FILE_FAILURES[file_id]
            file_server_core.log_event(
                event_type=FAILED, details={"file_id": file_id, "error": failure.get("error")}
            )
            return JSONResponse(
                {"status": "FAILURE", "error": failure.get("error", "Upload failed")}
            )
        if db_manager.file.is_file_saved(file_id):
            file_server_core.log_event(
                event_type=SUCCESS, details={"file_id": file_id, "status": SUCCESS}
            )
            return JSONResponse(
                {"status": SUCCESS, "message": "File is saved in the database"}
            )
        file_server_core.log_event(event_type="not_found", details={"file_id": file_id})
        return JSONResponse(
            {"status": STARTED, "message": "File is not yet saved"}
        )
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@router.get("/grievance-review/{grievance_id}")
def get_grievance_review(grievance_id: str, request: Request):
    """Get all review data for a grievance."""
    try:
        language_code = _get_language_code(request)
        file_server_core.log_event(event_type=STARTED, details={"grievance_id": grievance_id})
        data = db_manager.get_grievance_review_data(grievance_id)
        if not data:
            file_server_core.log_event(
                event_type=FAILED, details={"grievance_id": grievance_id, "error": "Not found"}
            )
            return JSONResponse({"error": "Not found"}, status_code=404)
        file_server_core.log_event(event_type=SUCCESS, details={"grievance_id": grievance_id})
        return JSONResponse(data)
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@router.post("/grievance-review/{grievance_id}")
async def update_grievance_review(grievance_id: str, request: Request):
    """Update review data for a grievance."""
    try:
        language_code = _get_language_code(request)
        file_server_core.log_event(event_type=STARTED, details={"grievance_id": grievance_id})
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            file_server_core.log_event(event_type=FAILED, details={"error": "Request must be JSON"})
            return JSONResponse({"error": "Request must be JSON"}, status_code=400)
        data = await request.json()
        success = db_manager.update_grievance_review_data(grievance_id, data)
        if not success:
            file_server_core.log_event(event_type=FAILED, details={"error": "Update failed"})
            return JSONResponse({"error": "Update failed"}, status_code=400)
        file_server_core.log_event(event_type=SUCCESS, details={"grievance_id": grievance_id})
        return JSONResponse({"message": "Update successful"})
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@router.post("/test-upload")
async def test_upload(request: Request):
    """Test endpoint to verify request handling."""
    try:
        form_data = {}
        files_list = []
        ct = request.headers.get("content-type", "")
        if "multipart/form-data" in ct:
            form = await request.form()
            if "files[]" in form:
                f = form["files[]"]
                if hasattr(f, "filename"):
                    files_list = [f.filename] if f.filename else []
                else:
                    files_list = [getattr(x, "filename", "") for x in (f if isinstance(f, list) else [f])]
        file_server_core.log_event(
            event_type="test_upload",
            details={"method": request.method, "files": files_list},
        )
        return JSONResponse({
            "status": "received",
            "message": "Test upload endpoint received request",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/task-status")
async def task_status_update(request: Request):
    """Receive task status updates and emit websocket messages. Uses stub emit until 8C wires Socket.IO."""
    try:
        data = await request.json()
        if not data:
            return JSONResponse({"error": "No data provided"}, status_code=400)

        grievance_id = data.get("grievance_id")
        flask_session_id = data.get("flask_session_id")
        source = "A" if grievance_id and str(grievance_id).endswith("A") else "B"
        status = data.get("status")
        task_data = data.get("data", {})

        if not status:
            return JSONResponse({"error": "Missing required field: status"}, status_code=400)
        if not grievance_id and not flask_session_id:
            return JSONResponse(
                {"error": "Missing required field: grievance_id or flask_session_id"},
                status_code=400,
            )

        file_server_core.log_event(
            event_type="task_status_update",
            details={
                "grievance_id": grievance_id,
                "flask_session_id": flask_session_id,
                "status": status,
                "data": task_data,
                "source": source,
            },
        )

        # Record file upload failures so GET /file-status/{file_id} can return FAILURE to the client
        if status == "FAILED" and task_data.get("file_id"):
            _FILE_FAILURES[task_data["file_id"]] = {
                "error": task_data.get("error", "Upload failed"),
                "timestamp": time.time(),
            }

        emit_fn = get_emit_status_update_accessible()

        if source == "A":
            # Accessible interface: emit status updates to the accessible Socket.IO app
            if grievance_id:
                emit_fn(grievance_id, status, task_data)
        else:
            # Bot/webchat interface (source "B"): mirror previous Flask behaviour by
            # emitting Socket.IO events that the webchat listens for ("task_status"
            # and "file_status_update") using the Flask session ID as the room.
            if flask_session_id:
                try:
                    from backend.api.websocket_utils import socketio  # lazy import

                    task_name = task_data.get("task_name", "unknown")
                    if "file" in str(task_name).lower():
                        event_name = "file_status_update"
                    else:
                        event_name = "task_status"

                    socketio.emit(
                        event_name,
                        {
                            "status": status,
                            "data": task_data,
                            "grievance_id": grievance_id,
                            "flask_session_id": flask_session_id,
                            "task_name": task_name,
                        },
                        room=flask_session_id,
                    )
                except Exception as emit_error:
                    file_server_core.log_event(
                        event_type="task_status_emit_error",
                        details={"error": str(emit_error), "source": source},
                    )

        file_server_core.log_event(
            event_type="task_status_emitted",
            details={
                "grievance_id": grievance_id,
                "flask_session_id": flask_session_id,
                "emit_websocket": source == "A",
                "status": status,
                "source": source,
            },
        )

        return JSONResponse({
            "status": status,
            "message": "Task status update sent",
            "grievance_id": grievance_id,
            "flask_session_id": flask_session_id,
            "source": source,
            "data": task_data,
        })
    except Exception as e:
        file_server_core.log_event(event_type="task_status_error", details={"error": str(e)})
        return JSONResponse(
            {"error": f"Internal server error: {str(e)}"},
            status_code=500,
        )
