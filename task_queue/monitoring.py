"""
Monitoring and logging utilities for the queue system.
"""

import logging
import smtplib
import json
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Dict, Any, Optional, Union
from pathlib import Path
from .config import logging_config

# Create logs directory if it doesn't exist
LOG_DIR = Path(logging_config.dir)
LOG_DIR.mkdir(exist_ok=True)

# Configure logging
def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with file and console handlers
    
    Args:
        name: Name of the logger
        log_file: Name of the log file
        level: Logging level
        
    Returns:
        Configured logger instance
    """
    formatter = logging.Formatter(logging_config.log_format)
    
    # File handler with daily rotation
    file_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / log_file,
        when='midnight',
        interval=1,
        backupCount=logging_config.max_files,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.suffix = "%Y-%m-%d"  # Format for rotated files
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Dynamic logger registry
logger_registry = {}

def register_logger(service_name: str) -> logging.Logger:
    """
    Register a new logger for a service
    
    Args:
        service_name: Name of the service (will be used for log file name)
        
    Returns:
        Configured logger instance
    """
    if service_name not in logger_registry:
        logger_registry[service_name] = setup_logger(
            service_name,
            f"{service_name.lower()}.log"
        )
    return logger_registry[service_name]

# Initialize default loggers
default_services = {
    'llm_processor': 'llm_processor.log',
    'queue_system': 'queue_system.log',
    'db_operations': 'db_operations.log',
    'db_migrations': 'db_migrations.log',
    'db_backup': 'db_backup.log',
    'ticket_processor': 'ticket_processor.log',
    'ticket_notifications': 'ticket_notifications.log',
    'ticket_assignments': 'ticket_assignments.log'
}

for service, log_file in default_services.items():
    register_logger(service)

# Metrics collection
class MetricsCollector:
    """Collect and store metrics for tasks and services"""
    
    def __init__(self):
        self.metrics_file = LOG_DIR / 'metrics.json'
        self.metrics: Dict[str, Any] = self._load_metrics()
    
    def _load_metrics(self) -> Dict[str, Any]:
        """Load existing metrics from file"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_metrics(self):
        """Save metrics to file"""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
    
    def record_task_metric(self, task_name: str, metric_name: str, value: Union[int, float]):
        """Record a metric for a task"""
        if task_name not in self.metrics:
            self.metrics[task_name] = {}
        self.metrics[task_name][metric_name] = value
        self._save_metrics()
    
    def get_task_metrics(self, task_name: str) -> Dict[str, Any]:
        """Get metrics for a task"""
        return self.metrics.get(task_name, {})

# Initialize metrics collector
metrics_collector = MetricsCollector()

# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')

def send_error_notification(task_name: str, error_message: str, task_id: Optional[str] = None) -> None:
    """
    Send email notification for task failures
    
    Args:
        task_name: Name of the failed task
        error_message: Error message
        task_id: Optional task ID
    """
    if not all([SMTP_USERNAME, SMTP_PASSWORD, ADMIN_EMAIL]):
        register_logger('queue_system').warning("Email configuration incomplete. Skipping email notification.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = f'Task Failure Alert: {task_name}'

        body = f"""
        Task Failure Alert
        
        Task Name: {task_name}
        Task ID: {task_id}
        Time: {datetime.utcnow()}
        Error: {error_message}
        
        Please check the logs for more details.
        """
        
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            
        register_logger('queue_system').info(f"Error notification sent for task {task_name}")
        
        # Record metric
        metrics_collector.record_task_metric(task_name, 'error_notifications', 
            metrics_collector.get_task_metrics(task_name).get('error_notifications', 0) + 1)
            
    except Exception as e:
        register_logger('queue_system').error(f"Failed to send error notification: {str(e)}")

def log_task_event(task_name: str, event_type: str, details: Optional[Dict[str, Any]] = None, 
                  service: str = 'queue_system') -> None:
    """
    Log task events with consistent formatting to appropriate service log file
    
    Args:
        task_name: Name of the task
        event_type: Type of event (e.g., 'started', 'completed', 'failed')
        details: Optional dictionary of event details
        service: Service name for logging
    """
    log_message = f"Task: {task_name} - Event: {event_type}"
    if details:
        log_message += f" - Details: {json.dumps(details)}"
    
    # Get or create logger for the service
    logger = logger_registry.get(service, register_logger(service))
    
    # Log the event
    logger.info(log_message)
    
    # Record metrics
    if event_type == 'started':
        metrics_collector.record_task_metric(task_name, 'start_time', time.time())
    elif event_type == 'completed':
        start_time = metrics_collector.get_task_metrics(task_name).get('start_time', time.time())
        duration = time.time() - start_time
        metrics_collector.record_task_metric(task_name, 'last_duration', duration)
        metrics_collector.record_task_metric(task_name, 'total_tasks', 
            metrics_collector.get_task_metrics(task_name).get('total_tasks', 0) + 1)
    elif event_type == 'failed':
        metrics_collector.record_task_metric(task_name, 'failed_tasks', 
            metrics_collector.get_task_metrics(task_name).get('failed_tasks', 0) + 1) 