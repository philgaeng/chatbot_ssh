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
def transcribe_audio_file_task(self, input_data: Dict[str, Any], emit_websocket: bool = True) -> Dict[str, Any]:
    """Transcribe an audio file."""
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    # Create task manager with the current task instance and proper websocket handling
    task_mgr = TaskManager(task=self, emit_websocket=True)
    try:
        if 'grievance' in input_data.get('field_name'):
            entity_type = 'grievance'
            entity_id = input_data.get('grievance_id')
            entity_key = 'grievance_id'
        elif 'user' in input_data.get('field_name'):
            entity_type = 'user'
            entity_id = input_data.get('user_id')
            entity_key = 'user_id'
        else:
            raise ValueError(f"Invalid field name: {input_data.get('field_name')}")
    except Exception as e:
        task_mgr.fail_task(str(e), stage='transcription')
        return {
            'status': 'error',
            'operation': 'transcription',
            'error': f"Missing key fields in input data: {str(e)}",
        }
   
    try:
        file_path = input_data['file_path']
        language_code = input_data['language_code']
        
        task_mgr.start_task(
            entity_type=entity_type,
            entity_id=entity_id,
            stage='transcription',
            extra_data={'file_path': file_path}
        )
        from actions_server.LLM_helpers import transcribe_audio_file
        transcription = transcribe_audio_file(file_path, language_code)
        
        result = {
            'status': 'SUCCESS',
            'operation': 'transcription',
            'field_name': 'grievance_details',
            'value': transcription,
            'file_path': file_path,
            'language_code': language_code,
            'task_id': task_id,
            'entity_key': entity_key,
            'id': entity_id
        }
        task_mgr.complete_task(result, stage='transcription')
        return result
    except Exception as e:
        error_result = {
            'status': 'error',
            'operation': 'transcription',
            'error': str(e),
            'task_id': task_id,
            'file_path': file_path,
            'entity_key': entity_key,
            'id': entity_id
        }

        task_mgr.fail_task(error_result, stage='transcription')
        return error_result

@TaskManager.register_task(task_type='LLM')
def classify_and_summarize_grievance_task(self, 
                                          file_data: Dict[str, Any], 
                                          emit_websocket: bool = True) -> Dict[str, Any]:
    """Classify and summarize a grievance text using the transcription result."""
    
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
    print(f"Classify and summarize grievance task called with file_data: {file_data}")
    # Extract data directly from file_data (transcription result)
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
                       'value': temp_result})
        task_mgr.complete_task(result, stage='classification')
        return result
    except Exception as e:
        result.update({'status': 'error',
                       'error': str(e)})
        task_mgr.fail_task(str(e), stage='classification')
        return result

@TaskManager.register_task(task_type='LLM')
def extract_contact_info_task(self, transcription_data: Dict[str, Any], emit_websocket: bool = False) -> Dict[str, Any]:
    """Extract contact information from transcription result."""
    # Get the Celery task ID from the current task
    
    task_id = self.request.id if hasattr(self, 'request') else None
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
    
    try:    
        # Extract data directly from transcription result
        field_name = transcription_data.get('field_name')
        contact_text = transcription_data.get('value')  # The transcription text
        language_code = transcription_data.get('language_code', 'ne')
        entity_type = 'grievance' if 'grievance' in field_name else 'user' if 'user' in field_name else None
        entity_id = transcription_data.get('id')
        entity_key = 'grievance_id' if 'grievance' in field_name else 'user_id' if 'user' in field_name else None
        result = {'operation': 'contact_extraction',
              'field_name': field_name,
              'entity_key': entity_key,
              'id': entity_id,
              'transcription_task_id': transcription_data.get('task_id'),
              'task_id': task_id,
              'language_code': language_code}
        
    except Exception as e:
        task_mgr.fail_task(str(e), stage='contact_info')
        return {
            'status': 'error',
            'operation': 'contact_extraction',
            'error': f"Missing key fields in input data: {str(e)}",
        }
    
    try:
    
        task_mgr.start_task(entity_type=entity_type, 
                        entity_id=entity_id,
                        stage='contact_info')
    
        from actions_server.LLM_helpers import extract_contact_info
        input_data = {
            'field_name': field_name,
            'value': contact_text,
            'language_code': language_code
        }
        contact_info = extract_contact_info(input_data)
    
    except Exception as llm_error:
        result.update({'status': 'error',
                       'error': str(llm_error)})
        return result   
    
    try:
        # Return results in standardized format
        result.update({'status': 'SUCCESS',
                       'value': contact_info})
        task_mgr.complete_task(result, stage='contact_info')
        return result
    except Exception as e:
        result.update({'status': 'error',
                       'error': str(e)})
        task_mgr.fail_task(str(e), stage='contact_info')
        return result

@TaskManager.register_task(task_type='LLM')
def translate_grievance_to_english_task(self, grievance_id: str, emit_websocket: bool = True) -> Dict[str, Any]:
    """Translate a grievance to English and save it to the database"""
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
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
def store_result_to_db_task(input_data: Dict[str, Any], emit_websocket: bool = False) -> Dict[str, Any]:
    """Store task result in database."""
    task_mgr = DatabaseTaskManager(emit_websocket=emit_websocket)
    task_mgr.start_task(entity_type=input_data.get('entity_key'), entity_id=input_data.get('id'))
    try:
        result = task_mgr.handle_task_db_operations(input_data)
        task_mgr.complete_task(result, stage='store_result')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='store_result')
        error_result = {
            'status': 'error',
            'operation': 'store_result',
            'error': str(e)
        }
        return error_result

def store_task_result_to_db_task(input_data: Dict[str, Any],
                                operation: str, 
                                service: str = None) -> Dict[str, Any]:
    """Dynamically store any result of a task in the dedicated table in the database"""
    task_mgr = DatabaseTaskManager(emit_websocket=False, service=service)
    return task_mgr.handle_task_db_operations(input_data)
