// Development Environment Configuration

// Server Configuration
const SERVER_CONFIG = {
    HOST: '54.255.219.233',  // Development server
    PORT: 5005,
    PATH: '/socket.io/',
    TRANSPORTS: ['websocket']
};

// WebSocket Configuration
const WEBSOCKET_CONFIG = {
    URL: `//${SERVER_CONFIG.HOST}:${SERVER_CONFIG.PORT}`,
    OPTIONS: {
        path: SERVER_CONFIG.PATH,
        transports: SERVER_CONFIG.TRANSPORTS
    }
};

// File Upload Configuration
const FILE_UPLOAD_CONFIG = {
    URL: 'http://localhost:5001/upload-files',  // Local development file server
    MAX_SIZE_MB: 10
};

// Session Configuration
const SESSION_CONFIG = {
    STORAGE_KEY: 'rasa_session_id',
    EXPIRY_DAYS: 7
};

// UI Configuration
const UI_CONFIG = {
    THEME: {
        PRIMARY_COLOR: '#4CAF50',
        SECONDARY_COLOR: '#2196F3',
        BACKGROUND_COLOR: '#f5f5f5',
        TEXT_COLOR: '#333333'
    },
    MESSAGES: {
        MAX_DISPLAY: 50,
        ANIMATION_DURATION: 300
    }
};

// Export configurations
export {
    SERVER_CONFIG,
    WEBSOCKET_CONFIG,
    SESSION_CONFIG,
    UI_CONFIG,
    FILE_UPLOAD_CONFIG
}; 