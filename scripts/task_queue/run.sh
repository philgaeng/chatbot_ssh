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
    local worker=${3:-"system"}
    echo "{\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",\"level\":\"$level\",\"worker\":\"$worker\",\"message\":\"$message\"}"
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

# Function to check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 is required but not installed"
        exit 1
    fi
}

# Function to check if a port is in use
check_port() {
    if lsof -i :$1 &> /dev/null; then
        log_error "Port $1 is already in use"
        exit 1
    fi
}

# Function to check Redis connection with retry
check_redis_with_retry() {
    local max_retries=$HEALTH_CHECK_RETRIES
    local retry_delay=$HEALTH_CHECK_DELAY
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if redis-cli -h $REDIS_HOST -p $REDIS_PORT ping &> /dev/null; then
            log "Redis connection successful"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            log_warning "Redis connection failed. Retrying in $retry_delay seconds..."
            sleep $retry_delay
        fi
    done
    
    log_error "Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT after $max_retries attempts"
    return 1
}

# Function to check system resources
check_system_resources() {
    # Check memory usage
    local memory_percent=$(free | grep Mem | awk '{print $3/$2 * 100.0}')
    if (( $(echo "$memory_percent > $MAX_MEMORY_PERCENT" | bc -l) )); then
        log_warning "High memory usage: ${memory_percent}%"
    fi
    
    # Check CPU usage
    local cpu_percent=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
    if (( $(echo "$cpu_percent > $MAX_CPU_PERCENT" | bc -l) )); then
        log_warning "High CPU usage: ${cpu_percent}%"
    fi
    
    # Check disk usage
    local disk_percent=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_percent" -gt "$MAX_DISK_PERCENT" ]; then
        log_warning "High disk usage: ${disk_percent}%"
    fi
}

# Function to create required directories
setup_directories() {
    mkdir -p "$PROJECT_ROOT/$LOG_DIR"
    mkdir -p "$PID_DIR"
    
    # Set proper permissions
    chmod 755 "$PID_DIR"
}

# Function to rotate logs with compression
rotate_logs() {
    local log_file=$1
    local max_size_mb=$LOG_MAX_SIZE_MB
    local max_files=$LOG_MAX_FILES

    if [ -f "$log_file" ]; then
        local size_kb=$(du -k "$log_file" | cut -f1)
        if [ $size_kb -gt $((max_size_mb * 1024)) ]; then
            for i in $(seq $max_files -1 1); do
                if [ -f "${log_file}.${i}.gz" ]; then
                    mv "${log_file}.${i}.gz" "${log_file}.$((i+1)).gz"
                fi
            done
            gzip -c "$log_file" > "${log_file}.1.gz"
            rm "$log_file"
            touch "$log_file"
        fi
    fi
}

# Function to clean up on exit
cleanup() {
    log "Cleaning up..."
    
    # Kill all workers
    for pid_file in $PID_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if ps -p $pid > /dev/null; then
                log "Stopping process $pid"
                kill $pid 2>/dev/null || true
                # Wait for process to terminate
                for i in {1..5}; do
                    if ! ps -p $pid > /dev/null; then
                        break
                    fi
                    sleep 1
                done
                # Force kill if still running
                if ps -p $pid > /dev/null; then
                    kill -9 $pid 2>/dev/null || true
                fi
            fi
            rm -f "$pid_file"
        fi
    done
    
    # Kill Flower
    if [ -f "$PID_DIR/flower.pid" ]; then
        pid=$(cat "$PID_DIR/flower.pid")
        if ps -p $pid > /dev/null; then
            log "Stopping Flower process $pid"
            kill $pid 2>/dev/null || true
            # Wait for process to terminate
            for i in {1..5}; do
                if ! ps -p $pid > /dev/null; then
                    break
                fi
                sleep 1
            done
            # Force kill if still running
            if ps -p $pid > /dev/null; then
                kill -9 $pid 2>/dev/null || true
            fi
        fi
        rm -f "$PID_DIR/flower.pid"
    fi
    
    log "Cleanup complete"
}

