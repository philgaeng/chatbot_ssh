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
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_LOW,
    TASK_TIME_LIMIT,
    TASK_SOFT_TIME_LIMIT,
    MAX_RETRIES,
    RETRY_DELAY,
    WORKER_CONCURRENCY
)
from .tasks import (
    high_priority_task,
    medium_priority_task,
    low_priority_task,
    task_with_retry
)
from .monitoring import (
    log_task_event,
    send_error_notification,
    setup_logger
)
from .workers import (
    start_high_priority_worker,
    start_medium_priority_worker,
    start_low_priority_worker,
    start_all_workers,
    start_flower
)
from .example_tasks import (
    process_voice_recording,
    extract_contact_info,
    process_file_upload,
    generate_file_metadata,
    cleanup_old_files,
    generate_usage_report,
    run_example_tasks
)

# Export all public symbols
__all__: List[str] = [
    # Version info
    '__version__',
    '__author__',
    
    # Configuration
    'celery_app',
    'PRIORITY_HIGH',
    'PRIORITY_MEDIUM',
    'PRIORITY_LOW',
    'TASK_TIME_LIMIT',
    'TASK_SOFT_TIME_LIMIT',
    'MAX_RETRIES',
    'RETRY_DELAY',
    'WORKER_CONCURRENCY',
    
    # Task decorators
    'high_priority_task',
    'medium_priority_task',
    'low_priority_task',
    'task_with_retry',
    
    # Monitoring
    'log_task_event',
    'send_error_notification',
    'setup_logger',
    
    # Worker management
    'start_high_priority_worker',
    'start_medium_priority_worker',
    'start_low_priority_worker',
    'start_all_workers',
    'start_flower',
    
    # Example tasks
    'process_voice_recording',
    'extract_contact_info',
    'process_file_upload',
    'generate_file_metadata',
    'cleanup_old_files',
    'generate_usage_report',
    'run_example_tasks'
] 