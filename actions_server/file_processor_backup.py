import os
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from actions_server.db_manager import db_manager
from actions_server.constants import (
    FILE_TYPES, 
    FILE_TYPE_MAX_SIZES,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB
)
from task_queue.tasks import medium_priority_task
from task_queue.monitoring import log_task_event
from task_queue.config import celery_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_file_type(filename: str) -> str:
    """Determine the type of file based on extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    for file_type, info in FILE_TYPES.items():
        if ext in info['extensions']:
            return file_type.lower()
    return 'other'

@medium_priority_task
def process_file_upload_task(grievance_id: str, file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an uploaded file (medium priority task)"""
    log_task_event('process_file_upload', 'started', {
        'grievance_id': grievance_id,
        'file': file_data['filename']
    })
    
    try:
        # Get file type
        file_type = get_file_type(file_data['filename'])
        
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
            
        log_task_event('process_file_upload', 'failed', {
            'grievance_id': grievance_id,
            'file': file_data['filename'],
            'error': str(e)
        })
        raise

def get_audio_metadata(file_path: str) -> Dict[str, Any]:
    """Get metadata for an audio file"""
    try:
        import wave
        import contextlib
        
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
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error getting audio metadata: {str(e)}")
        return {}

@medium_priority_task
def process_batch_files_task(grievance_id: str, file_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process a batch of files for a grievance"""
    log_task_event('process_batch_files', 'started', {
        'grievance_id': grievance_id,
        'file_count': len(file_list)
    })
    
    try:
        results = []
        for file_data in file_list:
            try:
                result = process_file_upload_task(grievance_id, file_data)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing file {file_data['filename']}: {str(e)}")
                results.append({
                    'status': 'failed',
                    'filename': file_data['filename'],
                    'error': str(e)
                })
        
        log_task_event('process_batch_files', 'completed', {
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
        log_task_event('process_batch_files', 'failed', {
            'grievance_id': grievance_id,
            'error': str(e)
        })
        raise

def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Get metadata for a file"""
    try:
        file_stats = os.stat(file_path)
        return {
            'file_size': file_stats.st_size,
            'created_date': datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
            'modified_date': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        logger.error(f"Error getting file metadata: {str(e)}")
        return {} 