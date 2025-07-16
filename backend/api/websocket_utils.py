
from flask_socketio import SocketIO
from flask import request
import os
from backend.logger.logger import TaskLogger
from backend.config.constants import FIELD_CATEGORIES_MAPPING

# Create a task logger instance for socketio
task_logger = TaskLogger(service_name='socketio')
logger = task_logger.logger

# Define Socket.IO path constant
SOCKETIO_PATH = '/accessible-socket.io'

# Use SOCKETIO_REDIS_URL from environment, default to DB 0
SOCKETIO_REDIS_URL = os.getenv('SOCKETIO_REDIS_URL', 'redis://localhost:6379/0')
task_logger.log_event(f"Initializing Socket.IO with Redis - redis_url: {SOCKETIO_REDIS_URL} - env_redis_url: {os.getenv('SOCKETIO_REDIS_URL')} - env_redis_password: {'REDIS_PASSWORD' in os.environ}")

# Create a socketio instance that can be imported by other modules
socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins="*",
    engineio_logger=True,
    logger=True,
    ping_timeout=3600,
    ping_interval=25000,
    path=SOCKETIO_PATH,
    log_output=True,
    debug=True,
    message_queue=SOCKETIO_REDIS_URL,
    transports=['websocket']  # Force WebSocket transport only
)

# Add connection event handlers
@socketio.on('connect')
def handle_connect():
    task_logger.log_event("Client connected", extra_data={"sid": request.sid})
    logger.debug(f"Transport: {request.environ.get('socketio').transport}")
    logger.debug(f"Protocol version: {request.environ.get('socketio').protocol}")

@socketio.on('join')
def on_join(data):
    room = data.get('room')
    if room:
        task_logger.log_event("Client joining room", extra_data={"sid": request.sid, "room": room})
        socketio.join_room(room)
        logger.debug(f"Client {request.sid} joined room: {room}")

@socketio.on('disconnect')
def handle_disconnect():
    task_logger.log_event("Client disconnected", extra_data={"sid": request.sid})

@socketio.on('error')
def handle_error(error):
    task_logger.log_event(message="error", extra_data={"error": str(error)})

def emit_status_update_accessible(session_id, status, message):
    """Emit a status update to a specific session"""
    try:
        task_logger.log_event(
            f"Emitting status update - session_id: {session_id} - status: {status} - message: {message} - message_queue_url: {SOCKETIO_REDIS_URL}"
        )
        logger.debug(f"SocketIO instance: {socketio}")
        logger.debug(f"Redis URL: {SOCKETIO_REDIS_URL}")
        logger.debug(f"Room to emit to: {session_id}")
        emit_key = 'status_update'
        # Emit the event
        #prepare emit key based on operation or field name
        emit_key = 'status_update'
        #prepare emit key based on operation or field nam
        if isinstance(message, dict):
            if 'operation' in message.keys():
                operation = message['operation']
                emit_key = f'status_update:{operation}'
            else:
                for k in message.keys():
                    operation = FIELD_CATEGORIES_MAPPING.get(k, None)
                    if operation:
                        emit_key = f'status_update:{operation}'
                        break
                    
        socketio.emit(emit_key, {
            'status': status,
            'message': message,
            'session_id': session_id
        }, room=session_id)
        
        task_logger.log_event(f"Status update emitted successfully - session_id: {session_id}")
        logger.debug(f"Event emitted to room: {session_id}")
    except Exception as e:
        task_logger.log_event(message="Failed to emit event to room", extra_data={"session_id": session_id, "error": str(e)})
        logger.error(f"Failed to emit event to room {session_id}: {str(e)}", exc_info=True) 

