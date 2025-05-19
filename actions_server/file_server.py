import os
import logging
from flask import request, jsonify, send_file, Blueprint, send_from_directory
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import wave
import contextlib
from actions_server.db_manager import db_manager
from actions_server.constants import (
    MAX_FILE_SIZE, 
    ALLOWED_EXTENSIONS, 
    ALLOWED_MIME_TYPES, 
    FILE_TYPE_MAX_SIZES,
    FILE_TYPES,
)
from actions_server.utterance_mapping_server import get_utterance
from task_queue.monitoring import log_task_event
from task_queue.task_status import get_task_status as get_queue_task_status
from typing import Dict, Any, Optional, List

# Define service name for logging
SERVICE_NAME = "file_processor"


# Configure upload settings
UPLOAD_FOLDER = 'uploads'

# File Processing Functions
def get_file_type(filename: str) -> str:
    """Determine the type of file based on extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    for file_type, info in FILE_TYPES.items():
        if ext in info['extensions']:
            return file_type.lower()
    return 'other'

def get_valid_file(file_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve and validate a file by ID."""
    try:
        log_task_event('get_valid_file', 'started', {
            'file_id': file_id
        }, service=SERVICE_NAME)
        
        file_data = db_manager.file.get_file_by_id(file_id)
        if file_data and os.path.exists(file_data['file_path']):
            log_task_event('get_valid_file', 'completed', {
                'file_id': file_id,
                'exists': True
            }, service=SERVICE_NAME)
            return file_data
            
        log_task_event('get_valid_file', 'completed', {
            'file_id': file_id,
            'exists': False
        }, service=SERVICE_NAME)
        return None
    except Exception as e:
        log_task_event('get_valid_file', 'failed', {
            'file_id': file_id,
            'error': str(e)
        }, service=SERVICE_NAME)
        return None

def get_audio_metadata(file_path: str) -> Dict[str, Any]:
    """Get metadata for an audio file"""
    try:
        log_task_event('get_audio_metadata', 'started', {
            'file_path': file_path
        }, service=SERVICE_NAME)
        
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
        
        log_task_event('get_audio_metadata', 'completed', {
            'file_path': file_path,
            'metadata': metadata
        }, service=SERVICE_NAME)
        
        return metadata
        
    except Exception as e:
        log_task_event('get_audio_metadata', 'failed', {
            'file_path': file_path,
            'error': str(e)
        }, service=SERVICE_NAME)
        return {}

def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Get metadata for a file"""
    try:
        log_task_event('get_file_metadata', 'started', {
            'file_path': file_path
        }, service=SERVICE_NAME)
        
        file_stats = os.stat(file_path)
        metadata = {
            'file_size': file_stats.st_size,
            'created_date': datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
            'modified_date': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        log_task_event('get_file_metadata', 'completed', {
            'file_path': file_path,
            'metadata': metadata
        }, service=SERVICE_NAME)
        
        return metadata
    except Exception as e:
        log_task_event('get_file_metadata', 'failed', {
            'file_path': file_path,
            'error': str(e)
        }, service=SERVICE_NAME)
        return {}

def process_file_upload(grievance_id: str, file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an uploaded file"""
    log_task_event('process_file_upload', 'started', {
        'grievance_id': grievance_id,
        'file': file_data['file_name']
    }, service=SERVICE_NAME)
    
    try:
        # Get file type
        file_type = get_file_type(file_data['file_name'])
        
        # Add metadata
        file_data.update({
            'file_type': file_type,
            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'processing_status': 'processing'
        })
        
        # Additional processing based on file type
        if file_type == 'audio':
            # Add audio-specific metadata
            audio_metadata = get_audio_metadata(file_data['file_path'])
            file_data.update(audio_metadata)
        
        # Store in database
        if db_manager.store_file_attachment(file_data):
            # Update processing status
            db_manager.update_file_status(file_data['file_id'], 'completed')
            
            log_task_event('process_file_upload', 'completed', {
                'grievance_id': grievance_id,
                'file': file_data['filename'],
                'status': 'success'
            }, service=SERVICE_NAME)
            
            return {
                'status': 'success',
                'file_id': file_data['file_id'],
                'filename': file_data['filename'],
                'file_size': file_data['file_size'],
                'file_type': file_type
            }
        else:
            raise Exception(f"Failed to store file metadata in database: {file_data['filename']}")
            
    except Exception as e:
        # Update processing status to failed
        if 'file_id' in file_data:
            db_manager.update_file_status(file_data['file_id'], 'failed')
            
        log_task_event('process_file_upload', 'failed', {
            'grievance_id': grievance_id,
            'file': file_data['filename'],
            'error': str(e)
        }, service=SERVICE_NAME)
        raise

