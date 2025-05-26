"""
Configuration settings for the task queue system.

This module handles all configuration settings for the task queue system, including:
- Redis connection settings (environment-specific)
- Celery task settings (application defaults)
- Worker settings (application defaults)
- Logging settings (application defaults)

Only sensitive and environment-specific settings should be set via environment variables.
All other settings use sensible defaults defined in the code.
"""

from celery import Celery
from kombu import Exchange, Queue
import os
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache

# Queue system configuration
QUEUE_FOLDER = 'task_queue'  # Name of the queue system folder

# Task configuration constants
TASK_TIME_LIMIT = 3600  # 1 hour
TASK_SOFT_TIME_LIMIT = 3300  # 55 minutes
MAX_RETRIES = 3
RETRY_DELAY = 60  # 1 minute

# Worker configuration
WORKER_CONCURRENCY = {
    'llm_queue': 6,  # LLM tasks are light-weight and can handle more concurrency since they are API calls
    'default': 4     # Default queue for other tasks
}

@dataclass
class ServiceConfig:
    """Service configuration settings"""
    name: str = "task_queue"
    user: str = "ubuntu"
    group: str = "ubuntu"

@dataclass
class QueueSystemConfig:
    """Queue system configuration settings"""
    redis_host: str = os.getenv('REDIS_HOST', 'localhost')
    redis_port: int = int(os.getenv('REDIS_PORT', '6379'))
    flower_port: int = int(os.getenv('FLOWER_PORT', '5555'))

@dataclass
class WorkerConfig:
    """Worker configuration settings"""
    start_timeout: int = 30
    restart_attempts: int = 3
    restart_delay: int = 5
    health_check_interval: int = 30
    prefetch_multiplier: int = 1
    max_tasks_per_child: int = 1000
    log_level: str = 'INFO'
    log_file: str = 'worker.log'
    pid_file: str = 'worker.pid'

@dataclass
class ResourceConfig:
    """Resource limit configuration settings"""
    max_memory_percent: int = 80
    max_cpu_percent: int = 90
    max_disk_percent: int = 90
    max_worker_memory_mb: int = 1000

@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    dir: str = "logs"
    max_size_mb: int = 100
    max_files: int = 5
    format: str = "json"  # or "text"
    level: str = 'INFO'
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    def __post_init__(self):
        """Create log directory if it doesn't exist"""
        Path(self.dir).mkdir(exist_ok=True)

@dataclass
class DirectoryConfig:
    """Directory configuration settings"""
    script_dir: Path = Path(__file__).parent
    project_root: Path = Path(__file__).parent.parent
    pid_dir: Path = Path("/tmp/task_queue_workers")

@dataclass
class HealthCheckConfig:
    """Health check configuration settings"""
    timeout: int = 30
    retries: int = 3
    delay: int = 5

@dataclass
class ErrorPatterns:
    """Error patterns to monitor"""
    patterns: List[str] = None
    
    def __post_init__(self):
        if self.patterns is None:
            self.patterns = [
                "Connection refused",
                "Broken pipe",
                "WorkerLostError",
                "MemoryError",
                "TimeoutError",
                "ConnectionError",
                "AuthenticationError",
                "ResourceExhausted",
                "TaskRevokedError",
                "TaskTimeoutError",
                "MaxRetriesExceededError"
            ]

@dataclass
class RedisConfig:
    """Redis connection configuration"""
    host: str
    port: int
    db: int
    password: Optional[str] = None
    require_password: bool = True
    
    @classmethod
    def from_env(cls) -> 'RedisConfig':
        """Create Redis config from environment variables"""
        host = os.getenv('REDIS_HOST')
        if not host:
            raise ValueError("REDIS_HOST environment variable is required")
            
        try:
            port = int(os.getenv('REDIS_PORT', '6379'))
        except ValueError:
            raise ValueError("REDIS_PORT must be a valid integer")
            
        try:
            db = int(os.getenv('REDIS_DB', '0'))
        except ValueError:
            raise ValueError("REDIS_DB must be a valid integer")
            
        password = os.getenv('REDIS_PASSWORD')
        if not password:
            logger.warning("REDIS_PASSWORD not set in environment variables")
        
        return cls(
            host=host,
            port=port,
            db=db,
            password=password,
            require_password=True
        )
    
    def validate(self) -> None:
        """Validate Redis configuration"""
        if not (1024 <= self.port <= 65535):
            raise ValueError(f"Invalid Redis port {self.port}")
            
        if not (0 <= self.db <= 15):
            raise ValueError(f"Invalid Redis database {self.db}")
            
        if self.require_password and not self.password:
            raise ValueError("Redis password is required but not provided")
            
        if self.password is not None and not self.password:
            raise ValueError("Redis password cannot be empty")
            
        if not self.host:
            raise ValueError("Redis host cannot be empty")
            
        if self.host in ('localhost', '127.0.0.1') and os.getenv('ENVIRONMENT') == 'production':
            logger.warning("Using localhost Redis in production environment")

@dataclass
class TaskConfig:
    """Task execution configuration"""
    time_limit: int = 3600  # 1 hour
    soft_time_limit: int = 3300  # 55 minutes
    max_retries: int = 3
    retry_delay: int = 60  # 1 minute

# Initialize all configuration objects
service_config = ServiceConfig()
queue_system_config = QueueSystemConfig()
worker_config = WorkerConfig()
resource_config = ResourceConfig()
logging_config = LoggingConfig()
directory_config = DirectoryConfig()
health_check_config = HealthCheckConfig()
error_patterns = ErrorPatterns()

# Configure logging
logging.basicConfig(level=logging_config.level)
logger = logging.getLogger(__name__)

