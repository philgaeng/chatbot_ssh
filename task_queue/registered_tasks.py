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
from actions_server.constants import CLASSIFICATION_DATA, ALLOWED_EXTENSIONS, USER_FIELDS, FIELD_CATEGORIES_MAPPING, TASK_STATUS
from actions_server.db_manager import db_manager
from actions_server.messaging import CommunicationClient
from actions_server.file_server_core import FileServerCore
from task_queue.task_manager import TaskManager, DatabaseTaskManager
from task_queue.celery_app import celery_app
import json
from celery import group, chord
from actions_server.websocket_utils import emit_file_status_to_rasa, emit_file_status_update

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

# Define task status constants
SUCCESS = TASK_STATUS['SUCCESS']
IN_PROGRESS = TASK_STATUS['IN_PROGRESS']
FAILED = TASK_STATUS['FAILED']
ERROR = TASK_STATUS['ERROR']
RETRYING = TASK_STATUS['RETRYING']

#---------------------------------REGISTERED TASKS---------------------------------
# File Processing Tasks
@celery_app.task(name='process_file_upload_task')
def process_file_upload_task(grievance_id: str, 
                           file_data: Dict[str, Any], 
                           emit_websocket: bool = True,
                           session_type: str = 'bot',
                           session_id: str = None) -> Dict[str, Any]:
    """
    Process a single file upload.
    
    Args:
        grievance_id: ID of the grievance
        file_data: File metadata and path
        emit_websocket: Whether to emit a websocket message (default: True)
        session_type: Type of session (default: 'bot')
        session_id: ID of the session
        
    Returns:
        Dict containing processing results with keys:
        - status: SUCCESS or ERROR
        - operation: 'file_upload'
        - field_name: 'file_data'
        - value: Processed file data
    """
    task_mgr = TaskManager(task=process_file_upload_task, task_type='FileUpload', emit_websocket=emit_websocket, service='file_processor')
    task_mgr.start_task(entity_key='grievance_id', entity_id=grievance_id, grievance_id=grievance_id, stage='single_file_upload')
    try:
        file_data = file_server_core.process_file_upload(grievance_id=grievance_id, 
                                                         file_data=file_data,
                                                         )
        result = {
            'status': SUCCESS,
            'operation': 'file_upload',
            'field_name': 'file_data',
            'value': file_data,
        }
        task_mgr.complete_task(result, stage='single_file_upload')
        try:
            emit_file_status_update(
                session_id=session_id,
                status=SUCCESS,
                file_id=file_data['file_id'],
                operation='file_upload',
                session_type=session_type,
                file_name=file_data['file_name']
            )
        except Exception as e:
            task_mgr.fail_task(error=str(e), 
            stage='single_file_upload_websocket_emit')
            raise
        
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='single_file_upload')
        raise

