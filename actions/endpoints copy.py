import os
import sys

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from actions.update_location_copy import update_constants_file
from actions.constants import BASE_URL, SOCKET_URL, WS_URL
from engineio.async_drivers import gevent

# Initialize Flask app
app = Flask(__name__)

# Allow CORS for all routes with proper WebSocket support
CORS(app, resources={
    r"/*": {
        "origins": "*",  # Allow all origins for development
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Initialize Socket.IO with proper WebSocket configuration
socketio = SocketIO(
    app,
    cors_allowed_origins="*",  # Allow all origins for development
    async_mode='gevent',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    transports=['websocket'],
    always_connect=True,
    manage_session=True
)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    session_id = request.args.get('session_id')
    print(f'Client connected with session ID: {session_id}')
    socketio.emit('connect_response', {'status': 'connected', 'session_id': session_id})
    return {'status': 'connected'}

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('session_request')
def handle_session_request(data):
    """Handle session initialization request"""
    print('Session request:', data)
    socketio.emit('session_confirm', {'status': 'ok', 'session_id': data.get('session_id')})
    return {'status': 'ok'}

@socketio.on('user_uttered')
def handle_message(data):
    """Handle incoming user messages"""
    print('Received message:', data)
    try:
        # Echo back the message for testing
        response = {
            'text': f"I received your message: {data.get('message')}",
            'quick_replies': []
        }
        socketio.emit('bot_uttered', response, room=request.sid)
    except Exception as e:
        print(f"Error handling message: {e}")
        socketio.emit('bot_uttered', {
            'text': "Sorry, there was an error processing your message.",
            'quick_replies': []
        }, room=request.sid)

@app.route('/update_location', methods=['POST', 'OPTIONS'])
def update_location():
    """Handle location updates"""
    # Handle preflight requests
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    try:
        data = request.get_json()
        province = data.get('province')
        district = data.get('district')
        
        if not province or not district:
            return jsonify({
                'success': False,
                'error': 'Province and district are required'
            }), 400
        
        success = update_constants_file(province, district)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Updated location to {province}, {district}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update constants file'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print(f"Starting server on {SOCKET_URL}")
    # Use socketio.run instead of app.run
    socketio.run(
        app,
        host='0.0.0.0',
        port=5005,
        allow_unsafe_werkzeug=True,
        debug=True,
        use_reloader=False,  # Disable reloader in production
        log_output=True
    ) 