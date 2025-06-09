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
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'))




        
class FileServerCore(APIManager):
    """Core business logic for file operations"""
    
    def __init__(self, upload_folder: str = UPLOAD_FOLDER, allowed_extensions: list = ALLOWED_EXTENSIONS):
        super().__init__(SERVICE_NAME)
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
            self.log_event(event_type='started', details={'file_id': file_id})
            
            file_data = db_manager.file.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                self.log_event(event_type='completed', details={'file_id': file_id, 'exists': True})
                return file_data
            
            self.log_event(event_type='completed', details={'file_id': file_id, 'exists': False})
            return None
        except Exception as e:
            self.log_event(event_type='failed', details={'file_id': file_id, 'error': str(e)})
            return None

    def get_audio_metadata(self, file_path: str) -> dict:
        """Get metadata for an audio file"""
        try:
            self.log_event(event_type='started', details={'file_path': file_path})
            
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
            
            self.log_event(event_type='completed', details={'file_path': file_path, 'metadata': metadata})
            
            return metadata
            
        except Exception as e:
            self.log_event(event_type='failed', details={'file_path': file_path, 'error': str(e)})
            return {}

    def get_file_metadata(self, file_path: str) -> dict:
        """Get metadata for a file"""
        try:
            self.log_event(event_type='started', details={'file_path': file_path})
            
            file_stats = os.stat(file_path)
            metadata = {
                'file_size': file_stats.st_size,
                'created_date': datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                'modified_date': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.log_event(event_type='completed', details={'file_path': file_path, 'metadata': metadata})
            
            return metadata
        except Exception as e:
            self.log_event(event_type='failed', details={'file_path': file_path, 'error': str(e)})
            return {}

    def process_file_upload(self, grievance_id: str, file_data: dict) -> dict:
        """Process an uploaded file"""
        self.log_event(event_type='started', details={'grievance_id': grievance_id, 'file': file_data['file_name']})
        
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
        
        return file_data


    def process_batch_files(self, grievance_id: str, file_list: list) -> dict:
        """Process a batch of files for a grievance"""
        self.log_event(event_type='started', details={'grievance_id': grievance_id, 'file_count': len(file_list)})
        
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
                    self.log_event(event_type='failed', details={'grievance_id': grievance_id, 'file': file_data['filename'], 'error': str(e)})
                    results.append({
                        'status': 'failed',
                        'filename': file_data['filename'],
                        'error': str(e)
                    })
            
            self.log_event(event_type='completed', details={'grievance_id': grievance_id, 'success_count': len([r for r in results if r['status'] == 'success']), 'failed_count': len([r for r in results if r['status'] == 'failed'])})
            
            return {
                'status': 'completed',
                'grievance_id': grievance_id,
                'results': results
            }
            
        except Exception as e:
            self.log_event(event_type='failed', details={'grievance_id': grievance_id, 'error': str(e)})
            raise

    def allowed_mime_type(self, mime_type):
        """Check if mime type is allowed"""
        return mime_type in ALLOWED_MIME_TYPES 
    
# Initialize the core  instances
file_server_core = FileServerCore()
 