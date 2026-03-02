"""
Task logging functionality for the Nepal Chatbot Queue System.

Logs append to a file per day (e.g. queue_system_2026-03-02.log). Each day gets
a new file; within the day all sessions/restarts append to that day's file.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class LoggingConfig:
    """Centralized logging configuration for the entire system"""
    
    # Directory and file settings
    LOG_DIR = "logs"
    LOG_MAX_SIZE_MB = 100
    LOG_MAX_FILES = 5
    
    # Use daily filenames (service_YYYY-MM-DD.log) so each day gets a new file, append within day
    USE_DAILY_FILENAME = True
    
    # Format settings
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = 'INFO'
    
    # Metrics configuration
    METRICS_FILE = 'metrics.json'
    
    # Default services to monitor (centralized service registry)
    # Base names only; date suffix is added when USE_DAILY_FILENAME is True
    DEFAULT_SERVICES = {
        'llm_service': 'llm_service',
        'queue_system': 'queue_system',
        'db_operations': 'db_operations',
        'database_service': 'database_service',
        'db_migrations': 'db_migrations',
        'db_backup': 'db_backup',
        'ticket_processor': 'ticket_processor',
        'ticket_notifications': 'ticket_notifications',
        'ticket_assignments': 'ticket_assignments',
        'monitoring_config': 'monitoring_config',
        'socketio': 'socketio',
        'voice_grievance': 'voice_grievance',
        'api_manager': 'api_manager',
        'file_processor': 'file_processor',
        'file_service': 'file_service',
        'messaging_service': 'messaging_service',
        'channels_api': 'channels_api'
    }
    
    @classmethod
    def get_log_path(cls, service_name: str, date: Optional[datetime] = None) -> Path:
        """Get the full log file path for a service. If USE_DAILY_FILENAME, includes date."""
        log_dir = Path(cls.LOG_DIR)
        log_dir.mkdir(exist_ok=True)
        base = cls.DEFAULT_SERVICES.get(service_name, service_name)
        if cls.USE_DAILY_FILENAME:
            d = (date or datetime.now()).strftime('%Y-%m-%d')
            filename = f'{base}_{d}.log'
        else:
            filename = f'{base}.log'
        return log_dir / filename
    
    @classmethod
    def get_metrics_path(cls) -> Path:
        """Get the full metrics file path"""
        return Path(cls.LOG_DIR) / cls.METRICS_FILE


class DailyRotatingFileHandler(logging.FileHandler):
    """
    File handler that writes to a file named with the current date
    (e.g. service_2026-03-02.log). Appends within the day; rolls to a new
    file when the date changes (e.g. after midnight).
    """

    def __init__(self, service_name: str, config: LoggingConfig, **kwargs):
        self._service_name = service_name
        self._config = config
        self._current_date: Optional[str] = None
        path = self._get_today_path()
        super().__init__(path, mode='a', encoding='utf-8', **kwargs)
        self._current_date = datetime.now().strftime('%Y-%m-%d')

    def _get_today_path(self) -> Path:
        return self._config.get_log_path(self._service_name)

    def emit(self, record: logging.LogRecord) -> None:
        today = datetime.now().strftime('%Y-%m-%d')
        if self._current_date != today:
            self.close()
            self.baseFilename = str(self._get_today_path())
            self.stream = self._open()
            self._current_date = today
        super().emit(record)


class TaskLogger:
    """Centralized task logging functionality"""
    
    def __init__(self, service_name: str = 'queue_system'):
        self.service_name = service_name
        self.config = LoggingConfig()
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Set up the logger with file and console handlers. File: append, new file each day."""
        logger = logging.getLogger(self.service_name)
        if not logger.handlers:
            formatter = logging.Formatter(self.config.LOG_FORMAT)

            if self.config.USE_DAILY_FILENAME:
                file_handler = DailyRotatingFileHandler(self.service_name, self.config)
            else:
                log_file_path = self.config.get_log_path(self.service_name)
                file_handler = logging.FileHandler(
                    log_file_path, mode='a', encoding='utf-8'
                )
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        return logger
    
    def log_task_event(self, task_name: str, details: Optional[Dict[str, Any]] = None, service_name: str = None, event_type=None) -> None:
        """Log task events with consistent formatting"""
        log_message = f"Service: {service_name or self.service_name} - Task or function: {task_name}"
        if details:
            log_message += f" - Details: {json.dumps(details)}"
        
        self.logger.info(log_message)
        if event_type:
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