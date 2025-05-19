import datetime
from actions_server.db_manager import db_manager
from actions_server.app import emit_status_update
class TaskManager:
    """
    Handles the lifecycle of a Celery task, including database logging for start, completion, and failure.
    Usage:
        task_mgr = TaskManager(task=self, emit_websocket=False)
        task_mgr.start_task(grievance_id, stage='transcription')
        ...
        task_mgr.complete_task(result, stage='transcription')
        ...
        task_mgr.fail_task(error, stage='transcription')
    """
    def __init__(self, task=None, emit_websocket=False):
        self.task = task
        self.emit_websocket = emit_websocket
        self.task_id = None
        self.grievance_id = None
        self.celery_task_id = None
        self.start_time = None
        self.end_time = None
        self.status = None
        self.result = None
        self.error = None
        self.db_task = db_manager.task

    def _emit_status(self, grievance_id, status, data):
        if self.emit_websocket:
            emit_status_update(grievance_id, status, data)

    def start_task(self, grievance_id: str, stage: str = None, extra_data=None) -> bool:
        """Start a new task and record it in the database. Optionally emit WebSocket status."""
        try:
            self.grievance_id = grievance_id
            self.start_time = datetime.datetime.utcnow()
            self.status = 'PENDING'
            self.task_id = self.db_task.create_task_execution(
                task_id=self.task.name if self.task else None,
                grievance_id=grievance_id,
                celery_task_id=getattr(self.task.request, 'id', None)
            )
            if stage:
                self._emit_status(grievance_id, 'processing', {'stage': stage, **(extra_data or {})})
            return True
        except Exception as e:
            self.error = str(e)
            return False

    def complete_task(self, result=None, stage: str = None) -> bool:
        """Mark task as complete and record the result. Optionally emit WebSocket status."""
        try:
            self.end_time = datetime.datetime.utcnow()
            self.status = 'COMPLETED'
            self.result = result
            updated = self.db_task.update_task_execution(
                task_id=self.task_id,
                status='COMPLETED',
                result=result
            )
            if stage:
                self._emit_status(self.grievance_id, 'completed', {'stage': stage, 'result': result})
            return updated
        except Exception as e:
            self.error = str(e)
            return False

    def fail_task(self, error: str, stage: str = None) -> bool:
        """Mark task as failed and record the error. Optionally emit WebSocket status."""
        try:
            self.end_time = datetime.datetime.utcnow()
            self.status = 'FAILED'
            self.error = error
            updated = self.db_task.update_task_execution(
                task_id=self.task_id,
                status='FAILED',
                error=error
            )
            if stage:
                self._emit_status(self.grievance_id, 'failed', {'stage': stage, 'error': str(error)})
            return updated
        except Exception as e:
            self.error = str(e)
            return False
