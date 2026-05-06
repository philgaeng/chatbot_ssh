// Configuration Loader
// This script is auto-generated from env.local

// Server Configuration
const SERVER_CONFIG = {
    HOST: 'localhost',
    PORT: 8082,
    PATH: '/socket.io/',
    TRANSPORTS: ['websocket']
};

// Orchestrator Configuration - use relative URL so API calls go through same host (works with localhost or WSL IP)
const ORCHESTRATOR_CONFIG = {
    URL: '/message'
};

// File Upload Configuration - use relative URL (nginx proxies to backend)
const FILE_UPLOAD_CONFIG = {
    URL: '/upload-files',
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
    SESSION_CONFIG,
    UI_CONFIG,
    FILE_UPLOAD_CONFIG,
    ORCHESTRATOR_CONFIG
};
