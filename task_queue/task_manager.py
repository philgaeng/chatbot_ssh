"""
Task queue management system.

This module provides task management functionality including task registration,
execution tracking, and logging.
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
from .logger import TaskLogger

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
    TASK_CONFIGS = {
        'llm': {
            'max_retries': 3,
            'initial_delay': 2,
            'max_delay': 30,
            'backoff_factor': 2,
            'retry_on': ['ConnectionError', 'TimeoutError', 'RateLimitError']
        },
        'file_processing': {
            'max_retries': 2,
            'initial_delay': 1,
            'max_delay': 10,
            'backoff_factor': 2,
            'retry_on': ['IOError', 'FileNotFoundError']
        },
        'database': {
            'max_retries': 3,
            'initial_delay': 1,
            'max_delay': 20,
            'backoff_factor': 2,
            'retry_on': ['ConnectionError', 'TimeoutError', 'DeadlockError']
        },
        'messaging': {
            'max_retries': 2,
            'initial_delay': 2,
            'max_delay': 15,
            'backoff_factor': 2,
            'retry_on': ['ConnectionError', 'TimeoutError']
        }
    }

class TaskManager:
    # Class-level registry and configuration
    TASK_REGISTRY = {}
    TASK_TYPE_CONFIG = {
        "LLM": {"priority": "high", "queue": "llm_queue", "bind": True},
        "FileUpload": {"priority": "medium", "queue": "default", "bind": False},
        "Messaging": {"priority": "high", "queue": "default", "bind": False},
        "Database": {"priority": "high", "queue": "default", "bind": False},
    }
    monitoring = MonitoringConfig()  # Initialize as class-level attribute
    
    def __init__(self, task=None, emit_websocket=False, service='queue_system'):
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
        
        # Retry tracking
        self.retry_count = 0
        self.last_retry_time = None
        self.retry_config = self._get_retry_config()
        self.retry_history: List[Dict[str, Any]] = []

    def _get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration based on task type"""
        task_type = self._get_task_type()
        return RetryConfig.TASK_CONFIGS.get(task_type, {
            'max_retries': RetryConfig.DEFAULT_MAX_RETRIES,
            'initial_delay': RetryConfig.DEFAULT_INITIAL_DELAY,
            'max_delay': RetryConfig.DEFAULT_MAX_DELAY,
            'backoff_factor': RetryConfig.DEFAULT_BACKOFF_FACTOR,
            'retry_on': ['Exception']
        })

    def _get_task_type(self) -> str:
        """Determine task type from task name"""
        task_name = self.task_name.lower()
        if any(x in task_name for x in ['llm', 'transcribe', 'classify', 'extract', 'translate']):
            return 'llm'
        elif any(x in task_name for x in ['file', 'upload', 'process']):
            return 'file_processing'
        elif any(x in task_name for x in ['db', 'store', 'update']):
            return 'database'
        elif any(x in task_name for x in ['sms', 'email', 'message']):
            return 'messaging'
        return 'default'

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
            
        self.retry_count += 1
        self.last_retry_time = datetime.datetime.utcnow()
        
        # Record retry attempt
        retry_info = {
            'retry_count': self.retry_count,
            'error': str(error),
            'error_type': type(error).__name__,
            'timestamp': self.last_retry_time.isoformat()
        }
        self.retry_history.append(retry_info)
        
        # Update task status
        self.db_task.update_task(
            self.task_id,
            {
                'status_code': 'RETRYING',
                'retry_count': self.retry_count,
                'last_error': str(error),
                'retry_history': self.retry_history
            }
        )
        
        # Log retry attempt
        self.monitoring.log_task_event(
            self.task_name,
            'retrying',
            {
                'entity_type': self.entity_type,
                'entity_id': self.entity_id,
                'retry_count': self.retry_count,
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
                'retry_count': self.retry_count,
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
            self.status = 'COMPLETED'
            self.result = result
            updated = self.db_task.update_task(
                self.task_id,
                {
                    'status_code': 'COMPLETED',
                    'result': result,
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
        """Decorator to register a task in the TASK_REGISTRY and apply Celery task."""
        # Import celery_app here to avoid circular import
        from .config import celery_app
        
        if task_type not in cls.TASK_TYPE_CONFIG:
            error_msg = f"Unknown task_type '{task_type}'. Please add it to TASK_TYPE_CONFIG."
            cls.monitoring.log_task_event('task_registry', 'error', {'error': error_msg})
            raise ValueError(error_msg)
            
        config = cls.TASK_TYPE_CONFIG[task_type]
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if 'service' not in kwargs:
                    kwargs['service'] = config['queue']
                return func(*args, **kwargs)
                
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
            
            # Register with Celery
            celery_task = celery_app.task(
                bind=config.get('bind', False),
                name=func.__name__,
                queue=config['queue']
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
    def __init__(self, task=None, emit_websocket=False):
        super().__init__(task=task, emit_websocket=emit_websocket, service='db_operations')
        
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
        
    def handle_db_operation(self, operation: str, data: dict, file_data: dict) -> dict:
        """Handle database operations with consistent error handling"""
        try:
            entity_type, entity_id, recording_id, execution_id = self.validate_ids(operation, file_data)
            
            # Start task with appropriate entity type and ID
            self.start_task(entity_type, entity_id, stage=f'db_{operation}')
            
            # Perform the database operation
            if operation == 'user_info':
                db_manager.user.update_user(entity_id, data)
            elif operation == 'grievance':
                db_manager.grievance.update_grievance(entity_id, data)
            elif operation == 'transcription':
                db_manager.recording.update_transcription(entity_id, data)
            elif operation == 'task':
                success = db_manager.task.update_task(
                    entity_id,  # Use execution_id as task_id
                    {
                        'status_code': data.get('status_code'),
                        'error_message': data.get('error_message')
                    }
                )
                if not success:
                    raise Exception('Update failed')
            else:
                raise ValueError(f"Unknown database operation: {operation}")
                
            result = {
                'status': 'success',
                'recording_id': recording_id,
                'execution_id': execution_id if operation == 'task' else None
            }
            self.complete_task(result, stage=f'db_{operation}')
            return result
            
        except Exception as e:
            error_msg = f"Error in {operation} operation: {str(e)}"
            self.fail_task(error_msg, stage=f'db_{operation}')
            return {'status': 'error', 'error': error_msg}
