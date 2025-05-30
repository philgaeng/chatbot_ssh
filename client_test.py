import socketio

# Use 'wss://' for secure connections, 'ws://' for local/non-SSL
sio = socketio.Client()

@sio.event
def connect():
    print("Connected to server!")
    sio.disconnect()

@sio.event
def connect_error(data):
    print("Connection failed:", data)

@sio.event
def disconnect():
    print("Disconnected from server.")

# Connect to your server
sio.connect(
    'https://nepal-gms-chatbot.facets-ai.com',
    socketio_path='/socket.io'
)