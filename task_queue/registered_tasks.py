"""
List of all registered tasks in the system.

This module serves as a central registry of all tasks that can be processed by Celery.
Each task should be documented with its purpose, priority level, and any dependencies.
"""

from typing import Dict, Any, List, Tuple, Callable, Optional
from .tasks import high_priority_task, medium_priority_task, low_priority_task
from actions_server.constants import CLASSIFICATION_DATA
from celery import shared_task, current_task
import logging
import traceback
from task_queue.monitoring import log_task_event

from actions_server.db_manager import db_manager
from actions_server.messaging import CommunicationClient
import os
import functools
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Task registry for monitoring and task lookup
TASK_REGISTRY = {}

def register_task(task_type: str, priority: str = 'medium', bind: bool = False):
    """
    Decorator to register a task in the TASK_REGISTRY and apply Celery shared_task.
    
    Args:
        task_type: Type of task (e.g., 'File Upload', 'Messaging', 'LLM')
        priority: Task priority ('high', 'medium', 'low')
        bind: Whether to bind the task instance to the function (for self parameter)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get task context
            task = current_task
            if not task:
                return func(*args, **kwargs)
            
            # Record task start
            db_manager.record_task_start(
                task_id=task.id,
                grievance_id=kwargs.get('grievance_id'),
                task_name=func.__name__,
                task_type=task_type
            )
            
            try:
                # Execute the task
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = int((time.time() - start_time) * 1000)
                
                # Record successful completion
                db_manager.record_task_completion(
                    task_id=task.id,
                    status='SUCCESS',
                    execution_time_ms=execution_time,
                    result_text=str(result)
                )
                
                return result
                
            except Exception as e:
                # Record failure
                db_manager.record_task_completion(
                    task_id=task.id,
                    status='FAILED',
                    error_message=str(e)
                )
                raise
            
        # Register the task in TASK_REGISTRY
        TASK_REGISTRY[func.__name__] = {
            'name': func.__name__.replace('_', ' ').title(),
            'description': func.__doc__ or '',
            'priority': priority,
            'type': task_type,
            'task': wrapper
        }
        
        # Apply Celery shared_task decorator
        celery_task = shared_task(bind=bind, name=func.__name__)(wrapper)
        
        # Apply the appropriate priority decorator
        if priority == 'high':
            return high_priority_task(celery_task)
        elif priority == 'medium':
            return medium_priority_task(celery_task)
        else:
            return low_priority_task(celery_task)
            
    return decorator

# File Processing Tasks
@register_task(task_type='File Upload', priority='medium')
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
    return process_file_upload(grievance_id, file_data)

@register_task(task_type='File Upload', priority='medium')
def process_batch_files_task(grievance_id: str, files_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process multiple files in batch.
    
    Args:
        grievance_id: ID of the grievance
        files_data: List of file metadata and paths
        
    Returns:
        Dict containing batch processing results
    """
    from actions_server.file_server import process_batch_files
    return process_batch_files(grievance_id, files_data)

# Messaging Tasks
@register_task(task_type='Messaging', priority='high')
def send_sms_task(phone_number: str, message: str):
    """Send an SMS message"""
    from actions_server.messaging import SMSClient
    return SMSClient().send_sms(phone_number, message)

@register_task(task_type='Messaging', priority='high')
def send_email_task(to_emails, subject, body):
    """Send an email message"""
    from actions_server.messaging import EmailClient
    return EmailClient().send_email(to_emails, subject, body)

# Voice Grievance & LLM Tasks

