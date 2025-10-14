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
import json
from celery import group, chord
from typing import Dict, Any, List, Tuple, Callable, Optional
from backend.config.constants import CLASSIFICATION_DATA, ALLOWED_EXTENSIONS, USER_FIELDS, FIELD_CATEGORIES_MAPPING
from backend.services.database_services.postgres_services import db_manager
from backend.services.messaging import messaging
from backend.services.file_server_core import FileServerCore
from backend.logger.logger import TaskLogger
from .task_manager import TaskManager, DatabaseTaskManager
from .celery_app import celery_app


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

# Define task status constants from database
from backend.config.database_constants import get_task_status_codes

# Get status codes from database constants (ensuring cohesiveness)
status_codes = get_task_status_codes()
STARTED = status_codes['STARTED']
SUCCESS = status_codes['SUCCESS']
FAILED = status_codes['FAILED']
RETRYING = status_codes['RETRYING']



#---------------------------------REGISTERED TASKS---------------------------------
# File Processing Tasks
@TaskManager.register_task(task_type='FileUpload')
def process_file_upload_task(self, grievance_id: str, 
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
        - status: SUCCESS or FAILED
        - operation: 'file_upload'
        - field_name: 'file_data'
        - value: Processed file data
    """
    session_id = grievance_id if session_id is None else session_id
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
    
    # Mark task as started (now executing in Celery worker)
    task_mgr.start_task(
        entity_key='grievance_id', 
        entity_id=grievance_id, 
        grievance_id=grievance_id, 
        session_id=session_id
    )
    
    try:
        result = file_server_core.process_file_upload(grievance_id=grievance_id, 
                                                         file_data=file_data,
                                                         )
        task_mgr.complete_task(
            result=result, 
            grievance_id=grievance_id, 
            session_id=session_id
        )
        
        return result
    except Exception as e:
        task_mgr.fail_task(
            error=str(e), 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='grievance_id', 
            entity_id=grievance_id
        )
        raise

@TaskManager.register_task(task_type='FileUpload')
def process_batch_files_task(self, 
                             grievance_id: str, 
                             files_data: List[Dict[str, Any]], 
                             allowed_extensions: List[str] = ALLOWED_EXTENSIONS, 
                             emit_websocket: bool = True,
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
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
    task_mgr.start_task(
        entity_key='grievance_id', 
        entity_id=grievance_id, 
        grievance_id=grievance_id, 
        session_id=session_id
    )
    try:
        upload_group = group(
            process_file_upload_task.s(grievance_id, file_data, 
                                       emit_websocket=False)
            for file_data in files_data
        )
        # The callback will be called with the list of results
        callback = aggregate_batch_results.s(grievance_id)
        result = chord(upload_group)(callback)
        # Return the chord id for tracking
        summary = {
            'status': STARTED,
            'grievance_id': grievance_id,
            'chord_id': result.id,
            'file_task_ids': [r.id for r in result.parent.results],
            'message': 'Batch file upload tasks have been launched and will be aggregated.'
        }
        task_mgr.complete_task(
            result=summary, 
            grievance_id=grievance_id, 
            session_id=session_id
        )
        
        return summary
    except Exception as e:
        task_mgr.fail_task(
            error=str(e), 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='grievance_id', 
            entity_id=grievance_id
        )
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
    task_mgr = TaskManager(task=self, emit_websocket=True)
    task_mgr.emit_status(
        status=summary['status'], 
        data=summary, 
        grievance_id=grievance_id, 
        session_id=None
    )
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
    task_mgr = TaskManager(task=self,  emit_websocket=False)
    if grievance_id:
        task_mgr.start_task(
            entity_key='grievance_id',
            entity_id=grievance_id,
            grievance_id=grievance_id,
            session_id=None,
            extra_data={'phone_number': phone_number}
        )
    try:
        result = messaging.send_sms(phone_number, message)
        if grievance_id:
            task_mgr.complete_task(
                result=result, 
                grievance_id=grievance_id, 
                session_id=None
            )
        return result
    except Exception as e:
        if grievance_id:
            task_mgr.fail_task(
                error=str(e), 
                grievance_id=grievance_id, 
                session_id=None, 
                entity_key='grievance_id', 
                entity_id=grievance_id
            )
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
    task_mgr = TaskManager(task=self, emit_websocket=False)
    if grievance_id:
        task_mgr.start_task(
            entity_key='grievance_id',
            entity_id=grievance_id,
            grievance_id=grievance_id,
            session_id=None,
            extra_data={'to_emails': to_emails}
        )
    try:
        result = messaging.send_email(to_emails, subject, body)
        if grievance_id:
            task_mgr.complete_task(
                result=result, 
                grievance_id=grievance_id, 
                session_id=None
            )
        return result
    except Exception as e:
        if grievance_id:
            task_mgr.fail_task(
                error=str(e), 
                grievance_id=grievance_id, 
                session_id=None, 
                entity_key='grievance_id', 
                entity_id=grievance_id
            )
        raise

# LLM Tasks
@TaskManager.register_task(task_type='LLM')
def transcribe_audio_file_task(self, input_data: Dict[str, Any], 
                               grievance_id: str = None,
                               session_id: str = None,
                               emit_websocket: bool = True) -> Dict[str, Any]:
    """
    Transcribe an audio file.
    
    Args:
        input_data: Dictionary containing:
            - complainant_id: ID of the user
            - grievance_id: ID of the grievance
            - complainant_province: Province of the user
            - complainant_district: District of the user
            - field_name: Name of the field being transcribed
            - file_path: Path to the audio file
            - language_code: Language code of the audio
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing transcription results with keys:
        - status: SUCCESS or 'error'
        - operation: 'transcription'
        - complainant_province: Province of the user
        - complainant_district: District of the user
        - field_name: Name of the field
        - values: Transcription text {field_name: transcription_text}
        - file_path: Path to the audio file
        - language_code: Language code of the audio
        - task_id: ID of the task
        - entity_key: 'transcription_id'
        - id: Dummy transcription_id (same as task_id)
        - grievance_id: ID of the grievance
        - recording_id: ID of the recording
        - complainant_id: ID of the user
    """
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    
    # Create task manager with the current task instance and proper websocket handling
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
    try:
        complainant_id = input_data.get('complainant_id')
        grievance_id = input_data.get('grievance_id')
        field_name = input_data.get('field_name')
        
        if not grievance_id:
            raise ValueError(f"grievance_id is required but not found in input data: {input_data}")
        
        if not field_name:
            raise ValueError(f"field_name is required but not found in input data: {input_data}")
            
    except Exception as e:
        task_mgr.fail_task(
            error="Missing key fields in input data: {str(e)}", 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='transcription_id', 
            entity_id='unknown'
        )
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
            from backend.services.database_services.postgres_services import db_manager
            recording_id = db_manager.get_recording_id_for_grievance_id_and_field_name(grievance_id, field_name)
            if not recording_id:
                raise ValueError(f"Could not find recording_id for grievance_id: {grievance_id}, field_name: {field_name}")
        
        # Use task_id as dummy transcription_id for flow continuity
        dummy_transcription_id = task_id
        
        task_mgr.start_task(
            entity_key='transcription_id',
            entity_id=str(dummy_transcription_id),  # Use task_id as dummy transcription_id
            grievance_id=grievance_id,
            session_id=session_id,
            extra_data={'file_path': file_path}
        )
        
        from backend.services.LLM_services import transcribe_audio_file
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
            'entity_id': dummy_transcription_id,  # Dummy transcription_id (same as task_id)
            'grievance_id': grievance_id,
            'recording_id': recording_id,
            'complainant_id': complainant_id,
            'complainant_province': input_data.get('complainant_province'),
            'complainant_district': input_data.get('complainant_district')
        }
    except Exception as e:
        error = "error during transcription: " + str(e) #adding context to error message
        task_mgr.fail_task(
            error=error, 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='transcription_id', 
            entity_id=str(task_id)
        )
        return {
        'status': FAILED,
        'operation': 'transcription',
        'error': error,
        'task_id': task_id,
        'file_path': file_path,
        'entity_key': 'transcription_id',
        'entity_id': task_id,  # Use task_id even for errors
        'grievance_id': grievance_id,
        'complainant_id': complainant_id
        }
             # ✅ QUICK FIX (direct call):
    try:
        task_mgr = DatabaseTaskManager(task=self, emit_websocket=False)
        db_result = task_mgr.handle_db_operation(result)
        print(f"Database operation completed: {db_result}")
    except Exception as e:
        error = "error during database operation: " + str(e) #adding context to error message
        task_mgr.fail_task(
            error=error, 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='transcription_id', 
            entity_id=str(task_id)
        )
        return {
        'status': FAILED,
        'operation': 'transcription',
        'error': error,
        'task_id': task_id,
        'file_path': file_path,
        'entity_key': 'transcription_id',
        'entity_id': task_id,  # Use task_id even for errors
        'grievance_id': grievance_id,
        'complainant_id': complainant_id
        }
        
    try:        
        task_mgr.complete_task(
            result=values, 
            grievance_id=grievance_id, 
            session_id=session_id
        )

    
        # # Store result to database asynchronously (fire & forget)
        # store_result_to_db_task.delay(result)
        
        return result
    except Exception as e:
        error = "error during transcription: " + str(e) #adding context to error message
        task_mgr.fail_task(
            error=error, 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='transcription_id', 
            entity_id=str(task_id)
        )
        return {
            'status': FAILED,
            'operation': 'transcription',
            'error': str(e),
            'task_id': task_id,
            'file_path': file_path,
            'entity_key': 'transcription_id',
            'entity_id': task_id,  # Use task_id even for errors
            'grievance_id': grievance_id,
            'complainant_id': complainant_id
        }

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
            - complainant_province: Province of the user
            - complainant_district: District of the user
            - complainant_id: ID of the user
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing classification results with keys:
        - status: SUCCESS or FAILED
        - operation: 'classification'
        - entity_key: grievance_id
        - id: ID from file_data
        - task_id: ID of the task
        - grievance_id: ID of the grievance
        - values: {grievance_summary: summary_text, grievance_categories: [category1, category2, ...], grievance_categories_alternative: [category3, category4, ...]}
        - language_code: Language code of the transcription
        - complainant_id: ID of the user
        - complainant_province: Province of the user
        - complainant_district: District of the user
    """
    # Assign the entity_key to grievance_id
    input_data['entity_key'] = 'grievance_id'
    
    if not input_data.get('grievance_id'):
        raise ValueError(f"Missing grievance_id in input data: {input_data}")
    
    # Get the Celery task ID from the current task
    self.request.task_id = self.request.id if hasattr(self, 'request') else None
    
    task_mgr = TaskManager(task=self,  emit_websocket=emit_websocket)
    print(f"Classify and summarize grievance task called with file_data: {input_data}")
    
    # Extract grievance_id from the file_data
    grievance_id = input_data.get('grievance_id')
    entity_key = 'grievance_id'
    entity_id = grievance_id

    
    # Extract session_id for websocket emission (handle both Rasa and Flask frontends)
    session_id = input_data.get('flask_session_id') or input_data.get('session_id')
    if not session_id:
        raise ValueError(f"Missing session_id (flask_session_id or session_id) in input data: {input_data} - emission will fail")
    
    # Store context data in TaskManager instance for later retrieval
    # (This is the proper way according to Celery documentation)
    
    # Extract data directly from file_data (transcription result)
    language_code = input_data.get('language_code', 'ne')
    grievance_description = input_data.get('values', {}).get('grievance_description')  # The transcription text
 
        
    if not grievance_description:
        raise ValueError(f"No transcription text found in input data: {input_data.get('values')}")
    
    task_mgr.start_task(
        entity_key=entity_key, 
        entity_id=entity_id,
        grievance_id=grievance_id,
        session_id=session_id
    )
    try:
        from backend.services.LLM_services import classify_and_summarize_grievance
        complainant_district = input_data.get('complainant_district')
        complainant_province = input_data.get('complainant_province')
        values = classify_and_summarize_grievance(grievance_description, language_code, complainant_district, complainant_province) #values is a dict with keys: grievance_summary, grievance_categories
        if not values:
            raise ValueError(f"No result found in classify_and_summarize_grievance: {values}")

        # Flatten the classification results into the main result for frontend
        values.update({'grievance_description': grievance_description})
        result = {'status': SUCCESS,  
                  'operation': 'classification',
                  'entity_key': entity_key,
                  'entity_id': entity_id,
                  'task_id': self.request.id,
                  'grievance_id': grievance_id,
                  'values': values,
                  'language_code': language_code,
                  'complainant_id': input_data.get('complainant_id'),
                  'complainant_province': input_data.get('complainant_province'),
                  'complainant_district': input_data.get('complainant_district')
                  }
        
        
    except Exception as e:
        error = "error during classification by LLM: " + str(e) #adding context to error message
        task_mgr.fail_task(
            error=error, 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key=entity_key, 
            entity_id=entity_id
        )
        return {
            'status': FAILED,
            'operation': 'classification',
            'error': error,
            'task_id': self.request.task_id,
            'entity_key': entity_key,
        }

    # ✅ QUICK FIX (direct database call call):
    try:
        db_mgr = DatabaseTaskManager(task=self, emit_websocket=False)
        db_result = db_mgr.handle_db_operation(result)
        print(f"Database operation completed: {db_result}")
    except Exception as e:
        error = "Error in classify_and_summarize_grievance_task during database operation: " + str(e) #adding context to error message
        task_mgr.fail_task(
            error=error, 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='grievance_id', 
            entity_id=grievance_id
        )
        return {
            'status': FAILED,
            'operation': 'classification',
            'error': error,
            'task_id': self.request.task_id,
            'entity_key': entity_key,
        }

    task_mgr.complete_task(
        result=values, 
        grievance_id=grievance_id, 
        session_id=session_id
    )
    try:
        # # Store result to database asynchronously (fire & forget)
        # store_result_to_db_task.delay(result)
        
        return result
    except Exception as e:
        error = str(e)
        task_mgr.fail_task(
            error=str(e), 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='grievance_id', 
            entity_id=grievance_id
        )
        return {
            'status': FAILED,
            'operation': 'classification',
            'error': error,
            'task_id': self.request.task_id,
            'entity_key': entity_key,
        }

@TaskManager.register_task(task_type='LLM')
def extract_contact_info_task(self, input_data: Dict[str, Any], 
                              grievance_id: str = None,
                              session_id: str = None,
                              emit_websocket: bool = True) -> Dict[str, Any]:
    """
    Extract contact information from transcription result.
    
    Args:
        transcription_data: Dictionary containing:
            - entity_key: Entity key
            - field_name: Name of the field
            - values: Transcription text {field_name: transcription_text}
            - grievance_id: ID of the grievance
            - complainant_id: ID of the user
            - language_code: Language code of the transcription
            - complainant_province: Province of the user
            - complainant_district: District of the user
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing contact information extraction results with keys:
        - status: SUCCESS or FAILED
        - operation: 'contact_info'
        - entity_key: 'complainant_id'
        - id: ID of the user
        - language_code: Language code of the transcription
        - task_id: ID of the task
        - grievance_id: ID of the grievance
        - complainant_id: ID of the user
        - values: {field_name: contact_info_value}
        - complainant_province: Province of the user
        - complainant_district: District of the user
    """
    # Get the Celery task ID from the current task
    task_id = self.request.id if hasattr(self, 'request') else None
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
    
    # Extract context data directly from input_data
    grievance_id = input_data.get('grievance_id')
    session_id = input_data.get('flask_session_id') or input_data.get('session_id')
    
    try:    
        # Extract data directly from transcription result
        entity_key = input_data.get('entity_key')
        field_name = input_data.get('field_name')
        language_code = input_data.get('language_code')

        if not grievance_id:
            raise ValueError(f"Missing grievance_id - must be provided as task argument or in input_data")
        
        if not session_id:
            raise ValueError(f"Missing session_id - must be provided as task argument or in input_data")
        
        complainant_id = input_data.get('complainant_id')
        if not complainant_id:
            raise ValueError(f"Missing complainant_id in input_data: {input_data}")
        complainant_district = input_data.get('complainant_district')
        complainant_province = input_data.get('complainant_province')
        # TaskManager will use grievance_id for websocket emissions
        task_mgr.start_task(
            entity_key='complainant_id', 
            entity_id=complainant_id,
            grievance_id=grievance_id,
            session_id=session_id
        )
    
        from backend.services.LLM_services import extract_contact_info
        contact_data = input_data['values']
        values = extract_contact_info(contact_data, language_code, complainant_district, complainant_province)
        
        incorrect_fields = [k for k in values.keys() if k not in USER_FIELDS]
        if incorrect_fields:
            raise ValueError(f"Incorrect fields found in contact info: {incorrect_fields}")
        
        result= {'status': SUCCESS,
                 'operation': 'contact_info',
                 'entity_key': "complainant_id",
                 'entity_id': complainant_id,
                 'language_code': language_code,
                 'task_id': task_id,
                 'grievance_id': grievance_id,
                 'complainant_id': complainant_id,
                 'values': values,
                 'complainant_province': complainant_province,
                 'complainant_district': complainant_district
                 }
            # result.update({'result': contact_info})  # Use contact_info direc
    
        # ✅ QUICK FIX (direct call):
        try:
            task_mgr = DatabaseTaskManager(task=self, emit_websocket=False)
            db_result = task_mgr.handle_db_operation(result)
            print(f"Database operation completed: {db_result}")
        except Exception as e:
            task_mgr.fail_task(
                error=str(e), 
                grievance_id=grievance_id, 
                session_id=session_id, 
                entity_key='complainant_id', 
                entity_id=complainant_id
            )
            return {
                'status': FAILED,
                'operation': 'contact_info',
                'error': "Error in extract_contact_info_task during database operation: " + str(e),
                'entity_key': 'complainant_id',
                'task_id':task_id
            }
        task_mgr.complete_task(
            result=values, 
            grievance_id=grievance_id, 
            session_id=session_id
        )
        
        # # Store result to database asynchronously (fire & forget)
        # store_result_to_db_task.delay(result)
        
        return result
    
    except Exception as e:
        error = "error during contact info extraction by LLM: " + str(e) #adding context to error message
        task_mgr.fail_task(
            error=error, 
            grievance_id=grievance_id, 
            session_id=session_id, 
            entity_key='complainant_id', 
            entity_id=complainant_id
        )
        return {
            'status': FAILED,
            'operation': 'contact_info',
            'error': error,
            'entity_key': 'complainant_id',
            'task_id':task_id
        }

@TaskManager.register_task(task_type='LLM')
def translate_grievance_to_english_task(self, input_data: Dict[str, Any], 
                                         grievance_id: str = None,
                                         session_id: str = None,
                                         emit_websocket: bool = True) -> Dict[str, Any]:
    """
    Translate a grievance to English and save it to the database.
    
    Args:
        file_data: Dictionary containing:
            - grievance_id: ID of the grievance
            - language_code: Language code of the grievance
            - values: Grievance data including 'grievance_description'
        emit_websocket: Whether to emit a websocket message (default: True)
        
    Returns:
        Dict containing translation results with keys:
        - status: SUCCESS or FAILED
        - operation: 'translation'
        - value: Translated grievance data
        - language_code: 'en'
        - entity_key: 'translation_id'
        - id: Dummy translation_id (same as task_id)
        - task_id: ID of the task
        - grievance_id: ID of the grievance
        - complainant_id: ID of the user
    """
    task_id = self.request.id if hasattr(self, 'request') else None
    task_mgr = TaskManager(task=self, emit_websocket=emit_websocket)
    
    # Extract context data directly from input_data
    grievance_id = input_data.get('grievance_id')
    session_id = input_data.get('flask_session_id') or input_data.get('session_id')
    
    try:
        task_mgr.monitoring.log_task_event(task_name='translate_grievance_to_english',
                                           details=input_data)
        # Extract data from potentially nested group result
        language_code = input_data.get('language_code')
        grievance_data = input_data.get('values')
        
        if not grievance_id:
            raise ValueError(f"Missing grievance_id - must be provided as task argument or in input_data")
        
        if not session_id:
            raise ValueError(f"Missing session_id - must be provided as task argument or in input_data")
        if not language_code:
            raise ValueError(f"Missing language_code in input data: {input_data}")
        if not grievance_data:
            raise ValueError(f"Missing grievance_data in input data: {input_data}")
        if not grievance_data.get('grievance_description'):
            raise ValueError(f"Missing grievance_description in input data: {input_data}")
        
        grievance_data.update({'language_code': language_code, 'grievance_id': grievance_id})
        
        task_mgr.monitoring.log_task_event(task_name='translate_grievance_to_english', 
details=grievance_data)
    
        
        task_mgr.start_task(
            entity_key='translation_id', 
            entity_id=str(task_id),  # Use task_id (UUID) instead of grievance_id (string)
            grievance_id=grievance_id,
            session_id=session_id
        )
        
        from backend.services.LLM_services import translate_grievance_to_english_LLM
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
            'entity_id': task_id,  # Use dummy translation_id (same as task_id)
            'task_id': task_id,
            'grievance_id': grievance_id,
            'complainant_id': input_data.get('complainant_id'),
            'complainant_province': input_data.get('complainant_province'),
            'complainant_district': input_data.get('complainant_district')


        }

                # ✅ QUICK FIX (direct call):
        try:
            task_mgr = DatabaseTaskManager(task=self, emit_websocket=False)
            db_result = task_mgr.handle_db_operation(result)
            print(f"Database operation completed: {db_result}")
        except Exception as e:
            error = "Error in translate_grievance_to_english_task during database operation: " + str(e)
            task_mgr.fail_task(
                error=error, 
                grievance_id=grievance_id, 
                session_id=session_id, 
                entity_key='translation_id', 
                entity_id=str(task_id)
            )
            return {
                'status': FAILED,
                'operation': 'translation',
                'error': error,
                'entity_key': 'translation_id',
                'task_id': task_id,
                'grievance_id': grievance_id,
                'source_language': language_code,
                'transcription_method': 'LLM'
            }
        task_mgr.complete_task(
            result=values, 
            grievance_id=grievance_id, 
            session_id=session_id
        )
        
        # # Store result to database asynchronously (fire & forget)
        # store_result_to_db_task.delay(result)
        
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
            
        error = "error during translation by LLM: " + str(e) #adding context to error message
        task_mgr.fail_task(error, grievance_id, session_id, 'translation_id', str(task_id))
        return {
            'status': FAILED,
            'operation': 'translation',
            'error': error,
            'entity_key': 'translation_id',  # Use task_id even for errors
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
            - status: SUCCESS or FAILED
        emit_websocket: Whether to emit a websocket message (default: False)
        
    Returns:
        Dict indicating the result of the storage operation with keys:
        - status: SUCCESS or FAILED
        - operation: 'store_result'
        - error: Error message if status is 'error'
    """
    task_mgr = DatabaseTaskManager(task=self, emit_websocket=emit_websocket)
    try:
        
        # Handle database operation with retroactive task creation
        result = task_mgr.handle_db_operation(input_data)
        return result
    except Exception as e:
        error_result = {
            'status': FAILED,
            'operation': 'store_result',
            'error': str(e)
        }
        return error_result

