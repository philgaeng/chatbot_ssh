"""
Database configuration for the grievance management system.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Database connection parameters
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'grievance_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASS', 'postgres'),
    'port': os.environ.get('DB_PORT', '5432'),
}

# Path to store uploaded files
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(os.getcwd(), 'uploads'))

# Max file size in bytes (2MB)
MAX_FILE_SIZE = 2 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
    'xls', 'xlsx', 'txt', 'csv', 'zip', 'rar'
}

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 