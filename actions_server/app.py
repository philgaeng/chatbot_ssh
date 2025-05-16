from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from actions_server.file_server import file_server_bp
from accessible_server.voice_grievance import voice_grievance_bp
from task_queue.task_status import get_task_status, get_task_info

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Register blueprints
app.register_blueprint(file_server_bp)
app.register_blueprint(voice_grievance_bp)

# Provide the emit_status_update function to file_server
def emit_status_update(grievance_id, status, data):
    """Emit status updates through WebSocket"""
    socketio.emit('grievance_status_update', {
        'grievance_id': grievance_id,
        'status': status,
        'data': data
    }, room=grievance_id)

# Make the function available to the file_server blueprint
file_server_bp.emit_status_update = emit_status_update

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)


