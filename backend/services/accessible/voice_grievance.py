"""
Voice grievance handling module.

This module provides endpoints and utilities for handling voice grievances,
including file uploads, transcription, and processing.
"""

import os
import uuid
from flask import request, jsonify, Blueprint
from datetime import datetime
from logger.logger import TaskLogger
from werkzeug.utils import secure_filename
# Update imports to use actions_server
from backend.services.database_services.postgres_services import db_manager
from backend.api.websocket_utils import emit_status_update_accessible
from backend.config.constants import VALID_FIELD_NAMES, DEFAULT_PROVINCE, DEFAULT_DISTRICT
from .voice_grievance_helpers import *
from .voice_grievance_orchestration import *
from task_queue.registered_tasks import process_batch_files_task


voice_grievance_bp = Blueprint('voice_grievance', __name__)

# Define service name for logging
SERVICE_NAME = "voice_grievance"

# Create a TaskLogger instance at module level
task_logger = TaskLogger(service_name='voice_grievance')


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
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path) #save the file to the upload directory
                files_data.append({
                    'file_id': str(uuid.uuid4()),
                    'grievance_id': grievance_id,
                    'file_name': filename,
                    'file_path': file_path,
                    'file_type': filename.rsplit('.', 1)[-1].lower(),
                    'file_size': os.path.getsize(file_path),
                    'upload_date': datetime.now().isoformat(),
                    'mimetype': file.mimetype
                })
                if _is_audio_file(filename):
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
        status = db_manager.get_grievance_status(grievance_id)
        
        # Get file statuses
        files = db_manager.get_grievance_files(grievance_id)
        
        return jsonify({
            'status': SUCCESS,
            'grievance': grievance,
            'status': status,
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
        
        # Extract complainant_id, grievance_id, province, and district from the form data
        complainant_id = request.form.get('complainant_id')
        grievance_id = request.form.get('grievance_id')
        province = request.form.get('province', DEFAULT_PROVINCE)
        district = request.form.get('district', DEFAULT_DISTRICT)
        
        task_logger.log_task_event('submit_grievance', 'processing', {
            'received_complainant_id': complainant_id,
            'received_grievance_id': grievance_id,
            'form_keys': list(request.form.keys()),
            'files_keys': list(request.files.keys())
        })
        

            
        # Save audio files and collect their data
        audio_files = []
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                filename, field_name = ensure_valid_audio_filename(file.filename, key)
                upload_dir = create_grievance_directory(grievance_id)
                file_path, file_size = save_uploaded_file(file, upload_dir, filename)
                field_name = next((field for field in VALID_FIELD_NAMES if field in file_path), None)
                if not field_name:
                    task_logger.log_task_event('submit_grievance', 'failed', {'error': f'No field name found for file {file_path}'})
                    return jsonify({'status': 'error', 'error': f'No field name found for file {file_path}'}), 400
                #sanitize duration to int
                duration = request.form.get(f'duration', None)
                if duration in ['float', 'int']:
                    duration = int(duration)
                else:
                    duration = None
                
                
                # Create recording data dictionary
                recording_data = {
                    'recording_id': str(uuid.uuid4()),
                    'complainant_id': complainant_id,
                    'grievance_id': grievance_id,
                    'complainant_province': province,
                    'complainant_district': district,
                    'file_path': file_path,
                    'field_name': field_name,
                    'file_size': file_size,
                    'upload_date': datetime.now().isoformat(),
                    'language_code': request.form.get('language_code', 'en'),
                    'processing_status': 'COMPLETED' 
                }
                if duration and duration is not None:
                    recording_data['duration_seconds'] = duration
                task_logger.log_task_event('submit_grievance', 'processing', f"has_duration: {'TRUE' if duration else 'FALSE'}")
                
                # Store recording in database directly (not using result storage task)
                recording_id = db_manager.create_or_update_recording(recording_data)
                if recording_id:
                    # Add to audio files list with the format expected by orchestrate_voice_processing
                    audio_files.append(recording_data)
                else:
                    task_logger.log_task_event('submit_grievance', 'failed', {'error': f'Failed to create recording {recording_data}'})
                    return jsonify({'status': 'error', 'error': f'Failed to create recording {recording_data}'}), 500
                    
        if not audio_files:
            task_logger.log_task_event('submit_grievance', 'failed', {'error': 'No audio files provided in submission'})
            return jsonify({'status': 'error', 'error': 'No audio files provided'}), 400
        else:
            task_logger.log_task_event('submit_grievance', 'processing', f"audio_files: {audio_files}")
            
        # Queue Celery tasks for each file
        result = orchestrate_voice_processing(audio_files)
        
        emit_status_update_accessible(grievance_id, 'submitted', {
            'complainant_id': complainant_id,
            'tasks': result.get('files', {})
        })
        
        # Return response
        task_logger.log_task_event('submit_grievance', 'completed', {
            'grievance_id': grievance_id,
            'complainant_id': complainant_id,
            'tasks': result.get('files', {})
        })
        
        return jsonify({
            'status': 'success',
            'message': 'Grievance submitted successfully',
            'grievance_id': grievance_id,
            'complainant_id': complainant_id,
            'tasks': result.get('files', {})
        }), 200
            
    except Exception as e:
        
        task_logger.log_task_event('submit_grievance', 'failed', {'error': str(e)})
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


