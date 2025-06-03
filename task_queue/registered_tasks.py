"""
Registered Tasks Module - Clean Task Functions with Automatic Service Configuration

This module contains all task functions registered with TaskManager using a centralized
service configuration approach.

Key Features:
============

1. **No Service Parameters Required**:
   - Task functions don't include 'service' in their signatures
   - Service is automatically set by @TaskManager.register_task() decorator
   - Access service via self.service within task functions

2. **Clean Business Logic Focus**:
   - Functions contain only essential business parameters
   - No configuration pollution in function signatures  
   - Pure focus on task-specific logic

3. **Automatic Service Assignment**:
   - @TaskManager.register_task(task_type='LLM') sets self.service from TASK_CONFIG
   - Service configuration centralized in task_manager.py TASK_CONFIG
   - No need to pass or manage service manually

4. **Task Type Categories**:
   - LLM: Language model processing tasks (service: 'llm_processor')
   - FileUpload: File processing tasks (service: 'queue_system')  
   - Messaging: Email/SMS tasks (service: 'messaging_service')
   - Database: Database operations (service: 'db_operations')

Example Pattern:
===============
```python
@TaskManager.register_task(task_type='LLM')
def my_task(self, input_data: Dict[str, Any], emit_websocket: bool = True):
    # self.service automatically set to 'llm_processor' from TASK_CONFIG
    logger.info(f"Processing with service: {self.service}")
    return result
```

Architecture Benefits:
===================
- Clean, focused function signatures
- Centralized service management
- Easy maintenance and updates
- Consistent task registration pattern
- No configuration duplication
"""

from typing import Dict, Any, List, Tuple, Callable, Optional
from actions_server.constants import CLASSIFICATION_DATA, ALLOWED_EXTENSIONS, USER_FIELDS, FIELD_CATEGORIES_MAPPING
from actions_server.db_manager import db_manager
from actions_server.messaging import CommunicationClient
from actions_server.file_server_core import FileServerCore
from task_queue.task_manager import TaskManager, DatabaseTaskManager
import json
from celery import group, chord

__all__ = [
    'process_file_upload_task',
    'process_batch_files_task',
    'send_sms_task',
    'send_email_task',
    'transcribe_audio_file_task',
    'classify_and_summarize_grievance_task',
    'extract_contact_info_task',
    'translate_grievance_to_english_task',
    'store_result_to_db_task',
]

# Initialize FileServerCore
file_server_core = FileServerCore()

#---------------------------------REGISTERED TASKS---------------------------------
# File Processing Tasks
@TaskManager.register_task(task_type='FileUpload')
def process_file_upload_task(self, 
                             grievance_id: str, 
                             file_data: Dict[str, Any], 
                             emit_websocket: bool = True) -> Dict[str, Any]:
    """
    Process a single file upload.
    
    Args:
        grievance_id: ID of the grievance
        file_data: File metadata and path
        
    Returns:
        Dict containing processing results
    """
    task_mgr = TaskManager(task=self, task_type='FileUpload', emit_websocket=emit_websocket, service=self.service)
    task_mgr.start_task(entity_key='grievance_id', entity_id=grievance_id, stage='single_file_upload')
    try:
        file_data = file_server_core.process_file_upload(grievance_id, file_data)
        result = {
            'status': 'success',
            'operation': 'file_upload',
            'field_name': 'file_data',
            'value': file_data,
        }
        task_mgr.complete_task(result, stage='single_file_upload')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='single_file_upload')
        raise

@TaskManager.register_task(task_type='FileUpload')
def process_batch_files_task(self, 
                             grievance_id: str, 
                             files_data: List[Dict[str, Any]], 
                             allowed_extensions: List[str] = ALLOWED_EXTENSIONS, 
                             emit_websocket: bool = True):
    """
    Process multiple files in batch using Celery chord for per-file parallelism and aggregation.
    """
    task_mgr = TaskManager(task=self, task_type='FileUpload', emit_websocket=emit_websocket, service=self.service)
    task_mgr.start_task(entity_key='grievance_id', entity_id=grievance_id, stage='batch_file_processing')
    try:
        upload_group = group(
            process_file_upload_task.s(grievance_id, file_data, emit_websocket=False, service=self.service)
            for file_data in files_data
        )
        # The callback will be called with the list of results
        callback = aggregate_batch_results.s(grievance_id)
        result = chord(upload_group)(callback)
        # Return the chord id for tracking
        summary = {
            'status': 'processing',
            'grievance_id': grievance_id,
            'chord_id': result.id,
            'file_task_ids': [r.id for r in result.parent.results],
            'message': 'Batch file upload tasks have been launched and will be aggregated.'
        }
        task_mgr.complete_task(summary, stage='batch_file_processing')
        return summary
    except Exception as e:
        task_mgr.fail_task(str(e), stage='batch_file_processing')
        raise

