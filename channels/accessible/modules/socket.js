// Socket.IO CDN Configuration
export const SOCKET_IO_CDN_VERSION = '4.7.4';
export const SOCKET_IO_CDN_URL = `https://cdn.socket.io/${SOCKET_IO_CDN_VERSION}/socket.io.min.js`;


function loadSocketIoClient() {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = SOCKET_IO_CDN_URL;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

await loadSocketIoClient();

// Use the global 'io' provided by the CDN script
const socket = io('https://nepal-gms-chatbot.facets-ai.com', {
    path: '/accessible-socket.io',
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    timeout: 3600,
    pingInterval: 25000,
    pingTimeout: 3600,
    debug: true,
    forceNew: true
});

// Add detailed connection logging
socket.on('connect', () => {
    console.log('Socket.IO connected successfully');
    console.log('Transport:', socket.io.engine.transport.name);
    console.log('Protocol version:', socket.io.engine.protocol);
    console.log('Session ID:', socket.id);
    console.log('Current rooms:', socket.rooms); // Add this line
});

socket.on('connect_error', (error) => {
    console.error('Socket.IO connection error:', error);
    console.log('Transport:', socket.io.engine?.transport?.name);
    console.log('Protocol version:', socket.io.engine?.protocol);
});

socket.on('error', (error) => {
    console.error('Socket.IO error:', error);
});

socket.on('disconnect', (reason) => {
    console.log('Socket.IO disconnected:', reason);
});

// Send a test message
socket.emit('test', {message: 'Hello'}, (response) => {
    console.log('Test response:', response);
});


// Listen for all events
socket.onAny((eventName, ...args) => {
    console.log('Received event:', eventName, args);
    console.log('Current rooms:', socket.rooms); // Add this line
});

// Listen for status updates
socket.on('status_update', function(data) {
    console.log('Received status update:', data);
    console.log('Current rooms:', socket.rooms); // Add this line
    // Handle the status update
    if (data.status === 'submitted') {
        console.log('Grievance submitted:', data);
        // Update UI or show notification
    }
});

// Add room join confirmation
socket.on('room_joined', (room) => {
    console.log('Successfully joined room:', room);
    console.log('Current rooms:', socket.rooms);
});

// Export the socket instance
export default socket;
