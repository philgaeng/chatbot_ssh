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
    DB_NAME="${POSTGRES_DB:-app_db}"
    DB_USER="${POSTGRES_USER:-user}"
    # No fallback: the value comes from the env file sourced above (env.local),
    # which is the same source every compose service interpolates from.
    DB_PASSWORD="${POSTGRES_PASSWORD:-}"
    
    # Encryption configuration
    DB_ENCRYPTION_KEY="${DB_ENCRYPTION_KEY:-}"
    DB_ENCRYPTION_ENABLED="${DB_ENCRYPTION_ENABLED:-false}"
else
    # Fallback to default values
    DB_HOST="localhost"
    DB_PORT="5432"
    DB_NAME="app_db"
    DB_USER="user"
    # No env file was found, so there is no password to use. Connecting will fail
    # with a clear authentication error rather than a committed credential.
    DB_PASSWORD=""
    
    # Default encryption settings
    DB_ENCRYPTION_KEY=""
    DB_ENCRYPTION_ENABLED="false"
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

# Encryption Configuration
ENCRYPTION_ENABLED="${DB_ENCRYPTION_ENABLED:-false}"
ENCRYPTION_KEY="${DB_ENCRYPTION_KEY:-}"
ENCRYPTION_TEST_ENABLED="${ENCRYPTION_TEST_ENABLED:-true}"

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
    "extension pgcrypto does not exist"
    "encryption key not set"
)

# Export all variables
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
export DB_CONNECTION_TIMEOUT DB_CONNECTION_RETRIES DB_CONNECTION_DELAY
export BACKUP_DIR BACKUP_RETENTION_DAYS BACKUP_COMPRESSION
export LOG_DIR LOG_MAX_SIZE_MB LOG_MAX_FILES LOG_FORMAT
export SCRIPT_DIR PROJECT_ROOT
export HEALTH_CHECK_TIMEOUT HEALTH_CHECK_RETRIES HEALTH_CHECK_DELAY
export ENCRYPTION_ENABLED ENCRYPTION_KEY ENCRYPTION_TEST_ENABLED
export ERROR_PATTERNS

# Log which configuration was loaded
echo "Database configuration loaded from: $ENV_SOURCE"
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT"
echo "User: $DB_USER" 
echo "Encryption enabled: $ENCRYPTION_ENABLED"
if [ -n "$ENCRYPTION_KEY" ]; then
    echo "Encryption key: [SET]"
else
    echo "Encryption key: [NOT SET]"
fi 