"""
Nepal Chatbot Queue System

This module provides a task queue system for the Nepal Chatbot using Celery.
It supports priority-based task processing with high, medium, and low priority queues.
"""

__version__ = '1.0.0'
__author__ = 'Nepal Chatbot Team'

from typing import List, Dict, Any, Optional
from .config import (
    celery_app,
    QUEUE_LLM,
    QUEUE_DEFAULT,
    TASK_TIME_LIMIT,
    TASK_SOFT_TIME_LIMIT,
    MAX_RETRIES,
    RETRY_DELAY,
    WORKER_CONCURRENCY,
    service_config,
    queue_system_config,
    worker_config,
    resource_config,
    logging_config,
    directory_config,
    health_check_config,
    error_patterns,
    redis_config,
    TASK_REGISTRY,
    register_all_tasks,
    TaskConfig,
    WorkerConfig,
    LoggingConfig,
    ResourceConfig,
    HealthCheckConfig,
    ErrorPatterns,
    RedisConfig,
    QueueSystemConfig,
    ServiceConfig,
    DirectoryConfig
)
from .logger import TaskLogger
from .task_manager import (
    TaskManager,
    DatabaseTaskManager,
    RetryConfig,
    MonitoringConfig
)

# Import task registry and utilities from TaskManager
TASK_TYPE_CONFIG = TaskManager.TASK_TYPE_CONFIG
register_task = TaskManager.register_task
get_task_function = TaskManager.get_task_function
get_task_metadata = TaskManager.get_task_metadata

# Initialize empty task registry
task_registry = {}

# Export all public symbols
__all__: List[str] = [
    # Version info
    '__version__',
    '__author__',
    
    # Configuration
    'celery_app',
    'QUEUE_LLM',
    'QUEUE_DEFAULT',
    'TASK_TIME_LIMIT',
    'TASK_SOFT_TIME_LIMIT',
    'MAX_RETRIES',
    'RETRY_DELAY',
    'WORKER_CONCURRENCY',
    
    # Config objects
    'service_config',
    'queue_system_config',
    'worker_config',
    'resource_config',
    'logging_config',
    'directory_config',
    'health_check_config',
    'error_patterns',
    'redis_config',
    
    # Task Management
    'TaskManager',
    'TaskLogger',
    'DatabaseTaskManager',
    'MonitoringConfig',
    'RetryConfig',
    
    # Task Registry
    'TASK_REGISTRY',
    'TASK_TYPE_CONFIG',
    'register_task',
    'get_task_function',
    'get_task_metadata',
    
    # Registered Tasks (will be populated after registration)
    'process_file_upload_task',
    'process_batch_files_task',
    'send_sms_task',
    'send_email_task',
    'transcribe_audio_file_task',
    'classify_and_summarize_grievance_task',
    'extract_contact_info_task',
    'translate_grievance_to_english_task',
    'store_user_info_task',
    'store_grievance_task',
    'store_transcription_task',
    'update_task_execution_task'
]

# Lazy initialization of tasks
def _get_registered_tasks():
    """Get registered tasks, initializing them if needed"""
    if not task_registry:
        from .registered_tasks import (
            process_file_upload_task,
            process_batch_files_task,
            send_sms_task,
            send_email_task,
            transcribe_audio_file_task,
            classify_and_summarize_grievance_task,
            extract_contact_info_task,
            translate_grievance_to_english_task,
            store_user_info_task,
            store_grievance_task,
            store_transcription_task,
            update_task_execution_task
        )
        
        # Update the task registry
        task_registry.update(register_all_tasks())
        
        # Update globals with registered tasks
        globals().update({
            'process_file_upload_task': process_file_upload_task,
            'process_batch_files_task': process_batch_files_task,
            'send_sms_task': send_sms_task,
            'send_email_task': send_email_task,
            'transcribe_audio_file_task': transcribe_audio_file_task,
            'classify_and_summarize_grievance_task': classify_and_summarize_grievance_task,
            'extract_contact_info_task': extract_contact_info_task,
            'translate_grievance_to_english_task': translate_grievance_to_english_task,
            'store_user_info_task': store_user_info_task,
            'store_grievance_task': store_grievance_task,
            'store_transcription_task': store_transcription_task,
            'update_task_execution_task': update_task_execution_task
        })
    
    return task_registry

# Initialize tasks when first accessed
def __getattr__(name):
    """Lazy load tasks when accessed"""
    if name in __all__:
        _get_registered_tasks()
        return globals().get(name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'") 