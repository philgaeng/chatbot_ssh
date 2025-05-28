import logging
import eventlet
from flask_socketio import SocketIO
from flask import request

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('socketio')
logger.setLevel(logging.DEBUG)

# Define Socket.IO path constant
SOCKETIO_PATH = '/accessible-socket.io'

# Create a socketio instance that can be imported by other modules
socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins="*",
    engineio_logger=True,
    logger=True,
    ping_timeout=3600,  # Match Nginx proxy_read_timeout
    ping_interval=25000,  # Keep existing ping interval
    path=SOCKETIO_PATH,  # Match Nginx location path
    log_output=True,
    debug=True
)

def emit_status_update(session_id, status, message=None):
    """Emit status update to the client."""
    try:
        logger.debug(f"Emitting status update - Session: {session_id}, Status: {status}, Message: {message}")
        socketio.emit('status_update', {
            'status': status,
            'message': message
        }, room=session_id)
    except Exception as e:
        logger.error(f"Error emitting status update: {str(e)}", exc_info=True) 