@TaskManager.register_task(task_type='FileUpload')
def aggregate_batch_results(self, results, grievance_id):
    """
    Aggregates results of all file upload tasks in a batch.
    """
    # results is a list of return values from process_file_upload_task
    success_count = sum(1 for r in results if r.get('status') == 'success')
    failed_count = sum(1 for r in results if r.get('status') != 'success')
    summary = {
        'status': 'completed' if failed_count == 0 else 'failed',
        'grievance_id': grievance_id,
        'results': results,
        'success_count': success_count,
        'failed_count': failed_count,
    }
    # Emit WebSocket message for batch completion
    task_mgr = TaskManager(task=self, task_type='FileUpload', emit_websocket=True, service=self.service)
    task_mgr._emit_status(grievance_id, summary['status'], summary)
    return summary

# Messaging Tasks
@TaskManager.register_task(task_type='Messaging')
def send_sms_task(self, phone_number: str, message: str, grievance_id: str = None):
    """Send an SMS message"""
    from actions_server.messaging import SMSClient
    task_mgr = TaskManager(task=self, task_type='Messaging', emit_websocket=False, service=self.service)
    if grievance_id:
        task_mgr.start_task(
            entity_key='grievance_id',
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
def send_email_task(self, to_emails, subject, body, grievance_id: str = None):
    """Send an email message"""
    from actions_server.messaging import EmailClient
    task_mgr = TaskManager(task=self, task_type='Messaging', emit_websocket=False, service=self.service)
    if grievance_id:
        task_mgr.start_task(
            entity_key='grievance_id',
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
def transcribe_audio_file_task(self, input_data: Dict[str, Any], 
                               emit_websocket: bool = True) -> Dict[str, Any]:
    """Transcribe an audio file."""
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    # Create task manager with the current task instance and proper websocket handling
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    try:
        grievance_id = input_data.get('grievance_id')
        if 'grievance' in input_data.get('field_name'):
            entity_key = 'grievance_id'
            entity_id = input_data.get('grievance_id')
        elif 'user' in input_data.get('field_name'):
            entity_key = 'user_id'
            entity_id = input_data.get('user_id')
            # For user fields, grievance_id should be in input_data
           
        else:
            raise ValueError(f"Invalid field name: {input_data.get('field_name')}")
        
        if not grievance_id:
            raise ValueError(f"grievance_id is required but not found in input data: {input_data}")
            
    except Exception as e:
        task_mgr.fail_task(str(e), stage='transcription')
        return {
            'status': 'error',
            'operation': 'transcription',
            'error': f"Missing key fields in input data: {str(e)}",
        }
   
    try:
        file_path = input_data.get('file_path')
        language_code = input_data.get('language_code')
        task_mgr.start_task(
            entity_key=entity_key,
            entity_id=entity_id,
            stage='transcription',
            extra_data={'file_path': file_path},
            grievance_id=grievance_id
        )
        from actions_server.LLM_helpers import transcribe_audio_file
        transcription = transcribe_audio_file(file_path, language_code)
        
        result = {
            'status': 'SUCCESS',
            'operation': 'transcription',
            'field_name': input_data.get('field_name'),
            'value': transcription,
            'file_path': file_path,
            'language_code': language_code,
            'task_id': task_id,
            'entity_key': entity_key,
            'id': entity_id,
            'grievance_id': grievance_id
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
    
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    print(f"Classify and summarize grievance task called with file_data: {file_data}")
    
    # Extract grievance_id from the file_data
    grievance_id = file_data.get('grievance_id')
    if not grievance_id:
        raise ValueError(f"Missing grievance_id in input data: {file_data}")
    
    # Extract data directly from file_data (transcription result)
    language_code = file_data.get('language_code', 'ne')
    grievance_details = file_data.get('value')  # The transcription text

        
    if not grievance_details:
        raise ValueError(f"No transcription text found in input data: {grievance_details}")
    
    task_mgr.start_task(entity_key='grievance_id', 
                        entity_id=grievance_id,
                        grievance_id=grievance_id)
    try:
        from actions_server.LLM_helpers import classify_and_summarize_grievance
        values = classify_and_summarize_grievance(grievance_details, language_code) #values is a dict with keys: grievance_summary, grievance_categories
        if not values:
            raise ValueError(f"No result found in classify_and_summarize_grievance: {values}")

        # Flatten the classification results into the main result for frontend
        values.update({'grievance_details': grievance_details})
        result = {'status': 'SUCCESS',  
                  'operation': 'classification',
                  'entity_key': file_data.get('entity_key'),
                  'id': file_data.get('id'),
                  'task_id': task_id,
                  'grievance_id': grievance_id,
                  'values': values}
        
        task_mgr.complete_task(values, stage='classification')
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='classification')
        return {
            'status': 'error',
            'operation': 'classification',
            'error': str(e),
            'task_id': task_id,
            'entity_key': file_data.get('entity_key'),
        }

@TaskManager.register_task(task_type='LLM')
def extract_contact_info_task(self, transcription_data: Dict[str, Any], emit_websocket: bool = True) -> Dict[str, Any]:
    """Extract contact information from transcription result."""
    # Get the Celery task ID from the current task
    
    task_id = self.request.id if hasattr(self, 'request') else None
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    
    try:    
        # Extract data directly from transcription result
        entity_key = transcription_data.get('entity_key')
        field_name = transcription_data.get('field_name')
        if not entity_key:
            raise ValueError(f"Missing entity_key in input data: {transcription_data}")
        elif entity_key not in ['user_id', 'grievance_id']:
            raise ValueError(f"Invalid entity_key in input data: {entity_key}")
        else:
            entity_id = transcription_data.get('id')
        
        # FIXED: Extract grievance_id from transcription_data
        # The transcription task should have passed this along
        grievance_id = transcription_data.get('grievance_id')
        if not grievance_id and entity_key == 'grievance_id':
            grievance_id = entity_id
        if not grievance_id:
            raise ValueError(f"Missing grievance_id in transcription_data: {transcription_data}")
        
        # TaskManager will use grievance_id for websocket emissions
        task_mgr.start_task(
            entity_key=entity_key, 
            entity_id=entity_id,
            grievance_id=grievance_id,
            stage='contact_info'
        )
    
        from actions_server.LLM_helpers import extract_contact_info
        input_data = {k:v for k,v in transcription_data.items() if k in ['field_name', 'value', 'language_code']}
        contact_info = extract_contact_info(input_data)
        
        incorrect_fields = [k for k in contact_info.keys() if k not in USER_FIELDS]
        if incorrect_fields:
            raise ValueError(f"Incorrect fields found in contact info: {incorrect_fields}")
        
        result= {'status': 'SUCCESS',
                 'operation': 'contact_info',
                 'entity_key': entity_key,
                 'id': entity_id,
                 'language_code': transcription_data.get('language_code'),
                 'task_id': task_id,
                 'grievance_id': grievance_id,
                 'values': contact_info}
            # result.update({'result': contact_info})  # Use contact_info direc
    
 
        task_mgr.complete_task(contact_info, stage='contact_info')
        return result
    
    except Exception as e:
        result.update({'status': 'error',
                       'error': str(e)})
        task_mgr.fail_task(str(e), stage='contact_info')
        return result

@TaskManager.register_task(task_type='LLM')
def translate_grievance_to_english_task(self, grievance_id: str, emit_websocket: bool = True) -> Dict[str, Any]:
    """Translate a grievance to English and save it to the database"""
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    task_mgr.start_task(entity_key='grievance_id', entity_id=grievance_id, grievance_id=grievance_id)
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
            'id': grievance_id,
            'grievance_id': grievance_id
        }
        task_mgr.complete_task(standardized_result, stage='translation')
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
def store_result_to_db_task(self, input_data: Dict[str, Any], emit_websocket: bool = False,) -> Dict[str, Any]:
    """Store the result of a task in database.
    Args:
        input_data: Dict[str, Any] - The results of another task
        emit_websocket: bool - Whether to emit a websocket message
        
        The mandatory fields in input_data are:
        {
            'entity_key': str,
            'id': str,
            'operation': str,
            'value': Dict[str, Any],
            'status': str,
        }
        
    
    Returns:
        Dict[str, Any] - Whether the result was stored successfully or not with 
        {
            'status': 'success' or 'error',
            'operation': 'store_result',
            'error': str(e) if status == 'error' else None
        }
    """
    task_mgr = DatabaseTaskManager(task=self, task_type='Database', emit_websocket=emit_websocket)
    task_mgr.start_task(entity_key=input_data.get('entity_key'), entity_id=input_data.get('id'), grievance_id=input_data.get('grievance_id'))
    try:
        result = task_mgr.handle_db_operation(input_data)
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

