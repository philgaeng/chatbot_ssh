import sqlite3
from datetime import datetime

def create_file_attachments_table():
    """Create the file_attachments table in the database"""
    
    # Connect to the database
    conn = sqlite3.connect('grievance.db')
    cursor = conn.cursor()
    
    # Create the file_attachments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS file_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grievance_id TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_content TEXT NOT NULL,  -- Base64 encoded file content
        file_type TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        upload_timestamp TEXT NOT NULL,
        FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
    )
    ''')
    
    # Create an index for faster lookups
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id 
    ON file_attachments(grievance_id)
    ''')
    
    # Commit the changes and close the connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_file_attachments_table()