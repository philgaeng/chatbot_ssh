#!/usr/bin/env python3

import os
import sys

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

# Import the db_manager singleton
from actions_server.db_manager import db_manager

def main():
    """Initialize the database tables and indexes"""
    print("Starting database initialization...")
    db_manager.init_db()
    print("Database initialization completed.")

if __name__ == "__main__":
    main() 