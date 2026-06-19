import os
import logging
import time
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import wave
import contextlib
from .database_services.postgres_services import db_manager
from ..config.constants import (
    MAX_FILE_SIZE,
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    FILE_TYPE_MAX_SIZES,
    FILE_TYPES,
    AUDIO_EXTENSIONS,
    # TASK_STATUS is now accessed through database_constants.py
)
from ..shared_functions.utterance_mapping_server import get_utterance
from typing import Dict, Any, Optional, List
from ..api.api_manager import APIManager
from backend.logger.logger import TaskLogger

# Define service name for logging
SERVICE_NAME = "file_processor"

UPLOAD_FOLDER = 'uploads'

# In-memory voice chunk upload sessions (upload_id -> session dict). TTL 1 hour.
_VOICE_CHUNK_SESSIONS: Dict[str, Dict[str, Any]] = {}
_VOICE_CHUNK_TTL_SEC = 3600
_VOICE_CHUNK_AUDIO_MAX_BYTES = FILE_TYPE_MAX_SIZES.get(
    "AUDIO", MAX_FILE_SIZE
)

# Get status codes from database constants (ensuring cohesiveness)
from backend.config.database_constants import get_task_status_codes

status_codes = get_task_status_codes()
SUCCESS = status_codes['SUCCESS']
STARTED = status_codes['STARTED']
FAILED = status_codes['FAILED']
RETRYING = status_codes['RETRYING']

        
class FileServerCore(APIManager):
    """Core business logic for file operations"""
    
    def __init__(self, upload_folder: str = UPLOAD_FOLDER, allowed_extensions: list = ALLOWED_EXTENSIONS):
        super().__init__(SERVICE_NAME)
        self.task_logger = TaskLogger(service_name=SERVICE_NAME)
        self.logger = self.task_logger.logger
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        os.makedirs(upload_folder, exist_ok=True)

    def get_file_type(self, filename: str) -> str:
        """Determine the type of file based on extension."""
        name_lower = (filename or "").lower()
        ext = name_lower.rsplit(".", 1)[-1] if "." in name_lower else ""

        # In-chat voice notes use webm; classify as audio (webm is also listed under VIDEO).
        if name_lower.startswith("voice_note_") or (
            ext in FILE_TYPES["AUDIO"]["extensions"]
        ):
            return "audio"

        for file_type, info in FILE_TYPES.items():
            if ext in info["extensions"]:
                return file_type.lower()
        return "other"

    def get_valid_file(self, file_id: str) -> dict:
        """Retrieve and validate a file by ID."""
        try:
            self.log_event(event_type=STARTED, details={'file_id': file_id})
            
            file_data = db_manager.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                self.log_event(event_type=SUCCESS, details={'file_id': file_id, 'exists': True})
                return file_data
            
            self.log_event(event_type=SUCCESS, details={'file_id': file_id, 'exists': False})
            return None
        except Exception as e:
            self.log_event(event_type=FAILED, details={'file_id': file_id, 'error': str(e)})
            return None

    def get_audio_metadata(self, file_path: str) -> dict:
        """Get metadata for an audio file"""
        try:
            self.log_event(event_type=STARTED, details={'file_path': file_path})
            
            metadata = {}
            
            # Try to get duration for WAV files
            if file_path.lower().endswith('.wav'):
                with contextlib.closing(wave.open(file_path, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = frames / float(rate)
                    metadata['duration_seconds'] = round(duration, 2)
            
            # For other audio formats, we could use libraries like pydub or mutagen
            # but for now we'll just return basic metadata
            file_stats = os.stat(file_path)
            metadata.update({
                'audio_format': file_path.rsplit('.', 1)[1].lower() if '.' in file_path else 'unknown',
                'file_size': file_stats.st_size,
                'created_date': datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                'modified_date': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
            
            self.log_event(event_type=SUCCESS, details={'file_path': file_path, 'metadata': metadata})
            
            return metadata
            
        except Exception as e:
            self.log_event(event_type=FAILED, details={'file_path': file_path, 'error': str(e)})
            return {}

    def get_file_metadata(self, file_path: str) -> dict:
        """Get metadata for a file"""
        try:
            self.log_event(event_type=STARTED, details={'file_path': file_path})
            
            file_stats = os.stat(file_path)
            metadata = {
                'file_size': file_stats.st_size,
                'created_date': datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                'modified_date': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.log_event(event_type=SUCCESS, details={'file_path': file_path, 'metadata': metadata})
            
            return metadata
        except Exception as e:
            self.log_event(event_type=FAILED, details={'file_path': file_path, 'error': str(e)})
            return {}

    def process_file_upload(self, grievance_id: str, file_data: dict) -> dict:
        """Process an uploaded file"""
        # Get file type
        file_type = self.get_file_type(file_data['file_name'])
        
        # Add metadata
        file_data.update({
            'file_type': file_type,
            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'grievance_id': grievance_id
        })
        
        # Additional processing based on file type
        if file_type == 'audio':
            # Add audio-specific metadata
            audio_metadata = self.get_audio_metadata(file_data['file_path'])
            file_data.update(audio_metadata)

        if file_type == 'image':
            from backend.services.image_compression import compress_image

            compress_result = compress_image(file_data['file_path'])
            if compress_result.output_path != file_data['file_path']:
                file_data['file_path'] = compress_result.output_path
                file_data['file_name'] = os.path.basename(compress_result.output_path)
            file_data['file_size'] = compress_result.compressed_bytes
            self.logger.info(
                "image_compression result status=%s original_bytes=%s compressed_bytes=%s "
                "width=%s height=%s file=%s",
                compress_result.status,
                compress_result.original_bytes,
                compress_result.compressed_bytes,
                compress_result.width,
                compress_result.height,
                compress_result.output_path,
            )

        client_meta = file_data.get("client_metadata") or {}
        if client_meta:
            from backend.shared_functions.geo_pin import build_file_client_metadata

            file_data["client_metadata"] = build_file_client_metadata(client_meta)

        # Store file attachment in DB (requires grievance_id to exist in grievances table)
        success = db_manager.store_file_attachment(file_data)

        if not success:
            raise Exception(
                f"Failed to store file {file_data['file_name']} in database "
                "(check DB logs for cause; often grievance_id missing or FK violation)"
            )

        return file_data


    def process_batch_files(self, grievance_id: str, file_list: list) -> dict:
        """Process a batch of files for a grievance"""
        self.log_event(event_type=STARTED, details={'grievance_id': grievance_id, 'file_count': len(file_list)})
        
        try:
            results = []
            for file_data in file_list:
                ext = file_data['file_type']
                mimetype = file_data.get('mimetype')
                if self.allowed_extensions and ext not in self.allowed_extensions:
                    # skip or log error
                    continue
                try:
                    result = self.process_file_upload(grievance_id, file_data)
                    results.append(result)
                except Exception as e:
                    self.log_event(event_type=FAILED, details={'grievance_id': grievance_id, 'file': file_data['file_name'], 'error': str(e)})
                    results.append({
                        'status': FAILED,
                        'file_name': file_data['file_name'],
                        'error': str(e)
                    })
            
            self.log_event(event_type=SUCCESS, details={'grievance_id': grievance_id, 'success_count': len([r for r in results if r['status'] == SUCCESS]), 'failed_count': len([r for r in results if r['status'] == FAILED])})
            
            return {
                'status': SUCCESS,
                'grievance_id': grievance_id,
                'results': results
            }
            
        except Exception as e:
            self.log_event(event_type=FAILED, details={'grievance_id': grievance_id, 'error': str(e)})
            raise

    def allowed_mime_type(self, mime_type):
        """Check if mime type is allowed"""
        return mime_type in ALLOWED_MIME_TYPES

    def _prune_expired_voice_chunk_sessions(self) -> None:
        now = time.time()
        expired = [
            uid
            for uid, session in _VOICE_CHUNK_SESSIONS.items()
            if (now - session.get("created_at", 0)) > _VOICE_CHUNK_TTL_SEC
        ]
        for uid in expired:
            session = _VOICE_CHUNK_SESSIONS.pop(uid, None)
            if session:
                part_path = session.get("part_path")
                if part_path and os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except OSError:
                        pass

    def _validate_voice_chunk_filename(self, filename: str) -> str:
        safe_name = secure_filename(filename or "")
        if not safe_name.lower().startswith("voice_note_"):
            raise ValueError("invalid_voice_filename")
        ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        if ext not in AUDIO_EXTENSIONS:
            raise ValueError("invalid_voice_extension")
        return safe_name

    def create_voice_chunk_session(
        self,
        grievance_id: str,
        file_name: str,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a resumable voice-note upload; first chunk is appended separately."""
        self._prune_expired_voice_chunk_sessions()
        safe_name = self._validate_voice_chunk_filename(file_name)
        if mime_type and mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError("invalid_voice_mime_type")

        upload_id = str(uuid.uuid4())
        file_id = str(uuid.uuid4())
        grievance_dir = os.path.join(self.upload_folder, grievance_id)
        os.makedirs(grievance_dir, exist_ok=True)
        part_path = os.path.join(grievance_dir, f".voice_part_{upload_id}.part")

        session = {
            "upload_id": upload_id,
            "file_id": file_id,
            "grievance_id": grievance_id,
            "file_name": safe_name,
            "mime_type": mime_type or "audio/webm",
            "part_path": part_path,
            "next_chunk_index": 0,
            "total_bytes": 0,
            "created_at": time.time(),
        }
        _VOICE_CHUNK_SESSIONS[upload_id] = session
        self.log_event(
            event_type=STARTED,
            details={
                "operation": "voice_chunk_session",
                "upload_id": upload_id,
                "file_id": file_id,
                "grievance_id": grievance_id,
            },
        )
        return session

    def append_voice_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        chunk_bytes: bytes,
    ) -> Dict[str, Any]:
        """Append one ordered chunk; duplicate indices are acknowledged (retry-safe)."""
        self._prune_expired_voice_chunk_sessions()
        session = _VOICE_CHUNK_SESSIONS.get(upload_id)
        if not session:
            raise ValueError("upload_session_not_found")

        expected = session["next_chunk_index"]
        if chunk_index < expected:
            return {"duplicate": True, "session": session}
        if chunk_index > expected:
            raise ValueError("chunk_out_of_order")

        chunk_len = len(chunk_bytes)
        if chunk_len == 0:
            raise ValueError("empty_chunk")

        projected = session["total_bytes"] + chunk_len
        if projected > _VOICE_CHUNK_AUDIO_MAX_BYTES:
            raise ValueError("voice_chunk_size_exceeded")

        with open(session["part_path"], "ab") as part_file:
            part_file.write(chunk_bytes)

        session["next_chunk_index"] = expected + 1
        session["total_bytes"] = projected
        return {"duplicate": False, "session": session}

    def finalize_voice_chunk_upload(
        self,
        upload_id: str,
        expected_grievance_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Move assembled part file into place and return file_data for Celery."""
        session = _VOICE_CHUNK_SESSIONS.pop(upload_id, None)
        if not session:
            raise ValueError("upload_session_not_found")
        if (
            expected_grievance_id
            and session["grievance_id"] != expected_grievance_id
        ):
            _VOICE_CHUNK_SESSIONS[upload_id] = session
            raise ValueError("grievance_mismatch")
        if session["next_chunk_index"] < 1:
            part_path = session.get("part_path")
            if part_path and os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except OSError:
                    pass
            raise ValueError("no_chunks_received")

        grievance_dir = os.path.dirname(session["part_path"])
        final_path = os.path.join(grievance_dir, session["file_name"])
        os.replace(session["part_path"], final_path)

        metadata = self.get_file_metadata(final_path)
        file_data = {
            "file_id": session["file_id"],
            "file_name": session["file_name"],
            "file_path": final_path,
            "file_size": session["total_bytes"],
            **metadata,
        }
        self.log_event(
            event_type=SUCCESS,
            details={
                "operation": "voice_chunk_finalize",
                "upload_id": upload_id,
                "file_id": session["file_id"],
                "bytes": session["total_bytes"],
                "chunks": session["next_chunk_index"],
            },
        )
        return file_data

    def abort_voice_chunk_upload(self, upload_id: str) -> None:
        session = _VOICE_CHUNK_SESSIONS.pop(upload_id, None)
        if not session:
            return
        part_path = session.get("part_path")
        if part_path and os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass

# Initialize the core  instances
file_server_core = FileServerCore()
 