import os
import uuid
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes and origins

# Database connection parameters - adjust as needed
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'grievance_db')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASS = os.environ.get('DB_PASS', 'postgres')
DB_PORT = os.environ.get('DB_PORT', '5432')

# Max file size (2MB)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Create a connection to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        # For development, return None so we can continue without DB
        logger.warning("Continuing without database connection for development")
        return None

def init_db():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    if not conn:
        logger.warning("Skipping database initialization - no connection")
        return

    cur = conn.cursor()
    try:
        # Create file_attachments table if it doesn't exist
        cur.execute('''
        CREATE TABLE IF NOT EXISTS file_attachments (
            id SERIAL PRIMARY KEY,
            file_id UUID NOT NULL,
            grievance_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create index for faster lookups
        cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id 
        ON file_attachments(grievance_id)
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        conn.rollback()
        logger.error(f"Database initialization error: {e}")
    finally:
        cur.close()
        conn.close()

@app.route('/upload-files', methods=['POST'])
def upload_files():
    """Handle file uploads"""
    logger.info("File upload request received")
    logger.debug(f"Headers: {request.headers}")
    logger.debug(f"Form data: {request.form}")
    
    # Check if grievance_id is provided
    grievance_id = request.form.get('grievance_id')
    if not grievance_id:
        logger.warning("No grievance ID provided")
        grievance_id = 'pending'  # Default for development
    
    # Check if files are provided
    if 'files' not in request.files:
        logger.warning("No files in request")
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        logger.warning("Empty file list or empty filename")
        return jsonify({'error': 'No files selected'}), 400
    
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        logger.info(f"Created upload directory: {upload_dir}")
    
    # Process each file
    file_references = []
    conn = get_db_connection()
    
    try:
        for file in files:
            logger.info(f"Processing file: {file.filename}")
            if file and allowed_file(file.filename):
                # Generate a unique filename
                file_id = str(uuid.uuid4())
                filename = secure_filename(file.filename)
                file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                unique_filename = f"{file_id}.{file_ext}" if file_ext else file_id
                
                # Save file to disk
                file_path = os.path.join(upload_dir, unique_filename)
                file.save(file_path)
                logger.info(f"File saved to: {file_path}")
                
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Add file reference to the response
                file_references.append({
                    'id': file_id,
                    'name': filename,
                    'type': file.content_type,
                    'size': file_size
                })
                
                # Store file metadata in database if we have a connection
                if conn:
                    cur = conn.cursor()
                    try:
                        cur.execute('''
                        INSERT INTO file_attachments 
                        (file_id, grievance_id, file_name, file_path, file_type, file_size)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        ''', (
                            file_id, 
                            grievance_id,
                            filename,
                            file_path,
                            file.content_type,
                            file_size
                        ))
                        
                        db_id = cur.fetchone()[0]
                        logger.info(f"File metadata saved to DB with ID: {db_id}")
                        conn.commit()
                    except Exception as e:
                        if conn:
                            conn.rollback()
                        logger.error(f"Database error: {e}")
                    finally:
                        if cur:
                            cur.close()
            else:
                logger.warning(f"Invalid file: {file.filename}")
        
        logger.info(f"Successfully processed {len(file_references)} file(s)")
        response = {
            'message': f'{len(file_references)} file(s) uploaded successfully',
            'file_references': file_references
        }
        logger.debug(f"Response: {response}")
        return jsonify(response), 200
    
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error during file upload: {e}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/files/<grievance_id>', methods=['GET'])
def get_files(grievance_id):
    """Get all files for a specific grievance"""
    logger.info(f"File retrieval request for grievance ID: {grievance_id}")
    
    conn = get_db_connection()
    if not conn:
        # For development, return example data
        logger.warning("No DB connection, returning example data")
        return jsonify({
            'grievance_id': grievance_id,
            'files': []
        }), 200
        
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute('''
        SELECT file_id, file_name, file_type, file_size, upload_timestamp
        FROM file_attachments
        WHERE grievance_id = %s
        ORDER BY upload_timestamp DESC
        ''', (grievance_id,))
        
        files = [dict(row) for row in cur.fetchall()]
        logger.info(f"Found {len(files)} files for grievance ID: {grievance_id}")
        return jsonify({
            'grievance_id': grievance_id,
            'files': files
        }), 200
    
    except Exception as e:
        logger.error(f"Error retrieving files: {e}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        cur.close()
        conn.close()

@app.route('/', methods=['GET'])
def index():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'OK',
        'message': 'File server is running'
    }), 200

if __name__ == '__main__':
    # Initialize the database when the app starts
    init_db()
    port = int(os.environ.get('PORT', 5001))
    logger.info(f"Starting file server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)