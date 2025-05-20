"""
Task logging functionality for the Nepal Chatbot Queue System.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import TimedRotatingFileHandler

class TaskLogger:
    """Centralized task logging functionality"""
    
    def __init__(self, service_name: str = 'queue_system'):
        self.service_name = service_name
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Set up the logger with file and console handlers"""
        logger = logging.getLogger(self.service_name)
        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # File handler
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)
            file_handler = TimedRotatingFileHandler(
                filename=log_dir / f'{self.service_name}.log',
                when='midnight',
                interval=1,
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def log_task_event(self, task_name: str, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log task events with consistent formatting"""
        log_message = f"Task: {task_name} - Event: {event_type}"
        if details:
            log_message += f" - Details: {json.dumps(details)}"
        
        self.logger.info(log_message)
        
        # Record metrics if needed
        if event_type == 'started':
            self._record_metric(task_name, 'start_time', time.time())
        elif event_type == 'completed':
            start_time = self._get_metric(task_name, 'start_time', time.time())
            duration = time.time() - start_time
            self._record_metric(task_name, 'last_duration', duration)
            self._record_metric(task_name, 'total_tasks', 
                self._get_metric(task_name, 'total_tasks', 0) + 1)
        elif event_type == 'failed':
            self._record_metric(task_name, 'failed_tasks', 
                self._get_metric(task_name, 'failed_tasks', 0) + 1)
        elif event_type == 'retrying':
            self._record_metric(task_name, 'retry_count', 
                self._get_metric(task_name, 'retry_count', 0) + 1)
    
    def _record_metric(self, task_name: str, metric_name: str, value: float):
        """Record a metric for a task"""
        metrics_file = Path('logs/metrics.json')
        metrics = {}
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    metrics = json.load(f)
            except json.JSONDecodeError:
                pass
        
        if task_name not in metrics:
            metrics[task_name] = {}
        metrics[task_name][metric_name] = value
        
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def _get_metric(self, task_name: str, metric_name: str, default: Any = None) -> Any:
        """Get a metric value for a task"""
        metrics_file = Path('logs/metrics.json')
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    metrics = json.load(f)
                    return metrics.get(task_name, {}).get(metric_name, default)
            except json.JSONDecodeError:
                pass
        return default 