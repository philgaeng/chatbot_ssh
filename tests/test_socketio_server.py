from actions_server.app import app, socketio
from flask import request
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('socketio')
logger.setLevel(logging.DEBUG)

@socketio.on('connect', namespace='/')
def on_connect():
    logger.debug(f"Connection request received from {request.sid}")
    print('\n=== Client Connected ===')
    print('Client connected to default namespace')
    print('Session ID:', request.sid)
    print('===========================\n')

@socketio.on('disconnect', namespace='/')
def on_disconnect():
    logger.debug(f"Disconnection request received from {request.sid}")
    print('\n=== Client Disconnected ===')
    print('Client disconnected from default namespace')
    print('===========================\n')

@socketio.on('test', namespace='/')
def on_test(data):
    logger.debug(f"Test message received from {request.sid}: {data}")
    print('\n=== Received Test Message ===')
    print('Data:', data)
    print('Session ID:', request.sid)
    print('Emitting response...')
    try:
        socketio.emit('message', {'response': 'Server received your test message'}, namespace='/')
        logger.debug(f"Response emitted to {request.sid}")
    except Exception as e:
        logger.error(f"Error emitting response: {str(e)}", exc_info=True)
    print('===========================\n')

@socketio.on('status_update', namespace='/')
def on_status_update(data):
    logger.debug(f"Status update received from {request.sid}: {data}")
    print('\n=== Received Status Update ===')
    print('Status:', data.get('status'))
    print('Message:', data.get('message'))
    print('Session ID:', request.sid)
    print('===========================\n')

if __name__ == '__main__':
    import eventlet
    import eventlet.wsgi
    print('Starting Socket.IO server on port 5001...')
    socketio.run(app, host='0.0.0.0', port=5001, debug=True) 