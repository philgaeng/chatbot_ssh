from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', path='/socket.io', message_queue='redis://:password@localhost:6379/0')

@socketio.on('connect')
def test_connect():
    print('Client connected')


if __name__ == '__main__':
    import eventlet
    import eventlet.wsgi
    socketio.run(app, host='0.0.0.0', port=5001)


