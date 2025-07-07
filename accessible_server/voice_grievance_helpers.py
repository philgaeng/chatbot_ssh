
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
from typing import Dict, Any, List, Optional, Tuple
from backend.config.constants import AUDIO_EXTENSIONS, FIELD_MAPPING

# Define service name for logging
SERVICE_NAME = "voice_grievance"

# Load environment variables
load_dotenv('/home/ubuntu/nepal_chatbot/.env')

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB max size for audio files

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ------- Utility Functions -------

def ensure_directory_exists(directory_path: str) -> None:
    """Ensure that a directory exists, creating it if necessary"""
    os.makedirs(directory_path, exist_ok=True)

def create_grievance_directory(grievance_id: str, dir_type: str = None) -> str:
    """Create and return a directory path for a specific grievance"""
    if dir_type:
        directory = os.path.join(UPLOAD_FOLDER, dir_type, grievance_id)
    else:
        directory = os.path.join(UPLOAD_FOLDER, grievance_id)
    
    ensure_directory_exists(directory)
    return directory

def _is_audio_file(filename: str) -> bool:
    """Check if the filename has a valid audio extension"""
    return any(filename.lower().endswith(ext) for ext in AUDIO_EXTENSIONS)

def ensure_valid_audio_filename(original_name: str, field_key: str = None, field_mapping: dict = FIELD_MAPPING) -> str:
    """Ensure the filename has a valid extension and is secure
    and returns the needed parameters for the recording data
    field_name and filename"""
    # First secure the filename
    filename = secure_filename(original_name)
    
    # If 'blob' or empty, use the field_key if available
    if not filename or filename == 'blob':
        if field_key:
            filename = secure_filename(field_key)
        else:
            filename = f"audio_{uuid.uuid4()}"
    
    if not _is_audio_file(filename):
        filename += '.webm'  # Default to webm extension
    field_name = None

    for key, value in field_mapping.items():
        if key or value in filename:
            field_name = key
            break
            
    if not field_name:
        raise ValueError(f"Invalid file name: {original_name}")
    
    return filename, field_name

def save_uploaded_file(file_obj, directory: str, filename: str) -> Tuple[str, int]:
    """Save an uploaded file and return the path and size"""
    if not file_obj:
        raise ValueError("No file provided")
    
    file_path = os.path.join(directory, filename)
    file_obj.save(file_path)
    file_size = os.path.getsize(file_path)
    
    # If file is empty, remove it and raise error
    if file_size == 0:
        try:
            os.remove(file_path)
        except Exception:
            pass
        raise ValueError("File is empty")
    
    return file_path, file_size

__all__ = [
    'ensure_directory_exists',
    'create_grievance_directory',
    'ensure_valid_audio_filename',
    'save_uploaded_file',
    '_is_audio_file'
]