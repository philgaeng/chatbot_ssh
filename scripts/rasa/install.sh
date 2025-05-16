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

# Function to check Python version
check_python_version() {
    if ! command -v python3.10 &> /dev/null; then
        log_error "Python 3.10 is required but not installed"
        exit 1
    fi
}

# Function to create virtual environment
create_venv() {
    local venv_path="$HOME/rasa-env-21"
    
    if [ -d "$venv_path" ]; then
        log_warning "Virtual environment already exists at $venv_path"
        read -p "Do you want to recreate it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Removing existing virtual environment..."
            rm -rf "$venv_path"
        else
            log "Using existing virtual environment"
            return 0
        fi
    fi
    
    log "Creating new Python virtual environment..."
    python3.10 -m venv "$venv_path"
    source "$venv_path/bin/activate"
}

# Function to install dependencies with retry
install_with_retry() {
    local package=$1
    local max_retries=$HEALTH_CHECK_RETRIES
    local retry_delay=$HEALTH_CHECK_DELAY
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if pip install $package; then
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            log_warning "Failed to install $package. Retrying in $retry_delay seconds..."
            sleep $retry_delay
        fi
    done
    
    log_error "Failed to install $package after $max_retries attempts"
    return 1
}

# Create logs directory
mkdir -p "$PROJECT_ROOT/$LOG_DIR"

# Check Python version
check_python_version

# Create and activate virtual environment
create_venv

# Upgrade pip
log "Upgrading pip..."
python3.10 -m pip install --upgrade pip setuptools wheel

# Install Rasa with dependencies
log "Installing Rasa version $RASA_VERSION..."
install_with_retry "rasa[spacy]==$RASA_VERSION" || exit 1

# Install rasa-sdk
log "Installing Rasa SDK..."
install_with_retry "rasa-sdk==${RASA_VERSION%.*}.2" || exit 1

# Install spaCy and download model
log "Installing spaCy and downloading English model..."
install_with_retry "spacy" || exit 1
python -m spacy download en_core_web_md || {
    log_error "Failed to download spaCy model"
    exit 1
}

# Install additional dependencies
log "Installing additional dependencies..."
install_with_retry "tensorflow==2.12.0" || exit 1
install_with_retry "scikit-learn==1.1.3" || exit 1
install_with_retry "python-crfsuite==0.9.11" || exit 1

# Print version info
log "Installation complete! Checking versions:"
python --version
pip --version
rasa --version
spacy --version

log "You can now copy your project files and start developing!" 