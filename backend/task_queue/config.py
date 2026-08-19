# SPDX-License-Identifier: Apache-2.0

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

import os
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache
from .settings import *  # Import all Celery/queue constants and env variables from settings.py
from .celery_app import celery_app  # Import celery_app from celery_app.py
from .registered_tasks import *  # Eagerly import all tasks for Celery registration

# Configure logging early
logging.basicConfig(level='INFO')
logger = logging.getLogger(__name__)

# Import settings classes with aliases to avoid conflicts
from .settings import TaskConfig as SettingsTaskConfig, WorkerConfig as SettingsWorkerConfig

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
    redis_host: str = REDIS_HOST
    redis_port: int = REDIS_PORT
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
            
        password = os.getenv('REDIS_PASSWORD') or None
        if password is not None:
            password = password.strip() or None
        if not password:
            logger.warning("REDIS_PASSWORD not set in environment variables (using Redis without auth)")
        
        return cls(
            host=host,
            port=port,
            db=db,
            password=password,
            require_password=bool(password),  # require password only when one is configured
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
            
        if self.host in ('localhost', '127.0.0.1') and os.getenv('APP_ENV') == 'production':
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

# ── The shell-config generator was deleted 2026-08-19 (D-47) ─────────────────
#
# `generate_shell_config()` / `update_shell_config()` used to live here, and the module called the
# latter **at import time** — writing `backend/scripts/task_queue/config.sh`, a file tracked in
# git, from whatever environment happened to be importing. In the compose stack that wrote
# `REDIS_HOST="redis"`; on the host, `"localhost"`. So the working tree went dirty on its own after
# every test run, and the committed value recorded whichever environment imported last.
#
# It was safe to delete outright, not merely redirect: **nothing sourced the file.** Its consumers
# — the legacy systemd/shell runtime scripts — were removed in `28508aec` ("remove legacy runtime
# scripts and align docs to docker workflow") when the stack moved to Docker, and the generator
# plus its output were left behind. Every commit touching `config.sh` since then has been an
# accidental sweep: its entire history is `REDIS_HOST` flipping between the two values, carried
# into three unrelated commits in this sprint alone.
#
# ⚠ If a shell runtime ever comes back, generate it to an **untracked** path. The queue's settings
# come from the environment (`REDIS_HOST`, `REDIS_PORT`, …) and from the dataclasses above; a
# generated artefact belongs in the build output, never in the source tree.

# Load Redis configuration
redis_config = RedisConfig.from_env()
redis_config.validate()

# Build Redis URLs
redis_url = f'redis://{redis_config.host}:{redis_config.port}/{redis_config.db}'
if redis_config.password:
    redis_url = f'redis://:{redis_config.password}@{redis_config.host}:{redis_config.port}/{redis_config.db}'

# Initialize TASK_REGISTRY as empty
TASK_REGISTRY = {}
