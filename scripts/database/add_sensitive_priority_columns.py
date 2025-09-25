#!/usr/bin/env python3

import os
import sys

# Add the project directory to the Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

# Set PYTHONPATH to include the project root
os.environ['PYTHONPATH'] = PROJECT_ROOT

import logging
from backend.services.database_services import db_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        with db_manager.base.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                """, (table_name, column_name))
                return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking column {column_name} in table {table_name}: {str(e)}")
        return False

def add_column_if_not_exists(table_name: str, column_name: str, column_definition: str):
    """Add a column to a table if it doesn't exist"""
    if check_column_exists(table_name, column_name):
        logger.info(f"✅ Column '{column_name}' already exists in table '{table_name}'")
        return True
    
    try:
        with db_manager.base.get_connection() as conn:
            with conn.cursor() as cur:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                logger.info(f"Executing: {sql}")
                cur.execute(sql)
                conn.commit()
                logger.info(f"✅ Successfully added column '{column_name}' to table '{table_name}'")
                return True
    except Exception as e:
        logger.error(f"❌ Failed to add column '{column_name}' to table '{table_name}': {str(e)}")
        return False

def main():
    """Add sensitive_issue and high_priority columns to grievances table"""
    logger.info("Starting migration to add sensitive_issue and high_priority columns...")
    
    # Define the columns to add
    columns_to_add = [
        {
            'table': 'grievances',
            'column': 'grievance_sensitive_issue',
            'definition': 'BOOLEAN DEFAULT FALSE'
        },
        {
            'table': 'grievances',
            'column': 'grievance_high_priority',
            'definition': 'BOOLEAN DEFAULT FALSE'
        }
    ]
    
    success = True
    
    for col_info in columns_to_add:
        if not add_column_if_not_exists(col_info['table'], col_info['column'], col_info['definition']):
            success = False
    
    if success:
        logger.info("✅ Migration completed successfully!")
        logger.info("The grievances table now includes:")
        logger.info("  - grievance_sensitive_issue (BOOLEAN, default FALSE)")
        logger.info("  - grievance_high_priority (BOOLEAN, default FALSE)")
        logger.info("All existing data has been preserved.")
    else:
        logger.error("❌ Migration failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
