"""
Enhanced logging for Rasa actions with better control and file output.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Dict, Any, Optional


def setup_enhanced_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_directory: str = "logs"
) -> None:
    """
    Set up enhanced logging for Rasa actions.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to files
        log_directory: Directory to store log files
    """
    
    # Create logs directory if it doesn't exist
    if log_to_file and not os.path.exists(log_directory):
        os.makedirs(log_directory)
    
    # Convert string level to logging constant
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    numeric_level = level_map.get(log_level.upper(), logging.INFO)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handlers
    if log_to_file:
        # Main actions log file
        actions_log_file = os.path.join(log_directory, "rasa_actions.log")
        file_handler = logging.handlers.RotatingFileHandler(
            actions_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        # Error-only log file
        error_log_file = os.path.join(log_directory, "rasa_actions_errors.log")
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)
    
    # Set specific logger levels
    logging.getLogger("rasa_chatbot.actions").setLevel(numeric_level)
    logging.getLogger("backend").setLevel(numeric_level)
    
    # Reduce noise from third-party libraries
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("rasa_sdk").setLevel(logging.INFO)


def log_action_execution(action_name: str, tracker_id: str, data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log action execution with structured data.
    
    Args:
        action_name: Name of the action being executed
        tracker_id: Rasa tracker ID
        data: Additional data to log
    """
    logger = logging.getLogger("rasa_chatbot.actions.backend_repository")
    
    log_data = {
        "action": action_name,
        "tracker_id": tracker_id,
        "timestamp": datetime.now().isoformat(),
        "data": data or {}
    }
    
    logger.info(f"Action execution: {log_data}")


def log_backend_operation(operation: str, success: bool, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log backend operations with structured data.
    
    Args:
        operation: Name of the operation (e.g., "create_complainant")
        success: Whether the operation was successful
        details: Additional details about the operation
    """
    logger = logging.getLogger("rasa_chatbot.actions.backend_repository")
    
    level = logging.INFO if success else logging.ERROR
    status = "SUCCESS" if success else "FAILED"
    
    log_data = {
        "operation": operation,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    }
    
    logger.log(level, f"Backend operation: {log_data}")


def log_error_with_context(error: Exception, context: str, additional_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log errors with context and structured data.
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        additional_data: Additional data to include
    """
    logger = logging.getLogger("rasa_chatbot.actions.backend_repository")
    
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "timestamp": datetime.now().isoformat(),
        "additional_data": additional_data or {}
    }
    
    logger.error(f"Error occurred: {error_data}", exc_info=True)


# Initialize logging when this module is imported
if __name__ != "__main__":
    # Set up logging with default configuration
    setup_enhanced_logging(
        log_level="INFO",
        log_to_file=True
    ) 