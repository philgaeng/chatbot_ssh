"""
File server API router (production). Same URL surface as legacy FileServerAPI in channels_api.py.
Uses FileServerCore and Celery; accessible emit is wired from fastapi_app lifespan (Socket.IO ASGI).
"""

import json
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
from backend.actions.grievance_intake.ensure_records import (
    ensure_intake_records_for_attachment,
)
from backend.shared_functions.utterance_mapping_server import get_utterance
from backend.task_queue.registered_tasks import process_file_upload_task
from werkzeug.utils import secure_filename

status_codes = get_task_status_codes()
SUCCESS = status_codes["SUCCESS"]
FAILED = status_codes["FAILED"]
RETRYING = status_codes["RETRYING"]
STARTED = status_codes["STARTED"]

# Core instance (shared with Celery tasks)
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


def _resolve_grievance_for_upload(
    grievance_id: Optional[str],
    complainant_id: Optional[str],
) -> Dict[str, Optional[str]]:
    grievance_id = (grievance_id or "").strip() or None
    complainant_id = (complainant_id or "").strip() or None

    if not grievance_id:
        ensured = ensure_intake_records_for_attachment(
            db_manager,
            grievance_id=None,
            complainant_id=complainant_id,
        )
        return {
            "grievance_id": ensured["grievance_id"],
            "complainant_id": ensured["complainant_id"],
        }
    if not db_manager.check_entry_exists_for_entity_key("grievance_id", grievance_id):
        ensured = ensure_intake_records_for_attachment(
            db_manager,
            grievance_id=grievance_id,
            complainant_id=complainant_id,
        )
        return {
            "grievance_id": ensured["grievance_id"],
            "complainant_id": ensured.get("complainant_id") or complainant_id,
        }
    return {"grievance_id": grievance_id, "complainant_id": complainant_id}


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
    grievance_id: Optional[str] = Form(None),
    complainant_id: Optional[str] = Form(None),
    rasa_session_id: Optional[str] = Form(None),
    flask_session_id: Optional[str] = Form(None),
    file_metadata: Optional[str] = Form(None),
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
        grievance_id = (grievance_id or "").strip() or None
        complainant_id = (complainant_id or "").strip() or None

        if not grievance_id:
            ensured = ensure_intake_records_for_attachment(
                db_manager,
                grievance_id=None,
                complainant_id=complainant_id,
            )
            grievance_id = ensured["grievance_id"]
            complainant_id = ensured["complainant_id"]
        elif not db_manager.check_entry_exists_for_entity_key("grievance_id", grievance_id):
            ensured = ensure_intake_records_for_attachment(
                db_manager,
                grievance_id=grievance_id,
                complainant_id=complainant_id,
            )
            grievance_id = ensured["grievance_id"]
            complainant_id = ensured.get("complainant_id") or complainant_id

        if db_manager.is_grievance_archived(grievance_id):
            file_server_core.log_event(
                event_type=FAILED,
                details={"error": "grievance_archived", "grievance_id": grievance_id},
            )
            return JSONResponse(
                {
                    "error": "This grievance has been archived. New uploads are not allowed.",
                    "grievance_id": grievance_id,
                },
                status_code=409,
            )

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

        metadata_by_name: Dict[str, Dict[str, Any]] = {}
        if file_metadata:
            try:
                parsed = json.loads(file_metadata)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get("file_name"):
                            metadata_by_name[item["file_name"]] = item
            except json.JSONDecodeError:
                pass

        task_ids = []
        for file_data in uploaded_files:
            client_meta = metadata_by_name.get(file_data.get("file_name"), {})
            if client_meta:
                file_data["client_metadata"] = client_meta
            result = process_file_upload_task.delay(
                grievance_id=grievance_id,
                file_data=file_data,
                session_id=flask_session_id,
            )
            task_ids.append(result.id)

        return JSONResponse(
            {
                "status": STARTED,
                "grievance_id": grievance_id,
                "complainant_id": complainant_id,
                "flask_session_id": flask_session_id,
                "message": "Files are being processed - those listed in oversized_files and wrong_extensions_list will be ignored",
                "files": [f["file_id"] for f in uploaded_files],
                "oversized_files": oversized_files,
                "wrong_extensions_list": wrong_extensions_list,
                "max_file_size": MAX_FILE_SIZE,
                "task_id": task_ids[0] if task_ids else None,
                "task_ids": task_ids,
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


@router.post("/upload-voice-chunk")
async def upload_voice_chunk(
    request: Request,
    chunk_index: int = Form(...),
    grievance_id: Optional[str] = Form(None),
    complainant_id: Optional[str] = Form(None),
    upload_id: Optional[str] = Form(None),
    file_name: Optional[str] = Form(None),
    mime_type: Optional[str] = Form(None),
    rasa_session_id: Optional[str] = Form(None),
    flask_session_id: Optional[str] = Form(None),
    chunk: UploadFile = File(...),
):
    """Append one voice-note chunk (1s MediaRecorder slice). Idempotent on retry."""
    language_code = _get_language_code(request)
    try:
        resolved = _resolve_grievance_for_upload(grievance_id, complainant_id)
        grievance_id = resolved["grievance_id"]
        complainant_id = resolved["complainant_id"]

        if db_manager.is_grievance_archived(grievance_id):
            return JSONResponse(
                {
                    "error": "This grievance has been archived. New uploads are not allowed.",
                    "grievance_id": grievance_id,
                },
                status_code=409,
            )

        chunk_bytes = await chunk.read()
        if chunk_index < 0:
            return JSONResponse({"error": "Invalid chunk_index"}, status_code=400)

        if not upload_id:
            if chunk_index != 0:
                return JSONResponse(
                    {"error": "upload_id required for chunk_index > 0"},
                    status_code=400,
                )
            if not file_name:
                return JSONResponse({"error": "file_name required on first chunk"}, status_code=400)
            session = file_server_core.create_voice_chunk_session(
                grievance_id=grievance_id,
                file_name=file_name,
                mime_type=mime_type,
            )
            upload_id = session["upload_id"]
        else:
            session = None

        try:
            result = file_server_core.append_voice_chunk(
                upload_id=upload_id,
                chunk_index=chunk_index,
                chunk_bytes=chunk_bytes,
            )
            session = result["session"]
        except ValueError as exc:
            code = str(exc)
            if code == "upload_session_not_found":
                return JSONResponse({"error": "Upload session expired or not found"}, status_code=404)
            if code == "chunk_out_of_order":
                return JSONResponse({"error": "Chunk received out of order"}, status_code=409)
            if code == "empty_chunk":
                return JSONResponse({"error": "Empty chunk"}, status_code=400)
            if code == "voice_chunk_size_exceeded":
                file_server_core.abort_voice_chunk_upload(upload_id)
                return JSONResponse(
                    {"error": "Voice note exceeds maximum size"},
                    status_code=413,
                )
            raise

        return JSONResponse(
            {
                "status": SUCCESS,
                "upload_id": upload_id,
                "file_id": session["file_id"],
                "chunk_index": chunk_index,
                "duplicate": result.get("duplicate", False),
                "bytes_received": len(chunk_bytes),
                "total_bytes": session["total_bytes"],
                "chunks_received": session["next_chunk_index"],
                "grievance_id": grievance_id,
                "complainant_id": complainant_id,
                "flask_session_id": flask_session_id,
                "rasa_session_id": rasa_session_id,
            }
        )
    except ValueError as exc:
        if str(exc) in {"invalid_voice_filename", "invalid_voice_extension", "invalid_voice_mime_type"}:
            return JSONResponse({"error": "Invalid voice note file"}, status_code=400)
        raise
    except Exception as e:
        file_server_core.log_event(event_type=FAILED, details={"error": str(e)})
        error_message = get_utterance("file_server", "upload_files", 6, language_code)
        return JSONResponse(
            {"error": error_message, "detail": str(e)},
            status_code=500,
        )


@router.post("/upload-voice-complete")
async def upload_voice_complete(
    request: Request,
    upload_id: str = Form(...),
    grievance_id: Optional[str] = Form(None),
    complainant_id: Optional[str] = Form(None),
    flask_session_id: Optional[str] = Form(None),
    rasa_session_id: Optional[str] = Form(None),
):
    """Finalize a chunked voice note and queue the standard file-upload task."""
    language_code = _get_language_code(request)
    try:
        resolved = _resolve_grievance_for_upload(grievance_id, complainant_id)
        grievance_id = resolved["grievance_id"]
        complainant_id = resolved["complainant_id"]

        if db_manager.is_grievance_archived(grievance_id):
            return JSONResponse(
                {
                    "error": "This grievance has been archived. New uploads are not allowed.",
                    "grievance_id": grievance_id,
                },
                status_code=409,
            )

        try:
            file_data = file_server_core.finalize_voice_chunk_upload(
                upload_id,
                expected_grievance_id=grievance_id,
            )
        except ValueError as exc:
            code = str(exc)
            if code == "upload_session_not_found":
                return JSONResponse({"error": "Upload session expired or not found"}, status_code=404)
            if code == "no_chunks_received":
                return JSONResponse({"error": "No audio chunks received"}, status_code=400)
            if code == "grievance_mismatch":
                return JSONResponse({"error": "Grievance mismatch for upload session"}, status_code=409)
            raise

        result = process_file_upload_task.delay(
            grievance_id=grievance_id,
            file_data=file_data,
            session_id=flask_session_id,
        )

        return JSONResponse(
            {
                "status": STARTED,
                "grievance_id": grievance_id,
                "complainant_id": complainant_id,
                "flask_session_id": flask_session_id,
                "rasa_session_id": rasa_session_id,
                "message": "Voice note is being processed",
                "files": [file_data["file_id"]],
                "upload_id": upload_id,
                "task_id": result.id,
                "task_ids": [result.id],
                "chunked": True,
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
            # Bot/webchat (source "B"): emit to the webchat Socket.IO room (session id from client).
            if flask_session_id:
                try:
                    from backend.api.websocket_fastapi import emit_webchat_task_status

                    task_name = task_data.get("task_name", "unknown")
                    if "file" in str(task_name).lower():
                        event_name = "file_status_update"
                    else:
                        event_name = "task_status"

                    emit_webchat_task_status(
                        flask_session_id,
                        event_name,
                        {
                            "status": status,
                            "data": task_data,
                            "grievance_id": grievance_id,
                            "flask_session_id": flask_session_id,
                            "task_name": task_name,
                        },
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
