"""
Voice grievance handling module.

This module provides endpoints and utilities for handling voice grievances,
including file uploads, transcription, and processing.
"""

import os
import uuid
import json
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from flask import request, jsonify, Blueprint
from werkzeug.utils import secure_filename
from datetime import datetime
import traceback
from dotenv import load_dotenv
from task_queue.tasks import high_priority_task
from task_queue.monitoring import log_task_event
from task_queue.registered_tasks import (
    transcribe_audio_file_task,
    classify_and_summarize_grievance_task,
    extract_contact_info_task,
    translate_grievance_to_english_task,
    store_user_info_task,
    store_grievance_task,
    store_transcription_task
)
from celery import chain, group

# Update imports to use actions_server
from actions_server.db_manager import db_manager
from actions_server.constants import GRIEVANCE_STATUS


voice_grievance_bp = Blueprint('voice_grievance', __name__)

# Define service name for logging
SERVICE_NAME = "voice_grievance"

# Load environment variables
load_dotenv('/home/ubuntu/nepal_chatbot/.env')

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
AUDIO_EXTENSIONS = {'webm', 'mp3', 'wav', 'ogg', 'm4a'}
VALID_EXTENSIONS = ['.webm', '.mp3', '.wav', '.ogg', '.m4a']
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

def get_recording_type_from_filename(filename: str) -> str:
    """Determine recording type based on filename"""
    filename = filename.lower()
    
    if 'grievance' in filename or 'grievance_details' in filename:
        return 'details'
    elif 'name' in filename or 'user_full_name' in filename:
        return 'contact'
    elif 'phone' in filename or 'user_contact_phone' in filename or 'contact' in filename:
        return 'contact'
    elif 'municipality' in filename or 'user_municipality' in filename:
        return 'location'
    elif 'village' in filename or 'user_village' in filename:
        return 'location'
    elif 'address' in filename or 'user_address' in filename:
        return 'location'
    
    return 'details'  # Default

def get_grievance_field_from_filename(filename: str) -> str:
    """Map filename to corresponding grievance data field"""
    filename = filename.lower()
    
    if 'grievance' in filename or 'grievance_details' in filename:
        return 'grievance_details'
    elif 'name' in filename or 'user_full_name' in filename:
        return 'user_full_name'
    elif 'phone' in filename or 'user_contact_phone' in filename:
        return 'user_contact_phone'
    elif 'municipality' in filename or 'user_municipality' in filename:
        return 'user_municipality'
    elif 'village' in filename or 'user_village' in filename:
        return 'user_village'
    elif 'address' in filename or 'user_address' in filename:
        return 'user_address'
    
    return None  # No direct mapping

def ensure_valid_filename(original_name: str, field_key: str = None) -> str:
    """Ensure the filename has a valid extension and is secure"""
    # First secure the filename
    filename = secure_filename(original_name)
    
    # If 'blob' or empty, use the field_key if available
    if not filename or filename == 'blob':
        if field_key:
            filename = secure_filename(field_key)
        else:
            filename = f"audio_{uuid.uuid4()}"
    
    # Check if the filename has a valid audio extension
    has_valid_extension = any(filename.lower().endswith(ext) for ext in VALID_EXTENSIONS)
    if not has_valid_extension:
        filename += '.webm'  # Default to webm extension
    
    return filename

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



