import logging
import eventlet
import traceback
import socketio
import time
from actions_server.websocket_utils import socketio as server_socketio, SOCKETIO_PATH

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('socketio')
logger.setLevel(logging.DEBUG)


# Create a Socket.IO client with detailed configuration
sio = socketio.Client(
    logger=True,
    engineio_logger=True
)

@sio.event
def connect():
    logger.debug("Connection established")
    print('\n=== Connection Established ===')
    print('Transport:', sio.transport())
    if hasattr(sio, 'eio') and hasattr(sio.eio, 'protocol'):
        print('Protocol version:', sio.eio.protocol)
    print('Session ID:', sio.sid)
    print('===========================\n')

@sio.event
def connect_error(error):
    logger.error(f"Connection error: {error}")
    print('\n=== Connection Error ===')
    print('Error:', error)
    print('Transport:', sio.transport())
    if hasattr(sio, 'eio') and hasattr(sio.eio, 'protocol'):
        print('Protocol version:', sio.eio.protocol)
    print('Full error details:')
    traceback.print_exc()
    print('===========================\n')

@sio.event
def disconnect(reason):
    logger.debug(f"Disconnected: {reason}")
    print('\n=== Disconnected ===')
    print('Reason:', reason)
    print('===========================\n')

@sio.event
def message(data):
    logger.debug(f"Received message: {data}")
    print('\n=== Received Message ===')
    print('Data:', data)
    print('===========================\n')

@sio.event
def status_update(data):
    logger.debug(f"Received status update: {data}")
    print('\n=== Status Update ===')
    print('Status:', data.get('status'))
    print('Message:', data.get('message'))
    print('===========================\n')

@sio.on('*')
def catch_all(event, data):
    logger.debug(f"Received event {event}: {data}")
    print(f'\n=== Received Event: {event} ===')
    print('Data:', data)
    print('===========================\n')

def test_connection():
    """Test basic connection and message exchange"""
    try:
        # Connect to the test server
        server_url = 'http://localhost:5001'
        print(f'\nAttempting to connect to {server_url}')
        print(f'Using Socket.IO path: {SOCKETIO_PATH}')
        
        # First try to connect to the default namespace
        print('\nConnecting to default namespace...')
        sio.connect(server_url, 
                   transports=['websocket'],
                   wait_timeout=10,
                   socketio_path=SOCKETIO_PATH,
                   namespaces=['/']
                   )  # Temporarily disable SSL verification for testing
        
        # Send a test message to the default namespace
        print('\nSending test message to default namespace...')
        sio.emit('test', {'message': 'Hello from test client'}, namespace='/')
        
        # Send a status update test
        print('\nSending status update test...')
        sio.emit('status_update', {
            'status': 'testing',
            'message': 'Testing status updates'
        }, namespace='/')
        
        # Keep the connection alive for a while to test ping/pong
        print('\nConnection established. Press Ctrl+C to exit...')
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
    except Exception as e:
        print('\nError during test:')
        print('Error:', e)
        print('Full error details:')
        traceback.print_exc()
    finally:
        print('\nDisconnecting...')
        sio.disconnect()

if __name__ == '__main__':
    test_connection() 