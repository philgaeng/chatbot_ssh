import os
from dataclasses import dataclass
# Queue system configuration
QUEUE_FOLDER = 'task_queue'
QUEUE_LLM = 'llm_queue'
QUEUE_DEFAULT = 'default'

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
if REDIS_PASSWORD:
    REDIS_URL = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}' 
    

# Celery configuration: use environment variables for broker and backend
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')


@dataclass
class TaskConfig:
    time_limit: int = 3600
    soft_time_limit: int = 3300
    max_retries: int = 3
    retry_delay: int = 60

@dataclass
class WorkerConfig:
    prefetch_multiplier: int = 1
    max_tasks_per_child: int = 1000

task_config = TaskConfig()
worker_config = WorkerConfig()