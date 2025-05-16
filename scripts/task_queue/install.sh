#!/bin/bash

# Exit on any error
set -e

# Load configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/config.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log messages in JSON format
log_json() {
    local level=$1
    local message=$2
    echo "{\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",\"level\":\"$level\",\"message\":\"$message\"}"
}

# Function to log messages
log() {
    if [ "$LOG_FORMAT" = "json" ]; then
        log_json "INFO" "$1"
    else
        echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
    fi
}

log_error() {
    if [ "$LOG_FORMAT" = "json" ]; then
        log_json "ERROR" "$1"
    else
        echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
    fi
}

log_warning() {
    if [ "$LOG_FORMAT" = "json" ]; then
        log_json "WARNING" "$1"
    else
        echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
    fi
}

# Function to validate environment
validate_environment() {
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root"
        exit 1
    fi

    # Check if systemd is available
    if ! command -v systemctl &> /dev/null; then
        log_error "systemd is not available on this system"
        exit 1
    fi

    # Check if required files exist
    if [ ! -f "$SCRIPT_DIR/queue.service" ]; then
        log_error "queue.service file not found in $SCRIPT_DIR"
        exit 1
    fi

    if [ ! -f "$SCRIPT_DIR/run.sh" ]; then
        log_error "run.sh file not found in $SCRIPT_DIR"
        exit 1
    fi

    # Check if run.sh is executable
    if [ ! -x "$SCRIPT_DIR/run.sh" ]; then
        log_warning "Making run.sh executable..."
        chmod +x "$SCRIPT_DIR/run.sh"
    fi

    # Check if configuration file exists
    if [ ! -f "$SCRIPT_DIR/config.sh" ]; then
        log_error "config.sh file not found in $SCRIPT_DIR"
        exit 1
    fi
}

# Function to backup existing service
backup_service() {
    if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
        log "Backing up existing service file..."
        cp "/etc/systemd/system/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service.bak"
    fi
}

# Function to restore service from backup
restore_service() {
    if [ -f "/etc/systemd/system/${SERVICE_NAME}.service.bak" ]; then
        log "Restoring service from backup..."
        cp "/etc/systemd/system/${SERVICE_NAME}.service.bak" "/etc/systemd/system/${SERVICE_NAME}.service"
        systemctl daemon-reload
    fi
}

# Function to verify service installation
verify_installation() {
    if [ ! -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
        log_error "Service file was not installed correctly"
        return 1
    fi

    if ! systemctl is-enabled ${SERVICE_NAME}.service &> /dev/null; then
        log_error "Service is not enabled"
        return 1
    fi

    return 0
}

# Function to check service status with timeout
check_status_with_timeout() {
    local timeout=$HEALTH_CHECK_TIMEOUT
    local start_time=$(date +%s)
    
    while true; do
        if systemctl is-active --quiet ${SERVICE_NAME}.service; then
            log "Task queue service is running"
            systemctl status ${SERVICE_NAME}.service
            return 0
        fi
        
        if [ $(($(date +%s) - start_time)) -gt $timeout ]; then
            log_error "Task queue service failed to start within $timeout seconds"
            systemctl status ${SERVICE_NAME}.service
            return 1
        fi
        
        sleep 1
    done
}

# Function to start service with retry
start_service_with_retry() {
    local max_retries=$HEALTH_CHECK_RETRIES
    local retry_delay=$HEALTH_CHECK_DELAY
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        log "Starting task queue service (attempt $((retry_count + 1))/$max_retries)..."
        systemctl start ${SERVICE_NAME}.service
        
        if check_status_with_timeout; then
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            log_warning "Service start failed. Retrying in $retry_delay seconds..."
            sleep $retry_delay
        fi
    done
    
    log_error "Failed to start service after $max_retries attempts"
    return 1
}

# Function to stop service with timeout
stop_service_with_timeout() {
    local timeout=$HEALTH_CHECK_TIMEOUT
    local start_time=$(date +%s)
    
    log "Stopping task queue service..."
    systemctl stop ${SERVICE_NAME}.service
    
    while true; do
        if ! systemctl is-active --quiet ${SERVICE_NAME}.service; then
            log "Task queue service stopped successfully"
            return 0
        fi
        
        if [ $(($(date +%s) - start_time)) -gt $timeout ]; then
            log_error "Task queue service failed to stop within $timeout seconds"
            systemctl status ${SERVICE_NAME}.service
            return 1
        fi
        
        sleep 1
    done
}

# Function to show logs with error highlighting
show_logs() {
    log "Showing task queue service logs..."
    if [ "$LOG_FORMAT" = "json" ]; then
        journalctl -u ${SERVICE_NAME}.service -n 50 --no-pager | jq -r '.'
    else
        journalctl -u ${SERVICE_NAME}.service -n 50 --no-pager | while read -r line; do
            if [[ $line =~ error|Error|ERROR|failed|Failed|FAILED ]]; then
                echo -e "${RED}$line${NC}"
            elif [[ $line =~ warning|Warning|WARNING ]]; then
                echo -e "${YELLOW}$line${NC}"
            else
                echo "$line"
            fi
        done
    fi
}

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/$LOG_DIR"

# Validate environment
validate_environment

# Backup existing service
backup_service

# Copy service file to systemd directory
log "Installing task queue service..."
cp "$SCRIPT_DIR/queue.service" "/etc/systemd/system/${SERVICE_NAME}.service"

# Reload systemd to recognize new service
log "Reloading systemd..."
systemctl daemon-reload

# Enable service to start on boot
log "Enabling task queue service..."
systemctl enable ${SERVICE_NAME}.service

# Verify installation
if ! verify_installation; then
    log_error "Service installation verification failed"
    restore_service
    exit 1
fi

# Parse command line arguments
case "$1" in
    "start")
        start_service_with_retry
        ;;
    "stop")
        stop_service_with_timeout
        ;;
    "restart")
        stop_service_with_timeout && start_service_with_retry
        ;;
    "status")
        check_status_with_timeout
        ;;
    "logs")
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac 