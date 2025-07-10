import os
from flask import request, jsonify, send_file, Blueprint, send_from_directory
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import wave
import contextlib
from ..services.database_services.postgres_services.db_manager import db_manager
from ..config.constants import (
    MAX_FILE_SIZE, 
    TASK_STATUS
)
from ..shared_functions.utterance_mapping_server import get_utterance
from typing import Dict, Any, Optional, List
from ..api.api_manager import APIManager
from ..services.file_server_core import FileServerCore
from task_queue.registered_tasks import process_batch_files_task, process_file_upload_task
from icecream import ic

SUCCESS = TASK_STATUS['SUCCESS']
IN_PROGRESS = TASK_STATUS['IN_PROGRESS']
FAILED = TASK_STATUS['FAILED']
ERROR = TASK_STATUS['ERROR']
RETRYING = TASK_STATUS['RETRYING']

file_server_core = FileServerCore()

class FileServerAPI:
    """API routes for file operations"""
    
    def __init__(self, core: FileServerCore):
        self.core = core
        self.blueprint = Blueprint('file_server', __name__)
        self._register_routes()

    def _get_language_code(self) -> str:
        """Get language code from request parameters or headers"""
        return request.args.get('language', 'en')

    def _extract_session_type_from_grievance_id(self, grievance_id: str) -> str:
        """Extract session type from grievance_id suffix
        
        Args:
            grievance_id: The grievance ID (e.g., 'GR-20241201-KO-JH-ABC1-A')
            
        Returns:
            str: Session type ('accessible' for 'A', 'bot' for 'B', 'unknown' for others)
        """
        return self.__class__.extract_session_type_from_grievance_id(grievance_id)

    @staticmethod
    def extract_session_type_from_grievance_id(grievance_id: str) -> str:
        """Extract session type from grievance_id suffix (static method)
        
        Args:
            grievance_id: The grievance ID (e.g., 'GR-20241201-KO-JH-ABC1-A')
            
        Returns:
            str: Session type ('accessible' for 'A', 'bot' for 'B', 'unknown' for others)
        """
        if not grievance_id or '-' not in grievance_id:
            return 'unknown'
        
        # Get the last part after the last dash
        suffix = grievance_id.split('-')[-1]
        if len(suffix) == 1:
            if suffix == 'A':
                return 'accessible'
            elif suffix == 'B':
                return 'bot'
        
        return 'unknown'

    def _register_routes(self):
        """Register all routes with the blueprint"""
        self.blueprint.route('/')(self.health_check)
        self.blueprint.route('/test-db')(self.test_db)
        self.blueprint.route('/generate-ids', methods=['POST'])(self.generate_ids)
        self.blueprint.route('/upload-files', methods=['POST'])(self.upload_files)
        self.blueprint.route('/files/<grievance_id>', methods=['GET'])(self.get_files)
        self.blueprint.route('/download/<file_id>', methods=['GET'])(self.download_file)
        self.blueprint.route('/file-status/<file_id>', methods=['GET'])(self.get_file_status)
        self.blueprint.route('/grievance-review/<grievance_id>', methods=['GET'])(self.get_grievance_review)
        self.blueprint.route('/grievance-review/<grievance_id>', methods=['POST'])(self.update_grievance_review)
        self.blueprint.route('/files/<filename>')(self.get_file)
        self.blueprint.route('/test-upload', methods=['POST'])(self.test_upload)
        self.blueprint.route('/task-status', methods=['POST'])(self.task_status_update)

    @staticmethod
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "ok", "message": "File server is running"})

    def test_db(self):
        """Test database connectivity"""
        try:
            self.core.log_event(event_type=IN_PROGRESS, details={})
            
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
                "status": SUCCESS, 
                "message": "Database connection successful",
                "tables_exist": tables_count > 0,
                "grievance_count": grievance_count,
                "test_grievance_id": test_id
            })
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            return jsonify({
                "status": ERROR, 
                "message": f"Database connection error: {str(e)}"
            }), 500
            
    def generate_ids(self):
        """Generate grievance_id and complainant_id using centralized ID generation"""
        try:
            self.core.log_event(event_type=IN_PROGRESS, details={'method': 'POST', 'endpoint': '/generate-ids'})
            
            # Get optional parameters from request
            data = request.get_json() or {}
            province = data.get('province', 'KO')  # Default to 'KO' if not provided
            district = data.get('district', 'JH')  # Default to 'JH' if not provided
            
            # Generate both IDs using the centralized function
            grievance_id = db_manager.base.generate_id(type='grievance_id', province=province, district=district)
            complainant_id = db_manager.base.generate_id(type='complainant_id', province=province, district=district)
            
            self.core.log_event(event_type='completed', details={
                'grievance_id': grievance_id,
                'complainant_id': complainant_id,
                'province': province,
                'district': district
            })
            
            return jsonify({
                'status': SUCCESS,
                'grievance_id': grievance_id,
                'complainant_id': complainant_id,
                'province': province,
                'district': district
            }), 200
            
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            return jsonify({
                'status': ERROR,
                'message': f'Failed to generate IDs: {str(e)}'
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
                    wrong_extensions_list.append({'file_name': filename, 'extension': 'None'})
                elif extension not in self.core.allowed_extensions:
                    wrong_extensions_list.append({'file_name': filename, 'extension': extension})
                    continue
                
                else:
                    file_id = str(uuid.uuid4())
                    # Create grievance-specific directory
                    grievance_dir = os.path.join(self.core.upload_folder, request.form.get('grievance_id'))
                    os.makedirs(grievance_dir, exist_ok=True)
                    
                    # Save file in grievance directory
                    file_path = os.path.join(grievance_dir, filename)
                    
                    # Save file
                    file.save(file_path)
                    
                    # Get file metadata
                    metadata = self.core.get_file_metadata(file_path)
                    
                    # Prepare file data
                    file_data = {
                        'file_id': file_id,
                        'file_name': filename,
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
            self.core.log_event(event_type=IN_PROGRESS, details={'method': 'POST', 'endpoint': '/upload-files'})
            
            # Check if grievance_id is provided
            grievance_id = request.form.get('grievance_id')
            session_id = request.form.get('session_id')
            self.source = self._extract_session_type_from_grievance_id(grievance_id)

            
            self.core.log_event(event_type=IN_PROGRESS, details={
                'grievance_id': grievance_id,
                'source': self.source,
                'session_id': session_id
            })
            
            if not grievance_id:
                self.core.log_event(event_type=FAILED, details={'error': 'No grievance_id provided'})
                error_message = get_utterance('file_server', 'upload_files', 1, language_code)
                return jsonify({"error": error_message}), 400

            # Check if any file was sent
            if 'files[]' not in request.files:
                self.core.log_event(event_type=FAILED, details={'error': "No files[] in request.files"})
                error_message = get_utterance('file_server', 'upload_files', 3, language_code)
                return jsonify({"error": error_message}), 400

            files = request.files.getlist('files[]')
            self.core.log_event(event_type=IN_PROGRESS, details={'file_count': len(files)})
            
            if not files:
                self.core.log_event(event_type=FAILED, details={'error': "No files in files[] list"})
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
                self.core.log_event(event_type=FAILED, details={'error': "All files were invalid"})

            else:
                file = uploaded_files[0]
                result = process_file_upload_task.delay(grievance_id=grievance_id, file_data=file, session_id=session_id)

                response_data = jsonify({
                    "status": IN_PROGRESS,
                    "session_id": session_id,
                    "message": "Files are being processed - those listed in oversized_files and wrong_extensions_list will be ignored",
                    "files": [file['file_id'] for file in uploaded_files],
                    "oversized_files": oversized_files,
                    "wrong_extensions_list": wrong_extensions_list,
                    "max_file_size": MAX_FILE_SIZE,
                    "task_id": result.id
                }),202
                        
            return response_data
            
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            error_message = get_utterance('file_server', 'upload_files', 6, language_code)
            return jsonify({"error": error_message}), 500

    def get_files(self, grievance_id):
        """Get list of files for a grievance"""
        try:
            language_code = self._get_language_code()
            session_type = self._extract_session_type_from_grievance_id(grievance_id)
            self.core.log_event(event_type=IN_PROGRESS, details={
                'grievance_id': grievance_id,
                'session_type': session_type
            })
            
            files = db_manager.get_grievance_files(grievance_id)
            
            self.core.log_event(event_type='completed', details={
                'grievance_id': grievance_id, 
                'file_count': len(files),
                'session_type': session_type
            })
            
            return jsonify({"files": files}), 200
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            error_message = get_utterance('file_server', 'get_files', 1, language_code)
            return jsonify({"error": error_message}), 500

    def download_file(self, file_id):
        """Download a specific file"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type=IN_PROGRESS, details={'file_id': file_id})
            
            file_data = db_manager.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                self.core.log_event(event_type='completed', details={'file_id': file_id, 'file_name': file_data['file_name']})
                return send_file(
                    file_data['file_path'],
                    as_attachment=True,
                    download_name=file_data['file_name']
                )
            return jsonify({"error": "File not found"}), 404
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            return jsonify({"error": "Internal server error"}), 500

    def get_file_status(self, file_id):
        """Get the processing status of a file"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type=IN_PROGRESS, details={'file_id': file_id})
            
            if db_manager.is_file_saved(file_id):
                self.core.log_event(event_type='completed', details={'file_id': file_id, 'status': SUCCESS})
                return jsonify({"status": SUCCESS, "message": "File is saved in the database"}), 200
            else:
                self.core.log_event(event_type='not_found', details={'file_id': file_id})
                return jsonify({"status": IN_PROGRESS, "message": "File is not yet saved"}), 200
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            return jsonify({"error": "Internal server error"}), 500

    def get_grievance_review(self, grievance_id):
        """Get all review data for a grievance"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type=IN_PROGRESS, details={'grievance_id': grievance_id})
            
            data = db_manager.get_grievance_review_data(grievance_id)
            if not data:
                self.core.log_event(event_type=FAILED, details={'grievance_id': grievance_id, 'error': 'Not found'})
                return jsonify({'error': 'Not found'}), 404
                
            self.core.log_event(event_type='completed', details={'grievance_id': grievance_id})
            return jsonify(data), 200
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            return jsonify({'error': 'Internal server error'}), 500

    def update_grievance_review(self, grievance_id):
        """Update review data for a grievance (all at once)"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type=IN_PROGRESS, details={'grievance_id': grievance_id})
            
            if not request.is_json:
                self.core.log_event(event_type=FAILED, details={'error': 'Request must be JSON'})
                return jsonify({'error': 'Request must be JSON'}), 400
                
            data = request.get_json()
            success = db_manager.update_grievance_review_data(grievance_id, data)
            if not success:
                self.core.log_event(event_type=FAILED, details={'error': 'Update failed'})
                return jsonify({'error': 'Update failed'}), 400
                
            self.core.log_event(event_type='completed', details={'grievance_id': grievance_id})
            return jsonify({'message': 'Update successful'}), 200
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            return jsonify({'error': 'Internal server error'}), 500

    def get_file(self, filename):
        """Serve uploaded files"""
        try:
            language_code = self._get_language_code()
            self.core.log_event(event_type=IN_PROGRESS, details={'file_name': filename})
            
            result = send_from_directory(self.core.upload_folder, filename)
            
            self.core.log_event(event_type='completed', details={'file_name': filename})
            
            return result
        except Exception as e:
            self.core.log_event(event_type=FAILED, details={'error': str(e)})
            return jsonify({'error': str(e)}), 404

    def test_upload(self):
        """Test endpoint to verify request handling"""
        try:
            self.core.log_event(event_type='test_upload', details={
                'method': request.method,
                'form_data': dict(request.form),
                'files': [f.filename for f in request.files.getlist('files[]')] if 'files[]' in request.files else [],
                'headers': dict(request.headers)
            })
            return jsonify({"status": "received", "message": "Test upload endpoint received request"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def task_status_update(self):
        """
        API endpoint to receive task status updates and emit websocket messages
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Extract required fields - support both grievance_id and session_id
            grievance_id = data.get('grievance_id')
            session_id = data.get('session_id')
            source = 'A' if grievance_id and grievance_id.endswith('A') else 'B'  # default to B "Bot"
            status = data.get('status')
            task_data = data.get('data', {})
            
            if not status:
                return jsonify({'error': 'Missing required field: status'}), 400
            
            if not grievance_id and not session_id:
                return jsonify({'error': 'Missing required field: grievance_id or session_id'}), 400
            
            # Log the incoming request
            self.core.log_event(event_type='task_status_update', details={
                'grievance_id': grievance_id,
                'session_id': session_id,
                'status': status,
                'data': task_data,
                'source': source
            })
            
            # Import socketio here to avoid circular imports
            from .websocket_utils import socketio, emit_status_update_accessible
            
            if source == 'A':
                # Emit to the grievance room (accessible interface)
                 # Prepare websocket data
                websocket_data = {
                    'status': status,
                    'data': task_data,
                    'timestamp': eventlet.time.time()
                }
                
                # Add grievance_id if available
                if grievance_id:
                    websocket_data['grievance_id'] = grievance_id
                    emit_status_update_accessible(grievance_id, status, task_data)

            # for the bot case, we don't need to use websocket as the frontend listens to the event from the backend
            self.core.log_event(event_type='task_status_emitted', details={
                'grievance_id': grievance_id,
                'session_id': session_id,
                'emit_websocket': True if source == 'A' else False,
                'status': status,
                'source': source
            })
            
            return jsonify({
                'status': status,
                'message': 'Task status update sent',
                'grievance_id': grievance_id,
                'session_id': session_id,
                'source': source,
                'data': task_data
            }), 200
            
        except Exception as e:
            self.core.log_event(event_type='task_status_error', details={'error': str(e)})
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500


file_server = FileServerAPI(file_server_core)

# Export the blueprint for use in the main app
file_server_bp = file_server.blueprint
