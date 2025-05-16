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

# Function to check AWS CLI
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
}

# Function to check SSH key
check_ssh_key() {
    if [ ! -f "$KEY_FILE" ]; then
        log_error "SSH key file not found: $KEY_FILE"
        exit 1
    fi
    chmod 600 "$KEY_FILE"
}

# Function to wait for SSH with timeout
wait_for_ssh() {
    local host=$1
    local timeout=$TRAIN_TIMEOUT
    local start_time=$(date +%s)
    
    while ! nc -z $host 22; do
        if [ $(($(date +%s) - start_time)) -gt $timeout ]; then
            log_error "Timeout waiting for SSH connection"
            return 1
        fi
        log "Waiting for SSH to be available..."
        sleep 5
    done
    
    log "SSH is available"
    return 0
}

# Create required directories
mkdir -p "$PROJECT_ROOT/$LOG_DIR"
mkdir -p "$PROJECT_ROOT/$RASA_MODEL_DIR"

# Check prerequisites
check_aws_cli
check_ssh_key

log "Starting training instance..."

# Start the training instance
aws ec2 start-instances --instance-ids $TRAIN_INSTANCE_ID
aws ec2 wait instance-running --instance-ids $TRAIN_INSTANCE_ID

# Get private IP
PRIVATE_IP=$(aws ec2 describe-instances \
    --instance-ids $TRAIN_INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PrivateIpAddress' \
    --output text)

log "Instance private IP: $PRIVATE_IP"

# Wait for SSH with timeout
if ! wait_for_ssh $PRIVATE_IP; then
    log_error "Failed to establish SSH connection"
    aws ec2 stop-instances --instance-ids $TRAIN_INSTANCE_ID
    exit 1
fi

# Sync training files
log "Syncing training files..."
if ! rsync -av -e "ssh -i $KEY_FILE" --progress \
    --include="domain.yml" \
    --include="config.yml" \
    --include="data/***" \
    --exclude="*" \
    "$PROJECT_ROOT/" "ubuntu@$PRIVATE_IP:~/nepal_chatbot/"; then
    log_error "Failed to sync training files"
    aws ec2 stop-instances --instance-ids $TRAIN_INSTANCE_ID
    exit 1
fi

# Run training with timeout
log "Starting Rasa training..."
if ! timeout $TRAIN_TIMEOUT ssh -i $KEY_FILE ubuntu@$PRIVATE_IP << 'EOF'
    cd nepal_chatbot
    source /home/ubuntu/rasa-env-21/bin/activate
    rasa train --num-threads $TRAIN_BATCH_SIZE --epochs $TRAIN_EPOCHS
    if [ $? -eq 0 ]; then
        echo "Training complete!"
        exit 0
    else
        echo "Training failed!"
        exit 1
    fi
EOF
then
    log_error "Training failed or timed out"
    aws ec2 stop-instances --instance-ids $TRAIN_INSTANCE_ID
    exit 1
fi

# Copy trained model back
log "Copying trained model back..."
if ! scp -i $KEY_FILE "ubuntu@$PRIVATE_IP:~/nepal_chatbot/models/*" "$PROJECT_ROOT/$RASA_MODEL_DIR/"; then
    log_error "Failed to copy trained model"
    aws ec2 stop-instances --instance-ids $TRAIN_INSTANCE_ID
    exit 1
fi

# Stop the instance
log "Stopping training instance..."
aws ec2 stop-instances --instance-ids $TRAIN_INSTANCE_ID

log "Training process complete! New model has been copied to models directory." 