@voice_grievance_bp.route('/accessible-file-upload', methods=['POST'])
def accessible_file_upload():
    """Handle file uploads from the accessible interface directly"""
    try:
        log_task_event('accessible_file_upload', 'started', {}, service=SERVICE_NAME)
        
        # Check if grievance_id is provided
        grievance_id = request.form.get('grievance_id')
        if not grievance_id:
            log_task_event('accessible_file_upload', 'failed', {'error': 'No grievance_id provided'}, service=SERVICE_NAME)
            return jsonify({"error": "Grievance ID is required for file upload"}), 400
        
        # Determine the interface language from the request
        interface_language = request.form.get('interface_language', 'ne')
        
        # Check if files are provided
        if 'files[]' not in request.files:
            log_task_event('accessible_file_upload', 'failed', {'error': "No files[] in request.files"}, service=SERVICE_NAME)
            return jsonify({"error": "No files provided under 'files[]' key"}), 400
        
        files = request.files.getlist('files[]')
        if not files or len(files) == 0:
            log_task_event('accessible_file_upload', 'failed', {'error': "No files found in the request"}, service=SERVICE_NAME)
            return jsonify({"error": "No files found in the request"}), 400
        
        # Create the upload directory for this grievance
        upload_dir = create_grievance_directory(grievance_id)
        
        # Process and save each file
        saved_files = []
        has_voice_recording = False
        
        for file in files:
            if file and file.filename:
                # Ensure valid filename
                filename = ensure_valid_filename(file.filename)
                file_path = os.path.join(upload_dir, filename)
                
                # Save file
                file.save(file_path)
                log_task_event('accessible_file_upload', 'file_saved', {'file_path': file_path}, service=SERVICE_NAME)
                
                # Check if it's a voice recording
                if filename.lower().endswith(tuple(AUDIO_EXTENSIONS)):
                    has_voice_recording = True
                
                # Store file metadata
                file_data = {
                    'file_id': str(uuid.uuid4()),
                    'grievance_id': grievance_id,
                    'file_name': filename,
                    'file_path': file_path,
                    'file_type': filename.rsplit('.', 1)[1].lower(),
                    'file_size': os.path.getsize(file_path),
                    'upload_date': datetime.now().isoformat(),
                    'language_code': interface_language
                }
                
                # Store in database
                success = db_manager.file.store_file_attachment(file_data)
                if success:
                    saved_files.append({
                        'file_id': file_data['file_id'],
                        'file_name': filename,
                        'file_type': file_data['file_type']
                    })
        
        if not saved_files:
            log_task_event('accessible_file_upload', 'failed', {'error': 'Failed to save any files'}, service=SERVICE_NAME)
            return jsonify({
                'status': 'error',
                'error': 'Failed to save any files'
            }), 500
        
        if has_voice_recording:
            log_task_event('accessible_file_upload', 'completed', {'grievance_id': grievance_id, 'files': saved_files, 'has_voice_recording': True}, service=SERVICE_NAME)
            return jsonify({
                'status': 'SUCCESS',
                'message': 'Files uploaded successfully, however if you want to complete the grievance process, please use the voice grievance collection process instead of direct file upload.',
                'grievance_id': grievance_id,
                'files': saved_files
            }), 200
        
        log_task_event('accessible_file_upload', 'completed', {'grievance_id': grievance_id, 'files': saved_files, 'has_voice_recording': False}, service=SERVICE_NAME)
        return jsonify({
            'status': 'SUCCESS',
            'message': 'Files uploaded successfully',
            'grievance_id': grievance_id,
            'files': saved_files
        })
    except Exception as e:
        log_task_event('accessible_file_upload', 'failed', {'error': str(e)}, service=SERVICE_NAME)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
    
@voice_grievance_bp.route('/grievance-status/<grievance_id>', methods=['GET'])
def get_grievance_status(grievance_id):
    """Get the current status of a grievance and its associated tasks"""
    try:
        # Get grievance data
        grievance = db_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            return jsonify({
                'status': 'error',
                'error': 'Grievance not found'
            }), 404
        
        # Get task statuses
        tasks = db_manager.get_grievance_tasks(grievance_id)
        
        # Get file statuses
        files = db_manager.get_grievance_files(grievance_id)
        
        return jsonify({
            'status': 'SUCCESS',
            'grievance': grievance,
            'tasks': tasks,
            'files': files
        })
        
    except Exception as e:
        log_task_event('get_grievance_status', 'failed', {'error': str(e)}, service=SERVICE_NAME)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@voice_grievance_bp.route('/submit-grievance', methods=['POST'])
def submit_grievance():
    """Unified endpoint for submitting a grievance with user info and audio recordings"""
    try:
        log_task_event('submit_grievance', 'started', {}, service=SERVICE_NAME)
        
        # Initialize the grievance and user
        # Merge or create user
        user_id = db_manager.user.create_user(dict())
        if not user_id:
            log_task_event('submit_grievance', 'failed', {'error': 'Failed to create or merge user'}, service=SERVICE_NAME)
            return jsonify({'status': 'error', 'error': 'Failed to create user'}), 500
            
        # Create grievance
        grievance_id = db_manager.grievance.create_grievance(user_id=user_id, source='accessibility')
        if not grievance_id:
            log_task_event('submit_grievance', 'failed', {'error': 'Failed to create grievance'}, service=SERVICE_NAME)
            return jsonify({'status': 'error', 'error': 'Failed to create grievance'}), 500
            
        # Save audio files and collect their data
        audio_files = []
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                filename = ensure_valid_filename(file.filename, key)
                upload_dir = create_grievance_directory(grievance_id)
                file_path, file_size = save_uploaded_file(file, upload_dir, filename)
                
                # Create file data dictionary
                file_data = {
                    'file_id': str(uuid.uuid4()),
                    'grievance_id': grievance_id,
                    'file_name': filename,
                    'file_path': file_path,
                    'file_type': filename.rsplit('.', 1)[1].lower(),
                    'file_size': file_size,
                    'upload_date': datetime.now().isoformat(),
                    'language_code': request.form.get('language', 'en')
                }
                
                # Store in database
                success = db_manager.file.store_file_attachment(file_data)
                if success:
                    # Add to audio files list with the format expected by orchestrate_voice_processing
                    audio_files.append({
                        'filename': filename,
                        'file_path': file_path,
                        'file_data': file_data
                    })
                
        if not audio_files:
            log_task_event('submit_grievance', 'failed', {'error': 'No audio files provided in submission'}, service=SERVICE_NAME)
            return jsonify({'status': 'error', 'error': 'No audio files provided'}), 400
            
        # Queue Celery tasks for each file
        result = orchestrate_voice_processing(audio_files, language=request.form.get('language', 'en'))
        
        emit_status_update(grievance_id, 'submitted', {
            'user_id': user_id,
            'tasks': result.get('files', {})
        })
        
        # Return response
        log_task_event('submit_grievance', 'completed', {
            'grievance_id': grievance_id,
            'user_id': user_id,
            'tasks': result.get('files', {})
        }, service=SERVICE_NAME)
        
        return jsonify({
            'status': 'success',
            'message': 'Grievance submitted successfully',
            'grievance_id': grievance_id,
            'user_id': user_id,
            'tasks': result.get('files', {})
        }), 200
        
    except Exception as e:
        log_task_event('submit_grievance', 'failed', {'error': str(e)}, service=SERVICE_NAME)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500



