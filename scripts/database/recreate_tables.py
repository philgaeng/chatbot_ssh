#!/usr/bin/env python3

import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback
from typing import List, Optional
import argparse
from backend.config.constants import load_environment

# Add the project directory to the Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # Go up two levels to reach project root
sys.path.insert(0, PROJECT_ROOT)

# Set PYTHONPATH to include the project root
os.environ['PYTHONPATH'] = PROJECT_ROOT

# Import the db_manager from the new modular structure
from backend.services.database_services import db_manager

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
    
    logger = logging.getLogger('database_recreate')
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    
    # File handler
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'database_recreate.log'),
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

class DatabaseRecreateError(Exception):
    """Custom exception for database recreation errors"""
    pass

def enable_pgcrypto_extension() -> bool:
    """Enable pgcrypto extension for encryption support"""
    try:
        logger.info("Enabling pgcrypto extension for encryption...")
        with db_manager.base.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
                conn.commit()
        logger.info("✅ pgcrypto extension enabled successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to enable pgcrypto extension: {str(e)}")
        return False

def recreate_tables_with_retry(max_retries: int, retry_delay: int) -> bool:
    """Recreate tables with retry mechanism"""
    max_retries = max_retries or config['HEALTH_CHECK_RETRIES']
    retry_delay = retry_delay or config['HEALTH_CHECK_DELAY']
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Starting table recreation (attempt {attempt + 1}/{max_retries})...")
            
            if not db_manager.recreate_all_tables():
                raise DatabaseRecreateError("Failed to recreate tables")
            
            logger.info("Table recreation completed successfully")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Table recreation attempt {attempt + 1} failed: {str(e)}")
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Table recreation failed after {max_retries} attempts: {str(e)}")
                logger.error(f"Error details: {traceback.format_exc()}")
                return False
    return False

def verify_tables() -> bool:
    """Verify that tables were recreated correctly"""
    try:
        tables = db_manager.get_all_tables()
        for table in tables:
            if not db_manager.table_exists(table):
                logger.error(f"Table '{table}' not found after recreation")
                return False
        logger.info("Table verification successful")
        return True
    except Exception as e:
        logger.error(f"Table verification failed: {str(e)}")
        return False

def test_encryption_setup() -> bool:
    """Test encryption functionality if encryption key is available"""
    try:
        encryption_key = os.getenv('DB_ENCRYPTION_KEY')
        if not encryption_key:
            logger.warning("DB_ENCRYPTION_KEY not set - encryption will be disabled")
            return True
        
        logger.info("Testing encryption functionality...")
        from backend.services.database_services import ComplainantDbManager
        
        manager = ComplainantDbManager()
        
        # Test data
        test_data = {
            'complainant_full_name': 'Test User',
            'complainant_phone': '+977-1234567890',
            'complainant_email': 'test@example.com'
        }
        
        # Test encryption
        encrypted = manager._encrypt_complainant_data(test_data)
        logger.info("✅ Encryption test passed")
        
        # Test decryption
        decrypted = manager._decrypt_complainant_data(encrypted)
        logger.info("✅ Decryption test passed")
        
        # Verify integrity
        for key in test_data:
            if test_data[key] != decrypted[key]:
                logger.error(f"❌ Data integrity check failed for {key}")
                return False
        
        logger.info("✅ Encryption setup verified successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Encryption test failed: {str(e)}")
        return False

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Recreate database tables')
    parser.add_argument('--all', action='store_true', help='Recreate all tables')
    parser.add_argument('--retries', type=int, help='Number of retry attempts')
    parser.add_argument('--delay', type=int, help='Delay between retries in seconds')
    parser.add_argument('--enable-encryption', action='store_true', help='Enable pgcrypto extension')
    parser.add_argument('--test-encryption', action='store_true', help='Test encryption functionality')
    return parser.parse_args()

def main():
    """Recreate database tables with enhanced error handling and encryption support"""
    args = parse_args()
    
    try:
        if not args.all:
            logger.error("No tables specified. Use --all to recreate all tables")
            return 1
        
        logger.info("Starting recreation of all tables...")
        
        # Enable pgcrypto extension if requested
        if args.enable_encryption:
            if not enable_pgcrypto_extension():
                logger.warning("Failed to enable pgcrypto extension - continuing without encryption")
        
        # Recreate tables with retry mechanism
        if not recreate_tables_with_retry(args.retries, args.delay):
            raise DatabaseRecreateError("Failed to recreate tables")
        
        # Verify the recreation
        if not verify_tables():
            raise DatabaseRecreateError("Table verification failed")
        
        # Test encryption if requested
        if args.test_encryption:
            if not test_encryption_setup():
                logger.warning("Encryption test failed - check DB_ENCRYPTION_KEY environment variable")
        
        logger.info("Table recreation completed successfully")
        return 0
    except DatabaseRecreateError as e:
        logger.error(f"Table recreation error: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during table recreation: {str(e)}")
        logger.error(f"Error details: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 