@register_task(task_type='LLM', priority='high', bind=True)
def transcribe_audio_file_task(self, file_path: str, language: str = None) -> Dict[str, Any]:
    """Transcribe an audio file and queue classification if it's the grievance details"""
    try:
        # Import here to avoid circular imports
        from actions_server.LLM_helpers import transcribe_audio_file
        
        # Perform transcription
        transcription = transcribe_audio_file(file_path, language)
        
        # If this is the grievance details file, queue classification
        if 'grievance_details' in file_path:
            classify_task = classify_and_summarize_grievance_task.delay(
                transcription,
                language
            )
            return {
                'status': 'SUCCESS',
                'transcription': transcription,
                'classification_task_id': classify_task.id
            }
        
        return {
            'status': 'SUCCESS',
            'transcription': transcription
        }
        
    except Exception as e:
        logger.error(f"Error in transcribe_audio_file_task: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

@register_task(task_type='LLM', priority='high', bind=True)
def classify_and_summarize_grievance_task(self,
                                          recording_id: str, 
                                          ) -> Dict[str, Any]:
    """Classify and summarize a grievance text, and store the result if grievance_id is provided."""
    # Import here to avoid circular imports
    from actions_server.LLM_helpers import classify_and_summarize_grievance
    #get grievance text from db
    try:
        transcription_data = db_manager.get_transcription_for_recording_id(recording_id)
    except Exception as e:
        logger.error(f"Error retrieving grievance transcription for recording ID: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

    
    # LLM processing
    try:
        grievance_id = transcription_data.get('grievance_id')
        language_code = transcription_data.get('language_code')
        grievance_details = transcription_data.get('automated_transcript')
        field_name = transcription_data.get('field_name')
        if field_name == 'grievance_details':
            result = classify_and_summarize_grievance(grievance_details, language_code)
        else:
            raise ValueError(f"Field name {field_name} is not grievance details")
            result = {
                'status': 'FAILED',
                'error': f"Field name {field_name} is not grievance details"
            }
            
    except Exception as llm_error:
        logger.error(f"LLM error in classify_and_summarize_grievance_task: {str(llm_error)}")
        return {
            'status': 'error',
            'stage': 'llm',
            'error': str(llm_error)
        }
    # Store the result in the database
    try:
        db_manager.update_grievance_classification(
            grievance_id,
            result['summary'],
            result['categories']
        )
        return {
            'status': 'SUCCESS',
            'summary': result['summary'],
            'categories': result['categories']
        }
    except Exception as db_error:
        logger.error(f"DB error in classify_and_summarize_grievance_task: {str(db_error)}")
        return {
            'status': 'error',
            'stage': 'db',
            'error': str(db_error),
            'summary': result.get('summary'),
            'categories': result.get('categories')
        }


@register_task(task_type='LLM', priority='high', bind=True)
def extract_contact_info_task(self, recording_id: str) -> Dict[str, Any]:
    """Extract user information from text"""
    #get user text from transcription
    try:
        transcription_data = db_manager.get_transcription_for_recording_id(recording_id)
        contact_text = transcription_data.get('automated_transcript')
        field_name = transcription_data.get('field_name')
        grievance_id = transcription_data.get('grievance_id')
        language_code = transcription_data.get('language_code')
        if 'user' in field_name:
            pass
        else:
            raise ValueError(f"Field name {field_name} is not contact info")
    except Exception as e:
        logger.error(f"Error retrieving grievance transcription for recording ID: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }
    try:
        # Import here to avoid circular imports
        from actions_server.LLM_helpers import extract_contact_info
        contact_data = {field_name: contact_text}
        result = extract_contact_info(contact_data)
    except Exception as llm_error:
        logger.error(f"LLM error in extract_contact_info_task: {str(llm_error)}")
        return {
            'status': 'error',
            'stage': 'llm',
            'error': str(llm_error)
        }
    #store result in db if result is not empty to avoid overwriting existing data
    if result[field_name] == '':
        logger.error(f"No result found in extract_contact_info_task for field {field_name}")
        return {
            'status': 'error',
            'error': f"No result found in extract_contact_info_task for field {field_name}"
        }
    else:
        #check if the user already exists in the database
        if db_manager.get_user(grievance_id):
            db_manager.update_user(grievance_id, result)
        else:
            db_manager.create_user(grievance_id, result)
        return {
            'status': 'SUCCESS',
            'result': result
        }
        
@register_task(task_type='LLM', priority='high', bind=True)
def translate_grievance_to_english_task(self, grievance_id: str) -> Dict[str, Any]:
    """Translate a grievance to English and save it to the database"""
    try:
        # Import here to avoid circular imports
        from actions_server.LLM_helpers import translate_grievance_to_english   
        result = translate_grievance_to_english(grievance_id)
        return {
            'status': 'SUCCESS',
            'result': result
        }
    except Exception as e:
        logger.error(f"Error in translate_grievance_to_english_task: {str(e)}")

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

@register_task(task_type='Database', priority='high')
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

@register_task(task_type='Database', priority='high')
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

@register_task(task_type='Database', priority='high')
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