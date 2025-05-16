# Nepal Chatbot Scripts Documentation

This document explains how to use the various scripts in the Nepal Chatbot project.

## Directory Structure

```
scripts/
├── rasa/              # Rasa-related scripts
│   ├── install.sh     # Rasa installation script
│   ├── train.sh       # Rasa training script
│   └── config.sh      # Rasa configuration
├── servers/           # Server management scripts
│   ├── run_servers.py # Main server orchestration
│   └── config.json    # Server configuration
└── database/          # Database management scripts
    ├── init.py        # Database initialization
    └── migrate.py     # Database migrations
```

## Server Management

### Server Components

The Nepal Chatbot consists of several components:

1. **Rasa Action Server** (port 5055): Handles actions for the Rasa chatbot
2. **File Server** (port 5001): Handles file uploads and downloads
3. **Accessibility App** (port 5006): Provides an accessible interface for users
4. **Main Rasa Server** (port 5005): Handles the core chatbot functionality
5. **Database**: PostgreSQL database used by all components

### Running Servers

The easiest way to run all components is using the `run_servers.py` script:

```bash
# First kill any existing processes
pkill -f run_servers.py; sleep 2

# Then start all servers
python3 run_servers.py --all
```

#### Configuration Options

The server can be configured in three ways (in order of precedence):

1. **Command Line Arguments**:
   ```bash
   python run_servers.py --all \
     --file-server-port 5002 \
     --accessibility-port 5007 \
     --rasa-action-port 5056 \
     --rasa-server-port 5006 \
     --log-retention 30
   ```

2. **Configuration File** (JSON):
   ```json
   {
     "file_server_port": 5001,
     "accessibility_port": 5006,
     "rasa_action_port": 5055,
     "rasa_server_port": 5005,
     "log_retention_days": 90,
     "max_memory_percent": 80,
     "max_cpu_percent": 90,
     "max_disk_percent": 90
   }
   ```

3. **Environment Variables**:
   ```bash
   export FILE_SERVER_PORT=5001
   export ACCESSIBILITY_PORT=5006
   export RASA_ACTION_PORT=5055
   export RASA_SERVER_PORT=5005
   export LOG_RETENTION_DAYS=90
   ```

#### Command Line Options

```bash
# Skip database initialization
python run_servers.py --all --skip-db-init

# Run only specific servers
python run_servers.py --file-server-only
python run_servers.py --accessibility-only
python run_servers.py --rasa-action-only
python run_servers.py --rasa-server-only

# Use a configuration file
python run_servers.py --all --config config.json
```

## Rasa Management

### Installation

To install Rasa and its dependencies:

```bash
cd scripts/rasa
./install.sh
```

This will:
1. Create a Python virtual environment
2. Install Rasa and required packages
3. Download spaCy models
4. Set up necessary directories

### Training

To train the Rasa model:

```bash
cd scripts/rasa
./train.sh
```

The training script will:
1. Start an AWS instance for training
2. Sync training files
3. Run the training process
4. Copy the trained model back
5. Stop the AWS instance

#### Training Configuration

Configure training parameters in `config.sh`:
```bash
# Training parameters
TRAIN_BATCH_SIZE=4
TRAIN_EPOCHS=100
TRAIN_TIMEOUT=3600  # 1 hour

# AWS configuration
TRAIN_INSTANCE_ID="i-xxxxxxxxxxxxxxxxx"
KEY_FILE="~/.ssh/nepal-chatbot.pem"
```

## Database Management

### Initialization

To initialize the database:

```bash
cd scripts/database
python init.py
```

This will:
1. Create necessary tables
2. Set up indexes
3. Initialize required data

### Migrations

To run database migrations:

```bash
cd scripts/database
python migrate.py
```

## Logging

Logs are stored in the `logs/` directory with separate files for each component:

- `server_manager.log`: Main server management logs
- `rasa_server.log`: Main Rasa server logs
- `actions_server.log`: Rasa action server logs
- `file_server.log`: File server logs
- `accessible_server.log`: Accessibility app logs

Log rotation is configured to:
- Rotate daily
- Keep logs for 90 days by default
- Maximum file size of 100MB
- Maximum of 5 backup files

## File Management

### Uploads Directory

The system stores uploaded files in the `uploads/` directory:

```bash
# Create directory structure for uploads
mkdir -p uploads/voice_recordings

# Set appropriate permissions
chmod -R 775 uploads
chown -R ubuntu:www-data uploads
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**:
   ```bash
   # Check what's using a specific port
   sudo lsof -i:5001

   # Kill process using port
   sudo fuser -k 5001/tcp
   ```

2. **Database Issues**:
   ```bash
   # Check database connection
   sudo -u postgres psql
   \c grievance_db
   \dt
   
   # Check database logs
   sudo tail -f /var/log/postgresql/postgresql-*.log
   ```

3. **Rasa Issues**:
   ```bash
   # Check Rasa logs
   tail -f logs/rasa_server.log
   tail -f logs/actions_server.log
   
   # Verify Rasa installation
   rasa --version
   python -c "import rasa; print(rasa.__version__)"
   ```

4. **Permission Issues**:
   ```bash
   # Fix permissions
   sudo chown -R ubuntu:www-data /home/ubuntu/nepal_chatbot
   sudo chmod -R 775 /home/ubuntu/nepal_chatbot
   sudo chmod g+s /home/ubuntu/nepal_chatbot
   ```

## Production Deployment

For production environments:

1. **Configure Nginx** to proxy requests to the appropriate server ports
2. **Set up proper permissions** for the www-data user
3. **Enable HTTPS** using Let's Encrypt
4. **Configure startup scripts** for automatic server startup

### Nginx Configuration

```nginx
# Example Nginx configuration
server {
    listen 80;
    server_name chatbot.example.com;

    location / {
        proxy_pass http://localhost:5005;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /actions {
        proxy_pass http://localhost:5055;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /accessible {
        proxy_pass http://localhost:5006;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Development Workflow

1. **Making Changes**:
   - Update Rasa files in the project root
   - Update server code in `actions_server/`
   - Update accessible interface in `channels/accessible/`

2. **Testing Changes**:
```bash
   # Start all servers
   python run_servers.py --all
   
   # Test Rasa
   rasa test
   
   # Test API endpoints
   curl http://localhost:5005/webhooks/rest/webhook
   ```

3. **Deploying Changes**:
   ```bash
   # Train new model
   ./train.sh
   
   # Restart servers
   pkill -f run_servers.py
   python run_servers.py --all
   ``` 