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
    return {"result": "success"}

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
from actions_server.db_manager import db_manager
from actions_server.websocket_utils import emit_status_update
from typing import Dict, Any, Optional, List, Tuple, Callable
import time
import random
import logging
import json
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
import functools
from logger.logger import TaskLogger
from actions_server.constants import FIELD_MAPPING
from .celery_app import celery_app  # Safe to import at module level now

# Task type names (single source of truth)
TASK_TYPE_LLM = "LLM"
TASK_TYPE_FILEUPLOAD = "FileUpload"
TASK_TYPE_MESSAGING = "Messaging"
TASK_TYPE_DATABASE = "Database"
TASK_TYPE_DEFAULT = "Default"

TASK_CONFIG = {
    TASK_TYPE_LLM: {'service': 'llm_processor', 
        'queue': {"priority": "high", "queue": "llm_queue", "bind": True},
        'retries': {
            'max_retries': 3,
            'initial_delay': 2,
            'max_delay': 30,
            'backoff_factor': 2,
            'retry_on': ['ConnectionError', 'TimeoutError', 'RateLimitError'],
            'bind': True
        }
    },
    TASK_TYPE_FILEUPLOAD: {'service': 'queue_system',
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

class MonitoringConfig:
    """Configuration for task monitoring and logging"""
    # Logging configuration
    LOG_DIR = "logs"
    LOG_MAX_SIZE_MB = 100
    LOG_MAX_FILES = 5
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = 'INFO'
    
    # Metrics configuration
    METRICS_FILE = 'metrics.json'
    
    # Default services to monitor
    DEFAULT_SERVICES = {
        'llm_processor': 'llm_processor.log',
        'queue_system': 'queue_system.log',
        'db_operations': 'db_operations.log',
        'db_migrations': 'db_migrations.log',
        'db_backup': 'db_backup.log',
        'ticket_processor': 'ticket_processor.log',
        'ticket_notifications': 'ticket_notifications.log',
        'ticket_assignments': 'ticket_assignments.log'
    }
    
    def __init__(self):
        # Initialize logger registry
        self.logger_registry = {}
        
        # Initialize default loggers
        for service in self.DEFAULT_SERVICES:
            self.register_logger(service)
    
    def register_logger(self, service_name: str) -> TaskLogger:
        """Register a new logger for a service"""
        if service_name not in self.logger_registry:
            self.logger_registry[service_name] = TaskLogger(service_name)
        return self.logger_registry[service_name]
    
    def log_task_event(self, task_name: str, event_type: str, details: Optional[Dict[str, Any]] = None, 
                      service: str = 'queue_system') -> None:
        """Log task events with consistent formatting"""
        # Get or create logger for the service
        logger = self.logger_registry.get(service, self.register_logger(service))
        
        # Log the event
        logger.log_task_event(task_name, event_type, details)

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
    
    def __init__(self, task=None, task_type='Default', emit_websocket=False, service='queue_system'):
        self.task = task
        self.emit_websocket = emit_websocket
        self.service = service  # Service name for logging
        self.task_id = None
        self.entity_type = None
        self.entity_id = None
        self.celery_task_id = None
        self.start_time = None
        self.end_time = None
        self.status = None
        self.result = None
        self.error = None
        self.db_task = db_manager.task
        self.task_name = task.name if task else 'unknown_task'
        self.task_type = task_type
        
        # Retry tracking
        self.retry_count = 0
        self.last_retry_time = None
        self.retry_config = self._get_retry_config()
        self.retry_history: List[Dict[str, Any]] = []

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
        if self.retry_count >= self.retry_config['max_retries']:
            return False
            
        error_type = type(error).__name__
        return error_type in self.retry_config['retry_on']

    def _calculate_retry_delay(self) -> float:
        """Calculate delay for next retry using exponential backoff with jitter"""
        if self.retry_count == 0:
            return self.retry_config['initial_delay']
            
        delay = min(
            self.retry_config['initial_delay'] * (self.retry_config['backoff_factor'] ** self.retry_count),
            self.retry_config['max_delay']
        )
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter

    def _emit_status(self, entity_id, status, data):
        if self.emit_websocket:
            emit_status_update(entity_id, status, data)

    def retry_task(self, error: Exception) -> Tuple[bool, Optional[float]]:
        """
        Handle task retry logic
        
        Args:
            error: The exception that caused the failure
            
        Returns:
            Tuple of (should_retry, delay_seconds)
        """
        if not self._should_retry(error):
            return False, None
            
        # Get current retry count from database using simpler query
        task_info = self.db_task.get_task_status(self.task_id)
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
                'status_code': 'RETRYING',
                'retry_count': new_retry_count,
                'error_message': str(error),
                'retry_history': retry_history_json
            }
        )
        
        if not updated:
            return False, None
            
        # Update instance variables to match database state
        self.retry_count = new_retry_count
        self.retry_history = retry_history
        self.last_retry_time = datetime.datetime.utcnow()
        
        # Log retry attempt
        self.monitoring.log_task_event(
            self.task_name,
            'retrying',
            {
                'entity_type': self.entity_type,
                'entity_id': self.entity_id,
                'retry_count': new_retry_count,
                'error': str(error),
                'next_retry_delay': self._calculate_retry_delay()
            },
            service=self.service
        )
        
        # Emit retry status
        self._emit_status(
            self.entity_id,
            'retrying',
            {
                'retry_count': new_retry_count,
                'error': str(error),
                'next_retry_delay': self._calculate_retry_delay()
            }
        )
        
        return True, self._calculate_retry_delay()

    def start_task(self, entity_type: str, entity_id: str, stage: str = None, extra_data=None) -> bool:
        """Start a new task and record it in the database. Optionally emit WebSocket status."""
        try:
            self.entity_type = entity_type
            self.entity_id = entity_id
            self.start_time = datetime.datetime.utcnow()
            self.status = 'PENDING'
            
            # Get Celery's task ID
            celery_task_id = getattr(self.task.request, 'id', None)
            if not celery_task_id:
                raise ValueError("No Celery task ID available")
            
            # Create task record using Celery's task ID
            self.task_id = self.db_task.create_task(
                task_id=celery_task_id,
                task_name=self.task_name,
                entity_type=entity_type,
                entity_id=entity_id
            )
            
            if not self.task_id:
                raise ValueError("Failed to create task record")
            
            # Log task start
            self.monitoring.log_task_event(
                self.task_name,
                'started',
                {
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'stage': stage,
                    'task_id': self.task_id,
                    **(extra_data or {})
                },
                service=self.service
            )
            
            if stage:
                self._emit_status(entity_id, 'processing', {'stage': stage, **(extra_data or {})})
            return True
        except Exception as e:
            self.error = str(e)
            self.monitoring.log_task_event(
                self.task_name,
                'failed',
                {
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'stage': stage,
                    'error': str(e),
                    **(extra_data or {})
                },
                service=self.service
            )
            return False

    def complete_task(self, result=None, stage: str = None) -> bool:
        """Mark task as complete and record the result. Optionally emit WebSocket status."""
        try:
            self.end_time = datetime.datetime.utcnow()
            self.status = 'SUCCESS'
            self.result = result
            updated = self.db_task.update_task(
                self.task_id,
                {
                    'status_code': 'SUCCESS',
                    'result': json.dumps(result),
                    'retry_count': self.retry_count,
                    'retry_history': self.retry_history
                }
            )
            
            # Log task completion
            self.monitoring.log_task_event(
                self.task_name,
                'completed',
                {
                    'entity_type': self.entity_type,
                    'entity_id': self.entity_id,
                    'stage': stage,
                    'task_id': self.task_id,
                    'result': result,
                    'retry_count': self.retry_count
                },
                service=self.service
            )
            
            if stage:
                self._emit_status(self.entity_id, 'completed', {'stage': stage, 'result': result})
            return updated
        except Exception as e:
            self.error = str(e)
            self.monitoring.log_task_event(
                self.task_name,
                'failed',
                {
                    'entity_type': self.entity_type,
                    'entity_id': self.entity_id,
                    'stage': stage,
                    'error': str(e)
                },
                service=self.service
            )
            return False

    def fail_task(self, error: str, stage: str = None) -> bool:
        """Mark task as failed and record the error. Optionally emit WebSocket status."""
        try:
            self.end_time = datetime.datetime.utcnow()
            self.status = 'FAILED'
            self.error = error
            updated = self.db_task.update_task(
                self.task_id,
                {
                    'status_code': 'FAILED',
                    'error_message': error,
                    'retry_count': self.retry_count,
                    'retry_history': self.retry_history
                }
            )
            
            # Log task failure
            self.monitoring.log_task_event(
                self.task_name,
                'failed',
                {
                    'entity_type': self.entity_type,
                    'entity_id': self.entity_id,
                    'stage': stage,
                    'error': error,
                    'retry_count': self.retry_count
                },
                service=self.service
            )
            
            if stage:
                self._emit_status(self.entity_id, 'failed', {'stage': stage, 'error': str(error)})
            return updated
        except Exception as e:
            self.error = str(e)
            self.monitoring.log_task_event(
                self.task_name,
                'failed',
                {
                    'entity_type': self.entity_type,
                    'entity_id': self.entity_id,
                    'stage': stage,
                    'error': f"Failed to record failure: {str(e)}"
                },
                service=self.service
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
            cls.monitoring.log_task_event('task_registry', 'error', {'error': error_msg})
            raise ValueError(error_msg)
            
        config = TASK_CONFIG[task_type]  # Get full config from TASK_CONFIG
        
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                # Automatically set service from TASK_CONFIG - no parameter needed
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
                'priority': config['priority'],
                'type': task_type,
                'queue': config['queue'],
                'task': wrapper
            }
            
            # Log task registration
            cls.monitoring.log_task_event(
                'task_registry',
                'registered',
                {
                    'task_name': func.__name__,
                    'task_type': task_type,
                    'queue': config['queue'],
                    'priority': config['priority']
                }
            )
            
            # Register with Celery with proper binding
            celery_task = celery_app.task(
                bind=True,  # Always bind the task
                name=func.__name__,
                queue=config['queue']['queue']
            )(wrapper)
            
            cls.TASK_REGISTRY[func.__name__]['celery_task'] = celery_task
            return celery_task
        return decorator
    
    @classmethod
    def get_task_function(cls, task_name: str) -> Optional[Callable]:
        """Get a task function from the registry by name."""
        task_info = cls.TASK_REGISTRY.get(task_name)
        if not task_info:
            cls.monitoring.log_task_event('task_registry', 'error', 
                {'error': f"Task '{task_name}' not found in registry"})
        return task_info['task'] if task_info else None
    
    @classmethod
    def get_task_metadata(cls, task_name: str):
        """Get task metadata from the registry by name"""
        task_info = cls.TASK_REGISTRY.get(task_name)
        if task_info:
            return {k: v for k, v in task_info.items() if k != 'task'}
        error_msg = f"Task '{task_name}' not found in registry"
        cls.monitoring.log_task_event('task_registry', 'error', {'error': error_msg})
        raise KeyError(error_msg)

