import os
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
from actions_server.db_manager import db_manager
from actions_server.constants import MAX_FILE_SIZE  # Import MAX_FILE_SIZE from constants
from actions_server.utterance_mapping_server import get_utterance

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Default language
language = 'en'

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {
    # Images
    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'heic', 'heif',
    
    # Videos
    'mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm', 'm4v',
    
    # Documents
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 
    'txt', 'rtf', 'csv', 'odt', 'ods', 'odp',
    
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz'
}

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Register voice endpoints from accessible_server on initialization
def register_voice_endpoints():
    """Register voice-related endpoints to the file server app"""
    try:
        from accessible_server.voice_grievance import register_voice_endpoints as external_register_voice_endpoints
        external_register_voice_endpoints(app)
        logger.info("Voice endpoints registered with file server")
    except Exception as e:
        logger.error(f"Error registering voice endpoints: {str(e)}", exc_info=True)

# Register voice endpoints
register_voice_endpoints()

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "File server is running"})

@app.route('/test-db')
def test_db():
    """Test database connectivity"""
    try:
        # Try to connect to the database
        connection = db_manager.get_connection()
        cursor = connection.cursor()
        
        # Check if the grievances table exists
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'grievances'")
        tables_count = cursor.fetchone()[0]
        
        # Count grievances
        grievance_count = 0
        if tables_count > 0:
            cursor.execute("SELECT COUNT(*) FROM grievances")
            grievance_count = cursor.fetchone()[0]
        
        # Create a test grievance ID
        test_id = db_manager.generate_grievance_id('test')
        
        connection.close()
        
        return jsonify({
            "status": "ok", 
            "message": "Database connection successful",
            "tables_exist": tables_count > 0,
            "grievance_count": grievance_count,
            "test_grievance_id": test_id
        })
    except Exception as e:
        logger.error(f"Database test error: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"Database connection error: {str(e)}"
        }), 500

@app.route('/upload-files', methods=['POST'])
def upload_files():
    """Handle file uploads for a grievance"""
    try:
        logger.info("Received file upload request")
        
        # Check if grievance_id is provided
        grievance_id = request.form.get('grievance_id')
        logger.info(f"Received grievance ID: {grievance_id} (length: {len(grievance_id) if grievance_id else 0})")
        
        if not grievance_id:
            logger.error("No grievance_id provided")
            error_message = get_utterance('file_server', 'upload_files', 1, language)
            return jsonify({"error": error_message}), 400

        # Reject uploads for pending grievances
        if grievance_id == "pending":
            logger.error("Attempted to upload file for pending grievance")
            error_message = get_utterance('file_server', 'upload_files', 2, language)
            return jsonify({"error": error_message}), 400

        # Check if any file was sent
        logger.info(f"Files in request: {request.files}")
        if 'files[]' not in request.files:
            logger.error("No files[] in request.files")
            error_message = get_utterance('file_server', 'upload_files', 3, language)
            return jsonify({"error": error_message}), 400

        files = request.files.getlist('files[]')
        logger.info(f"Number of files received: {len(files)}")
        
        if not files:
            logger.error("No files in files[] list")
            error_message = get_utterance('file_server', 'upload_files', 4, language)
            return jsonify({"error": error_message}), 400

        uploaded_files = []
        oversized_files = []
        
        for file in files:
            logger.info(f"Processing file: {file.filename}")
            if file and allowed_file(file.filename):
                # Check file size
                file.seek(0, 2)  # Seek to end of file
                file_size = file.tell()  # Get current position (file size)
                file.seek(0)  # Reset file pointer to beginning
                
                if file_size > MAX_FILE_SIZE:
                    oversized_files.append({
                        'filename': file.filename,
                        'size': file_size
                    })
                    continue
                
                # Secure the filename and generate unique ID
                filename = secure_filename(file.filename)
                file_id = str(uuid.uuid4())
                logger.info(f"Generated file_id: {file_id}")
                
                # Create grievance-specific directory
                grievance_dir = os.path.join(UPLOAD_FOLDER, grievance_id)
                if not os.path.exists(grievance_dir):
                    os.makedirs(grievance_dir)
                    logger.info(f"Created directory: {grievance_dir}")
                
                # Save file
                file_path = os.path.join(grievance_dir, f"{file_id}_{filename}")
                logger.info(f"Saving file to: {file_path}")
                file.save(file_path)
                
                # Store file metadata in database
                file_data = {
                    'file_id': file_id,
                    'grievance_id': grievance_id,  # Using the full grievance ID
                    'file_name': filename,
                    'file_path': file_path,
                    'file_type': filename.rsplit('.', 1)[1].lower(),
                    'file_size': file_size
                }
                logger.info(f"Storing file metadata with grievance ID: {grievance_id}")
                
                # Save to database using DatabaseManager
                if db_manager.store_file_attachment(file_data):
                    logger.info(f"Successfully stored file metadata in database: {filename}")
                    uploaded_files.append({
                        'file_id': file_id,
                        'filename': filename,
                        'file_size': file_size
                    })
                else:
                    # If database storage fails, delete the file
                    os.remove(file_path)
                    logger.error(f"Failed to store file metadata in database: {filename}")
            else:
                extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'no extension'
                logger.error(f"Invalid file type: {extension} for file: {file.filename}")
                error_message = get_utterance('file_server', 'upload_files', 5, language)
                return jsonify({
                    "error": error_message
                }), 400

        response_data = {
            "message": "Files processed",
            "files": uploaded_files,
        }
        
        if oversized_files:
            response_data["oversized_files"] = oversized_files
            response_data["max_file_size"] = MAX_FILE_SIZE
            if not uploaded_files:
                return jsonify(response_data), 413
        
        if uploaded_files:
            response_data["message"] = "Files uploaded successfully"
            return jsonify(response_data), 200
        else:
            if not oversized_files:
                response_data["message"] = "No files were uploaded"
                return jsonify(response_data), 400
            return jsonify(response_data), 413

    except Exception as e:
        logger.error(f"Error uploading files: {str(e)}", exc_info=True)
        error_message = get_utterance('file_server', 'upload_files', 6, language)
        return jsonify({"error": error_message}), 500

@app.route('/files/<grievance_id>', methods=['GET'])
def get_files(grievance_id):
    """Get list of files for a grievance"""
    try:
        files = db_manager.get_grievance_files(grievance_id)
        return jsonify({"files": files}), 200
    except Exception as e:
        logger.error(f"Error retrieving files: {str(e)}")
        error_message = get_utterance('file_server', 'get_files', 1, language)
        return jsonify({"error": error_message}), 500

@app.route('/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """Download a specific file"""
    try:
        file_data = db_manager.get_file_by_id(file_id)
        if file_data and os.path.exists(file_data['file_path']):
            return send_file(
                file_data['file_path'],
                as_attachment=True,
                download_name=file_data['file_name']
            )
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001) 