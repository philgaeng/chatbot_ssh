from typing import Optional, Dict
from .config import celery_app
from actions_server.db_manager import db_manager

def get_task_status(task_id: str) -> str:
    """
    Return the status string for a given task_id.
    Checks the database first, then falls back to Celery.
    Returns 'NOT_FOUND' if the task is not found.
    """
    # Try DB first
    try:
        status = db_manager.get_task_status(task_id)  # Should return a string or None
        if status:
            return status
    except Exception:
        pass
    # Fallback to Celery
    try:
        async_result = celery_app.AsyncResult(task_id)
        return async_result.status
    except Exception:
        return "NOT_FOUND"

def get_task_info(task_id: str) -> Dict:
    """
    Return a full info dict for a given task_id.
    Checks the database first, then falls back to Celery.
    Returns a dict with at least a 'status' key.
    """
    # Try DB first
    try:
        info = db_manager.get_task_info(task_id)  # Should return a dict or None
        if info:
            return info
    except Exception:
        pass
    # Fallback to Celery
    try:
        async_result = celery_app.AsyncResult(task_id)
        return {
            'status': async_result.status,
            'result': str(async_result.result),
            'traceback': str(async_result.traceback),
            'task_id': task_id
        }
    except Exception:
        return {'status': 'NOT_FOUND', 'task_id': task_id} 