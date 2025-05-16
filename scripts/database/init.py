#!/usr/bin/env python3

import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback
from typing import Optional
import json

# Add the project directory to the Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.append(PROJECT_ROOT)

# Import the db_manager singleton
from actions_server.db_manager import db_manager

# Load configuration
def load_config():
    """Load configuration from config.sh"""
    config = {}
    config_file = os.path.join(SCRIPT_DIR, 'config.sh')
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                if value.isdigit():
                    value = int(value)
                elif value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                config[key] = value
    
    return config

# Load configuration
config = load_config()

# Configure logging
def setup_logging() -> logging.Logger:
    """Set up logging configuration"""
    log_dir = os.path.join(PROJECT_ROOT, config['LOG_DIR'])
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger('database_init')
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    
    # File handler
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'database_init.log'),
        maxBytes=config['LOG_MAX_SIZE_MB'] * 1024 * 1024,
        backupCount=config['LOG_MAX_FILES']
    )
    file_handler.setLevel(logging.INFO)
    
    if config['LOG_FORMAT'] == 'json':
        file_format = logging.Formatter('%(message)s')
    else:
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

class DatabaseInitError(Exception):
    """Custom exception for database initialization errors"""
    pass

def check_database_connection(max_retries: int = None, retry_delay: int = None) -> bool:
    """Check database connection with retries"""
    max_retries = max_retries or config['DB_CONNECTION_RETRIES']
    retry_delay = retry_delay or config['DB_CONNECTION_DELAY']
    
    for attempt in range(max_retries):
        try:
            db_manager.check_connection()
            logger.info("Database connection successful")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {str(e)}")
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                return False
    return False

def init_database_with_retry(max_retries: int = None, retry_delay: int = None) -> bool:
    """Initialize database with retry mechanism"""
    max_retries = max_retries or config['HEALTH_CHECK_RETRIES']
    retry_delay = retry_delay or config['HEALTH_CHECK_DELAY']
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Starting database initialization (attempt {attempt + 1}/{max_retries})...")
            db_manager.init_db()
            logger.info("Database initialization completed successfully")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database initialization attempt {attempt + 1} failed: {str(e)}")
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Database initialization failed after {max_retries} attempts: {str(e)}")
                logger.error(f"Error details: {traceback.format_exc()}")
                return False
    return False

def verify_database_setup() -> bool:
    """Verify that database was initialized correctly"""
    try:
        # Add your verification logic here
        # For example, check if required tables exist
        required_tables = ['users', 'tickets', 'files']  # Add your actual table names
        for table in required_tables:
            if not db_manager.table_exists(table):
                logger.error(f"Required table '{table}' not found")
                return False
        logger.info("Database setup verification successful")
        return True
    except Exception as e:
        logger.error(f"Database verification failed: {str(e)}")
        return False

def main():
    """Initialize the database tables and indexes with enhanced error handling"""
    try:
        # Check database connection first
        if not check_database_connection():
            raise DatabaseInitError("Failed to establish database connection")

        # Initialize database with retry mechanism
        if not init_database_with_retry():
            raise DatabaseInitError("Failed to initialize database")

        # Verify the setup
        if not verify_database_setup():
            raise DatabaseInitError("Database setup verification failed")

        logger.info("Database initialization completed successfully")
        return 0
    except DatabaseInitError as e:
        logger.error(f"Database initialization error: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {str(e)}")
        logger.error(f"Error details: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 