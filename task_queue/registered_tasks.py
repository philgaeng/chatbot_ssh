"""
List of all registered tasks in the system.

This module serves as a central registry of all tasks that can be processed by Celery.
Each task should be documented with its purpose, priority level, and any dependencies.
"""

from typing import Dict, Any, List, Tuple, Callable, Optional
from .tasks import high_priority_task, medium_priority_task, low_priority_task
from actions_server.constants import CLASSIFICATION_DATA, ALLOWED_EXTENSIONS
from celery import shared_task, current_task
import logging
import traceback
from task_queue.monitoring import log_task_event
from .config import celery_app  # Import celery_app instance

from actions_server.db_manager import db_manager
from actions_server.messaging import CommunicationClient
import os
import functools
import time
from task_queue.task_manager import TaskManager, TaskStatusEmitter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Task registry for monitoring and task lookup
TASK_REGISTRY = {}

# Central config for task types
TASK_TYPE_CONFIG = {
    "LLM": {"priority": "high", "queue": "llm_queue", "bind": True},
    "File Upload": {"priority": "medium", "queue": "default", "bind": False},
    "Messaging": {"priority": "high", "queue": "default", "bind": False},
    "Database": {"priority": "high", "queue": "default", "bind": False},
    # Add more as needed
}

#---------------------------------UTILITY FUNCTIONS---------------------------------
def register_task(task_type: str):
    """
    Decorator to register a task in the TASK_REGISTRY and apply Celery task.
    Args:
        task_type: Type of task (e.g., 'LLM', 'File Upload', etc.)
    """
    if task_type not in TASK_TYPE_CONFIG:
        raise ValueError(f"Unknown task_type '{task_type}'. Please add it to TASK_TYPE_CONFIG.")
    config = TASK_TYPE_CONFIG[task_type]
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
            
        # Register in TASK_REGISTRY
        TASK_REGISTRY[func.__name__] = {
            'name': func.__name__.replace('_', ' ').title(),
            'description': func.__doc__ or '',
            'priority': config['priority'],
            'type': task_type,
            'queue': config['queue'],
            'task': wrapper
        }
        
        # Register with Celery
        celery_task = celery_app.task(
            bind=config.get('bind', False),
            name=func.__name__,
            queue=config['queue']
        )(wrapper)
        
        # Store the Celery task in the registry
        TASK_REGISTRY[func.__name__]['celery_task'] = celery_task
        
        return celery_task
    return decorator

# Helper function to get task function from registry
def get_task_function(task_name: str) -> Optional[Callable]:
    """
    Get a task function from the registry by name.
    
    Args:
        task_name: Name of the task
        
    Returns:
        Task function if found, None otherwise
    """
    task_info = TASK_REGISTRY.get(task_name)
    return task_info['task'] if task_info else None

# Helper function to get task metadata from registry
def get_task_metadata(task_name: str):
    """Get task metadata from the registry by name"""
    task_info = TASK_REGISTRY.get(task_name)
    if task_info:
        return {k: v for k, v in task_info.items() if k != 'task'}
    raise KeyError(f"Task '{task_name}' not found in registry")

