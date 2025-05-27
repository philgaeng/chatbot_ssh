import os
from dataclasses import dataclass
# Queue system configuration
QUEUE_FOLDER = 'task_queue'
QUEUE_LLM = 'llm_queue'
QUEUE_DEFAULT = 'default'

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', '6379'))
redis_db = int(os.getenv('REDIS_DB', '0'))
redis_password = os.getenv('REDIS_PASSWORD')
redis_url = f'redis://{redis_host}:{redis_port}/{redis_db}'
if redis_password:
    redis_url = f'redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}' 
    

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