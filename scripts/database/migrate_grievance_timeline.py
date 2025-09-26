#!/usr/bin/env python3
"""
Migration script to add grievance_timeline column to existing grievances table
and populate it with calculated values (grievance_creation_date + 15 days)
"""

import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.database_services.base_manager import TableDbManager

def main():
    """Run the grievance_timeline migration"""
    print("🚀 Starting grievance_timeline column migration...")
    
    try:
        # Initialize table database manager
        db_manager = TableDbManager()
        
        # Run the migration
        success = db_manager.migrate_grievance_timeline_column()
        
        if success:
            print("✅ Migration completed successfully!")
            print("📊 grievance_timeline column has been added and populated")
            print("📈 Index has been created for optimal query performance")
        else:
            print("❌ Migration failed!")
            return 1
            
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
