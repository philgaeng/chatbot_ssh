"""
TaskManager Module - Centralized Task Management with Automatic Service Configuration

This module provides a centralized task management system with automatic service configuration,
monitoring, retries, and WebSocket status updates for async task processing.

Key Design Principles:
===================

1. **Centralized Service Configuration**: 
   - All service configurations are defined in TASK_CONFIG within this module
   - Task functions don't need service parameters - they're automatically set by the decorator
   - @TaskManager.register_task(task_type='LLM') automatically sets self.service from TASK_CONFIG['LLM']['service']

2. **Automatic Task Registration**:
   - Use @TaskManager.register_task(task_type='TaskType') decorator on task functions
   - The decorator handles Celery registration, service assignment, and wrapper logic
   - Task types must exist in TASK_CONFIG or registration will fail

3. **Clean Function Signatures**:
   - Task functions focus purely on business logic
   - No service parameters needed in function signatures
   - Service is automatically available as self.service within task methods

4. **Configuration Management**:
   - TASK_CONFIG defines all task types with their service, queue, and retry configurations
   - Single source of truth for all task-related settings
   - Easy to modify service assignments without touching individual task functions

Example Usage:
=============
```python
# In registered_tasks.py - Clean function signature, no service parameter
@TaskManager.register_task(task_type='LLM')
def my_llm_task(self, input_data: Dict[str, Any], emit_websocket: bool = True):
    # self.service is automatically set to TASK_CONFIG['LLM']['service'] = 'llm_processor'
    logger.info(f"Running LLM task with service: {self.service}")
    return {"result": "SUCCESS"}

@TaskManager.register_task(task_type='Messaging')  
def my_messaging_task(self, message: str):
    # self.service is automatically set to TASK_CONFIG['Messaging']['service'] = 'messaging_service'
    return {"sent": True}
```

Architecture Benefits:
===================
- Centralized configuration in TASK_CONFIG
- Clean separation of concerns
- Easy service reassignment
- Consistent task registration
- No parameter pollution in task functions

Dependencies:
============
- Celery for async task processing
- Redis for task queuing and WebSocket communication
- WebSocket utilities for real-time status updates
"""

import datetime
from backend.services.database_services.postgres_services import db_manager
from backend.services.database_services.base_manager import TaskDbManager
from backend.api.websocket_utils import emit_status_update_accessible
from typing import Dict, Any, Optional, List, Tuple, Callable
import time
import random
import logging
import json
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
import functools
from backend.logger.logger import TaskLogger, LoggingConfig  # Import LoggingConfig
from backend.config.constants import FIELD_MAPPING, VALID_FIELD_NAMES, TASK_STATUS, RASA_API_URL, FLASK_URL
from .celery_app import celery_app  # Safe to import at module level now
from celery import current_task

import requests

# Task type names (single source of truth)
TASK_TYPE_LLM = "LLM"
TASK_TYPE_FILEUPLOAD = "FileUpload"
TASK_TYPE_MESSAGING = "Messaging"
TASK_TYPE_DATABASE = "Database"
TASK_TYPE_DEFAULT = "Default"

MAP_TASK_TO_TYPE = {
    'process_file_upload_task': TASK_TYPE_FILEUPLOAD,
    'process_batch_files_task': TASK_TYPE_FILEUPLOAD,
    'aggregate_batch_results': TASK_TYPE_FILEUPLOAD,
    'send_sms_task': TASK_TYPE_MESSAGING,
    'send_email_task': TASK_TYPE_MESSAGING,
    'transcribe_audio_file_task': TASK_TYPE_LLM,
    'classify_and_summarize_grievance_task': TASK_TYPE_LLM,
    'extract_contact_info_task': TASK_TYPE_LLM,
    'translate_grievance_to_english_task': TASK_TYPE_LLM,
    'store_result_to_db_task': TASK_TYPE_DATABASE,
    'task_registry': TASK_TYPE_DEFAULT,
    'trigger_rasa_action': TASK_TYPE_DEFAULT,
    'operation_failed': TASK_TYPE_DEFAULT,
}

