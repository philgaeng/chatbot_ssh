#!/bin/bash

# Database Configuration
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="nepal_chatbot"
DB_USER="postgres"
DB_PASSWORD="postgres"

# Connection Settings
DB_CONNECTION_TIMEOUT=30
DB_CONNECTION_RETRIES=3
DB_CONNECTION_DELAY=5

# Backup Configuration
BACKUP_DIR="backups"
BACKUP_RETENTION_DAYS=7
BACKUP_COMPRESSION=true

# Logging Configuration
LOG_DIR="logs"
LOG_MAX_SIZE_MB=100
LOG_MAX_FILES=5
LOG_FORMAT="json"  # or "text"

# Directory Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Health Check Configuration
HEALTH_CHECK_TIMEOUT=30
HEALTH_CHECK_RETRIES=3
HEALTH_CHECK_DELAY=5

# Error Patterns to Monitor
ERROR_PATTERNS=(
    "connection refused"
    "authentication failed"
    "database does not exist"
    "permission denied"
    "duplicate key value"
    "deadlock detected"
    "timeout expired"
    "could not connect"
)

# Export all variables
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
export DB_CONNECTION_TIMEOUT DB_CONNECTION_RETRIES DB_CONNECTION_DELAY
export BACKUP_DIR BACKUP_RETENTION_DAYS BACKUP_COMPRESSION
export LOG_DIR LOG_MAX_SIZE_MB LOG_MAX_FILES LOG_FORMAT
export SCRIPT_DIR PROJECT_ROOT
export HEALTH_CHECK_TIMEOUT HEALTH_CHECK_RETRIES HEALTH_CHECK_DELAY
export ERROR_PATTERNS 