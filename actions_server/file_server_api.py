import os
from flask import request, jsonify, send_file, Blueprint, send_from_directory
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import wave
import contextlib
from actions_server.db_manager import db_manager
from actions_server.constants import (
    MAX_FILE_SIZE, 
)
from actions_server.utterance_mapping_server import get_utterance
from typing import Dict, Any, Optional, List
from actions_server.api_manager import APIManager
from actions_server.file_server_core import FileServerCore
from task_queue.registered_tasks import process_batch_files_task

file_server_core = FileServerCore()

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
            self.core.log_event(event_type='started', details={})
            
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
            
            self.core.log_event(event_type='completed', details={
                'tables_exist': tables_count > 0,
                'grievance_count': grievance_count,
                'test_grievance_id': test_id
            })
            
            return jsonify({
                "status": "ok", 
                "message": "Database connection successful",
                "tables_exist": tables_count > 0,
                "grievance_count": grievance_count,
                "test_grievance_id": test_id
            })
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            return jsonify({
                "status": "error", 
                "message": f"Database connection error: {str(e)}"
            }), 500
            
    def validate_files(self, files: List[Any]) -> bool:
        """Validate a file"""
        uploaded_files = []
        oversized_files = []
        wrong_extensions_list = []
        file_data_list = []

        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_size = len(file.read())
                file.seek(0)  # Reset file pointer
                
                if file_size > MAX_FILE_SIZE:
                    oversized_files.append(filename)
                    continue
                extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else None
                if not extension:
                    wrong_extensions_list.append({'filename': filename, 'extension': 'None'})
                elif extension not in self.core.allowed_extensions:
                    wrong_extensions_list.append({'filename': filename, 'extension': extension})
                    continue
                
                else:
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
                        **metadata
                    }
                    
                    uploaded_files.append(file_data)
                    
        return uploaded_files, oversized_files, wrong_extensions_list

    def upload_files(self):
        """Handle file uploads for a grievance"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type='started', details={'method': 'POST', 'endpoint': '/upload-files'})
            
            # Check if grievance_id is provided
            grievance_id = request.form.get('grievance_id')
            self.core.log_event(event_type='processing', details={'grievance_id': grievance_id})
            
            if not grievance_id:
                self.core.log_event(event_type='failed', details={'error': 'No grievance_id provided'})
                error_message = get_utterance('file_server', 'upload_files', 1, language_code)
                return jsonify({"error": error_message}), 400

            # Reject uploads for pending grievances
            if grievance_id == "pending":
                self.core.log_event(event_type='failed', details={'error': "Attempted to upload file for pending grievance"})
                error_message = get_utterance('file_server', 'upload_files', 2, language_code)
                return jsonify({"error": error_message}), 400

            # Check if any file was sent
            if 'files[]' not in request.files:
                self.core.log_event(event_type='failed', details={'error': "No files[] in request.files"})
                error_message = get_utterance('file_server', 'upload_files', 3, language_code)
                return jsonify({"error": error_message}), 400

            files = request.files.getlist('files[]')
            self.core.log_event(event_type='processing', details={'file_count': len(files)})
            
            if not files:
                self.core.log_event(event_type='failed', details={'error': "No files in files[] list"})
                error_message = get_utterance('file_server', 'upload_files', 4, language_code)
                return jsonify({"error": error_message}), 400

            uploaded_files, oversized_files, wrong_extensions_list = self.validate_files(files)

            if not uploaded_files:
                response_data = jsonify({
                    "error": "All files were invalid",
                    "wrong_extensions_list": wrong_extensions_list,
                    "oversized_files": oversized_files,
                    "max_file_size": MAX_FILE_SIZE
                }), 400
                self.core.log_event(event_type='failed', details={'error': "All files were invalid"})

            else:
                # Process files in batch
                result = process_batch_files_task.delay(grievance_id, uploaded_files)

                response_data = jsonify({
                    "status": "processing",
                    "message": "Files are being processed - those listed in oversized_files and wrong_extensions_list will be ignored",
                    "files": [file['file_id'] for file in uploaded_files],
                    "oversized_files": oversized_files,
                    "wrong_extensions_list": wrong_extensions_list,
                    "max_file_size": MAX_FILE_SIZE
                }),202
                        
            return response_data
            
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            error_message = get_utterance('file_server', 'upload_files', 6, language_code)
            return jsonify({"error": error_message}), 500

    def get_files(self, grievance_id):
        """Get list of files for a grievance"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type='started', details={'grievance_id': grievance_id})
            
            files = db_manager.get_grievance_files(grievance_id)
            
            self.core.log_event(event_type='completed', details={'grievance_id': grievance_id, 'file_count': len(files)})
            
            return jsonify({"files": files}), 200
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            error_message = get_utterance('file_server', 'get_files', 1, language_code)
            return jsonify({"error": error_message}), 500

    def download_file(self, file_id):
        """Download a specific file"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type='started', details={'file_id': file_id})
            
            file_data = db_manager.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                self.core.log_event(event_type='completed', details={'file_id': file_id, 'filename': file_data['file_name']})
                return send_file(
                    file_data['file_path'],
                    as_attachment=True,
                    download_name=file_data['file_name']
                )
            return jsonify({"error": "File not found"}), 404
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            return jsonify({"error": "Internal server error"}), 500

    def get_file_status(self, file_id):
        """Get the processing status of a file"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type='started', details={'file_id': file_id})
            
            status = db_manager.get_file_status(file_id)
            if status:
                self.core.log_event(event_type='completed', details={'file_id': file_id, 'status': status})
                return jsonify({"status": status}), 200
            return jsonify({"error": "File not found"}), 404
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            return jsonify({"error": "Internal server error"}), 500

    def get_grievance_review(self, grievance_id):
        """Get all review data for a grievance"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type='started', details={'grievance_id': grievance_id})
            
            data = db_manager.get_grievance_review_data(grievance_id)
            if not data:
                self.core.log_event(event_type='failed', details={'grievance_id': grievance_id, 'error': 'Not found'})
                return jsonify({'error': 'Not found'}), 404
                
            self.core.log_event(event_type='completed', details={'grievance_id': grievance_id})
            return jsonify(data), 200
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            return jsonify({'error': 'Internal server error'}), 500

    def update_grievance_review(self, grievance_id):
        """Update review data for a grievance (all at once)"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type='started', details={'grievance_id': grievance_id})
            
            if not request.is_json:
                self.core.log_event(event_type='failed', details={'error': 'Request must be JSON'})
                return jsonify({'error': 'Request must be JSON'}), 400
                
            data = request.get_json()
            success = db_manager.update_grievance_review_data(grievance_id, data)
            if not success:
                self.core.log_event(event_type='failed', details={'error': 'Update failed'})
                return jsonify({'error': 'Update failed'}), 400
                
            self.core.log_event(event_type='completed', details={'grievance_id': grievance_id})
            return jsonify({'message': 'Update successful'}), 200
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            return jsonify({'error': 'Internal server error'}), 500

    def get_file(self, filename):
        """Serve uploaded files"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type='started', details={'filename': filename})
            
            result = send_from_directory(self.core.upload_folder, filename)
            
            self.core.log_event(event_type='completed', details={'filename': filename})
            
            return result
        except Exception as e:
            self.core.log_event(event_type='failed', details={'error': str(e)})
            return jsonify({'error': str(e)}), 404


file_server = FileServerAPI(file_server_core)

# Export the blueprint for use in the main app
file_server_bp = file_server.blueprint
