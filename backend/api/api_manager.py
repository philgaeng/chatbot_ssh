from typing import Dict, Any, Optional
from backend.logger.logger import TaskLogger
from flask import jsonify
import inspect

class APIManager:
    """Manager class for API endpoints with common functionality"""
    
    def __init__(self, service_name: str):
        self.logger = TaskLogger(service_name)
        self.service_name = service_name
    
    def log_event(self, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log an event with consistent formatting"""
        # Get the name of the calling function
        frame = inspect.currentframe()
        outer_frames = inspect.getouterframes(frame)
        # The caller is at index 1
        function_name = outer_frames[1].function
        self.logger.log_task_event(
            service_name=self.service_name,
            task_name=function_name,
            event_type=event_type,
            details=details
        )
    
    def success_response(self, data: Dict[str, Any], message: str = "Success") -> Dict[str, Any]:
        """Create a standardized success response"""
        return jsonify({
            'status': 'success',
            'message': message,
            'data': data
        })
    
    def error_response(self, error: str, status_code: int = 500) -> Dict[str, Any]:
        """Create a standardized error response"""
        return jsonify({
            'status': 'error',
            'message': error
        }), status_code
    
    def handle_request(self, func):
        """Decorator to handle common request processing"""
        def wrapper(*args, **kwargs):
            try:
                self.log_event('started', {'args': args, 'kwargs': kwargs})
                result = func(*args, **kwargs)
                self.log_event('completed', {'result': result})
                return result
            except Exception as e:
                self.log_event('failed', {'error': str(e)})
                return self.error_response(str(e))
        return wrapper 