def generate_shell_config() -> str:
    """
    Generate shell configuration from Python config.
    
    Returns:
        str: Shell configuration as a string
    """
    # Convert all config objects to dictionaries
    config_dict = {
        'SERVICE_NAME': service_config.name,
        'SERVICE_USER': service_config.user,
        'SERVICE_GROUP': service_config.group,
        'QUEUE_FOLDER': QUEUE_FOLDER,
        'REDIS_HOST': queue_system_config.redis_host,
        'REDIS_PORT': queue_system_config.redis_port,
        'FLOWER_PORT': queue_system_config.flower_port,
        'WORKER_START_TIMEOUT': worker_config.start_timeout,
        'WORKER_RESTART_ATTEMPTS': worker_config.restart_attempts,
        'WORKER_RESTART_DELAY': worker_config.restart_delay,
        'WORKER_HEALTH_CHECK_INTERVAL': worker_config.health_check_interval,
        'MAX_MEMORY_PERCENT': resource_config.max_memory_percent,
        'MAX_CPU_PERCENT': resource_config.max_cpu_percent,
        'MAX_DISK_PERCENT': resource_config.max_disk_percent,
        'MAX_WORKER_MEMORY_MB': resource_config.max_worker_memory_mb,
        'LOG_DIR': logging_config.dir,
        'LOG_MAX_SIZE_MB': logging_config.max_size_mb,
        'LOG_MAX_FILES': logging_config.max_files,
        'LOG_FORMAT': logging_config.format,
        'HEALTH_CHECK_TIMEOUT': health_check_config.timeout,
        'HEALTH_CHECK_RETRIES': health_check_config.retries,
        'HEALTH_CHECK_DELAY': health_check_config.delay,
    }
    
    # Generate shell script content
    shell_script = [
        '#!/bin/bash',
        '',
        '# This file is auto-generated from task_queue/config.py',
        '# Do not edit this file directly',
        '',
    ]
    
    # Add variable declarations
    for key, value in config_dict.items():
        if isinstance(value, str):
            shell_script.append(f'{key}="{value}"')
        else:
            shell_script.append(f'{key}={value}')
    
    # Add error patterns array
    shell_script.extend([
        '',
        '# Error Patterns to Monitor',
        'ERROR_PATTERNS=(',
        *[f'    "{pattern}"' for pattern in error_patterns.patterns],
        ')',
        '',
        '# Export all variables',
        'export ' + ' '.join(config_dict.keys()),
        'export ERROR_PATTERNS',
    ])
    
    return '\n'.join(shell_script)

def update_shell_config() -> None:
    """Update the shell configuration file"""
    shell_config = generate_shell_config()
    config_path = Path(__file__).parent.parent / 'scripts' / 'task_queue' / 'config.sh'
    
    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write configuration
    config_path.write_text(shell_config)
    config_path.chmod(0o755)  # Make executable
    
    logger.info(f"Updated auto-generated shell configuration at {config_path}")

# Load Redis configuration
redis_config = RedisConfig.from_env()
redis_config.validate()

# Build Redis URLs
redis_url = f'redis://{redis_config.host}:{redis_config.port}/{redis_config.db}'
if redis_config.password:
    redis_url = f'redis://:{redis_config.password}@{redis_config.host}:{redis_config.port}/{redis_config.db}'

# Queue names (these are fixed constants, not configurable)
QUEUE_LLM = 'llm_queue'
QUEUE_DEFAULT = 'default'

# Create Celery instance
celery_app = Celery(QUEUE_FOLDER)

# Configure Celery
celery_app.conf.update(
    # Broker and backend
    broker_url=redis_url,
    result_backend=redis_url,
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Time and timezone
    timezone='UTC',
    enable_utc=True,
    
    # Task settings
    task_track_started=True,
    task_time_limit=TaskConfig().time_limit,
    task_soft_time_limit=TaskConfig().soft_time_limit,
    task_default_retry_delay=TaskConfig().retry_delay,
    task_max_retries=TaskConfig().max_retries,
    
    # Worker settings
    worker_prefetch_multiplier=worker_config.prefetch_multiplier,
    worker_max_tasks_per_child=worker_config.max_tasks_per_child,
    
    # Task acknowledgment
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Default queue settings
    task_default_queue=QUEUE_DEFAULT,
    task_queues=(
        Queue(QUEUE_LLM, Exchange(QUEUE_LLM), routing_key=QUEUE_LLM),
        Queue(QUEUE_DEFAULT, Exchange(QUEUE_DEFAULT), routing_key=QUEUE_DEFAULT),
    ),
    
    # Task routing
    task_routes={
        'task_queue.registered_tasks.*_llm_*': {'queue': QUEUE_LLM},
        'task_queue.registered_tasks.*_transcribe_*': {'queue': QUEUE_LLM},
        'task_queue.registered_tasks.*_classify_*': {'queue': QUEUE_LLM},
        'task_queue.registered_tasks.*_extract_*': {'queue': QUEUE_LLM},
        'task_queue.registered_tasks.*_translate_*': {'queue': QUEUE_LLM},
    },
)

# Initialize TASK_REGISTRY as empty
TASK_REGISTRY = {}

def register_all_tasks():
    """Register all tasks with Celery after all modules are loaded"""
    from .task_manager import TaskManager
    from .registered_tasks import (
        process_file_upload_task,
        process_batch_files_task,
        send_sms_task,
        send_email_task,
        transcribe_audio_file_task,
        classify_and_summarize_grievance_task,
        extract_contact_info_task,
        translate_grievance_to_english_task,
        store_result_to_db_task,
        store_task_result_to_db_task
    )
    return TaskManager.TASK_REGISTRY

# Update shell config when this module is imported
update_shell_config() 