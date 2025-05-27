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
from actions_server.db_manager import db_manager
from actions_server.websocket_utils import emit_status_update
from .voice_grievance_helpers import *
from .voice_grievance_orchestration import *
from task_queue.registered_tasks import process_batch_files_task, store_result_to_db_task


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
        grievance_id = db_manager.grievance.create_or_update_grievance({'user_id': user_id, 
                                                              'source': 'accessibility'})
        if not grievance_id:
            task_logger.log_task_event('submit_grievance', 'failed', {'error': 'Failed to create grievance'})
            return jsonify({'status': 'error', 'error': 'Failed to create grievance'}), 500
            
        # Save audio files and collect their data
        audio_files = []
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                filename, field_name = ensure_valid_audio_filename(file.filename, key)
                upload_dir = create_grievance_directory(grievance_id)
                file_path, file_size = save_uploaded_file(file, upload_dir, filename)
                
                # Create recording data dictionary
                recording_data = {
                    'recording_id': str(uuid.uuid4()),
                    'user_id': user_id,
                    'grievance_id': grievance_id,
                    'file_name': filename,
                    'file_path': file_path,
                    'field_name': field_name,
                    'file_size': file_size,
                    'upload_date': datetime.now().isoformat(),
                    'language_code': request.form.get('language_code', 'en'),
                    'duration_seconds': request.form.get(f'duration')  # Get duration from form data
                }
                
                # Store in database
                success = store_result_to_db_task.delay(recording_data)
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


