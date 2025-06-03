"""
Task logging functionality for the Nepal Chatbot Queue System.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import TimedRotatingFileHandler

class LoggingConfig:
    """Centralized logging configuration for the entire system"""
    
    # Directory and file settings
    LOG_DIR = "logs"
    LOG_MAX_SIZE_MB = 100
    LOG_MAX_FILES = 5
    
    # Format settings
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = 'INFO'
    
    # Metrics configuration
    METRICS_FILE = 'metrics.json'
    
    # Default services to monitor (centralized service registry)
    DEFAULT_SERVICES = {
        'llm_processor': 'llm_processor.log',
        'queue_system': 'queue_system.log',
        'db_operations': 'db_operations.log',
        'db_migrations': 'db_migrations.log',
        'db_backup': 'db_backup.log',
        'ticket_processor': 'ticket_processor.log',
        'ticket_notifications': 'ticket_notifications.log',
        'ticket_assignments': 'ticket_assignments.log',
        'monitoring_config': 'monitoring_config.log',
        'socketio': 'socketio.log',
        'voice_grievance': 'voice_grievance.log',
        'api_manager': 'api_manager.log'
    }
    
    @classmethod
    def get_log_path(cls, service_name: str) -> Path:
        """Get the full log file path for a service"""
        log_dir = Path(cls.LOG_DIR)
        log_dir.mkdir(exist_ok=True)
        filename = cls.DEFAULT_SERVICES.get(service_name, f'{service_name}.log')
        return log_dir / filename
    
    @classmethod
    def get_metrics_path(cls) -> Path:
        """Get the full metrics file path"""
        return Path(cls.LOG_DIR) / cls.METRICS_FILE

class TaskLogger:
    """Centralized task logging functionality"""
    
    def __init__(self, service_name: str = 'queue_system'):
        self.service_name = service_name
        self.config = LoggingConfig()
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Set up the logger with file and console handlers"""
        logger = logging.getLogger(self.service_name)
        if not logger.handlers:
            formatter = logging.Formatter(self.config.LOG_FORMAT)
            
            # File handler using centralized config
            log_file_path = self.config.get_log_path(self.service_name)
            file_handler = TimedRotatingFileHandler(
                filename=log_file_path,
                when='midnight',
                interval=1,
                backupCount=self.config.LOG_MAX_FILES,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
            
        return logger
    
    def log_task_event(self, task_name: str, event_type: str, details: Optional[Dict[str, Any]] = None, service_name: str = None) -> None:
        """Log task events with consistent formatting"""
        log_message = f"Service: {service_name or self.service_name} - Task or function: {task_name} - Event: {event_type}"
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
        metrics_file = self.config.get_metrics_path()
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
        metrics_file = self.config.get_metrics_path()
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    metrics = json.load(f)
                    return metrics.get(task_name, {}).get(metric_name, default)
            except json.JSONDecodeError:
                pass
        return default 
    
    def log_event(self, message: str, extra_data: Optional[Dict[str, Any]] = None, level: str = "info"):
        """General-purpose logging with consistent formatting."""
        log_message = f"Service: {self.service_name} - Message: {message}"
        if extra_data:
            log_message += f" - Extra Data: {json.dumps(extra_data)}"
        
        if level == "debug":
            self.logger.debug(log_message)
        elif level == "warning":
            self.logger.warning(log_message)
        elif level == "error":
            self.logger.error(log_message)
        elif level == "critical":
            self.logger.critical(log_message)
        else:
            self.logger.info(log_message)