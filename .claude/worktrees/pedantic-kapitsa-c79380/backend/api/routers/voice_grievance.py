"""
Voice grievance router. Same URL surface and behaviour as Flask blueprint.
Routes: POST /accessible-file-upload, GET /grievance-status/{grievance_id}, POST /submit-grievance.
"""

import os
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from werkzeug.utils import secure_filename

from backend.config.constants import DEFAULT_VALUES, VALID_FIELD_NAMES
from backend.config.database_constants import get_task_status_codes
from backend.logger.logger import TaskLogger
from backend.services.database_services.postgres_services import db_manager
from backend.task_queue.registered_tasks import process_batch_files_task

from backend.services.accessible.voice_grievance_helpers import (
    create_grievance_directory,
    ensure_valid_audio_filename,
    _is_audio_file,
)
from backend.services.accessible.voice_grievance_orchestration import orchestrate_voice_processing

# Emit helper: use FastAPI Socket.IO app if available, else Flask (for migration period)
try:
    from backend.api.websocket_fastapi import emit_status_update_accessible
except ImportError:
    from backend.api.websocket_utils import emit_status_update_accessible

status_codes = get_task_status_codes()
SUCCESS = status_codes["SUCCESS"]
STARTED = status_codes["STARTED"]
FAILED = status_codes["FAILED"]

DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]

router = APIRouter()
task_logger = TaskLogger(service_name="voice_grievance")


@router.post("/accessible-file-upload")
async def accessible_file_upload(
    grievance_id: str = Form(...),
    files: List[UploadFile] = File(..., alias="files[]"),
):
    """Handle file uploads from the accessible interface. Same behaviour as Flask."""
    try:
        task_logger.log_task_event("accessible_file_upload", STARTED, {})

        if not grievance_id:
            task_logger.log_task_event("accessible_file_upload", FAILED, {"error": "No grievance_id provided"})
            return JSONResponse(
                status_code=400,
                content={"error": "Grievance ID is required for file upload"},
            )

        if not files:
            task_logger.log_task_event("accessible_file_upload", FAILED, {"error": "No files found in the request"})
            return JSONResponse(status_code=400, content={"error": "No files provided"})

        upload_dir = create_grievance_directory(grievance_id)
        files_data = []
        audio_files = []

        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_dir, filename)
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                files_data.append({
                    "file_id": str(uuid.uuid4()),
                    "grievance_id": grievance_id,
                    "file_name": filename,
                    "file_path": file_path,
                    "file_type": filename.rsplit(".", 1)[-1].lower() if "." in filename else "",
                    "file_size": os.path.getsize(file_path),
                    "upload_date": datetime.now().isoformat(),
                    "mimetype": file.content_type or "application/octet-stream",
                })
                if _is_audio_file(filename):
                    audio_files.append(filename)

        if not files_data:
            task_logger.log_task_event("accessible_file_upload", FAILED, {"error": "Failed to save any files"})
            return JSONResponse(
                status_code=500,
                content={"status": FAILED, "error": "Failed to save any files"},
            )

        process_batch_files_task.delay(grievance_id, files_data)

        response = {
            "status": "processing",
            "message": "Files are being processed. You will be notified when processing is complete.",
            "grievance_id": grievance_id,
            "files": [f["file_name"] for f in files_data],
        }
        if audio_files:
            response["warning"] = (
                "Note: Audio files uploaded as attachments will not be transcribed "
                "and should not be used for submitting grievances."
            )

        return JSONResponse(status_code=202, content=response)

    except Exception as e:
        task_logger.log_task_event("accessible_file_upload", FAILED, {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"status": FAILED, "error": str(e)},
        )


@router.get("/grievance-status/{grievance_id}")
def get_grievance_status(grievance_id: str):
    """Get the current status of a grievance and its associated tasks. Same as Flask."""
    try:
        grievance = db_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            return JSONResponse(
                status_code=404,
                content={"status": FAILED, "error": "Grievance not found"},
            )

        status = db_manager.get_grievance_status(grievance_id)
        files = db_manager.get_grievance_files(grievance_id)

        # Match Flask: duplicate "status" key (second overwrites in JSON)
        return {
            "status": SUCCESS,
            "grievance": grievance,
            "status": status,
            "files": files,
        }

    except Exception as e:
        task_logger.log_task_event("get_grievance_status", FAILED, {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"status": FAILED, "error": str(e)},
        )