def process_batch_files(grievance_id: str, file_list: List[Dict[str, Any]], allowed_extensions=ALLOWED_EXTENSIONS) -> Dict[str, Any]:
    """Process a batch of files for a grievance"""
    log_task_event('process_batch_files', 'started', {
        'grievance_id': grievance_id,
        'file_count': len(file_list)
    }, service=SERVICE_NAME)
    
    try:
        results = []
        for file_data in file_list:
            ext = file_data['file_type']
            mimetype = file_data.get('mimetype')
            if allowed_extensions and ext not in allowed_extensions:
                # skip or log error
                continue
            try:
                result = process_file_upload(grievance_id, file_data)
                results.append(result)
            except Exception as e:
                log_task_event('process_batch_files', 'failed', {
                    'grievance_id': grievance_id,
                    'file': file_data['filename'],
                    'error': str(e)
                }, service=SERVICE_NAME)
                results.append({
                    'status': 'failed',
                    'filename': file_data['filename'],
                    'error': str(e)
                })
        
        log_task_event('process_batch_files', 'completed', {
            'grievance_id': grievance_id,
            'success_count': len([r for r in results if r['status'] == 'success']),
            'failed_count': len([r for r in results if r['status'] == 'failed'])
        }, service=SERVICE_NAME)
        
        return {
            'status': 'completed',
            'grievance_id': grievance_id,
            'results': results
        }
        
    except Exception as e:
        log_task_event('process_batch_files', 'failed', {
            'grievance_id': grievance_id,
            'error': str(e)
        }, service=SERVICE_NAME)
        raise


def allowed_mime_type(mime_type):
    """Check if mime type is allowed"""
    return mime_type in ALLOWED_MIME_TYPES

# Initialize Blueprint
file_server_bp = Blueprint('file_server', __name__)

@file_server_bp.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "File server is running"})

@file_server_bp.route('/task-status/<task_id>', methods=['GET'])
def get_task_status_endpoint(task_id):
    """Get the status of a task"""
    try:
        status = get_queue_task_status(task_id)
        return jsonify({'status': status}), 200
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