@TaskManager.register_task(task_type='FileUpload')
def process_batch_files_task(self, 
                             grievance_id: str, 
                             files_data: List[Dict[str, Any]], 
                             allowed_extensions: List[str] = ALLOWED_EXTENSIONS, 
                             emit_websocket: bool = True,
                             session_type: str = None,
                             session_id: str = None):
    """
    Process multiple files in batch using Celery chord for per-file parallelism and aggregation.
    
    Args:
        grievance_id: ID of the grievance
        files_data: List of file metadata and paths
        allowed_extensions: List of allowed file extensions (default: ALLOWED_EXTENSIONS)
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing batch processing summary with keys:
        - status: 'processing'
        - grievance_id: ID of the grievance
        - chord_id: ID of the Celery chord
        - file_task_ids: List of task IDs for each file
        - message: Status message
    """
    task_mgr = TaskManager(task=self, task_type='FileUpload', emit_websocket=emit_websocket, service=self.service)
    task_mgr.start_task(entity_key='grievance_id', entity_id=grievance_id, stage='batch_file_processing')
    try:
        upload_group = group(
            process_file_upload_task.s(grievance_id, file_data, 
                                       emit_websocket=False, 
                                       service=self.service,
                                       session_type=session_type,
                                       session_id=session_id)
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
    
    Args:
        results: List of results from process_file_upload_task
        grievance_id: ID of the grievance
        
    Returns:
        Dict containing aggregation summary with keys:
        - status: SUCCESS or FAILED
        - grievance_id: ID of the grievance
        - results: List of individual task results
        - success_count: Number of successful tasks
        - failed_count: Number of failed tasks
    """
    # results is a list of return values from process_file_upload_task
    success_count = sum(1 for r in results if r.get('status') == SUCCESS)
    failed_count = sum(1 for r in results if r.get('status') != SUCCESS)
    summary = {
        'status': SUCCESS if failed_count == 0 else FAILED,
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
    """
    Send an SMS message.
    
    Args:
        phone_number: Recipient's phone number
        message: SMS message content
        grievance_id: ID of the grievance (optional)
        
    Returns:
        Result of the SMS sending operation.
    """
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
    """
    Send an email message.
    
    Args:
        to_emails: Recipient email addresses
        subject: Email subject
        body: Email body content
        grievance_id: ID of the grievance (optional)
        
    Returns:
        Result of the email sending operation.
    """
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
    """
    Transcribe an audio file.
    
    Args:
        input_data: Dictionary containing:
            - user_id: ID of the user
            - grievance_id: ID of the grievance
            - user_province: Province of the user
            - user_district: District of the user
            - field_name: Name of the field being transcribed
            - file_path: Path to the audio file
            - language_code: Language code of the audio
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing transcription results with keys:
        - status: SUCCESS or 'error'
        - operation: 'transcription'
        - user_province: Province of the user
        - user_district: District of the user
        - field_name: Name of the field
        - values: Transcription text {field_name: transcription_text}
        - file_path: Path to the audio file
        - language_code: Language code of the audio
        - task_id: ID of the task
        - entity_key: 'transcription_id'
        - id: Dummy transcription_id (same as task_id)
        - grievance_id: ID of the grievance
        - recording_id: ID of the recording
        - user_id: ID of the user
    """
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    # Create task manager with the current task instance and proper websocket handling
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    try:
        user_id = input_data.get('user_id')
        grievance_id = input_data.get('grievance_id')
        field_name = input_data.get('field_name')
        
        if not grievance_id:
            raise ValueError(f"grievance_id is required but not found in input data: {input_data}")
        
        if not field_name:
            raise ValueError(f"field_name is required but not found in input data: {input_data}")
            
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
        
        # Get recording_id from input_data or lookup from database
        recording_id = input_data.get('recording_id')
        if not recording_id:
            from actions_server.db_manager import db_manager
            recording_id = db_manager.recording.get_recording_id_for_grievance_id_and_field_name(grievance_id, field_name)
            if not recording_id:
                raise ValueError(f"Could not find recording_id for grievance_id: {grievance_id}, field_name: {field_name}")
        
        # Use task_id as dummy transcription_id for flow continuity
        dummy_transcription_id = task_id
        
        task_mgr.start_task(
            entity_key='transcription_id',
            entity_id=dummy_transcription_id,  # Use task_id as dummy transcription_id
            stage='transcription',
            extra_data={'file_path': file_path},
            grievance_id=grievance_id
        )
        
        from actions_server.LLM_helpers import transcribe_audio_file
        transcription = transcribe_audio_file(file_path, language_code)
        values = {field_name: transcription}
        result = {
            'status': SUCCESS,
            'operation': 'transcription',
            'field_name': input_data.get('field_name'),
            'values': values,
            'file_path': file_path,
            'language_code': language_code,
            'task_id': task_id,
            'entity_key': 'transcription_id',
            'id': dummy_transcription_id,  # Dummy transcription_id (same as task_id)
            'grievance_id': grievance_id,
            'recording_id': recording_id,
            'user_id': user_id,
            'user_province': input_data.get('user_province'),
            'user_district': input_data.get('user_district')
        }
        task_mgr.complete_task(values, stage='transcription')
        
        # Store result to database asynchronously (fire & forget)
        store_result_to_db_task.delay(result)
        
        return result
    except Exception as e:
        error_result = {
            'status': ERROR,
            'operation': 'transcription',
            'error': str(e),
            'task_id': task_id,
            'file_path': file_path,
            'entity_key': 'transcription_id',
            'id': task_id,  # Use task_id even for errors
            'grievance_id': grievance_id,
            'user_id': user_id
        }

        task_mgr.fail_task(error_result, stage='transcription')
        return error_result

@TaskManager.register_task(task_type='LLM')
def classify_and_summarize_grievance_task(self, 
                                          input_data: Dict[str, Any], 
                                          emit_websocket: bool = True) -> Dict[str, Any]:
    """
    Classify and summarize a grievance text using the transcription result.
    
    Args:
        input_data: Dictionary containing:
            - grievance_id: ID of the grievance
            - language_code: Language code of the transcription
            - field_name: Name of the field being transcribed
            - values: Transcription text {field_name: transcription_text}
            - user_province: Province of the user
            - user_district: District of the user
            - user_id: ID of the user
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing classification results with keys:
        - status: SUCCESS or ERROR
        - operation: 'classification'
        - entity_key: Entity key from file_data
        - id: ID from file_data
        - task_id: ID of the task
        - grievance_id: ID of the grievance
        - values: {grievance_summary: summary_text, grievance_categories: [category1, category2, ...]}
        - language_code: Language code of the transcription
        - user_id: ID of the user
        - user_province: Province of the user
        - user_district: District of the user
    """
    
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    print(f"Classify and summarize grievance task called with file_data: {input_data}")
    
    # Extract grievance_id from the file_data
    grievance_id = input_data.get('grievance_id')
    if not grievance_id:
        raise ValueError(f"Missing grievance_id in input data: {input_data}")
    
    # Extract data directly from file_data (transcription result)
    language_code = input_data.get('language_code', 'ne')
    grievance_details = input_data.get('values', {}).get('grievance_details')  # The transcription text
    user_district = input_data.get('user_district')
    user_province = input_data.get('user_province')
        
    if not grievance_details:
        raise ValueError(f"No transcription text found in input data: {file_data.get('values')}")
    
    task_mgr.start_task(entity_key='grievance_id', 
                        entity_id=grievance_id,
                        grievance_id=grievance_id)
    try:
        from actions_server.LLM_helpers import classify_and_summarize_grievance
        values = classify_and_summarize_grievance(grievance_details, language_code, user_district, user_province) #values is a dict with keys: grievance_summary, grievance_categories
        if not values:
            raise ValueError(f"No result found in classify_and_summarize_grievance: {values}")

        # Flatten the classification results into the main result for frontend
        values.update({'grievance_details': grievance_details})
        result = {'status': SUCCESS,  
                  'operation': 'classification',
                  'entity_key': input_data.get('entity_key'),
                  'id': input_data.get('id'),
                  'task_id': task_id,
                  'grievance_id': grievance_id,
                  'values': values,
                  'language_code': language_code,
                  'user_id': input_data.get('user_id'),
                  'user_province': user_province,
                  'user_district': user_district
                  }
        
        task_mgr.complete_task(values, stage='classification')
        
        # Store result to database asynchronously (fire & forget)
        store_result_to_db_task.delay(result)
        
        return result
    except Exception as e:
        task_mgr.fail_task(str(e), stage='classification')
        return {
            'status': ERROR,
            'operation': 'classification',
            'error': str(e),
            'task_id': task_id,
            'entity_key': input_data.get('entity_key'),
        }

@TaskManager.register_task(task_type='LLM')
def extract_contact_info_task(self, input_data: Dict[str, Any], emit_websocket: bool = True) -> Dict[str, Any]:
    """
    Extract contact information from transcription result.
    
    Args:
        transcription_data: Dictionary containing:
            - entity_key: Entity key
            - field_name: Name of the field
            - values: Transcription text {field_name: transcription_text}
            - grievance_id: ID of the grievance
            - user_id: ID of the user
            - language_code: Language code of the transcription
            - user_province: Province of the user
            - user_district: District of the user
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing contact information extraction results with keys:
        - status: SUCCESS or ERROR
        - operation: 'contact_info'
        - entity_key: 'user_id'
        - id: ID of the user
        - language_code: Language code of the transcription
        - task_id: ID of the task
        - grievance_id: ID of the grievance
        - user_id: ID of the user
        - values: {field_name: contact_info_value}
        - user_province: Province of the user
        - user_district: District of the user
    """
    # Get the Celery task ID from the current task
    
    task_id = self.request.id if hasattr(self, 'request') else None
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    
    try:    
        # Extract data directly from transcription result
        entity_key = input_data.get('entity_key')
        field_name = input_data.get('field_name')
        language_code = input_data.get('language_code')

        
        # FIXED: Extract grievance_id from transcription_data
        # The transcription task should have passed this along
        grievance_id = input_data.get('grievance_id')
        user_id = input_data.get('user_id')
        if not grievance_id:
            raise ValueError(f"Missing grievance_id in input_data: {input_data}")
        if not user_id:
            raise ValueError(f"Missing user_id in input_data: {input_data}")
        user_district = input_data.get('user_district')
        user_province = input_data.get('user_province')
        # TaskManager will use grievance_id for websocket emissions
        task_mgr.start_task(
            entity_key='user_id', 
            entity_id=user_id,
            grievance_id=grievance_id,
            stage='contact_info'
        )
    
        from actions_server.LLM_helpers import extract_contact_info
        contact_data = input_data['values']
        values = extract_contact_info(contact_data, language_code, user_district, user_province)
        
        incorrect_fields = [k for k in values.keys() if k not in USER_FIELDS]
        if incorrect_fields:
            raise ValueError(f"Incorrect fields found in contact info: {incorrect_fields}")
        
        result= {'status': SUCCESS,
                 'operation': 'contact_info',
                 'entity_key': "user_id",
                 'id': user_id,
                 'language_code': language_code,
                 'task_id': task_id,
                 'grievance_id': grievance_id,
                 'user_id': user_id,
                 'values': values,
                 'user_province': user_province,
                 'user_district': user_district
                 }
            # result.update({'result': contact_info})  # Use contact_info direc
    
 
        task_mgr.complete_task(values, stage='contact_info')
        
        # Store result to database asynchronously (fire & forget)
        store_result_to_db_task.delay(result)
        
        return result
    
    except Exception as e:
        task_mgr.fail_task(str(e), stage='contact_info')
        return {
            'status': ERROR,
            'operation': 'contact_info',
            'error': str(e),
            'entity_key': 'user_id',
            'task_id':task_id
        }

@TaskManager.register_task(task_type='LLM')
def translate_grievance_to_english_task(self, input_data: Dict[str, Any], emit_websocket: bool = True) -> Dict[str, Any]:
    """
    Translate a grievance to English and save it to the database.
    
    Args:
        file_data: Dictionary containing:
            - grievance_id: ID of the grievance
            - language_code: Language code of the grievance
            - values: Grievance data including 'grievance_details'
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing translation results with keys:
        - status: SUCCESS or ERROR
        - operation: 'translation'
        - value: Translated grievance data
        - language_code: 'en'
        - entity_key: 'translation_id'
        - id: Dummy translation_id (same as task_id)
        - task_id: ID of the task
        - grievance_id: ID of the grievance
        - user_id: ID of the user
    """
    task_id = self.request.id if hasattr(self, 'request') else None
    task_mgr = TaskManager(task=self, task_type='LLM', emit_websocket=emit_websocket, service=self.service)
    
    try:
        task_mgr.monitoring.log_task_event(task_name='translate_grievance_to_english',
                                           event_type='raw_input_data_for_translation',
                                           service='llm_processor',
                                           details=input_data)
        # Extract data from potentially nested group result
        grievance_id = input_data.get('grievance_id')
        language_code = input_data.get('language_code')
        grievance_data = input_data.get('values')
        if not grievance_id:
            raise ValueError(f"Missing grievance_id in input data: {input_data}")
        if not language_code:
            raise ValueError(f"Missing language_code in input data: {input_data}")
        if not grievance_data:
            raise ValueError(f"Missing grievance_data in input data: {input_data}")
        if not grievance_data.get('grievance_details'):
            raise ValueError(f"Missing grievance_details in input data: {input_data}")
        
        grievance_data.update({'language_code': language_code, 'grievance_id': grievance_id})
        
        task_mgr.monitoring.log_task_event(task_name='translate_grievance_to_english', 
                                           event_type='extracted_input_data_for_translation', 
                                           service='llm_processor', details=grievance_data)
    
        
        task_mgr.start_task(
            entity_key='translation_id', 
            entity_id=task_id,  # Use task_id (UUID) instead of grievance_id (string)
            grievance_id=grievance_id
        )
        
        from actions_server.LLM_helpers import translate_grievance_to_english_LLM
        result = translate_grievance_to_english_LLM(grievance_data)
        
        if not result:
            raise ValueError(f"Translation failed - no result returned from LLM - input_data: {input_data}, grievance_data: {grievance_data}")
        
        values = {k:v for k,v in result.items() if k not in ['grievance_id']}
        values.update({'source_language': language_code, 'transcription_method': 'LLM'})
        #avoid duplicate grievance_id
        
        # Return results in standardized format
        result = {
            'status': SUCCESS,
            'operation': 'translation',
            'values': values,
            'language_code': 'en',
            'entity_key': 'translation_id',
            'id': task_id,  # Use dummy translation_id (same as task_id)
            'task_id': task_id,
            'grievance_id': grievance_id,
            'user_id': input_data.get('user_id'),
            'user_province': input_data.get('user_province'),
            'user_district': input_data.get('user_district')
        }
        task_mgr.complete_task(values, stage='translation')
        
        # Store result to database asynchronously (fire & forget)
        store_result_to_db_task.delay(result)
        
        return result
        
    except Exception as e:
        # Try to get grievance_id for error response, fallback to 'unknown'
        grievance_id = 'unknown'
        try:
            if isinstance(input_data, dict):
                grievance_id = input_data.get('grievance_id', 'unknown')
            elif isinstance(input_data, list) and len(input_data) > 0:
                # Try to find grievance_id in group result
                for item in input_data:
                    if isinstance(item, dict) and 'grievance_id' in item:
                        grievance_id = item['grievance_id']
                        break
        except:
            pass
            
        task_mgr.fail_task(str(e), stage='translation')
        return {
            'status': ERROR,
            'operation': 'translation',
            'error': str(e),
            'entity_key': 'translation_id',
            'id': task_id,  # Use task_id even for errors
            'task_id': task_id,
            'grievance_id': grievance_id,
            'source_language': language_code,
            'transcription_method': 'LLM'
        }

@TaskManager.register_task(task_type='Database')
def store_result_to_db_task(self, input_data: Dict[str, Any], emit_websocket: bool = False,) -> Dict[str, Any]:
    """
    Store the result of a task in database using asynchronous task tracking.
    
    Args:
        input_data: Dictionary containing:
            - entity_key: Key of the entity (e.g., 'grievance_id')
            - id: ID of the entity
            - operation: Operation type (e.g., 'store_result')
            - value: Result data to store
            - status: SUCCESS or ERROR
        emit_websocket: Whether to emit a websocket message (default: False)
        
    Returns:
        Dict indicating the result of the storage operation with keys:
        - status: SUCCESS or ERROR
        - operation: 'store_result'
        - error: Error message if status is 'error'
    """
    task_mgr = DatabaseTaskManager(task=self, task_type='Database', emit_websocket=emit_websocket)
    try:
        
        # Handle database operation with retroactive task creation
        result = task_mgr.handle_db_operation(input_data)
        return result
    except Exception as e:
        error_result = {
            'status': ERROR,
            'operation': 'store_result',
            'error': str(e)
        }
        return error_result