@router.post("/submit-grievance")
async def submit_grievance(request: Request):
    """Unified endpoint for submitting a grievance with user info and audio recordings. Same as Flask."""
    try:
        task_logger.log_task_event("submit_grievance", STARTED, {})

        form = await request.form()

        complainant_id = form.get("complainant_id")
        grievance_id = form.get("grievance_id")
        province = form.get("province", DEFAULT_PROVINCE)
        district = form.get("district", DEFAULT_DISTRICT)

        task_logger.log_task_event("submit_grievance", STARTED, {
            "received_complainant_id": complainant_id,
            "received_grievance_id": grievance_id,
            "form_keys": list(form.keys()),
        })

        audio_files = []

        for key in form.keys():
            field = form[key]
            if not hasattr(field, "read") or not callable(getattr(field, "read", None)):
                continue
            file = field
            if not file or not file.filename:
                continue

            try:
                filename, field_name = ensure_valid_audio_filename(file.filename, key)
            except ValueError as e:
                task_logger.log_task_event("submit_grievance", FAILED, {"error": str(e)})
                return JSONResponse(
                    status_code=400,
                    content={"status": FAILED, "error": str(e)},
                )

            upload_dir = create_grievance_directory(grievance_id)
            file_path = os.path.join(upload_dir, filename)
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            file_size = os.path.getsize(file_path)

            field_name = next((f for f in VALID_FIELD_NAMES if f in file_path), None)
            if not field_name:
                task_logger.log_task_event("submit_grievance", FAILED, {"error": f"No field name found for file {file_path}"})
                return JSONResponse(
                    status_code=400,
                    content={"status": FAILED, "error": f"No field name found for file {file_path}"},
                )

            duration = form.get("duration")
            if duration in ("float", "int"):
                duration = int(duration)
            else:
                duration = None

            recording_data = {
                "recording_id": str(uuid.uuid4()),
                "complainant_id": complainant_id,
                "grievance_id": grievance_id,
                "complainant_province": province,
                "complainant_district": district,
                "file_path": file_path,
                "field_name": field_name,
                "file_size": file_size,
                "upload_date": datetime.now().isoformat(),
                "language_code": form.get("language_code", "en"),
                "processing_status": "COMPLETED",
            }
            if duration is not None:
                recording_data["duration_seconds"] = duration

            recording_id = db_manager.create_or_update_recording(recording_data)
            if recording_id:
                audio_files.append(recording_data)
            else:
                task_logger.log_task_event("submit_grievance", FAILED, {"error": f"Failed to create recording {recording_data}"})
                return JSONResponse(
                    status_code=500,
                    content={"status": FAILED, "error": f"Failed to create recording"},
                )

        if not audio_files:
            task_logger.log_task_event("submit_grievance", FAILED, {"error": "No audio files provided in submission"})
            return JSONResponse(
                status_code=400,
                content={"status": FAILED, "error": "No audio files provided"},
            )

        result = orchestrate_voice_processing(audio_files)

        emit_status_update_accessible(grievance_id, "submitted", {
            "complainant_id": complainant_id,
            "tasks": result.get("files", {}),
        })

        task_logger.log_task_event("submit_grievance", SUCCESS, {
            "grievance_id": grievance_id,
            "complainant_id": complainant_id,
            "tasks": result.get("files", {}),
        })

        return {
            "status": SUCCESS,
            "message": "Grievance submitted successfully",
            "grievance_id": grievance_id,
            "complainant_id": complainant_id,
            "tasks": result.get("files", {}),
        }

    except Exception as e:
        task_logger.log_task_event("submit_grievance", FAILED, {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"status": FAILED, "error": str(e)},
        )
