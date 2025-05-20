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
from typing import Dict, Any, Optional, List
from actions_server.api_manager import APIManager

# Define service name for logging
SERVICE_NAME = "file_processor"

# Configure upload settings
UPLOAD_FOLDER = 'uploads'

class FileServerCore(APIManager):
    """Core business logic for file operations"""
    
    def __init__(self, upload_folder: str = 'uploads', allowed_extensions: list = ALLOWED_EXTENSIONS):
        super().__init__('file_processor')
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        os.makedirs(upload_folder, exist_ok=True)

    def get_file_type(self, filename: str) -> str:
        """Determine the type of file based on extension"""
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        for file_type, info in FILE_TYPES.items():
            if ext in info['extensions']:
                return file_type.lower()
        return 'other'

    def get_valid_file(self, file_id: str) -> dict:
        """Retrieve and validate a file by ID."""
        try:
            self.log_event('get_valid_file', 'started', {
                'file_id': file_id
            })
            
            file_data = db_manager.file.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                self.log_event('get_valid_file', 'completed', {
                    'file_id': file_id,
                    'exists': True
                })
                return file_data
            
            self.log_event('get_valid_file', 'completed', {
                'file_id': file_id,
                'exists': False
            })
            return None
        except Exception as e:
            self.log_event('get_valid_file', 'failed', {
                'file_id': file_id,
                'error': str(e)
            })
            return None

    def get_audio_metadata(self, file_path: str) -> dict:
        """Get metadata for an audio file"""
        try:
            self.log_event('get_audio_metadata', 'started', {
                'file_path': file_path
            })
            
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
            
            self.log_event('get_audio_metadata', 'completed', {
                'file_path': file_path,
                'metadata': metadata
            })
            
            return metadata
            
        except Exception as e:
            self.log_event('get_audio_metadata', 'failed', {
                'file_path': file_path,
                'error': str(e)
            })
            return {}

    def get_file_metadata(self, file_path: str) -> dict:
        """Get metadata for a file"""
        try:
            self.log_event('get_file_metadata', 'started', {
                'file_path': file_path
            })
            
            file_stats = os.stat(file_path)
            metadata = {
                'file_size': file_stats.st_size,
                'created_date': datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                'modified_date': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.log_event('get_file_metadata', 'completed', {
                'file_path': file_path,
                'metadata': metadata
            })
            
            return metadata
        except Exception as e:
            self.log_event('get_file_metadata', 'failed', {
                'file_path': file_path,
                'error': str(e)
            })
            return {}

    def process_file_upload(self, grievance_id: str, file_data: dict) -> dict:
        """Process an uploaded file"""
        self.log_event('process_file_upload', 'started', {
            'grievance_id': grievance_id,
            'file': file_data['file_name']
        })
        
        try:
            # Get file type
            file_type = self.get_file_type(file_data['file_name'])
            
            # Add metadata
            file_data.update({
                'file_type': file_type,
                'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'processing_status': 'processing'
            })
            
            # Additional processing based on file type
            if file_type == 'audio':
                # Add audio-specific metadata
                audio_metadata = self.get_audio_metadata(file_data['file_path'])
                file_data.update(audio_metadata)
            
            # Store in database
            if db_manager.store_file_attachment(file_data):
                # Update processing status
                db_manager.update_file_status(file_data['file_id'], 'completed')
                
                self.log_event('process_file_upload', 'completed', {
                    'grievance_id': grievance_id,
                    'file': file_data['filename'],
                    'status': 'success'
                })
                
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
            
            self.log_event('process_file_upload', 'failed', {
                'grievance_id': grievance_id,
                'file': file_data['filename'],
                'error': str(e)
            })
            raise

    def process_batch_files(self, grievance_id: str, file_list: list) -> dict:
        """Process a batch of files for a grievance"""
        self.log_event('process_batch_files', 'started', {
            'grievance_id': grievance_id,
            'file_count': len(file_list)
        })
        
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
                    self.log_event('process_batch_files', 'failed', {
                        'grievance_id': grievance_id,
                        'file': file_data['filename'],
                        'error': str(e)
                    })
                    results.append({
                        'status': 'failed',
                        'filename': file_data['filename'],
                        'error': str(e)
                    })
            
            self.log_event('process_batch_files', 'completed', {
                'grievance_id': grievance_id,
                'success_count': len([r for r in results if r['status'] == 'success']),
                'failed_count': len([r for r in results if r['status'] == 'failed'])
            })
            
            return {
                'status': 'completed',
                'grievance_id': grievance_id,
                'results': results
            }
            
        except Exception as e:
            self.log_event('process_batch_files', 'failed', {
                'grievance_id': grievance_id,
                'error': str(e)
            })
            raise

    def allowed_mime_type(self, mime_type):
        """Check if mime type is allowed"""
        return mime_type in ALLOWED_MIME_TYPES 

class FileServerAPI:
    """API routes for file operations"""
    
    def __init__(self, core: FileServerCore):
        self.core = core
        self.blueprint = Blueprint('file_server', __name__)
        self._register_routes()

    def _get_language_code(self) -> str:
        """Get language code from request or default to English"""
        return request.args.get('language', 'en')

    def _register_routes(self):
        """Register all routes with the blueprint"""
        self.blueprint.route('/')(self.health_check)
        self.blueprint.route('/test-db')(self.test_db)
        self.blueprint.route('/upload-files', methods=['POST'])(self.upload_files)
        self.blueprint.route('/files/<grievance_id>', methods=['GET'])(self.get_files)
        self.blueprint.route('/download/<file_id>', methods=['GET'])(self.download_file)
        self.blueprint.route('/file-status/<file_id>', methods=['GET'])(self.get_file_status)
        self.blueprint.route('/grievance-review/<grievance_id>', methods=['GET'])(self.get_grievance_review)
        self.blueprint.route('/grievance-review/<grievance_id>', methods=['POST'])(self.update_grievance_review)
        self.blueprint.route('/files/<filename>')(self.get_file)

    @staticmethod
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "ok", "message": "File server is running"})

    def test_db(self):
        """Test database connectivity"""
        try:
            self.core.log_event('test_db', 'started', {}, service=SERVICE_NAME)
            
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
            
            self.core.log_event('test_db', 'completed', {
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
            self.core.log_event('test_db', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            return jsonify({
                "status": "error", 
                "message": f"Database connection error: {str(e)}"
            }), 500

    def upload_files(self):
        """Handle file uploads for a grievance"""
        try:
            language_code = self._get_language_code()
            self.core.log_event('upload_files', 'started', {
                'method': 'POST',
                'endpoint': '/upload-files'
            }, service=SERVICE_NAME)
            
            # Check if grievance_id is provided
            grievance_id = request.form.get('grievance_id')
            self.core.log_event('upload_files', 'processing', {
                'grievance_id': grievance_id
            }, service=SERVICE_NAME)
            
            if not grievance_id:
                self.core.log_event('upload_files', 'failed', {
                    'error': 'No grievance_id provided'
                }, service=SERVICE_NAME)
                error_message = get_utterance('file_server', 'upload_files', 1, language_code)
                return jsonify({"error": error_message}), 400

            # Reject uploads for pending grievances
            if grievance_id == "pending":
                self.core.log_event('upload_files', 'failed', {
                    'error': "Attempted to upload file for pending grievance"
                }, service=SERVICE_NAME)
                error_message = get_utterance('file_server', 'upload_files', 2, language_code)
                return jsonify({"error": error_message}), 400

            # Check if any file was sent
            if 'files[]' not in request.files:
                self.core.log_event('upload_files', 'failed', {
                    'error': "No files[] in request.files"
                }, service=SERVICE_NAME)
                error_message = get_utterance('file_server', 'upload_files', 3, language_code)
                return jsonify({"error": error_message}), 400

            files = request.files.getlist('files[]')
            self.core.log_event('upload_files', 'processing', {
                'file_count': len(files)
            }, service=SERVICE_NAME)
            
            if not files:
                self.core.log_event('upload_files', 'failed', {
                    'error': "No files in files[] list"
                }, service=SERVICE_NAME)
                error_message = get_utterance('file_server', 'upload_files', 4, language_code)
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
                        
                    if '.' in filename and filename.rsplit('.', 1)[1].lower() in self.core.allowed_extensions:
                        file_id = str(uuid.uuid4())
                        file_path = os.path.join(self.core.upload_folder, file_id)
                        
                        # Save file
                        file.save(file_path)
                        
                        # Get file metadata
                        metadata = self.core.get_file_metadata(file_path)
                        
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
                        self.core.log_event('upload_files', 'failed', {
                            'error': f"Invalid file type: {extension} for file: {file.filename}"
                        }, service=SERVICE_NAME)
                        error_message = get_utterance('file_server', 'upload_files', 5, language_code)
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
            result = self.core.process_batch_files(grievance_id, file_data_list)
            
            response_data = {
                "status": "success",
                "message": "Files processed successfully",
                "files": uploaded_files
            }
            
            if oversized_files:
                response_data["oversized_files"] = oversized_files
                response_data["max_file_size"] = MAX_FILE_SIZE
            
            self.core.log_event('upload_files', 'completed', {
                'grievance_id': grievance_id,
                'processed_files': len(uploaded_files),
                'oversized_files': len(oversized_files)
            }, service=SERVICE_NAME)
            
            return jsonify(response_data), 202
            
        except Exception as e:
            self.core.log_event('upload_files', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            error_message = get_utterance('file_server', 'upload_files', 6, language_code)
            return jsonify({"error": error_message}), 500

    def get_files(self, grievance_id):
        """Get list of files for a grievance"""
        try:
            language_code = self._get_language_code()
            self.core.log_event('get_files', 'started', {
                'grievance_id': grievance_id
            }, service=SERVICE_NAME)
            
            files = db_manager.get_grievance_files(grievance_id)
            
            self.core.log_event('get_files', 'completed', {
                'grievance_id': grievance_id,
                'file_count': len(files)
            }, service=SERVICE_NAME)
            
            return jsonify({"files": files}), 200
        except Exception as e:
            self.core.log_event('get_files', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            error_message = get_utterance('file_server', 'get_files', 1, language_code)
            return jsonify({"error": error_message}), 500

    def download_file(self, file_id):
        """Download a specific file"""
        try:
            language_code = self._get_language_code()
            self.core.log_event('download_file', 'started', {
                'file_id': file_id
            }, service=SERVICE_NAME)
            
            file_data = db_manager.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                self.core.log_event('download_file', 'completed', {
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
            self.core.log_event('download_file', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            return jsonify({"error": "Internal server error"}), 500

    def get_file_status(self, file_id):
        """Get the processing status of a file"""
        try:
            language_code = self._get_language_code()
            self.core.log_event('get_file_status', 'started', {
                'file_id': file_id
            }, service=SERVICE_NAME)
            
            status = db_manager.get_file_status(file_id)
            if status:
                self.core.log_event('get_file_status', 'completed', {
                    'file_id': file_id,
                    'status': status
                }, service=SERVICE_NAME)
                return jsonify({"status": status}), 200
            return jsonify({"error": "File not found"}), 404
        except Exception as e:
            self.core.log_event('get_file_status', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            return jsonify({"error": "Internal server error"}), 500

    def get_grievance_review(self, grievance_id):
        """Get all review data for a grievance"""
        try:
            language_code = self._get_language_code()
            self.core.log_event('get_grievance_review', 'started', {
                'grievance_id': grievance_id
            }, service=SERVICE_NAME)
            
            data = db_manager.get_grievance_review_data(grievance_id)
            if not data:
                self.core.log_event('get_grievance_review', 'failed', {
                    'grievance_id': grievance_id,
                    'error': 'Not found'
                }, service=SERVICE_NAME)
                return jsonify({'error': 'Not found'}), 404
                
            self.core.log_event('get_grievance_review', 'completed', {
                'grievance_id': grievance_id
            }, service=SERVICE_NAME)
            return jsonify(data), 200
        except Exception as e:
            self.core.log_event('get_grievance_review', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            return jsonify({'error': 'Internal server error'}), 500

    def update_grievance_review(self, grievance_id):
        """Update review data for a grievance (all at once)"""
        try:
            language_code = self._get_language_code()
            self.core.log_event('update_grievance_review', 'started', {
                'grievance_id': grievance_id
            }, service=SERVICE_NAME)
            
            if not request.is_json:
                self.core.log_event('update_grievance_review', 'failed', {
                    'error': 'Request must be JSON'
                }, service=SERVICE_NAME)
                return jsonify({'error': 'Request must be JSON'}), 400
                
            data = request.get_json()
            success = db_manager.update_grievance_review_data(grievance_id, data)
            if not success:
                self.core.log_event('update_grievance_review', 'failed', {
                    'error': 'Update failed'
                }, service=SERVICE_NAME)
                return jsonify({'error': 'Update failed'}), 400
                
            self.core.log_event('update_grievance_review', 'completed', {
                'grievance_id': grievance_id
            }, service=SERVICE_NAME)
            return jsonify({'message': 'Update successful'}), 200
        except Exception as e:
            self.core.log_event('update_grievance_review', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            return jsonify({'error': 'Internal server error'}), 500

    def get_file(self, filename):
        """Serve uploaded files"""
        try:
            language_code = self._get_language_code()
            self.core.log_event('get_file', 'started', {
                'filename': filename
            }, service=SERVICE_NAME)
            
            result = send_from_directory(self.core.upload_folder, filename)
            
            self.core.log_event('get_file', 'completed', {
                'filename': filename
            }, service=SERVICE_NAME)
            
            return result
        except Exception as e:
            self.core.log_event('get_file', 'failed', {
                'error': str(e)
            }, service=SERVICE_NAME)
            return jsonify({'error': str(e)}), 404

# Initialize the core and API instances
file_server_core = FileServerCore()
file_server = FileServerAPI(file_server_core)

# Export the blueprint for use in the main app
file_server_bp = file_server.blueprint
