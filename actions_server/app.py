from flask import Flask, request, jsonify, send_from_directory
import os
import sys
import logging
import traceback
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Add parent directory to path to allow importing from shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import shared modules
from actions_server.db_manager import db_manager
from accessible_server.voice_grievance import register_voice_endpoints
from actions_server.file_server import allowed_file, ALLOWED_EXTENSIONS, MAX_FILE_SIZE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'channels', 'accessible'),
            static_url_path='')

# Configure uploads folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Configure allowed audio extensions
AUDIO_EXTENSIONS = {'webm', 'mp3', 'wav', 'ogg', 'm4a'}
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB max size for audio files

# Load environment variables
load_dotenv()

# Register voice endpoints from voice_grievance.py
register_voice_endpoints(app)

# Serve static files
@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

# File upload endpoint
@app.route('/upload-files', methods=['POST'])
def upload_files():
    from actions_server.file_server import upload_files as file_server_upload_files
    return file_server_upload_files()

# Get files endpoint
@app.route('/files/<grievance_id>', methods=['GET'])
def get_files(grievance_id):
    from actions_server.file_server import get_files as file_server_get_files
    return file_server_get_files(grievance_id)

# Download file endpoint
@app.route('/download/<file_id>', methods=['GET'])
def download_file(file_id):
    from actions_server.file_server import download_file as file_server_download_file
    return file_server_download_file(file_id)

if __name__ == '__main__':
    port = int(os.environ.get('ACCESSIBLE_PORT', 5006))
    app.run(host='0.0.0.0', port=port, debug=True) 