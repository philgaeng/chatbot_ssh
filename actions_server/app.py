from flask import Flask
from flask_cors import CORS
from actions_server.file_server_api import FileServerAPI, file_server_bp
from actions_server.file_server_core import FileServerCore
from accessible_server.voice_grievance import voice_grievance_bp
from actions_server.websocket_utils import socketio, emit_status_update
from actions_server.constants import ALLOWED_EXTENSIONS
import os

app = Flask(__name__)
CORS(app)
socketio.init_app(app, cors_allowed_origins="*")

# Initialize core and API instances
file_server_core = FileServerCore(
    upload_folder=os.getenv('UPLOAD_FOLDER', 'uploads'),
    allowed_extensions=ALLOWED_EXTENSIONS
)
file_server = FileServerAPI(core=file_server_core)

# Register blueprints
app.register_blueprint(file_server_bp)
app.register_blueprint(voice_grievance_bp)

# Make the function available to the file_server blueprint
file_server_bp.emit_status_update = emit_status_update

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)


