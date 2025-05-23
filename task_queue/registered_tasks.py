"""
List of all registered tasks in the system.

This module serves as a central registry of all tasks that can be processed by Celery.
Each task should be documented with its purpose, priority level, and any dependencies.
"""

from typing import Dict, Any, List, Tuple, Callable, Optional
from actions_server.constants import CLASSIFICATION_DATA, ALLOWED_EXTENSIONS
from actions_server.db_manager import db_manager
from actions_server.messaging import CommunicationClient
from actions_server.file_server import FileServerCore
from task_queue.task_manager import TaskManager, DatabaseTaskManager
import celery
import json

# Initialize FileServerCore
file_server_core = FileServerCore()

#---------------------------------REGISTERED TASKS---------------------------------
# File Processing Tasks
@TaskManager.register_task(task_type='FileUpload')
def process_file_upload_task(grievance_id: str, file_data: Dict[str, Any], service: str = None) -> Dict[str, Any]:
    """
    Process a single file upload.
    
    Args:
        grievance_id: ID of the grievance
        file_data: File metadata and path
        
    Returns:
        Dict containing processing results
    """
    task_mgr = TaskManager(emit_websocket=False, service=service)
    task_mgr.start_task(entity_type='grievance', entity_id=grievance_id, stage='single_file_upload')
    try:
        result = file_server_core.process_file_upload(grievance_id, file_data)
        task_mgr.complete_task(result, stage='single_file_upload')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='single_file_upload')
        raise

@TaskManager.register_task(task_type='FileUpload')
def process_batch_files_task(grievance_id: str, files_data: List[Dict[str, Any]], allowed_extensions: List[str] = ALLOWED_EXTENSIONS, service: str = None) -> Dict[str, Any]:
    """
    Process multiple files in batch.
    
    Args:
        grievance_id: ID of the grievance
        files_data: List of file metadata and paths
    """
    task_mgr = TaskManager(emit_websocket=False, service=service)
    task_mgr.start_task(entity_type='grievance', entity_id=grievance_id, stage='batch_file_processing')
    try:
        result = file_server_core.process_batch_files(grievance_id, files_data)
        task_mgr.complete_task(result, stage='batch_file_processing')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='batch_file_processing')
        raise

# Messaging Tasks
@TaskManager.register_task(task_type='Messaging')
def send_sms_task(phone_number: str, message: str, grievance_id: str = None, service: str = None):
    """Send an SMS message"""
    from actions_server.messaging import SMSClient
    task_mgr = TaskManager(emit_websocket=False, service=service)
    if grievance_id:
        task_mgr.start_task(
            entity_type='grievance',
            entity_id=grievance_id,
            stage='send_sms',
            extra_data={'phone_number': phone_number}
        )
    try:
        result = SMSClient().send_sms(phone_number, message)
        if grievance_id:
            task_mgr.complete_task(result, stage='send_sms')
        return result
    except Exception as e:
        if grievance_id:
            task_mgr.fail_task(str(e), stage='send_sms')
        raise

@TaskManager.register_task(task_type='Messaging')
def send_email_task(to_emails, subject, body, grievance_id: str = None):
    """Send an email message"""
    from actions_server.messaging import EmailClient
    task_mgr = TaskManager(emit_websocket=False)
    if grievance_id:
        task_mgr.start_task(
            entity_type='grievance',
            entity_id=grievance_id,
            stage='send_email',
            extra_data={'to_emails': to_emails}
        )
    try:
        result = EmailClient().send_email(to_emails, subject, body)
        if grievance_id:
            task_mgr.complete_task(result, stage='send_email')
        return result
    except Exception as e:
        if grievance_id:
            task_mgr.fail_task(str(e), stage='send_email')
        raise

# LLM Tasks
@TaskManager.register_task(task_type='LLM')
def transcribe_audio_file_task(self, file_path: str, language: str = None, grievance_id: str = None, service: str = None) -> Dict[str, Any]:
    """Transcribe an audio file."""
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    # Create task manager with the current task instance and proper websocket handling
    task_mgr = TaskManager(task=self, emit_websocket=True, service=service)
    if grievance_id:
        task_mgr.start_task(
            entity_type='grievance',
            entity_id=grievance_id,
            stage='transcription',
            extra_data={'file_path': file_path}
        )
    try:
        from actions_server.LLM_helpers import transcribe_audio_file
        transcription = transcribe_audio_file(file_path, language)
        
        result = {
            'status': 'SUCCESS',
            'operation': 'transcription',
            'field_name': 'grievance_details',
            'value': transcription,
            'file_path': file_path,
            'language_code': language,
            'task_id': task_id,
            'entity_key': 'grievance_id',
            'id': grievance_id
        }
        if grievance_id:
            # Convert result to JSON string for database storage
            task_mgr.complete_task(json.dumps(result), stage='transcription')
        return result
    except Exception as e:
        error_result = {
            'status': 'error',
            'operation': 'transcription',
            'error': str(e),
            'task_id': task_id,
            'file_path': file_path
        }
        if grievance_id:
            error_result.update({
                'entity_key': 'grievance_id',
                'id': grievance_id
            })
            task_mgr.fail_task(str(e), stage='transcription')
        return error_result

