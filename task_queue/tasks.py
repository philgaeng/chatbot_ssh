"""
Task decorators and utilities for the queue system.
"""

from typing import Dict, Any, Optional, Callable, TypeVar, cast
from functools import wraps
import time
import random
from .config import (
    celery_app,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_LOW,
    MAX_RETRIES,
    RETRY_DELAY,
    TASK_TIME_LIMIT,
    TASK_SOFT_TIME_LIMIT
)
from .monitoring import log_task_event, send_error_notification, metrics_collector

# Type variable for task functions
T = TypeVar('T')

def task_with_retry(max_retries: int = MAX_RETRIES, retry_delay: int = RETRY_DELAY,
                   exponential_backoff: bool = True) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add retry logic to tasks with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries in seconds
        exponential_backoff: Whether to use exponential backoff
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retries = 0
            last_error: Optional[Exception] = None
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    retries += 1
                    
                    if retries == max_retries:
                        # Record failure metric
                        metrics_collector.record_task_metric(
                            func.__name__,
                            'retry_failures',
                            metrics_collector.get_task_metrics(func.__name__).get('retry_failures', 0) + 1
                        )
                        send_error_notification(func.__name__, str(e))
                        raise
                    
                    # Calculate delay with jitter
                    if exponential_backoff:
                        delay = retry_delay * (2 ** (retries - 1))
                    else:
                        delay = retry_delay
                    
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, 0.1 * delay)
                    time.sleep(delay + jitter)
                    
                    # Log retry attempt
                    log_task_event(
                        func.__name__,
                        'retry',
                        {
                            'attempt': retries,
                            'max_retries': max_retries,
                            'delay': delay,
                            'error': str(e)
                        }
                    )
            
            # This should never be reached due to the raise in the loop
            raise last_error or Exception("Unexpected error in retry logic")
            
        return cast(Callable[..., T], wrapper)
    return decorator

def determine_service(func_name: str) -> str:
    """
    Determine the appropriate service based on function name
    
    Args:
        func_name: Name of the function
        
    Returns:
        Service name for logging
    """
    func_name = func_name.lower()
    
    # Processing services
    if 'voice' in func_name:
        return 'voice_processor'
    elif 'file' in func_name:
        return 'file_processor'
    elif 'contact' in func_name:
        return 'contact_processor'
    
    # Database services
    elif 'db_migration' in func_name or 'migration' in func_name:
        return 'db_migrations'
    elif 'db_backup' in func_name or 'backup' in func_name:
        return 'db_backup'
    elif 'db_' in func_name or 'database' in func_name:
        return 'db_operations'
    
    # Ticketing services
    elif 'ticket_notification' in func_name or 'notify' in func_name:
        return 'ticket_notifications'
    elif 'ticket_assignment' in func_name or 'assign' in func_name:
        return 'ticket_assignments'
    elif 'ticket_' in func_name or 'ticket' in func_name:
        return 'ticket_processor'
    
    # Default
    return 'queue_system'

def high_priority_task(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for high priority tasks
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function with high priority
    """
    @celery_app.task(bind=True, priority=PRIORITY_HIGH)
    @task_with_retry()
    @wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
        service = determine_service(func.__name__)
        start_time = time.time()
        
        log_task_event(func.__name__, 'started', {'priority': 'high'}, service=service)
        try:
            result = func(*args, **kwargs)
            
            # Record success metrics
            duration = time.time() - start_time
            metrics_collector.record_task_metric(func.__name__, 'last_duration', duration)
            metrics_collector.record_task_metric(func.__name__, 'total_tasks',
                metrics_collector.get_task_metrics(func.__name__).get('total_tasks', 0) + 1)
            
            log_task_event(func.__name__, 'completed', {
                'priority': 'high',
                'duration': duration
            }, service=service)
            
            return result
        except Exception as e:
            # Record failure metrics
            metrics_collector.record_task_metric(func.__name__, 'failed_tasks',
                metrics_collector.get_task_metrics(func.__name__).get('failed_tasks', 0) + 1)
            
            log_task_event(func.__name__, 'failed', {
                'priority': 'high',
                'error': str(e)
            }, service=service)
            raise
    return cast(Callable[..., T], wrapper)

def medium_priority_task(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for medium priority tasks
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function with medium priority
    """
    @celery_app.task(bind=True, priority=PRIORITY_MEDIUM)
    @task_with_retry()
    @wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
        service = determine_service(func.__name__)
        start_time = time.time()
        
        log_task_event(func.__name__, 'started', {'priority': 'medium'}, service=service)
        try:
            result = func(*args, **kwargs)
            
            # Record success metrics
            duration = time.time() - start_time
            metrics_collector.record_task_metric(func.__name__, 'last_duration', duration)
            metrics_collector.record_task_metric(func.__name__, 'total_tasks',
                metrics_collector.get_task_metrics(func.__name__).get('total_tasks', 0) + 1)
            
            log_task_event(func.__name__, 'completed', {
                'priority': 'medium',
                'duration': duration
            }, service=service)
            
            return result
        except Exception as e:
            # Record failure metrics
            metrics_collector.record_task_metric(func.__name__, 'failed_tasks',
                metrics_collector.get_task_metrics(func.__name__).get('failed_tasks', 0) + 1)
            
            log_task_event(func.__name__, 'failed', {
                'priority': 'medium',
                'error': str(e)
            }, service=service)
            raise
    return cast(Callable[..., T], wrapper)

def low_priority_task(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for low priority tasks
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function with low priority
    """
    @celery_app.task(bind=True, priority=PRIORITY_LOW)
    @task_with_retry()
    @wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
        service = determine_service(func.__name__)
        start_time = time.time()
        
        log_task_event(func.__name__, 'started', {'priority': 'low'}, service=service)
        try:
            result = func(*args, **kwargs)
            
            # Record success metrics
            duration = time.time() - start_time
            metrics_collector.record_task_metric(func.__name__, 'last_duration', duration)
            metrics_collector.record_task_metric(func.__name__, 'total_tasks',
                metrics_collector.get_task_metrics(func.__name__).get('total_tasks', 0) + 1)
            
            log_task_event(func.__name__, 'completed', {
                'priority': 'low',
                'duration': duration
            }, service=service)
            
            return result
        except Exception as e:
            # Record failure metrics
            metrics_collector.record_task_metric(func.__name__, 'failed_tasks',
                metrics_collector.get_task_metrics(func.__name__).get('failed_tasks', 0) + 1)
            
            log_task_event(func.__name__, 'failed', {
                'priority': 'low',
                'error': str(e)
            }, service=service)
            raise
    return cast(Callable[..., T], wrapper) 