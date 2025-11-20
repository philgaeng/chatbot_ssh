
from flask_socketio import SocketIO
from flask import request
import os
from backend.logger.logger import TaskLogger
from backend.config.constants import FIELD_CATEGORIES_MAPPING

# Create a task logger instance for socketio
task_logger = TaskLogger(service_name='socketio')
logger = task_logger.logger

# Define Socket.IO path constant
# Flask SocketIO path WITHOUT trailing slash (Flask SocketIO requirement)
SOCKETIO_PATH = '/accessible-socket.io'

# Use SOCKETIO_REDIS_URL from environment, default to DB 0
SOCKETIO_REDIS_URL = os.getenv('SOCKETIO_REDIS_URL', 'redis://localhost:6379/0')
logger.debug(f"Initializing Socket.IO with Redis - redis_url: {SOCKETIO_REDIS_URL} - env_redis_url: {os.getenv('SOCKETIO_REDIS_URL')} - env_redis_password: {'REDIS_PASSWORD' in os.environ}")

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
    transports=['websocket', 'polling']  # Allow both WebSocket and polling (client will upgrade to WebSocket)
)

# Add connection event handlers
@socketio.on('connect')
def handle_connect():
    logger.debug("Client connected", extra_data={"sid": request.sid})
    logger.debug(f"Transport: {request.environ.get('socketio').transport}")
    logger.debug(f"Protocol version: {request.environ.get('socketio').protocol}")
    # Log request headers for debugging Host/domain issues
    logger.debug(f"Host header: {request.headers.get('Host', 'NOT SET')}")
    logger.debug(f"X-Forwarded-Host: {request.headers.get('X-Forwarded-Host', 'NOT SET')}")
    logger.debug(f"X-Real-IP: {request.headers.get('X-Real-IP', 'NOT SET')}")
    logger.debug(f"X-Forwarded-Proto: {request.headers.get('X-Forwarded-Proto', 'NOT SET')}")
    logger.debug(f"Origin: {request.headers.get('Origin', 'NOT SET')}")
    logger.debug(f"Request path: {request.path}")
    logger.debug(f"Request url: {request.url}")

@socketio.on('join')
def on_join(data):
    room = data.get('room')
    if room:
        logger.debug("Client joining room", extra_data={"sid": request.sid, "room": room})
        socketio.join_room(room)
        logger.debug(f"Client {request.sid} joined room: {room}")

@socketio.on('disconnect')
def handle_disconnect():
    logger.debug("Client disconnected", extra_data={"sid": request.sid})

@socketio.on('error')
def handle_error(error):
    logger.debug(message="error", extra_data={"error": str(error)})

def emit_status_update_accessible(session_id, status, message):
    """Emit a status update to a specific session"""
    try:
        logger.debug(
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
        
        logger.debug(f"Status update emitted successfully - session_id: {session_id}")
        logger.debug(f"Event emitted to room: {session_id}")
    except Exception as e:
        logger.debug(message="Failed to emit event to room", extra_data={"session_id": session_id, "error": str(e)})
        logger.error(f"Failed to emit event to room {session_id}: {str(e)}", exc_info=True) 

