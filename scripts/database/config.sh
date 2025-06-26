#!/bin/bash

# Load database configuration from environment files
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Try to load environment variables from available files
ENV_LOCAL="$PROJECT_ROOT/env.local"
ENV_FILE="$PROJECT_ROOT/.env"

# Determine which environment file to use
if [ -f "$ENV_LOCAL" ]; then
    echo "Loading database configuration from $ENV_LOCAL (development)"
    source "$ENV_LOCAL"
    ENV_SOURCE="env.local"
elif [ -f "$ENV_FILE" ]; then
    echo "Loading database configuration from $ENV_FILE (production/remote)"
    source "$ENV_FILE"
    ENV_SOURCE=".env"
else
    echo "Warning: No environment file found, using default database configuration"
    ENV_SOURCE="default"
fi

# Map environment variables to config variables (works for both env.local and .env)
if [ "$ENV_SOURCE" != "default" ]; then
    # Map environment variables to config variables
    DB_HOST="${POSTGRES_HOST:-localhost}"
    DB_PORT="${POSTGRES_PORT:-5432}"
    DB_NAME="${POSTGRES_DB:-grievance_db}"
    DB_USER="${POSTGRES_USER:-nepal_grievance_admin}"
    DB_PASSWORD="${POSTGRES_PASSWORD:-K9!mP2$vL5nX8&qR4jW7}"
else
    # Fallback to default values
    DB_HOST="localhost"
    DB_PORT="5432"
    DB_NAME="grievance_db"
    DB_USER="nepal_grievance_admin"
    DB_PASSWORD="K9!mP2$vL5nX8&qR4jW7"
fi

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

# Log which configuration was loaded
echo "Database configuration loaded from: $ENV_SOURCE"
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT"
echo "User: $DB_USER" 