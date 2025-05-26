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
from task_queue.logger import TaskLogger
from task_queue.registered_tasks import (
    transcribe_audio_file_task,
    classify_and_summarize_grievance_task,
    extract_contact_info_task,
    translate_grievance_to_english_task,
    process_batch_files_task,
    store_result_to_db_task
)
from celery import chain, group

# Update imports to use actions_server
from actions_server.db_manager import db_manager
from actions_server.constants import GRIEVANCE_STATUS, ALLOWED_EXTENSIONS, AUDIO_EXTENSIONS
from actions_server.websocket_utils import emit_status_update
from actions_server.file_server import FileServerCore

# Initialize FileServerCore
file_server_core = FileServerCore()

voice_grievance_bp = Blueprint('voice_grievance', __name__)

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

# Create a TaskLogger instance at module level
task_logger = TaskLogger(service_name='voice_grievance')

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

def ensure_valid_audio_filename(original_name: str, field_key: str = None) -> str:
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
    has_valid_extension = any(filename.lower().endswith(ext) for ext in AUDIO_EXTENSIONS)
    if not has_valid_extension:
        filename += '.webm'  # Default to webm extension
    recording_type = get_recording_type_from_filename(filename)
    
    return filename, recording_type

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
        task_logger.log_task_event('accessible_file_upload', 'started', {})
        
        # Check if grievance_id is provided
        grievance_id = request.form.get('grievance_id')
        if not grievance_id:
            task_logger.log_task_event('accessible_file_upload', 'failed', {'error': 'No grievance_id provided'})
            return jsonify({"error": "Grievance ID is required for file upload"}), 400
        
        # Check if files are provided
        files = request.files.getlist('files[]')
        if not files:
            task_logger.log_task_event('accessible_file_upload', 'failed', {'error': "No files found in the request"})
            return jsonify({"error": "No files provided"}), 400
        
        # Create the upload directory for this grievance
        upload_dir = create_grievance_directory(grievance_id)
        
        # Process and save each file
        files_data = []
        audio_files = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                ext = '.' + filename.rsplit('.', 1)[-1].lower()
                mimetype = file.mimetype
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                files_data.append({
                    'file_id': str(uuid.uuid4()),
                    'grievance_id': grievance_id,
                    'file_name': filename,
                    'file_path': file_path,
                    'file_type': ext,
                    'file_size': os.path.getsize(file_path),
                    'upload_date': datetime.now().isoformat(),
                    'mimetype': mimetype
                })
                if ext in AUDIO_EXTENSIONS:
                    audio_files.append(filename)
        
        if not files_data:
            task_logger.log_task_event('accessible_file_upload', 'failed', {'error': 'Failed to save any files'})
            return jsonify({
                'status': 'error',
                'error': 'Failed to save any files'
            }), 500
        
        # Enqueue batch processing task
        process_batch_files_task.delay(grievance_id, files_data)

        response = {
            'status': 'processing',
            'message': 'Files are being processed. You will be notified when processing is complete.',
            'grievance_id': grievance_id,
            'files': [f['file_name'] for f in files_data]
        }

        if audio_files:
            response['warning'] = 'Note: Audio files uploaded as attachments will not be transcribed and should not be used for submitting grievances.'
        
        return jsonify(response), 202
    
    except Exception as e:
        task_logger.log_task_event('accessible_file_upload', 'failed', {'error': str(e)})
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
        task_logger.log_task_event('get_grievance_status', 'failed', {'error': str(e)})
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@voice_grievance_bp.route('/submit-grievance', methods=['POST'])
def submit_grievance():
    """Unified endpoint for submitting a grievance with user info and audio recordings"""
    try:
        task_logger.log_task_event('submit_grievance', 'started', {})
        
        # Initialize the grievance and user
        # Merge or create user
        user_id = db_manager.user.create_or_update_user()
        if not user_id:
            task_logger.log_task_event('submit_grievance', 'failed', {'error': 'Failed to create or merge user'})
            return jsonify({'status': 'error', 'error': 'Failed to create user'}), 500
            
        # Create grievance
        grievance_id = db_manager.grievance.create_grievance({'user_id': user_id, 
                                                              'source': 'accessibility'})
        if not grievance_id:
            task_logger.log_task_event('submit_grievance', 'failed', {'error': 'Failed to create grievance'})
            return jsonify({'status': 'error', 'error': 'Failed to create grievance'}), 500
            
        # Save audio files and collect their data
        audio_files = []
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                filename, recording_type = ensure_valid_audio_filename(file.filename, key)
                upload_dir = create_grievance_directory(grievance_id)
                file_path, file_size = save_uploaded_file(file, upload_dir, filename)
                
                # Create recording data dictionary
                recording_data = {
                    'recording_id': str(uuid.uuid4()),
                    'user_id': user_id,
                    'grievance_id': grievance_id,
                    'file_name': filename,
                    'recording_type': recording_type,
                    'file_path': file_path,
                    'field_name': filename.rsplit('.', 1)[1].lower(),
                    'file_size': file_size,
                    'upload_date': datetime.now().isoformat(),
                    'language_code': request.form.get('language_code', 'en'),
                    'duration_seconds': request.form.get(f'duration')  # Get duration from form data
                }
                
                # Store in database
                success = store_result_to_db_task.delay('recording', recording_data)
                if success:
                    # Add to audio files list with the format expected by orchestrate_voice_processing
                    audio_files.append({
                        'file_name': filename,
                        'file_path': file_path,
                        'file_data': recording_data
                    })
                
        if not audio_files:
            task_logger.log_task_event('submit_grievance', 'failed', {'error': 'No audio files provided in submission'})
            return jsonify({'status': 'error', 'error': 'No audio files provided'}), 400
            
        # Queue Celery tasks for each file
        result = orchestrate_voice_processing(audio_files, recording_data)
        
        emit_status_update(grievance_id, 'submitted', {
            'user_id': user_id,
            'tasks': result.get('files', {})
        })
        
        # Return response
        task_logger.log_task_event('submit_grievance', 'completed', {
            'grievance_id': grievance_id,
            'user_id': user_id,
            'tasks': result.get('files', {})
        })
        
        return jsonify({
            'status': 'success',
            'message': 'Grievance submitted successfully',
            'grievance_id': grievance_id,
            'user_id': user_id,
            'tasks': result.get('files', {})
        }), 200
        
    except Exception as e:
        task_logger.log_task_event('submit_grievance', 'failed', {'error': str(e)})
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


