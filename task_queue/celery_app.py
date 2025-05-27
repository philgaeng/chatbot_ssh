from celery import Celery
from kombu import Exchange, Queue
from .settings import (
    QUEUE_FOLDER,
    redis_url,
    QUEUE_LLM,
    QUEUE_DEFAULT,
    task_config,
    worker_config
)

celery_app = Celery(QUEUE_FOLDER)

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
    task_time_limit=task_config.time_limit,
    task_soft_time_limit=task_config.soft_time_limit,
    task_default_retry_delay=task_config.retry_delay,
    task_max_retries=task_config.max_retries,
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
    )
)


