"""
Development WebChat Config Generator
This script generates webchat config from env.local for WSL development environment
"""

import os

def parse_env_file(path):
    config = {}
    with open(path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

env_path = '.env'  # Updated to use .env file
config = parse_env_file(env_path)

# For production, use the domain from environment or detect from hostname
# If RASA_HOST is localhost but we're on production, use window.location for dynamic detection
host = config.get('RASA_HOST', 'localhost')
port = config.get('RASA_PORT', '5005')
path = config.get('RASA_WS_PATH', '/socket.io/')
protocol = config.get('RASA_API_PROTOCOL', 'http')
transports = config.get('RASA_WS_TRANSPORTS', 'websocket').split(',')

protocol_upload = config.get('FILE_UPLOAD_PROTOCOL', 'http')
port_upload = config.get('PORT_UPLOAD', ':5001')
file_upload_path = config.get('FILE_UPLOAD_PATH', '/upload-files')
file_upload_max_size = config.get('FILE_UPLOAD_MAX_SIZE_MB', '10')

# Production domain - use this when accessed via HTTPS
production_domain = config.get('PRODUCTION_DOMAIN', '')

session_key = config.get('SESSION_STORAGE_KEY', 'rasa_session_id')
session_expiry = config.get('SESSION_EXPIRY_DAYS', '7')

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_js_path = os.path.join(project_root, 'channels', 'webchat', 'config.js')

with open(config_js_path, 'w') as f:
    f.write(f"""// Configuration Loader
// This script is auto-generated from .env

// Server Configuration
const SERVER_CONFIG = {{
    HOST: '{host}',
    PORT: {port},
    PATH: '{path}',
    TRANSPORTS: {transports}
}};

// WebSocket Configuration
// Use window.location for dynamic host detection in browser
// This allows the same config to work in both localhost and production
const getWebSocketUrl = () => {{
    // If accessed via HTTPS, use wss:// and current domain (no port needed if proxied)
    if (window.location.protocol === 'https:') {{
        return `wss://${{window.location.hostname}}`;
    }}
    // For localhost/HTTP, use the configured host and port
    return `{protocol}://{host}:{port}`;
}};

const WEBSOCKET_CONFIG = {{
    URL: getWebSocketUrl(),
    OPTIONS: {{
        path: '{path}',
        transports: {transports}
    }}
}};

// File Upload Configuration
// Use window.location for dynamic host detection
const getFileUploadUrl = () => {{
    if (window.location.protocol === 'https:') {{
        return `https://${{window.location.hostname}}{file_upload_path}`;
    }}
    return `{protocol_upload}://{host}{port_upload}{file_upload_path}`;
}};

const FILE_UPLOAD_CONFIG = {{
    URL: getFileUploadUrl(),
    MAX_SIZE_MB: {file_upload_max_size}
}};

// Flask Socket Configuration (for file upload status)
// Flask socket is proxied via nginx at /accessible-socket.io/ path
const getFlaskSocketUrl = () => {{
    if (window.location.protocol === 'https:') {{
        return `wss://${{window.location.hostname}}`;
    }}
    return `{protocol_upload}://{host}{port_upload}`;
}};

const FLASK_SOCKET_CONFIG = {{
    URL: getFlaskSocketUrl(),
    OPTIONS: {{
        path: '/accessible-socket.io/',  // Flask socket path via nginx proxy
        transports: ['websocket']
    }}
}};

// Session Configuration
const SESSION_CONFIG = {{
    STORAGE_KEY: '{session_key}',
    EXPIRY_DAYS: {session_expiry}
}};

// UI Configuration (not auto-generated, keep in code)
import {{ UI_CONFIG }} from './ui_config.js';

// Export configurations
export {{
    SERVER_CONFIG,
    WEBSOCKET_CONFIG,
    SESSION_CONFIG,
    UI_CONFIG,
    FILE_UPLOAD_CONFIG,
    FLASK_SOCKET_CONFIG
}};
""")