def process_single_audio_file(recording_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single audio file and return its task chain.

    Args:
        recording_data: Dictionary containing recording data passed from the submit_grievance endpoint
        
    Returns:
        Dict containing task chain information
    """
    file_path = recording_data.get('file_path')
    language = recording_data.get('language_code')
    task_logger.log_task_event('process_single_audio_file', 'file_saved', {'file_path': file_path})

    # Extract the field name from the recording data
    field_mapping = {'user_full_name': 'full_name',
                     'user_contact_phone': 'contact_phone',
                     'user_contact_email': 'contact_email',
                     'user_province': 'province',
                     'user_district': 'district',
                     'user_municipality': 'municipality',
                     'user_ward': 'ward',
                     'user_village': 'village',
                     'user_address': 'address',
                     'grievance_details': 'grievance'}
    
    field_name = field_mapping.get(recording_data.get('field_name'))
    if field_name not in field_mapping.keys() and field_name in field_mapping.values():
        field_name = field_mapping.get(recording_data.get('field_name'))
        recording_data['field_name'] = field_name
    else:
        task_logger.log_task_event('process_single_audio_file', 'failed', {'error': f"Invalid field name: {recording_data.get('field_name')}"})
        raise ValueError(f"Invalid field name: {recording_data.get('field_name')}")
    
    is_contact_info = 'user' in recording_data.get('file_name')
    is_grievance_details = 'grievance' in recording_data.get('file_name')

    # Initialize task chain
    task_chain = {
        'temp_path': file_path,  # Store path for cleanup
        'file_data': recording_data
    }

    # Start with transcription task
    chain_tasks = [transcribe_audio_file_task.s(recording_data)]
    
    # Build the task chain based on file type
    if is_contact_info:
        task_chain['type'] = 'contact_info'
        # After transcription, extract contact info and store in parallel
        chain_tasks.extend([
            group(
                extract_contact_info_task.s(),
                store_result_to_db_task.s()
            )
        ])
        
    elif is_grievance_details:
        task_chain['type'] = 'grievance_details'
        # After transcription, store and classify in parallel
        chain_tasks.extend([
            group(
                store_result_to_db_task.s(),
                classify_and_summarize_grievance_task.s()
            )
        ])
        
        # Add translation if needed
        if language != 'en':
            chain_tasks.extend([
                translate_grievance_to_english_task.s(),
                store_result_to_db_task.s()
            ])
    else:
        task_chain['type'] = 'transcription_only'
        # Just store the transcription
        chain_tasks.append(store_result_to_db_task.s())
    
    # Create and execute the final chain
    final_chain = chain(*chain_tasks)
    result = final_chain.delay()
    
    # Store the final task ID for tracking
    task_chain['task_id'] = result.id

    return task_chain

def orchestrate_voice_processing(audio_files: List[Any], recording_data: Dict[str, Any]) -> Dict[str, Any]:
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
                    
                task_chain = process_single_audio_file(recording_data)
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
        task_logger.log_task_event('orchestrate_voice_processing', 'failed', {'error': str(e)})
        # Clean up any temp files that were created
        for temp_path in temp_paths:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as cleanup_error:
                task_logger.log_task_event('orchestrate_voice_processing', 'failed', {'error': str(cleanup_error)})
        raise