def process_single_audio_file(file_path: str, filename: str, language: str = 'en') -> Dict[str, Any]:
    """
    Process a single audio file and return its task chain.

    Args:
        file_path: Path to the audio file
        filename: Original filename
        language: Language code for processing
        
    Returns:
        Dict containing task chain information
    """
    log_task_event('process_single_audio_file', 'file_saved', {'file_path': file_path}, service=SERVICE_NAME)

    # Determine if this is a contact info or grievance details file
    is_contact_info = 'user' in filename.lower()
    is_grievance_details = 'grievance' in filename.lower() or 'details' in filename.lower()

    # Initialize task chain
    task_chain = {
        'temp_path': file_path,  # Store path for cleanup
        'file_data': {
            'file_name': filename,
            'file_path': file_path,
            'file_type': filename.rsplit('.', 1)[1].lower() if '.' in filename else 'webm',
            'file_size': os.path.getsize(file_path),
            'upload_date': datetime.now().isoformat(),
            'language_code': language
        }
    }

    # Create the base transcription task
    transcription_task = transcribe_audio_file_task.s(file_path, language)

    # Build the task chain based on file type
    if is_contact_info:
        # Chain: transcribe -> extract contact -> store
        task_chain['tasks'] = chain(
            transcription_task,
            extract_contact_info_task.s(),
            store_user_info_task.s(task_chain['file_data'])
        ).apply_async()
        task_chain['type'] = 'contact_info'
        
    elif is_grievance_details:
        # Chain: transcribe -> classify -> translate (if needed) -> store
        chain_tasks = [
            transcription_task,
            classify_and_summarize_grievance_task.s(language)
        ]
        
        if language != 'en':
            chain_tasks.append(translate_grievance_to_english_task.s())
            
        chain_tasks.append(store_grievance_task.s(task_chain['file_data']))
        task_chain['tasks'] = chain(*chain_tasks).apply_async()
        task_chain['type'] = 'grievance_details'
        
    else:
        # Just transcription and store
        task_chain['tasks'] = chain(
            transcription_task,
            store_transcription_task.s(task_chain['file_data'])
        ).apply_async()
        task_chain['type'] = 'transcription_only'

    # Store the final task ID for tracking
    task_chain['task_id'] = task_chain['tasks'].id

    return task_chain

def orchestrate_voice_processing(audio_files: List[Any], language: str = 'en') -> Dict[str, Any]:
    """
    Orchestrate parallel processing of multiple audio files.

    Args:
        audio_files: List of uploaded audio files
        language: Language code for processing
        
    Returns:
        Dict containing task IDs and status for all files
    """
    try:
        # Process each file and collect task chains
        file_tasks = {}
        temp_paths = []
        
        for audio_file in audio_files:
            if audio_file:
                # Get the original filename from the file_data if available
                filename = audio_file.get('filename', f"audio_{uuid.uuid4()}")
                file_path = audio_file.get('file_path')
                
                if not file_path:
                    continue
                    
                task_chain = process_single_audio_file(file_path, filename, language)
                file_tasks[filename] = {
                    'task_id': task_chain['task_id'],
                    'type': task_chain['type'],
                    'status': 'pending'
                }
                temp_paths.append(task_chain['temp_path'])
        
        if not file_tasks:
            raise ValueError("No valid audio files provided")
        
        return {
            'status': 'SUCCESS',
            'files': file_tasks
        }
            
    except Exception as e:
        log_task_event('orchestrate_voice_processing', 'failed', {'error': str(e)}, service=SERVICE_NAME)
        # Clean up any temp files that were created
        for temp_path in temp_paths:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as cleanup_error:
                log_task_event('orchestrate_voice_processing', 'failed', {'error': str(cleanup_error)}, service=SERVICE_NAME)
        raise

def emit_status_update(grievance_id, status, data):
    """Emit a status update via Socket.IO server (import or implement as needed)"""
    try:
        from actions_server.file_server import emit_status_update as file_server_emit_status_update
        file_server_emit_status_update(grievance_id, status, data)
    except Exception as e:
        log_task_event('emit_status_update', 'failed', {'error': str(e)}, service=SERVICE_NAME)