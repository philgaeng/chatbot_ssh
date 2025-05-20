from flask_socketio import SocketIO

# Create a socketio instance that can be imported by other modules
socketio = SocketIO()

def emit_status_update(grievance_id, status, data):
    """Emit status updates through WebSocket"""
    socketio.emit('grievance_status_update', {
        'grievance_id': grievance_id,
        'status': status,
        'data': data
    }, room=grievance_id) 