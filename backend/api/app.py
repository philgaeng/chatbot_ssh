import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_cors import CORS
from backend.api.channels_api import FileServerAPI
from backend.services.file_server_core import FileServerCore
from backend.services.accessible.voice_grievance import voice_grievance_bp
from backend.api.websocket_utils import socketio, emit_status_update_accessible
from backend.config.constants import ALLOWED_EXTENSIONS
from backend.api.gsheet_monitoring_api import gsheet_monitoring_bp
import os
from backend.logger.logger import TaskLogger
from flask_socketio import join_room, rooms

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio.init_app(app)

# Initialize core and API instances
file_server_core = FileServerCore(
    upload_folder=os.getenv('UPLOAD_FOLDER', 'uploads'),
    allowed_extensions=ALLOWED_EXTENSIONS
)
file_server = FileServerAPI(core=file_server_core)

# Register blueprints
app.register_blueprint(file_server.blueprint)
app.register_blueprint(voice_grievance_bp)
app.register_blueprint(gsheet_monitoring_bp)

# Make the function available to the file_server blueprint
file_server.blueprint.emit_status_update_accessible = emit_status_update_accessible

# === Add these handlers here ===

task_logger = TaskLogger(service_name='socketio')

def log_event(event, data):
    task_logger.log_event(f"[SOCKETIO] Event: {event}, Data: {data}")

@socketio.on('status_update')
def handle_status_update(data):
    log_event('status_update', data)
    # Re-emit the event to ensure the client receives it
    socketio.emit('status_update', data, room=data.get('session_id', request.sid))
    task_logger.log_event("Re-emitted status update to client", extra_data={"data": data})

@socketio.on('another_event')
def handle_another_event(data):
    log_event('another_event', data)

@socketio.on_error()
def error_handler(e):
    task_logger.logger.error(f"[SOCKETIO] Error: {e}")

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room')
    if room:
        join_room(room)
        print(f"Client {request.sid} joined room: {room}")
        print(f"Rooms for {request.sid}: {rooms(request.sid)}")
        # Confirm to client
        socketio.emit('room_joined', room, room=request.sid)

# === End handlers ===

@app.route('/health')
def health():
    return 'OK', 200



if __name__ == '__main__':
    import eventlet
    import eventlet.wsgi
    socketio.run(app, host='0.0.0.0', port=5001)