@file_server_bp.route('/test-db')
def test_db():
    """Test database connectivity"""
    try:
        log_task_event('test_db', 'started', {}, service=SERVICE_NAME)
        
        # Try to connect to the database
        connection = db_manager.get_connection()
        cursor = connection.cursor()
        
        # Check if the grievances table exists
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'grievances'")
        tables_count = cursor.fetchone()[0]
        
        # Count grievances
        grievance_count = 0
        if tables_count > 0:
            cursor.execute("SELECT COUNT(*) FROM grievances")
            grievance_count = cursor.fetchone()[0]
        
        # Create a test grievance ID
        test_id = db_manager.generate_grievance_id('test')
        
        connection.close()
        
        log_task_event('test_db', 'completed', {
            'tables_exist': tables_count > 0,
            'grievance_count': grievance_count,
            'test_grievance_id': test_id
        }, service=SERVICE_NAME)
        
        return jsonify({
            "status": "ok", 
            "message": "Database connection successful",
            "tables_exist": tables_count > 0,
            "grievance_count": grievance_count,
            "test_grievance_id": test_id
        })
    except Exception as e:
        log_task_event('test_db', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        return jsonify({
            "status": "error", 
            "message": f"Database connection error: {str(e)}"
        }), 500

@file_server_bp.route('/upload-files', methods=['POST'])
def upload_files():
    """Handle file uploads for a grievance"""
    try:
        log_task_event('upload_files', 'started', {
            'method': 'POST',
            'endpoint': '/upload-files'
        }, service=SERVICE_NAME)
        
        # Check if grievance_id is provided
        grievance_id = request.form.get('grievance_id')
        log_task_event('upload_files', 'processing', {
            'grievance_id': grievance_id
        }, service=SERVICE_NAME)
        
        if not grievance_id:
            log_task_event('upload_files', 'failed', {
                'error': 'No grievance_id provided'
            }, service=SERVICE_NAME)
            error_message = get_utterance('file_server', 'upload_files', 1, language)
            return jsonify({"error": error_message}), 400

        # Reject uploads for pending grievances
        if grievance_id == "pending":
            log_task_event('upload_files', 'failed', {
                'error': "Attempted to upload file for pending grievance"
            }, service=SERVICE_NAME)
            error_message = get_utterance('file_server', 'upload_files', 2, language)
            return jsonify({"error": error_message}), 400

        # Check if any file was sent
        if 'files[]' not in request.files:
            log_task_event('upload_files', 'failed', {
                'error': "No files[] in request.files"
            }, service=SERVICE_NAME)
            error_message = get_utterance('file_server', 'upload_files', 3, language)
            return jsonify({"error": error_message}), 400

        files = request.files.getlist('files[]')
        log_task_event('upload_files', 'processing', {
            'file_count': len(files)
        }, service=SERVICE_NAME)
        
        if not files:
            log_task_event('upload_files', 'failed', {
                'error': "No files in files[] list"
            }, service=SERVICE_NAME)
            error_message = get_utterance('file_server', 'upload_files', 4, language)
            return jsonify({"error": error_message}), 400

        uploaded_files = []
        oversized_files = []
        file_data_list = []

        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_size = len(file.read())
                file.seek(0)  # Reset file pointer
                
                if file_size > MAX_FILE_SIZE:
                    oversized_files.append(filename)
                    continue
                    
                if '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                    file_id = str(uuid.uuid4())
                    file_path = os.path.join(UPLOAD_FOLDER, file_id)
                    
                    # Save file
                    file.save(file_path)
                    
                    # Get file metadata
                    metadata = get_file_metadata(file_path)
                    
                    # Prepare file data
                    file_data = {
                        'file_id': file_id,
                        'filename': filename,
                        'file_path': file_path,
                        'file_size': file_size,
                        'grievance_id': grievance_id,
                        **metadata
                    }
                    
                    file_data_list.append(file_data)
                    uploaded_files.append({
                        'file_id': file_id,
                        'filename': filename,
                        'file_size': file_size
                    })
                else:
                    extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'no extension'
                    log_task_event('upload_files', 'failed', {
                        'error': f"Invalid file type: {extension} for file: {file.filename}"
                    }, service=SERVICE_NAME)
                    error_message = get_utterance('file_server', 'upload_files', 5, language)
                    return jsonify({
                        "error": error_message
                    }), 400

        if not file_data_list:
            if oversized_files:
                return jsonify({
                    "error": "All files were too large",
                    "oversized_files": oversized_files,
                    "max_file_size": MAX_FILE_SIZE
                }), 413
            return jsonify({
                "error": "No valid files to process"
            }), 400

        # Process files in batch
        result = process_batch_files(grievance_id, file_data_list)
        
        response_data = {
            "status": "success",
            "message": "Files processed successfully",
            "files": uploaded_files
        }
        
        if oversized_files:
            response_data["oversized_files"] = oversized_files
            response_data["max_file_size"] = MAX_FILE_SIZE
        
        log_task_event('upload_files', 'completed', {
            'grievance_id': grievance_id,
            'processed_files': len(uploaded_files),
            'oversized_files': len(oversized_files)
        }, service=SERVICE_NAME)
        
        return jsonify(response_data), 202
            
    except Exception as e:
        log_task_event('upload_files', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        error_message = get_utterance('file_server', 'upload_files', 6, language)
        return jsonify({"error": error_message}), 500

@file_server_bp.route('/files/<grievance_id>', methods=['GET'])
def get_files(grievance_id):
    """Get list of files for a grievance"""
    try:
        log_task_event('get_files', 'started', {
            'grievance_id': grievance_id
        }, service=SERVICE_NAME)
        
        files = db_manager.get_grievance_files(grievance_id)
        
        log_task_event('get_files', 'completed', {
            'grievance_id': grievance_id,
            'file_count': len(files)
        }, service=SERVICE_NAME)
        
        return jsonify({"files": files}), 200
    except Exception as e:
        log_task_event('get_files', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        error_message = get_utterance('file_server', 'get_files', 1, language)
        return jsonify({"error": error_message}), 500

@file_server_bp.route('/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """Download a specific file"""
    try:
        log_task_event('download_file', 'started', {
            'file_id': file_id
        }, service=SERVICE_NAME)
        
        file_data = db_manager.get_file_by_id(file_id)
        if file_data and os.path.exists(file_data['file_path']):
            log_task_event('download_file', 'completed', {
                'file_id': file_id,
                'filename': file_data['file_name']
            }, service=SERVICE_NAME)
            return send_file(
                file_data['file_path'],
                as_attachment=True,
                download_name=file_data['file_name']
            )
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        log_task_event('download_file', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        return jsonify({"error": "Internal server error"}), 500

@file_server_bp.route('/file-status/<file_id>', methods=['GET'])
def get_file_status(file_id):
    """Get the processing status of a file"""
    try:
        log_task_event('get_file_status', 'started', {
            'file_id': file_id
        }, service=SERVICE_NAME)
        
        status = db_manager.get_file_status(file_id)
        if status:
            log_task_event('get_file_status', 'completed', {
                'file_id': file_id,
                'status': status
            }, service=SERVICE_NAME)
            return jsonify({"status": status}), 200
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        log_task_event('get_file_status', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        return jsonify({"error": "Internal server error"}), 500

@file_server_bp.route('/grievance-review/<grievance_id>', methods=['GET'])
def get_grievance_review(grievance_id):
    """Get all review data for a grievance"""
    try:
        log_task_event('get_grievance_review', 'started', {
            'grievance_id': grievance_id
        }, service=SERVICE_NAME)
        
        data = db_manager.get_grievance_review_data(grievance_id)
        if not data:
            log_task_event('get_grievance_review', 'failed', {
                'grievance_id': grievance_id,
                'error': 'Not found'
            }, service=SERVICE_NAME)
            return jsonify({'error': 'Not found'}), 404
            
        log_task_event('get_grievance_review', 'completed', {
            'grievance_id': grievance_id
        }, service=SERVICE_NAME)
        return jsonify(data), 200
    except Exception as e:
        log_task_event('get_grievance_review', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        return jsonify({'error': 'Internal server error'}), 500

@file_server_bp.route('/grievance-review/<grievance_id>', methods=['POST'])
def update_grievance_review(grievance_id):
    """Update review data for a grievance (all at once)"""
    try:
        log_task_event('update_grievance_review', 'started', {
            'grievance_id': grievance_id
        }, service=SERVICE_NAME)
        
        if not request.is_json:
            log_task_event('update_grievance_review', 'failed', {
                'error': 'Request must be JSON'
            }, service=SERVICE_NAME)
            return jsonify({'error': 'Request must be JSON'}), 400
            
        data = request.get_json()
        success = db_manager.update_grievance_review_data(grievance_id, data)
        if not success:
            log_task_event('update_grievance_review', 'failed', {
                'error': 'Update failed'
            }, service=SERVICE_NAME)
            return jsonify({'error': 'Update failed'}), 400
            
        log_task_event('update_grievance_review', 'completed', {
            'grievance_id': grievance_id
        }, service=SERVICE_NAME)
        return jsonify({'message': 'Update successful'}), 200
    except Exception as e:
        log_task_event('update_grievance_review', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        return jsonify({'error': 'Internal server error'}), 500

@file_server_bp.route('/files/<filename>')
def get_file(filename):
    """Serve uploaded files"""
    try:
        log_task_event('get_file', 'started', {
            'filename': filename
        }, service=SERVICE_NAME)
        
        result = send_from_directory(UPLOAD_FOLDER, filename)
        
        log_task_event('get_file', 'completed', {
            'filename': filename
        }, service=SERVICE_NAME)
        
        return result
    except Exception as e:
        log_task_event('get_file', 'failed', {
            'error': str(e)
        }, service=SERVICE_NAME)
        return jsonify({'error': str(e)}), 404

def emit_status_update(grievance_id, status, data):
    """Emit status updates through WebSocket"""
    if hasattr(file_server_bp, 'emit_status_update'):
        file_server_bp.emit_status_update(grievance_id, status, data)
    else:
        log_task_event('emit_status_update', 'failed', {
            'error': 'WebSocket not initialized',
            'grievance_id': grievance_id,
            'status': status
        }, service=SERVICE_NAME) 