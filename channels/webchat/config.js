// Configuration Loader
// This script is auto-generated from env.local

// Server Configuration
const SERVER_CONFIG = {
    HOST: 'localhost',
    PORT: 5005,
    PATH: '/socket.io/',
    TRANSPORTS: ['websocket']
};

// WebSocket Configuration
const WEBSOCKET_CONFIG = {
    URL: `http://localhost:5005`, // TODO: check if the port is required when using on remote server
    OPTIONS: {
        path: '/socket.io/',
        transports: ['websocket']
    }
};

// File Upload Configuration
const FILE_UPLOAD_CONFIG = {
    URL: `http://localhost:5001/upload-files`,
    MAX_SIZE_MB: 10
};

// Session Configuration
const SESSION_CONFIG = {
    STORAGE_KEY: 'rasa_session_id',
    EXPIRY_DAYS: 7
};

// UI Configuration (not auto-generated, keep in code)
import { UI_CONFIG } from './ui_config.js';

// Export configurations
export {
    SERVER_CONFIG,
    WEBSOCKET_CONFIG,
    SESSION_CONFIG,
    UI_CONFIG,
    FILE_UPLOAD_CONFIG
};
