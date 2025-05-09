#!/bin/bash

# Exit on error
set -e

# Load configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../scripts/task_queue/config.sh"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    exit 1
fi

# Check if Redis is installed
if ! command -v redis-cli &> /dev/null; then
    print_error "Redis is not installed"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping &> /dev/null; then
    print_error "Redis is not running"
    print_status "Starting Redis..."
    redis-server --daemonize yes
    sleep 2
fi

# Check if we're in the right directory
if [ ! -f "$SCRIPT_DIR/run_examples.py" ]; then
    print_error "Please run this script from the $QUEUE_FOLDER directory"
    exit 1
fi

# Add the parent directory to PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/..:$PYTHONPATH"

# Run the example tasks
print_status "Running example tasks..."
cd "$SCRIPT_DIR"
python3 run_examples.py

# Check if there were any errors
if [ $? -eq 0 ]; then
    print_status "Example tasks completed successfully"
else
    print_error "Example tasks failed"
    exit 1
fi 