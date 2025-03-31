import os
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
from .db_manager import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "File server is running"})

@app.route('/upload-files', methods=['POST'])
def upload_files():
    """Handle file uploads for a grievance"""
    try:
        # Check if grievance_id is provided
        grievance_id = request.form.get('grievance_id')
        if not grievance_id:
            return jsonify({"error": "No grievance_id provided"}), 400

        # Check if any file was sent
        if 'files[]' not in request.files:
            return jsonify({"error": "No files provided"}), 400

        files = request.files.getlist('files[]')
        if not files:
            return jsonify({"error": "No files selected"}), 400

        uploaded_files = []
        for file in files:
            if file and allowed_file(file.filename):
                # Secure the filename and generate unique ID
                filename = secure_filename(file.filename)
                file_id = str(uuid.uuid4())
                
                # Create grievance-specific directory
                grievance_dir = os.path.join(UPLOAD_FOLDER, grievance_id)
                if not os.path.exists(grievance_dir):
                    os.makedirs(grievance_dir)
                
                # Save file
                file_path = os.path.join(grievance_dir, f"{file_id}_{filename}")
                file.save(file_path)
                
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Store file metadata in database
                file_data = {
                    'file_id': file_id,
                    'grievance_id': grievance_id,
                    'file_name': filename,
                    'file_path': file_path,
                    'file_type': filename.rsplit('.', 1)[1].lower(),
                    'file_size': file_size
                }
                
                # Save to database using DatabaseManager
                if db_manager.store_file_attachment(file_data):
                    uploaded_files.append({
                        'file_id': file_id,
                        'filename': filename,
                        'file_size': file_size
                    })
                else:
                    # If database storage fails, delete the file
                    os.remove(file_path)
                    logger.error(f"Failed to store file metadata in database: {filename}")

        if uploaded_files:
            return jsonify({
                "message": "Files uploaded successfully",
                "files": uploaded_files
            }), 200
        else:
            return jsonify({"error": "No files were uploaded"}), 400

    except Exception as e:
        logger.error(f"Error uploading files: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/files/<grievance_id>', methods=['GET'])
def get_files(grievance_id):
    """Get list of files for a grievance"""
    try:
        files = db_manager.get_grievance_files(grievance_id)
        return jsonify({"files": files}), 200
    except Exception as e:
        logger.error(f"Error retrieving files: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

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