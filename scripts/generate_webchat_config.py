import os

def parse_env_file(path):
    config = {}
    with open(path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

env_path = 'env.local'  # Adjust if needed
config = parse_env_file(env_path)

host = config.get('RASA_WS_HOST', 'localhost')
port = config.get('RASA_WS_PORT', '5005')
path = config.get('RASA_WS_PATH', '/socket.io/')
protocol = config.get('RASA_WS_PROTOCOL', 'ws')
transports = config.get('RASA_WS_TRANSPORTS', 'websocket').split(',')

file_upload_path = config.get('FILE_UPLOAD_PATH', '/upload-files')
file_upload_max_size = config.get('FILE_UPLOAD_MAX_SIZE_MB', '10')

session_key = config.get('SESSION_STORAGE_KEY', 'rasa_session_id')
session_expiry = config.get('SESSION_EXPIRY_DAYS', '7')

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_js_path = os.path.join(project_root, 'channels', 'webchat', 'config.js')

with open(config_js_path, 'w') as f:
    f.write(f"""// Configuration Loader
// This script is auto-generated from env.local

// Server Configuration
const SERVER_CONFIG = {{
    HOST: '{host}',
    PORT: {port},
    PATH: '{path}',
    TRANSPORTS: {transports}
}};

// WebSocket Configuration
const WEBSOCKET_CONFIG = {{
    URL: `{protocol}://{host}:{port}`, // TODO: check if the port is required when using on remote server
    OPTIONS: {{
        path: '{path}',
        transports: {transports}
    }}
}};

// File Upload Configuration
const FILE_UPLOAD_CONFIG = {{
    URL: `{protocol}://{host}{file_upload_path}`,
    MAX_SIZE_MB: {file_upload_max_size}
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
    FILE_UPLOAD_CONFIG
}};
""")