TASK_CONFIG = {
    TASK_TYPE_LLM: {'service': 'llm_processor', 
        'queue': {"priority": "high", "queue": "llm_queue"},
        'retries': {
            'max_retries': 3,
            'initial_delay': 2,
            'max_delay': 30,
            'backoff_factor': 2,
            'retry_on': ['ConnectionError', 'TimeoutError', 'RateLimitError']
        }
    },
    TASK_TYPE_FILEUPLOAD: {'service': 'file_processor',
                           'queue': {"priority": "medium", "queue": "default", "bind": False},
                           'retries': {
                            'max_retries': 2,
                            'initial_delay': 1,
                            'max_delay': 10,
                            'backoff_factor': 2,
                            'retry_on': ['IOError', 'FileNotFoundError'],
                            'bind': True
                        }
                    },
    TASK_TYPE_DATABASE: {'service': 'db_operations',
                         'queue': {"priority": "high", "queue": "default", "bind": False},
                         'retries': {
                            'max_retries': 3,
                            'initial_delay': 1,
                            'max_delay': 20,
                            'backoff_factor': 2,
                            'retry_on': ['ConnectionError', 'TimeoutError', 'DeadlockError'],
                            'bind': True
                        },
                    },
    TASK_TYPE_MESSAGING: {'service': 'messaging_service',
                          'queue': {"priority": "high", "queue": "default", "bind": False},
                            'retries': {
                            'max_retries': 2,
                            'initial_delay': 2,
                            'max_delay': 15,
                            'backoff_factor': 2,
                            'retry_on': ['ConnectionError', 'TimeoutError'],
                            'bind': True
                        },
                    },
    TASK_TYPE_DEFAULT: {'service': 'queue_system',
                        'queue': {"priority": "medium", "queue": "default", "bind": False},
                        'retries': {
                            'max_retries': 2,
                            'initial_delay': 1,
                            'max_delay': 10,
                            'backoff_factor': 2,
                            'retry_on': ['Exception'],
                            'bind': True
                        },
                    },
}



STARTED = TASK_STATUS['STARTED']
SUCCESS = TASK_STATUS['SUCCESS']
FAILED = TASK_STATUS['FAILED']
RETRYING = TASK_STATUS['RETRYING']


class MonitoringConfig:
    """Configuration for task monitoring and logging"""
    
    def __init__(self):
        # Use centralized logging configuration
        self.config = LoggingConfig()
        
        # Initialize logger registry
        self.logger_registry = {}
        
        # Initialize default loggers using centralized config
        for service in self.config.DEFAULT_SERVICES:
            self.register_logger(service)
    
    def get_service_from_task_name(self, task_name: str) -> str:
        """Get service from task name"""
        return TASK_CONFIG[MAP_TASK_TO_TYPE[task_name]]['service']
    
    def register_logger(self, service_name: str) -> TaskLogger:
        """Register a new logger for a service"""
        if service_name not in self.logger_registry:
            self.logger_registry[service_name] = TaskLogger(service_name)
        return self.logger_registry[service_name]
    
    def log_task_event(self, task_name: str, details: Optional[Dict[str, Any]] = None , level='info', event_type=None) -> None:
        """Log task events with consistent formatting"""
        service = self.get_service_from_task_name(task_name)
        # Get or create logger for the service
        logger = self.logger_registry.get(service, self.register_logger(service))
        
        # Log the event
        logger.log_task_event(service_name=service, task_name=task_name, details=details, event_type=event_type)

class RetryConfig:
    """Configuration for task retries"""
    # Base retry configurations
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_INITIAL_DELAY = 1  # seconds
    DEFAULT_MAX_DELAY = 60  # seconds
    DEFAULT_BACKOFF_FACTOR = 2
    
    # Task-specific configurations
    TASK_RETRY_CONFIGS = {k: v['retries'] for k, v in TASK_CONFIG.items()}

