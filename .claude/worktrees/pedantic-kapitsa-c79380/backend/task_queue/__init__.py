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
from backend.logger.logger import TaskLogger, LoggingConfig as CentralizedLoggingConfig
from .task_manager import (
    TaskManager,
    DatabaseTaskManager,
    MonitoringConfig
)

# Import all tasks eagerly for Celery registration
from .registered_tasks import *  # This ensures tasks are registered with Celery

# Initialize task registry from TaskManager
task_registry = TaskManager.TASK_REGISTRY

# Export all public symbols
__all__ = [
    'TaskManager',
    'DatabaseTaskManager',
    'MonitoringConfig',
    'CentralizedLoggingConfig',
    'TaskLogger',
    'task_registry',
    'celery_app',
    'QUEUE_LLM',
    'QUEUE_DEFAULT',
    'TASK_TIME_LIMIT',
    'TASK_SOFT_TIME_LIMIT',
    'MAX_RETRIES',
    'RETRY_DELAY',
    'WORKER_CONCURRENCY'
]