# Function to start a worker and wait for it to be ready
start_worker() {
    local name=$1
    local queue=$2
    local pid_file="$PID_DIR/${name}.pid"
    local log_file="$PROJECT_ROOT/$LOG_DIR/${name}.log"
    local restart_count=0
    
    while [ $restart_count -lt $WORKER_RESTART_ATTEMPTS ]; do
        log "Starting $name worker (attempt $((restart_count + 1))/$WORKER_RESTART_ATTEMPTS)..."
        
        # Rotate logs if needed
        rotate_logs "$log_file"
        
        # Start the worker with proper error handling
        if ! celery -A ${QUEUE_FOLDER}.config.celery_app worker -Q $queue -n ${name}@%h -l info > "$log_file" 2>&1 &; then
            log_error "Failed to start $name worker"
            restart_count=$((restart_count + 1))
            continue
        fi
        
        local pid=$!
        echo $pid > "$pid_file"
        
        # Wait for worker to start
        local start_time=$(date +%s)
        while true; do
            if ! ps -p $pid > /dev/null; then
                log_error "$name worker failed to start"
                break
            fi
            
            if grep -q "ready" "$log_file"; then
                log "$name worker is ready"
                return 0
            fi
            
            if [ $(($(date +%s) - start_time)) -gt $WORKER_START_TIMEOUT ]; then
                log_error "$name worker failed to start within timeout"
                break
            fi
            
            sleep 1
        done
        
        # If we get here, the worker failed to start
        kill $pid 2>/dev/null || true
        rm -f "$pid_file"
        restart_count=$((restart_count + 1))
        
        if [ $restart_count -lt $WORKER_RESTART_ATTEMPTS ]; then
            log_warning "Waiting $WORKER_RESTART_DELAY seconds before retry..."
            sleep $WORKER_RESTART_DELAY
        fi
    done
    
    log_error "$name worker failed to start after $WORKER_RESTART_ATTEMPTS attempts"
    return 1
}

# Function to check worker health
check_worker_health() {
    local name=$1
    local pid_file="$PID_DIR/${name}.pid"
    local log_file="$PROJECT_ROOT/$LOG_DIR/${name}.log"
    
    if [ ! -f "$pid_file" ]; then
        log_error "$name worker PID file not found"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    if ! ps -p $pid > /dev/null; then
        log_error "$name worker process not running"
        return 1
    fi
    
    # Check for common error patterns in logs
    for pattern in "${ERROR_PATTERNS[@]}"; do
        if grep -q "$pattern" "$log_file"; then
            log_error "$name worker shows error pattern: $pattern"
            return 1
        fi
    done
    
    # Check worker memory usage
    local worker_memory=$(ps -o rss= -p $pid | awk '{print $1/1024}')
    if (( $(echo "$worker_memory > $MAX_WORKER_MEMORY_MB" | bc -l) )); then
        log_warning "$name worker using high memory: ${worker_memory}MB"
    fi
    
    return 0
}

# Function to restart a worker
restart_worker() {
    local name=$1
    local queue=$2
    local pid_file="$PID_DIR/${name}.pid"
    
    log "Restarting $name worker..."
    
    # Kill existing worker
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null; then
            kill $pid 2>/dev/null || true
            # Wait for process to terminate
            for i in {1..5}; do
                if ! ps -p $pid > /dev/null; then
                    break
                fi
                sleep 1
            done
            # Force kill if still running
            if ps -p $pid > /dev/null; then
                kill -9 $pid 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
    
    # Start new worker
    start_worker "$name" "$queue"
}

# Function to check if all workers are running
check_workers() {
    local all_running=true
    for pid_file in $PID_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            local name=$(basename $pid_file .pid)
            if ! check_worker_health "$name"; then
                all_running=false
            fi
        fi
    done
    return $all_running
}

# Set up trap for cleanup
trap cleanup EXIT INT TERM

# Check prerequisites
log "Checking prerequisites..."
check_command redis-cli
check_command celery
check_command python
check_port $FLOWER_PORT
check_redis_with_retry

# Setup
log "Setting up environment..."
setup_directories

# Start Flower monitoring
log "Starting Flower monitoring..."
celery -A ${QUEUE_FOLDER}.config.celery_app flower --port=$FLOWER_PORT > "$PROJECT_ROOT/$LOG_DIR/flower.log" 2>&1 &
echo $! > "$PID_DIR/flower.pid"
sleep 2

# Start workers
log "Starting workers..."
start_worker "llm_worker" "$LLM_QUEUE" || exit 1
start_worker "default_worker" "$DEFAULT_QUEUE" || exit 1

# Verify all workers are running
if ! check_workers; then
    log_error "Not all workers are running"
    exit 1
fi

# Run the example tasks
log "Running example tasks..."
if ! python -c "from task_queue import run_example_tasks; run_example_tasks()"; then
    log_error "Failed to run example tasks"
    exit 1
fi

log "Example tasks have been queued successfully"
log "Check the logs directory for results: $PROJECT_ROOT/$LOG_DIR"
log "Monitor tasks at http://localhost:$FLOWER_PORT"
log "Press Ctrl+C to stop all workers"

# Monitor workers and restart if needed
while true; do
    # Check system resources
    check_system_resources
    
    # Check and restart workers if needed
    for worker in "llm_worker" "default_worker"; do
        if ! check_worker_health "$worker"; then
            log_warning "Restarting $worker worker..."
            restart_worker "$worker" "${worker/_worker/}"
        fi
    done
    
    sleep $WORKER_HEALTH_CHECK_INTERVAL
done 