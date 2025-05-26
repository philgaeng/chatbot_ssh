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
    MonitoringConfig
)

# Import task registry and utilities from TaskManager
TASK_TYPE_CONFIG = TaskManager.TASK_TYPE_CONFIG
register_task = TaskManager.register_task
get_task_function = TaskManager.get_task_function
get_task_metadata = TaskManager.get_task_metadata

# Initialize empty task registry
task_registry = {}

# List of all registered tasks
REGISTERED_TASKS = [
    'process_file_upload_task',
    'process_batch_files_task',
    'transcribe_audio_file_task',
    'classify_and_summarize_grievance_task',
    'extract_contact_info_task',
    'translate_grievance_to_english_task',
    'store_result_to_db_task'
]

# Export all public symbols
__all__ = [
    'TaskManager',
    'DatabaseTaskManager',
    'MonitoringConfig',
    'process_file_upload_task',
    'process_batch_files_task',
    'transcribe_audio_file_task',
    'classify_and_summarize_grievance_task',
    'extract_contact_info_task',
    'translate_grievance_to_english_task',
    'store_result_to_db_task',
    'REGISTERED_TASKS',
    'TASK_REGISTRY'
]

# Lazy initialization of tasks
def _get_registered_tasks():
    """Get registered tasks, initializing them if needed"""
    if not task_registry:
        # Import tasks only when needed
        from .registered_tasks import (
            process_file_upload_task,
            process_batch_files_task,
            transcribe_audio_file_task,
            classify_and_summarize_grievance_task,
            extract_contact_info_task,
            translate_grievance_to_english_task,
            store_result_to_db_task,
            store_task_result_to_db_task
        )
        
        # Update the task registry
        task_registry.update({
            'process_file_upload_task': process_file_upload_task,
            'process_batch_files_task': process_batch_files_task,
            'transcribe_audio_file_task': transcribe_audio_file_task,
            'classify_and_summarize_grievance_task': classify_and_summarize_grievance_task,
            'extract_contact_info_task': extract_contact_info_task,
            'translate_grievance_to_english_task': translate_grievance_to_english_task,
            'store_result_to_db_task': store_result_to_db_task,
            'store_task_result_to_db_task': store_task_result_to_db_task
        })
        
        # Update globals with registered tasks
        globals().update(task_registry)
    
    return task_registry

# Initialize tasks when first accessed
def __getattr__(name):
    """Lazy load tasks when accessed"""
    if name in __all__:
        _get_registered_tasks()
        return globals().get(name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'") 