@TaskManager.register_task(task_type='LLM')
def classify_and_summarize_grievance_task(self, 
                                          file_data: Dict[str, Any], 
                                          service: str = 'llm_queue', 
                                          emit_websocket: bool = True) -> Dict[str, Any]:
    """Classify and summarize a grievance text using the transcription result."""
    
     # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    task_mgr = TaskManager(task=self, service=service, emit_websocket=emit_websocket)
    print(f"Classify and summarize grievance task called with file_data: {file_data}")
    # Extract data directly from file_data (transcription result))  # In this case, id is the grievance_id
    language_code = file_data.get('language_code', 'ne')
    grievance_details = file_data.get('value')  # The transcription text
    result = {'operation': 'classification',
              'field_name': 'grievance_details',
              'entity_key': file_data.get('entity_key'),
              'id': file_data.get('id'),
              'transcription_task_id': file_data.get('task_id'),
              'task_id': task_id}
        
    if not grievance_details:
        result.update({'status': 'error',
                       'error': 'No transcription text found in input data'})
        return result
    
    task_mgr.start_task(entity_type='grievance', 
                        entity_id=file_data.get('id'),
                        stage='classification')
    try:
        from actions_server.LLM_helpers import classify_and_summarize_grievance
        temp_result = classify_and_summarize_grievance(grievance_details, language_code)
    except Exception as llm_error:
        result.update({'status': 'error',
                       'error': str(llm_error)})
        return result
    
    try:
        # Return results in standardized format
        result.update({'status': 'SUCCESS',
                       'field_name': 'grievance_categories, grievance_summary',
                       'value': json.dumps(temp_result)})
        
        task_mgr.complete_task(json.dumps(result), stage='classification')
        return result
    except Exception as db_error:
        result.update({'status': 'error',
                       'error': str(db_error)})
        return result

@TaskManager.register_task(task_type='LLM')
def extract_contact_info_task(self, transcription_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract user information from text"""
    task_mgr = TaskManager(task=self, emit_websocket=True, service='llm_queue')
    
    # Extract data directly from transcription result
    contact_text = transcription_data.get('value')  # The transcription text
    grievance_id = transcription_data.get('id')
    language_code = transcription_data.get('language_code', 'ne')
    field_name = transcription_data.get('field_name', 'user_contact')
    
    if not contact_text:
        return {
            'status': 'error',
            'operation': 'contact_extraction',
            'error': 'No transcription text found in input data',
            'entity_key': 'grievance_id',
            'id': grievance_id
        }
    
    task_mgr.start_task(entity_type='grievance', entity_id=grievance_id, stage='contact_extraction')
    try:
        from actions_server.LLM_helpers import extract_contact_info
        contact_data = {field_name: contact_text}
        result = extract_contact_info(contact_data)
    except Exception as llm_error:
        return {
            'status': 'error',
            'operation': 'contact_extraction',
            'error': str(llm_error),
            'entity_key': 'grievance_id',
            'id': grievance_id
        }
    
    if result[field_name] == '':
        return {
            'status': 'error',
            'operation': 'contact_extraction',
            'error': f"No result found for field {field_name}",
            'entity_key': 'grievance_id',
            'id': grievance_id
        }
    else:
        try:
            # Return results in standardized format
            result = {
                'status': 'SUCCESS',
                'operation': 'contact_extraction',
                'field_name': field_name,
                'value': result[field_name],
                'language_code': language_code,
                'entity_key': 'grievance_id',
                'id': grievance_id
            }
            task_mgr.complete_task(json.dumps(result), stage='contact_extraction')
            return result
        except Exception as db_error:
            return {
                'status': 'error',
                'operation': 'contact_extraction',
                'error': str(db_error),
                'entity_key': 'grievance_id',
                'id': grievance_id
            }

@TaskManager.register_task(task_type='LLM')
def translate_grievance_to_english_task(self, grievance_id: str, service: str = 'llm_queue') -> Dict[str, Any]:
    """Translate a grievance to English and save it to the database"""
    task_mgr = TaskManager(task=self, emit_websocket=True, service='llm_queue')
    task_mgr.start_task(entity_type='grievance', entity_id=grievance_id)
    try:
        from actions_server.LLM_helpers import translate_grievance_to_english
        result = translate_grievance_to_english(grievance_id)
        
        # Return results in standardized format
        standardized_result = {
            'status': 'SUCCESS',
            'operation': 'translation',
            'field_name': 'grievance_details_en',
            'value': result.get('details', ''),
            'language_code': 'en',
            'entity_key': 'grievance_id',
            'id': grievance_id
        }
        task_mgr.complete_task(json.dumps(standardized_result))
        return standardized_result
    except Exception as e:
        return {
            'status': 'error',
            'operation': 'translation',
            'error': str(e),
            'entity_key': 'grievance_id',
            'id': grievance_id
        }

@TaskManager.register_task(task_type='Database')
def store_result_to_db_task(input_data: Dict[str, Any],
                            operation: str, 
                            service: str = None) -> Dict[str, Any]:
    """Dynamically store any result of a task in the dedicated table in the database"""
    task_mgr = DatabaseTaskManager(emit_websocket=False, service=service)
    return task_mgr.handle_db_operation(operation, input_data)

def store_task_result_to_db_task(input_data: Dict[str, Any],
                                operation: str, 
                                service: str = None) -> Dict[str, Any]:
    """Dynamically store any result of a task in the dedicated table in the database"""
    task_mgr = DatabaseTaskManager(emit_websocket=False, service=service)
    return task_mgr.handle_task_db_operations(input_data)
