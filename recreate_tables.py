#!/usr/bin/env python3

import os
import sys
import logging

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

# Import the db_manager singleton
from actions_server.db_manager import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to recreate the database tables"""
    logger.info("Starting complete database recreation process")
    
    # Confirm with the user before proceeding
    print("⚠️  WARNING: This will delete ALL data in the database and recreate all tables! ⚠️")
    print("Are you sure you want to continue? This action cannot be undone.")
    response = input("Type 'YES' to confirm: ")
    
    if response.strip().upper() != "YES":
        print("Operation cancelled. No changes were made.")
        return
    
    # Use the db_manager recreate_db method
    success = db_manager.recreate_db()
    
    if success:
        logger.info("Database completely recreated successfully!")
        logger.info("The tables now include language_code fields for better language tracking.")
    else:
        logger.error("Failed to recreate database tables")

if __name__ == "__main__":
    main() 