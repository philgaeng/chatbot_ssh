#!/bin/bash

# Rasa Configuration
RASA_VERSION="3.10.0"
RASA_PORT="5005"
RASA_ACTIONS_PORT="5055"
RASA_MODEL_DIR="models"
RASA_DATA_DIR="data"
RASA_CONFIG_DIR="config"

# Training Configuration
TRAIN_TIMEOUT=3600  # 1 hour
TRAIN_RETRIES=3
TRAIN_DELAY=300  # 5 minutes
TRAIN_BATCH_SIZE=64
TRAIN_EPOCHS=100

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
    "failed to load model"
    "training failed"
    "connection refused"
    "timeout"
    "out of memory"
    "invalid configuration"
    "missing required component"
    "action server not running"
)

# Export all variables
export RASA_VERSION RASA_PORT RASA_ACTIONS_PORT
export RASA_MODEL_DIR RASA_DATA_DIR RASA_CONFIG_DIR
export TRAIN_TIMEOUT TRAIN_RETRIES TRAIN_DELAY
export TRAIN_BATCH_SIZE TRAIN_EPOCHS
export LOG_DIR LOG_MAX_SIZE_MB LOG_MAX_FILES LOG_FORMAT
export SCRIPT_DIR PROJECT_ROOT
export HEALTH_CHECK_TIMEOUT HEALTH_CHECK_RETRIES HEALTH_CHECK_DELAY
export ERROR_PATTERNS 