#---------------------------------REGISTERED TASKS---------------------------------
# File Processing Tasks
@register_task(task_type='File Upload')
def process_file_upload_task(grievance_id: str, file_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single file upload.
    
    Args:
        grievance_id: ID of the grievance
        file_data: File metadata and path
        
    Returns:
        Dict containing processing results
    """
    from actions_server.file_server import process_file_upload
    task_mgr = TaskManager(emit_websocket=False)
    task_mgr.start_task(grievance_id, stage='single_file_upload')
    try:
        result = process_file_upload(grievance_id, file_data)
        task_mgr.complete_task(result, stage='single_file_upload')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='single_file_upload')
        raise


@register_task(task_type='File Upload')
def process_batch_files_task(grievance_id: str, files_data: List[Dict[str, Any]], allowed_extensions: List[str] = ALLOWED_EXTENSIONS) -> Dict[str, Any]:
    """
    Process multiple files in batch.
    
    Args:
        grievance_id: ID of the grievance
        files_data: List of file metadata and paths
        
    
        Dict containing batch processing results
    """
    from actions_server.file_server import process_batch_files
    task_mgr = TaskManager(emit_websocket=False)
    task_mgr.start_task(grievance_id, stage='batch_file_processing')
    try:
        result = process_batch_files(grievance_id, files_data, ALLOWED_EXTENSIONS)
        task_mgr.complete_task(result, stage='batch_file_processing')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='batch_file_processing')
        raise

# Messaging Tasks
@register_task(task_type='Messaging')
def send_sms_task(phone_number: str, message: str, grievance_id: str = None):
    """Send an SMS message"""
    from actions_server.messaging import SMSClient
    task_mgr = TaskManager(emit_websocket=False)
    if grievance_id:
        task_mgr.start_task(grievance_id, stage='send_sms', extra_data={'phone_number': phone_number})
    try:
        result = SMSClient().send_sms(phone_number, message)
        if grievance_id:
            task_mgr.complete_task(result, stage='send_sms')
        return result
    except Exception as e:
        if grievance_id:
            task_mgr.fail_task(str(e), stage='send_sms')
        raise

@register_task(task_type='Messaging')
def send_email_task(to_emails, subject, body, grievance_id: str = None):
    """Send an email message"""
    from actions_server.messaging import EmailClient
    task_mgr = TaskManager(emit_websocket=False)
    if grievance_id:
        task_mgr.start_task(grievance_id, stage='send_email', extra_data={'to_emails': to_emails})
    try:
        result = EmailClient().send_email(to_emails, subject, body)
        if grievance_id:
            task_mgr.complete_task(result, stage='send_email')
        return result
    except Exception as e:
        if grievance_id:
            task_mgr.fail_task(str(e), stage='send_email')
        raise

# Voice Grievance & LLM Tasks

@register_task(task_type='LLM')
def transcribe_audio_file_task(self, file_path: str, language: str = None, grievance_id: str = None) -> Dict[str, Any]:
    """Transcribe an audio file."""
    task_mgr = TaskManager(self, emit_websocket=False)
    if grievance_id:
        task_mgr.start_task(grievance_id, stage='transcription', extra_data={'file_path': file_path})
    try:
        from actions_server.LLM_helpers import transcribe_audio_file
        transcription = transcribe_audio_file(file_path, language)
        result = {
            'status': 'SUCCESS',
            'transcription': transcription
        }
        task_mgr.complete_task(result, stage='transcription')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='transcription')
        return {
            'status': 'error',
            'error': str(e)
        }

@register_task(task_type='LLM')
def classify_and_summarize_grievance_task(self, recording_id: str) -> Dict[str, Any]:
    """Classify and summarize a grievance text, and store the result if grievance_id is provided."""
    task_mgr = TaskManager(self)
    # Try to get grievance_id from transcription_data
    try:
        transcription_data = db_manager.get_transcription_for_recording_id(recording_id)
        grievance_id = transcription_data.get('grievance_id')
    except Exception as e:
        task_mgr.fail_task(str(e))
        return {
            'status': 'error',
            'error': str(e)
        }
    task_mgr.start_task(grievance_id=grievance_id)
    try:
        from actions_server.LLM_helpers import classify_and_summarize_grievance
        language_code = transcription_data.get('language_code')
        grievance_details = transcription_data.get('automated_transcript')
        field_name = transcription_data.get('field_name')
        if field_name == 'grievance_details':
            result = classify_and_summarize_grievance(grievance_details, language_code)
        else:
            raise ValueError(f"Field name {field_name} is not grievance details")
    except Exception as llm_error:
        task_mgr.fail_task(str(llm_error))
        return {
            'status': 'error',
            'stage': 'llm',
            'error': str(llm_error)
        }
    try:
        db_manager.grievance.update_grievance_classification(
            grievance_id,
            result['summary'],
            result['categories']
        )
        task_mgr.complete_task(result)
        return {
            'status': 'SUCCESS',
            'summary': result['summary'],
            'categories': result['categories']
        }
    except Exception as db_error:
        task_mgr.fail_task(str(db_error))
        return {
            'status': 'error',
            'stage': 'db',
            'error': str(db_error),
            'summary': result.get('summary'),
            'categories': result.get('categories')
        }

@register_task(task_type='LLM')
def extract_contact_info_task(self, recording_id: str) -> Dict[str, Any]:
    """Extract user information from text"""
    task_mgr = TaskManager(self)
    try:
        transcription_data = db_manager.recording.get_transcription_for_recording_id(recording_id)
        contact_text = transcription_data.get('automated_transcript')
        field_name = transcription_data.get('field_name')
        grievance_id = transcription_data.get('grievance_id')
        language_code = transcription_data.get('language_code')
        recording_type = transcription_data.get('recording_type')
        if 'user' not in recording_type:
            raise ValueError(f"Field name {field_name} is not contact info")
    except Exception as e:
        task_mgr.fail_task(str(e))
        return {
            'status': 'error',
            'error': str(e)
        }
    task_mgr.start_task(grievance_id=grievance_id)
    try:
        from actions_server.LLM_helpers import extract_contact_info
        contact_data = {field_name: contact_text}
        result = extract_contact_info(contact_data)
    except Exception as llm_error:
        task_mgr.fail_task(str(llm_error))
        return {
            'status': 'error',
            'stage': 'llm',
            'error': str(llm_error)
        }
    if result[field_name] == '':
        task_mgr.fail_task(f"No result found in extract_contact_info_task for field {field_name}")
        return {
            'status': 'error',
            'error': f"No result found in extract_contact_info_task for field {field_name}"
        }
    else:
        try:
            if db_manager.user.get_user(grievance_id):
                db_manager.user.update_user(grievance_id, result)
            else:
                db_manager.user.create_user(grievance_id, result)
            task_mgr.complete_task(result)
            return {
                'status': 'SUCCESS',
                'result': result
            }
        except Exception as db_error:
            task_mgr.fail_task(str(db_error))
            return {
                'status': 'error',
                'stage': 'db',
                'error': str(db_error)
            }

@register_task(task_type='LLM')
def translate_grievance_to_english_task(self, grievance_id: str) -> Dict[str, Any]:
    """Translate a grievance to English and save it to the database"""
    task_mgr = TaskManager(self)
    task_mgr.start_task(grievance_id=grievance_id)
    try:
        from actions_server.LLM_helpers import translate_grievance_to_english
        result = translate_grievance_to_english(grievance_id)
        task_mgr.complete_task(result)
        return {
            'status': 'SUCCESS',
            'result': result
        }
    except Exception as e:
        task_mgr.fail_task(str(e))
        return {
            'status': 'error',
            'error': str(e)
        }



@register_task(task_type='Database')
def store_user_info_task(result: Dict[str, Any], file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Store user information in database"""
    try:
        # Get IDs from file_data
        grievance_id = file_data.get('grievance_id')
        recording_id = file_data.get('recording_id')
        
        if not grievance_id or not recording_id:
            logger.error("Missing grievance_id or recording_id in file_data")
            return {'status': 'error', 'error': 'Missing required IDs'}
        
        # Store user info from result
        db_manager.update_user(grievance_id, result)
        return {'status': 'success', 'recording_id': recording_id}
    except Exception as e:
        logger.error(f"Error storing user info: {str(e)}")
        return {'status': 'error', 'error': str(e)}

@register_task(task_type='Database')
def store_grievance_task(result: Dict[str, Any], file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Store grievance details in database"""
    try:
        # Get IDs from file_data
        grievance_id = file_data.get('grievance_id')
        recording_id = file_data.get('recording_id')
        
        if not grievance_id or not recording_id:
            logger.error("Missing grievance_id or recording_id in file_data")
            return {'status': 'error', 'error': 'Missing required IDs'}
        
        # Store grievance details from result
        db_manager.update_grievance(grievance_id, result)
        return {'status': 'success', 'recording_id': recording_id}
    except Exception as e:
        logger.error(f"Error storing grievance details: {str(e)}")
        return {'status': 'error', 'error': str(e)}

@register_task(task_type='Database')
def store_transcription_task(result: Dict[str, Any], file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Store transcription in database"""
    try:
        # Get IDs from file_data
        grievance_id = file_data.get('grievance_id')
        recording_id = file_data.get('recording_id')
        
        if not grievance_id or not recording_id:
            logger.error("Missing grievance_id or recording_id in file_data")
            return {'status': 'error', 'error': 'Missing required IDs'}
        
        # Store transcription from result
        db_manager.update_transcription(grievance_id, result)
        return {'status': 'success', 'recording_id': recording_id}
    except Exception as e:
        logger.error(f"Error storing transcription: {str(e)}")
        return {'status': 'error', 'error': str(e)}

@register_task(task_type='Database')
def update_task_execution_task(execution_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Dynamically update any field(s) in a task execution record."""
    try:
        success = db_manager.task.update_task(execution_id, update_data)
        if success:
            return {'status': 'success', 'execution_id': execution_id}
        else:
            return {'status': 'error', 'error': 'Update failed', 'execution_id': execution_id}
    except Exception as e:
        logger.error(f"Error updating task execution: {str(e)}")
        return {'status': 'error', 'error': str(e), 'execution_id': execution_id} 
    
    