class TaskManager:
    # Class-level registry and configuration
    TASK_REGISTRY = {}
    TASK_TYPE_CONFIG = {k:v['queue'] for k, v in TASK_CONFIG.items()}
    monitoring = MonitoringConfig()  # Initialize as class-level attribute
    
    def __init__(self, task=None, emit_websocket=False, service='queue_system'):
        self.task = task
        self.task_name = task.name if task else 'unknown_task'
        self.task_type = MAP_TASK_TO_TYPE.get(self.task_name, TASK_TYPE_DEFAULT)
        self.emit_websocket = emit_websocket
        self.start_time = None
        self.end_time = None
        self.status = None
        self.result = None
        self.error = None
        self.db_task = db_manager
        self.service = TASK_CONFIG[self.task_type]['service']
        print(f"�� DEBUG: TaskManager initialized for {self.task_name}")
        # Retry tracking
        self.retry_count = getattr(task.request, 'retries', 0) if task and hasattr(task, 'request') else 0
        # self.last_retry_time = None
        # self.retry_config = self._get_retry_config()
        # self.retry_history: List[Dict[str, Any]] = []


    def _get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration based on task type"""
        return RetryConfig.TASK_RETRY_CONFIGS.get(self.task_type, {
            'max_retries': RetryConfig.DEFAULT_MAX_RETRIES,
            'initial_delay': RetryConfig.DEFAULT_INITIAL_DELAY,
            'max_delay': RetryConfig.DEFAULT_MAX_DELAY,
            'backoff_factor': RetryConfig.DEFAULT_BACKOFF_FACTOR,
            'retry_on': ['Exception']
        })


    def _should_retry(self, error: Exception) -> bool:
        """Determine if task should be retried based on error type and retry count"""

        from celery import current_task
        
        if not current_task:
            raise RuntimeError("This method must be called within a Celery task")
            
        retry_config = self._get_retry_config()
        if current_task.request.retries >= retry_config['max_retries']:
            return False
            
        error_type = type(error).__name__
        return error_type in retry_config['retry_on']

    def _calculate_retry_delay(self) -> float:
        """Calculate delay for next retry using exponential backoff with jitter"""
        from celery import current_task
        
        if not current_task:
            raise RuntimeError("This method must be called within a Celery task")
            
        retry_config = self._get_retry_config()
        if current_task.request.retries == 0:
            return retry_config['initial_delay']
            
        delay = min(
            retry_config['initial_delay'] * (retry_config['backoff_factor'] ** current_task.request.retries),
            retry_config['max_delay']
        )
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter

    def emit_status(self, status, data, grievance_id=None, session_id=None):
        """
        Send task status update directly to Flask API endpoint for websocket emission
        Args:
            status (str): The status to send
            data (dict): The data to send
            grievance_id (str): Grievance ID for websocket emission (REQUIRED)
            session_id (str): Session ID for websocket emission (REQUIRED)
        """
        from celery import current_task
        
        if not current_task:
            raise RuntimeError("This method must be called within a Celery task")
            
        # Context data must be provided explicitly
        if not grievance_id:
            raise ValueError("grievance_id is required for emit_status")
        if not session_id:
            raise ValueError("session_id is required for emit_status")
            
        try:
            # Debug logging to understand the issue
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'status': status,
                    'data': data,
                    'task_name': current_task.name,
                    'requests_available': 'requests' in globals(),
                    'note': 'DEBUG: Starting emit_status method'
                }
            )
            
            if data is None:
                data = {}
            
            # Add task name and status to data
            data['task_name'] = self.task_name
            data['status'] = status
            
            # Send to Flask API endpoint
            url = FLASK_URL + "/task-status"
            payload = {
                'status': status,
                'data': data,
                'grievance_id': grievance_id,
                'flask_session_id': session_id,
            }
            
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details={
                    'url': url,
                    'payload': payload,
                    'note': 'Sending to Flask API endpoint'
                }
            )
        
            try:
                # Debug: Log before making the request
                self.monitoring.log_task_event(
                    task_name=self.task_name,
                    details={
                        'grievance_id': grievance_id,
                        'session_id': session_id,
                        'url': url,
                        'payload_keys': list(payload.keys()) if payload else None,
                        'note': 'DEBUG: About to make HTTP request'
                    }
                )
                
                try:
                    response = requests.post(url, json=payload, timeout=10)
                except ImportError as e:
                    raise Exception(f"requests module not available: {e}")
                except requests.exceptions.ConnectionError as e:
                    raise Exception(f"Connection error to {url}: {e}")
                except requests.exceptions.Timeout as e:
                    raise Exception(f"Timeout error to {url}: {e}")
                except Exception as e:
                    raise Exception(f"HTTP request error to {url}: {e}")
                
                self.monitoring.log_task_event(
                    task_name=self.task_name,
                    details={
                        'grievance_id': grievance_id,
                        'session_id': session_id,
                        'response_status': response.status_code,
                        'response_text': response.text,
                        'note': 'Task status update sent successfully'
                    }
                )
                
                if response.status_code != 200:
                    self.monitoring.log_task_event(
                        task_name=self.task_name,
                        details={
                            'grievance_id': grievance_id,
                            'session_id': session_id,
                            'error': f'API returned status {response.status_code}',
                            'response': response.text,
                            'note': 'Task status update failed'
                        }
                    )

            except Exception as e:
                # Debug logging for inner exception
                self.monitoring.log_task_event(
                    task_name=self.task_name,
                    details={
                        'grievance_id': grievance_id,
                        'session_id': session_id,
                        'error': str(e),
                        'exception_type': type(e).__name__,
                        'exception_traceback': str(e.__traceback__),
                        'note': 'DEBUG: Inner exception in HTTP request'
                    }
                )
                logging.error(f"Failed to send task status update for grievance '{grievance_id}' and session '{session_id}': {e}")

        except Exception as e:
            # Debug logging to understand the exception
            self.monitoring.log_task_event(
                task_name=current_task.name,
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'exception_traceback': str(e.__traceback__),
                    'note': 'DEBUG: Exception in emit_status method'
                }
            )
            
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'error': f"Failed to emit status update: {str(e)}"
                }
            )

    def retry_task(self, error: Exception) -> Tuple[bool, Optional[float]]:
        """
        Handle task retry logic
        
        Args:
            error: The exception that caused the failure
            
        Returns:
            Tuple of (should_retry, delay_seconds)
        """
        from celery import current_task
        
        if not current_task:
            raise RuntimeError("This method must be called within a Celery task")
            
        if not self._should_retry(error):
            return False, None
            
        # Get current retry count from database using simpler query
        task_info = self.db_task.get_task(self.task_id)
        if not task_info:
            return False, None
            
        current_retry_count = task_info.get('retry_count', 0)
        new_retry_count = current_retry_count + 1
        
        # Update retry count and history in database
        retry_info = {
            'retry_count': new_retry_count,
            'error': str(error),
            'error_type': type(error).__name__,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        
        # Get existing retry history or initialize empty list
        retry_history = json.loads(task_info.get('retry_history', '[]'))
        retry_history.append(retry_info)
        retry_history_json = json.dumps(retry_history)
        
        # Update task status with new retry count and history
        updated = self.db_task.update_task(
            self.task_id,
            {
                'status_code': RETRYING,
                'retry_count': new_retry_count,
                'error_message': str(error),
                'retry_history': retry_history_json
            }
        )
        
        if not updated:
            return False, None
            
        # Update instance variables to match database state
        # Note: retries is read-only in Celery, we track retry_count in our own logic
        # Store retry history and timing in our own instance variables
        self.retry_history = retry_history
        self.last_retry_time = datetime.datetime.utcnow()
        
        # Log retry attempt
        self.monitoring.log_task_event(
            task_name=current_task.name,
            details={
                'retry_count': new_retry_count,
                'error': str(error),
                'next_retry_delay': self._calculate_retry_delay()
            },
            event_type=RETRYING
        )
        
        # Emit retry status - Note: retry_task doesn't have context data, so we can't emit status
        # This is a limitation of the current retry mechanism
        # TODO: Consider passing context data to retry_task method
        
        return True, self._calculate_retry_delay()

    def start_task(self, entity_key: str, entity_id: str, grievance_id: str, 
                    extra_data=None, session_id: Optional[str] = None) -> bool:
        """Start a new task with logging and websocket emission only - no database interaction.
        Database task record will be created later by store_result_to_db_task when entity exists.
        
        Args:
            entity_key: Type of entity (complainant_id, grievance_id, etc.)
            entity_id: ID of the entity
            grievance_id: Grievance ID for websocket emissions (REQUIRED)
            extra_data: Optional extra data for logging
            session_id: Optional session identifier for websocket emissions
        """
        from celery import current_task
        
        if not current_task:
            raise RuntimeError("This method must be called within a Celery task")
            
        try:
            if not grievance_id:
                raise ValueError("grievance_id is required for all tasks")
            
            # Context data is passed explicitly to methods (cleaner approach)
                
            # Log task start with context data passed directly
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'entity_key': entity_key,
                    'entity_id': entity_id,
                    'note': 'Task started with unified API endpoint',
                    
                },
                event_type=STARTED
            )
            self.start_time = datetime.datetime.utcnow()
            self.status = STARTED
            
            # Get Celery's task ID for tracking
            celery_task_id = current_task.request.id
            if not celery_task_id:
                raise ValueError("No Celery task ID available")
            
            self.task_id = celery_task_id
            
            # Check if this is a retry by looking at Celery's retry count
            # (This is for logging purposes only - database logic is in handle_db_operation)
            celery_retry_count = getattr(current_task.request, 'retries', 0)
            is_retry = celery_retry_count > 0
            
            # Log task start (no database interaction)
            log_event_type = 'retry_started' if is_retry else STARTED
            log_details = {
                'session_id': session_id,
                'entity_key': entity_key,
                'entity_id': entity_id,
                'grievance_id': grievance_id,
                'task_id': current_task.request.id,
                'celery_retry_count': celery_retry_count,
                'note': f'Task {"retry" if is_retry else "execution"} started - database record will be created when results are stored',
                **(extra_data or {})
            }
            
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details=log_details,
                event_type=log_event_type
            )
            
            # Emit websocket status for UI updates
            if self.emit_websocket:
                websocket_data = {'task_name': self.task_name, **(extra_data or {})}
                if is_retry:
                    websocket_data['retry_count'] = celery_retry_count
                self.emit_status(STARTED, websocket_data, grievance_id, session_id)
            return True
        except Exception as e:
            self.error = str(e)
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details={
                    'entity_key': entity_key,
                    'entity_id': entity_id,
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'error': str(e),
                    **(extra_data or {})
                },
                event_type=FAILED
            )
            return False

    def complete_task(self, result=None, grievance_id=None, session_id=None) -> bool:
        """Mark task as complete with logging and websocket emission only - no database interaction.
        Also triggers a Rasa action via HTTP API if session_id and result are available (for file upload/classification tasks).
        Database task record will be created/updated later by store_result_to_db_task.
        
        Args:
            result: Task result data
            grievance_id: Grievance ID for websocket emission (REQUIRED)
            session_id: Session ID for websocket emission (REQUIRED)
        """
        from celery import current_task
        
        if not current_task:
            raise RuntimeError("This method must be called within a Celery task")
            
        # Context data must be provided explicitly
        if not grievance_id:
            raise ValueError("grievance_id is required for complete_task")
        if not session_id:
            raise ValueError("session_id is required for complete_task")
            
        try:
            self.end_time = datetime.datetime.utcnow()
            self.status = SUCCESS
            self.result = result

            # Log task completion (no database interaction)
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details={
                    'session_id': session_id,
                    'grievance_id': grievance_id,
                    'status': SUCCESS,
                    'task_id': current_task.request.id,
                    'result': result,
                    'retry_count': self.retry_count,
                    'note': 'Task completed - database record will be created when results are stored'
                },
                event_type=SUCCESS
            )

            # Emit websocket status for UI updates
            if self.emit_websocket:
                self.emit_status(SUCCESS, result, grievance_id, session_id)

            return True
        except Exception as e:
            self.error = str(e)
            self.monitoring.log_task_event(
                task_name=self.task_name,
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'error': str(e)
                },
                event_type=FAILED
            )
            return False

    def fail_task(self, error: str, grievance_id=None, session_id=None, entity_key=None, entity_id=None) -> bool:
        """Mark task as failed with logging and websocket emission only - no database interaction.
        Database task record will be created/updated later by store_result_to_db_task.
        
        Args:
            error: Error message
            grievance_id: Grievance ID for websocket emission (REQUIRED)
            session_id: Session ID for websocket emission (REQUIRED)
            entity_key: Type of entity for logging (optional, for debugging)
            entity_id: ID of the entity for logging (optional, for debugging)
        """
        from celery import current_task
        
        if not current_task:
            raise RuntimeError("This method must be called within a Celery task")
            
        # Context data must be provided explicitly
        if not grievance_id:
            raise ValueError("grievance_id is required for fail_task")
        if not session_id:
            raise ValueError("session_id is required for fail_task")
            
        try:
            self.end_time = datetime.datetime.utcnow()
            self.status = 'FAILED'
            self.error = error
            
            # Log task failure (no database interaction)
            log_details = {
                'grievance_id': grievance_id,
                'session_id': session_id,
                'error': error,
                'retry_count': current_task.request.retries,
                'note': 'Task failed - database record will be created when results are stored'
            }
            
            # Add entity information for debugging if provided
            if entity_key:
                log_details['entity_key'] = entity_key
            if entity_id:
                log_details['entity_id'] = entity_id
            
            self.monitoring.log_task_event(
                task_name=current_task.name,
                details=log_details,
                event_type=FAILED
            )
            
            # Emit websocket status for UI updates
            if self.emit_websocket:
                self.emit_status('FAILED', {'task_name': self.task_name, 'error': str(error)},
                               grievance_id, session_id)
            return True
        except Exception as e:
            self.error = str(e)
            self.monitoring.log_task_event(
                task_name=current_task.name,
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'error': f"Failed to record failure: {str(e)}"
                },
                event_type=FAILED
            )
            return False

    @classmethod
    def register_task(cls, task_type: str):
        """
        Decorator to register a task in the TASK_REGISTRY with automatic service configuration.
        
        This decorator automatically:
        1. Validates that task_type exists in TASK_CONFIG
        2. Sets self.service from TASK_CONFIG[task_type]['service'] 
        3. Removes any 'service' parameter from kwargs to keep function signatures clean
        4. Registers the task with Celery using the appropriate queue configuration
        
        Args:
            task_type (str): Must match a key in TASK_CONFIG (e.g., 'LLM', 'Messaging', 'FileUpload')
            
        Raises:
            ValueError: If task_type is not found in TASK_CONFIG
            
        Example:
            @TaskManager.register_task(task_type='LLM')
            def my_task(self, data: Dict[str, Any]):
                # self.service automatically set to TASK_CONFIG['LLM']['service']
                pass
        """
 
        if task_type not in cls.TASK_TYPE_CONFIG:
            error_msg = f"Unknown task_type '{task_type}'. Please add it to TASK_TYPE_CONFIG."
            cls.monitoring.log_task_event('task_registry', level='error', details={'error': error_msg})
            raise ValueError(error_msg)
        
        # Extract config from TASK_CONFIG
        config = TASK_CONFIG[task_type]  # Get full config from TASK_CONFIG
        queue_config = config.get('queue', {})
        retry_config = config.get('retry', {})
                
                
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                # Extract config from TASK_CONFIG
                self.service = config.get('service', 'queue_system')
                
                # Remove service from kwargs if somehow passed (keeps function signatures clean)
                kwargs.pop('service', None)
                
                # Ensure task instance is available
                if not hasattr(self, 'request'):
                    raise ValueError("Task instance not properly bound. Make sure to use bind=True in Celery task.")
                
                # Get task ID from request
                task_id = getattr(self.request, 'id', None)
                if not task_id:
                    raise ValueError("No Celery task ID available")
                
                return func(self, *args, **kwargs)
                
            # Register in TASK_REGISTRY
            cls.TASK_REGISTRY[func.__name__] = {
                'name': func.__name__.replace('_', ' ').title(),
                'description': func.__doc__ or '',
                'priority': queue_config['priority'],
                'type': task_type,
                'queue': queue_config['queue'],
                'task': wrapper
            }
            
            # Log task registration
            cls.monitoring.log_task_event(
                task_name='task_registry',
                details={
                    'task_name': func.__name__,
                    'task_type': task_type,
                    'queue': queue_config['queue'],
                    'priority': queue_config['priority']
                }
            )
            
            # Prepare Celery task options
            celery_options = {
                'bind': True,  # Always bind the task
                'name': func.__name__,
                'queue': queue_config['queue']
            }
            
            # Add retry configuration if available
            if retry_config:
                celery_options.update({
                    'max_retries': retry_config.get('max_retries', 3),
                    'default_retry_delay': retry_config.get('initial_delay', 1),
                    'retry_backoff': retry_config.get('backoff_factor', 2),
                    'retry_backoff_max': retry_config.get('max_delay', 60),
                    'autoretry_for': tuple(getattr(__builtins__, exc, Exception) for exc in retry_config.get('retry_on', ['Exception']))
                })
            
            # Add priority if available (Celery uses 0-9, with 9 being highest)
            priority_mapping = {'low': 3, 'medium': 5, 'high': 7, 'critical': 9}
            if queue_config.get('priority'):
                celery_options['priority'] = priority_mapping.get(queue_config['priority'], 5)
            
            # Register with Celery
            celery_task = celery_app.task(**celery_options)(wrapper)
            
            cls.TASK_REGISTRY[func.__name__]['celery_task'] = celery_task
            return celery_task
        return decorator
    
    @classmethod
    def get_task_function(cls, task_name: str) -> Optional[Callable]:
        """Get a task function from the registry by name."""
        task_info = cls.TASK_REGISTRY.get(task_name)
        if not task_info:
            cls.monitoring.log_task_event(task_name='task_registry', level='error', details={'error': f"Task '{task_name}' not found in registry"})
        return task_info['task'] if task_info else None
    
    @classmethod
    def get_task_metadata(cls, task_name: str):
        """Get task metadata from the registry by name"""
        task_info = cls.TASK_REGISTRY.get(task_name)
        if task_info:
            return {k: v for k, v in task_info.items() if k != 'task'}
        error_msg = f"Task '{task_name}' not found in registry"
        cls.monitoring.log_task_event(task_name='task_registry', level='error', details={'error': error_msg})
        raise KeyError(error_msg)

    def trigger_task_status_update(self, status: str, data: Optional[dict] = None, grievance_id=None, session_id=None):
        """
        Send task status update directly to Flask API endpoint for websocket emission
        Args:
            status (str): The status to send
            data (dict): The data to send
            grievance_id (str): Grievance ID for websocket emission
            session_id (str): Session ID for websocket emission
        """
        
        self.monitoring.log_task_event(
            task_name='trigger_task_status_update',
            details={
                'grievance_id': grievance_id,
                'session_id': session_id,
                'status': status,
                'data': data,
                'note': 'Sending task status update to Flask API'
            }
        )
        
        if data is None:
            data = {}
        
        # Add task name and status to data
        data['task_name'] = current_task.name
        data['status'] = status
        
        # Send to Flask API endpoint
        url = "http://localhost:5001/api/task-status"
        payload = {
            'status': status,
            'data': data
        }
        
        # Add grievance_id and session_id if available
        if grievance_id:
            payload['grievance_id'] = grievance_id
        
        if session_id:
            payload['session_id'] = session_id
        
        self.monitoring.log_task_event(
            task_name='trigger_task_status_update',
            details={
                'url': url,
                'payload': payload,
                'note': 'Sending to Flask API endpoint'
            }
        )
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            self.monitoring.log_task_event(
                task_name='trigger_task_status_update',
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'response_status': response.status_code,
                    'response_text': response.text,
                    'note': 'Task status update sent successfully'
                }
            )
            
            if response.status_code != 200:
                self.monitoring.log_task_event(
                    task_name='trigger_task_status_update',
                    details={
                        'grievance_id': grievance_id,
                        'session_id': session_id,
                        'error': f'API returned status {response.status_code}',
                        'response': response.text,
                        'note': 'Task status update failed'
                    }
                )

        except Exception as e:
            self.monitoring.log_task_event(
                task_name='trigger_task_status_update',
                details={
                    'grievance_id': grievance_id,
                    'session_id': session_id,
                    'error': str(e),
                    'note': 'Failed to send task status update'
                }
            )
            logging.error(f"Failed to send task status update for grievance '{grievance_id}' and session '{session_id}': {e}")


class DatabaseTaskManager(TaskManager):
    """
    Specialized TaskManager for database operations.
    Handles database-specific task lifecycle and error handling.
    """
    def __init__(self, task=None, emit_websocket=False):
        super().__init__(task=task,  emit_websocket=emit_websocket)

        
    def prepare_task_result_data_to_db(self, input_data: dict) -> dict:
        """Extract and prepare data from task results for database operations
        
        Args:
            operation: Type of database operation (user, grievance, transcription, etc.)
            result: Standardized task result data containing operation, field, value, etc.
            file_data: File metadata and context data
            
        Returns:
            dict: Prepared data ready for database operation
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate result has required fields
        try:
            required_fields = ['status', 'entity_key', 'entity_id', 'values', 'grievance_id', 'complainant_id']
            missing_fields = [field for field in required_fields if field not in input_data]
            if missing_fields:
                raise ValueError(f"Task result missing required fields: {missing_fields} in input data: {input_data}")
                                
            entity_key = input_data['entity_key']
            entity_id = input_data['entity_id']
            # Start with file_data as base
            update_data = input_data['values']
            if 'language_code' in input_data and not 'language_code' in update_data:
                update_data['language_code'] = input_data['language_code']
                
            # Add entity ID from result data and add other requred fields to pass to next step
            update_data[entity_key] = entity_id
            if entity_key not in ['complainant_id', 'grievance_id']:
                update_data['grievance_id'] = input_data['grievance_id']
                update_data['complainant_id'] = input_data['complainant_id'] 
                update_data['task_id'] = input_data['task_id']
            
            # Add result data based on entity key
            if entity_key == 'transcription_id':
                try:
                    field_name = input_data['field_name']
                    update_data['automated_transcript'] = input_data[field_name]
                    # Remove the field_name entry from update_data
                    del update_data[field_name]
                except Exception as e:
                    self.monitoring.log_task_event(task_name='task_registry', level='error', details={'error': f"Error in prepare_task_result_data_to_db: {str(e)} - input_data: {input_data}"})   
                    raise ValueError(f"Error in prepare_task_result_data_to_db: transcription - {str(e)} - input_data: {input_data} - update_data: {update_data}")
                
            
                
            elif entity_key == 'translation_id':
                update_data['source_language'] = input_data['language_code']
                # Remove the language_code entry from update_data
                del update_data['language_code']
                
            
            return update_data
        except Exception as e:
            
            self.monitoring.log_task_event(task_name='task_registry', level='error', details={'error': f"Error in prepare_task_result_data_to_db: {str(e)} - input_data: {input_data}"})   
            raise ValueError(f"Error in prepare_task_result_data_to_db: {str(e)} - input_data: {input_data} - update_data: {update_data}")
    


    def handle_db_operation(self, input_data: dict) -> dict:
        """Handle database operations with retroactive task record creation.
        
        This method:
        1. Creates/updates the entity in the relevant table first
        2. Then creates or updates the task record (handling retries)
        3. This solves the chicken-and-egg problem where entities need to exist before task creation
        """
        operation = 'default'
        task_name = 'unknown_task'
        try:
            update_data = self.prepare_task_result_data_to_db(input_data)
            entity_key = input_data['entity_key']
            entity_id = input_data['entity_id']
            if not entity_key:
                raise ValueError(f"Missing entity key in input data: {input_data}")
            if not db_manager.task.is_valid_entity_key(entity_key):
                raise ValueError(f"Invalid entity key: {entity_key} in input data: {input_data}")
            
            operation = entity_key.split('_')[0]
            task_name = f"{operation}_task"
            
            # STEP 1: Create/update the entity first
            if entity_key == 'complainant_id':
                actual_entity_id = db_manager.create_or_update_complainant(update_data)
            elif entity_key == 'grievance_id':
                actual_entity_id = db_manager.create_or_update_grievance(update_data)
            elif entity_key == 'recording_id':
                actual_entity_id = db_manager.create_or_update_recording(update_data)
            elif entity_key == 'transcription_id':
                actual_entity_id = db_manager.create_or_update_transcription(update_data)
            elif entity_key == 'translation_id':
                actual_entity_id = db_manager.create_or_update_translation(update_data)
            else:
                raise ValueError(f"Unsupported entity_key: {entity_key}")
            
            if not actual_entity_id:
                raise ValueError(f"Failed to create/update entity for {entity_key}")
            
            # STEP 2: Handle task record creation/update (including retry scenarios)
            task_id = input_data.get('task_id')  # Get original task ID from input_data
            if task_id:

                if self.retry_count == 0:
                    # FIRST EXECUTION: Create new task record
                    created_task_id = db_manager.task.create_task(
                        task_id=task_id,
                        task_name=task_name,
                        entity_key=entity_key,
                        entity_id=actual_entity_id
                    )
                    
                    if not created_task_id:
                        raise ValueError(f"Failed to create task record even after entity creation")
                    
                # Update task status 
                status_code = SUCCESS if input_data.get('status') == SUCCESS else 'FAILED'
                error_message = input_data.get('error') if status_code == 'FAILED' else None
                
                db_manager.task.update_task(
                    task_id,
                    {
                        'status_code': status_code,
                        'result': json.dumps(input_data.get('value', {})),
                        'error_message': error_message,
                        'retry_count': self.retry_count  # First execution
                    }
                )
                
                self.monitoring.log_task_event(
                    task_name=task_name,
                    details={
                        'entity_key': entity_key,
                        'entity_id': actual_entity_id,
                        'task_id': task_id,
                        'status': status_code,
                        'retry_count': self.retry_count,
                    }
                )
            
            result = {
                'status': SUCCESS,
                'operation': operation,
                'entity_key': entity_key,
                'entity_id': actual_entity_id,
                'task_id': task_id,
                'retry_count': self.retry_count,
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Error in {operation} operation: {str(e)} - input_data: {input_data} - update_data: {update_data}"
            self.monitoring.log_task_event(
                task_name='operation_failed',
                details={
                    'entity_key': input_data.get('entity_key', 'unknown'),
                    'entity_id': input_data.get('id', 'unknown'),
                    'task_id': input_data.get('task_id', 'unknown'),
                    'error': error_msg,
                    'note': 'Database operation failed'
                },
                event_type=FAILED
            )
            return {'status': 'error', 'error': error_msg}

        
        