class DatabaseTaskManager(TaskManager):
    """
    Specialized TaskManager for database operations.
    Handles database-specific task lifecycle and error handling.
    """
    def __init__(self, task=None, task_type='Database', emit_websocket=False, service='db_operations'):
        super().__init__(task=task, task_type=task_type, emit_websocket=emit_websocket, service=service)
        
    def validate_ids(self, operation: str, file_data: dict) -> tuple:
        """Validate required IDs in file_data"""
        grievance_id = file_data.get('grievance_id')
        recording_id = file_data.get('task_id')
        execution_id = file_data.get('execution_id')
        
        if operation in ['transcription']:
            if not grievance_id or not recording_id:
                error_msg = "Missing grievance_id or recording_id in file_data"
                self.fail_task(error_msg)
                raise ValueError(error_msg)
            return 'grievance', grievance_id, recording_id, execution_id
        elif operation in ['user_info', 'grievance']:
            if not grievance_id:
                error_msg = "Missing grievance_id in file_data"
                self.fail_task(error_msg)
                raise ValueError(error_msg)
            return 'grievance', grievance_id, recording_id, execution_id
        elif operation in ['task']:
            if not execution_id:
                error_msg = "Missing execution_id in file_data"
                self.fail_task(error_msg)
                raise ValueError(error_msg)
            return 'task', execution_id, recording_id, execution_id
            
        return None, None, None, None
        
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
            required_fields = ['status',  'field_name', 'value', 'entity_key', 'id']
            missing_fields = [field for field in required_fields if field not in input_data]
            if missing_fields:
                raise ValueError(f"Task result missing required fields: {missing_fields}")
                
            entity_key = input_data['entity_key']
            entity_id = input_data['id']
            # Start with file_data as base
            update_data = dict()
            
            # Add entity ID from result
            update_data[entity_key] = entity_id
            
            
            
            # Add result data based on operation type
            if entity_key == 'transcription_id':
                update_data.update({
                    'automated_transcript': input_data['value'],
                    'language_code': input_data.get('language_code', 'ne')
                })
                
            elif entity_key == 'translation_id':
                update_data.update({
                    'grievance_details_en': input_data['value'],
                    'translation_method': input_data.get('method', 'auto'),
                    'confidence_score': input_data.get('confidence_score')
                })
                
            else:
                value_fields = self._extract_value_and_field_from_input_data(input_data)
                update_data.update(value_fields)

            if 'language_code' in input_data:
                    update_data['language_code'] = input_data['language_code']
                
            return update_data
        except Exception as e:
            self.monitoring.log_task_event('task_registry', 'error', {'error': f"Error in prepare_task_result_data_to_db: {str(e)}"})   
            raise ValueError(f"Error in prepare_task_result_data_to_db: {str(e)}")
        
    def _extract_value_and_field_from_input_data(self, input_data: dict, field_mapping: dict = FIELD_MAPPING) -> tuple:
        """Extract value and field from input data"""
       # Map field to user data fields
        
        update_data = dict()
        
        value = input_data['value']
        field_name = input_data['field_name']
        if isinstance(value, dict):
            for key, val in value.items():
                if key in field_name:
                    if key in field_mapping.keys(): #future proofing for fields not aligned between task and database
                        update_data[field_mapping[key]] = val
                    else:
                        update_data[key] = val
        else:
            update_data[field_name] = value
        
        return update_data

    def handle_db_operation(self, input_data: dict) -> dict:
        """Handle database operations with consistent error handling"""
        try:
            update_data = self.prepare_task_result_data_to_db(input_data)
            entity_type = input_data['entity_key']
            entity_id = input_data['id']
            operation = entity_type.split('_')[0]
            
            # Start task with appropriate entity type and ID
            self.start_task(entity_type, entity_id, stage=f'db_{operation}')
            
            # Perform the database operation
            if operation == 'user':
                db_result = ('user_id', db_manager.user.create_or_update_user(update_data))
            elif operation == 'grievance':
                db_result = ('grievance_id', db_manager.grievance.create_or_update_grievance(update_data))
            elif operation == 'recording':
                db_result = ('recording_id', db_manager.recording.create_or_update_recording(update_data))
            elif operation == 'transcription':
                db_result = ('transcription_id', db_manager.recording.create_or_update_transcription(update_data))
            elif operation == 'translation':
                db_result = ('translation_id', db_manager.translation.create_or_update_translation(update_data))
            else:
                raise ValueError(f"Unknown database operation: {operation}")
            
            result = {
                'status': 'SUCCESS',
                'operation': operation,
                'entity_key': db_result[0],
                'entity_id': db_result[1],
            }
            self.complete_task(result, stage=f'db_{operation}')
            return result
            
        except Exception as e:
            error_msg = f"Error in {operation} operation: {str(e)}"
            self.fail_task(error_msg, stage=f'db_{operation}')
            return {'status': 'error', 'error': error_msg}


    def handle_task_db_operations(self,task_result: dict) -> dict:
        """Handle database operations with consistent error handling"""
        try:
            execution_id = task_result['execution_id']
            self.start_task('task', execution_id, stage='db_task')
            result = {'status_code': task_result.get('status_code')
                      }
            if task_result.get('error_message'):
                result['error_message'] = task_result.get('error_message')
                result['status_code'] = 'FAILED'
            success = db_manager.task.update_task(
                execution_id,  # Use execution_id as task_id
                result
            )
            result['entity_key'] = 'execution_id'
            result['entity_id'] = execution_id
            if not success:
                raise Exception('Update failed')
            self.complete_task(result, stage='db_task')
            return result
            
        except Exception as e:
            error_msg = f"Error in db_task operation: {str(e)}"
            self.fail_task(error_msg, stage='db_task')
            return {'status': 'error', 'error': error_msg}

        
        
