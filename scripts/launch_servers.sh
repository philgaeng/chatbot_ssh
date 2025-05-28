#!/bin/bash

# Set the base directory and environment variables
BASE_DIR="/home/ubuntu/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"
VENV_DIR="/home/ubuntu/rasa-env-21"
UPLOAD_DIR="$BASE_DIR/uploads"

# Export Redis and Celery environment variables globally
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD="3fduLmg25@k"
export CELERY_BROKER_URL="redis://:3fduLmg25%40k@localhost:6379/0"

# Create necessary directories
mkdir -p "$LOG_DIR" "$UPLOAD_DIR"

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        echo "Port $port is already in use. Please stop the service using this port first."
        return 1
    fi
    return 0
}

# Function to kill process by port
kill_process_by_port() {
    local port=$1
    local pid=$(sudo lsof -t -i:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        echo "Found process running on port $port (PID: $pid)"
        echo "Stopping process..."
        sudo kill $pid
        sleep 2
        if sudo lsof -i:$port > /dev/null 2>&1; then
            echo "Force stopping process..."
            sudo kill -9 $pid
            sleep 2
        fi
        if ! sudo lsof -i:$port > /dev/null 2>&1; then
            echo "✅ Process on port $port stopped"
            return 0
        fi
        echo "❌ Failed to stop process on port $port"
        return 1
    fi
    echo "✅ No process running on port $port"
    return 0
}

# Function to start Redis server
start_redis() {
    local redis_cli_cmd="redis-cli"
    if [ ! -z "$REDIS_PASSWORD" ]; then
        redis_cli_cmd="$redis_cli_cmd -a $REDIS_PASSWORD"
    fi

    # Stop any existing Redis processes
    echo "Checking for existing Redis processes..."
    $redis_cli_cmd shutdown 2>/dev/null
    sleep 2
    
    # Kill any remaining Redis processes
    local redis_pids=$(pgrep -f "redis-server" 2>/dev/null)
    if [ ! -z "$redis_pids" ]; then
        echo "Stopping Redis processes: $redis_pids"
        sudo kill -9 $redis_pids 2>/dev/null
        sleep 2
    fi

    # Clear old files
    rm -f "$LOG_DIR/redis.pid" "$LOG_DIR/redis.log"

    # Start Redis server
    echo "Starting Redis server..."
    redis-server --daemonize yes \
                --port $REDIS_PORT \
                --requirepass "$REDIS_PASSWORD" \
                --pidfile "$LOG_DIR/redis.pid" \
                --logfile "$LOG_DIR/redis.log" \
                --loglevel notice \
                --maxclients 10000 \
                --tcp-keepalive 300 \
                --timeout 0 \
                --maxmemory 2gb \
                --maxmemory-policy allkeys-lru \
                --appendonly yes \
                --appendfilename "appendonly.aof" \
                --appendfsync everysec

    # Wait for Redis to start
    local retry=0
    while [ $retry -lt 5 ]; do
        sleep 2
        if [ -f "$LOG_DIR/redis.pid" ] && $redis_cli_cmd ping &> /dev/null; then
            echo "✅ Redis server started"
            return 0
        fi
        retry=$((retry + 1))
        echo "Waiting for Redis to start (attempt $retry/5)..."
    done

    echo "❌ Failed to start Redis server"
    return 1
}

# Function to check if Redis is running
check_redis() {
    local redis_cli_cmd="redis-cli"
    if [ ! -z "$REDIS_PASSWORD" ]; then
        redis_cli_cmd="$redis_cli_cmd -a $REDIS_PASSWORD"
    fi
    $redis_cli_cmd ping &> /dev/null
}

# Function to wait for a worker to be fully ready
wait_for_worker_ready() {
    local queue_name=$1
    local log_file="$LOG_DIR/celery_${queue_name}.log"
    local max_wait_time=25
    local check_interval=2
    local elapsed=0

    echo "Waiting for $queue_name worker to be fully ready..."
    while [ $elapsed -lt $max_wait_time ]; do
        # Check if the worker is ready based on log file
        if grep -q "celery@.*ready" "$log_file" 2>/dev/null && \
           grep -q "Connected to redis://" "$log_file" 2>/dev/null; then
            echo "✅ $queue_name worker is running and ready"
            return 0
        fi

        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        echo "Still waiting for $queue_name worker to be ready... (${elapsed}s elapsed)"
    done

    echo "❌ Timed out waiting for $queue_name worker to be ready after ${max_wait_time}s"
    return 1
}

# Function to clean up Celery worker files
cleanup_celery_worker() {
    local queue_name=$1
    local pid_file="$LOG_DIR/celery_${queue_name}.pid"
    local log_file="$LOG_DIR/celery_${queue_name}.log"
    
    echo "Cleaning up ${queue_name} worker files..."
    
    # Kill any existing process using the PID file
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Killing existing process (PID: $pid)..."
            kill -9 $pid 2>/dev/null
            sleep 2
        fi
        rm -f "$pid_file"
    fi
    
    # Find and kill any processes by queue name
    local worker_pids=$(pgrep -f "celery.*worker.*$queue_name" 2>/dev/null)
    if [ ! -z "$worker_pids" ]; then
        echo "Found additional celery_${queue_name} processes: $worker_pids"
        for pid in $worker_pids; do
            kill -9 $pid 2>/dev/null
        done
        sleep 2
    fi
    
    # Remove log file if it exists
    if [ -f "$log_file" ]; then
        rm -f "$log_file"
    fi
    
    # Verify no processes are running
    if ! pgrep -f "celery.*worker.*$queue_name" > /dev/null; then
        echo "✅ ${queue_name} worker files cleaned up"
        return 0
    else
        echo "❌ Failed to clean up ${queue_name} worker files"
        return 1
    fi
}

# Function to start a Celery worker
start_celery_worker() {
    local queue_name=$1
    local concurrency=$2
    local log_file="$LOG_DIR/celery_${queue_name}.log"
    local pid_file="$LOG_DIR/celery_${queue_name}.pid"

    # Check Redis
    if ! check_redis; then
        echo "Redis not running, attempting to start it..."
        if ! start_redis; then
            echo "❌ Cannot start Celery without Redis"
            return 1
        fi
    fi

    # Clean up worker files
    if ! cleanup_celery_worker "$queue_name"; then
        echo "❌ Failed to clean up worker files"
        return 1
    fi

    # Wait a moment to ensure all cleanup is complete
    sleep 2

    # Start worker with explicit PID file handling
    echo "Starting Celery worker for $queue_name..."
    cd "$BASE_DIR" && source "$VENV_DIR/bin/activate" && \
    PYTHONPATH=$BASE_DIR \
    CELERY_PID_FILE="$pid_file" \
    celery -A task_queue worker -Q "$queue_name" \
        --concurrency="$concurrency" \
        --logfile="$log_file" \
        --pidfile="$pid_file" \
        --loglevel=INFO \
        --max-tasks-per-child=1000 \
        --prefetch-multiplier=1 \
        --without-gossip \
        --without-mingle \
        --without-heartbeat \
        -n "celery@${queue_name}.%h" \
        --detach &

    # Store PID and wait a moment for the process to start
    local worker_pid=$!
    echo $worker_pid > "$pid_file"
    sleep 2

    # Wait for worker to be ready
    if ! wait_for_worker_ready "$queue_name"; then
        echo "❌ Failed to start $queue_name worker"
        kill -9 $worker_pid 2>/dev/null
        rm -f "$pid_file"
        return 1
    fi

    return 0
}

# Function to start a service
start_service() {
    local name=$1
    local command=$2
    local log_file="$LOG_DIR/${name}.log"
    local pid_file="$LOG_DIR/${name}.pid"
    
    echo "Starting $name..."
    if check_port $(echo $command | grep -oP '(?<=:)\d+'); then
        cd "$BASE_DIR" && source "$VENV_DIR/bin/activate" && \
        PYTHONPATH=$BASE_DIR \
        FLASK_APP=actions_server/app.py \
        FLASK_ENV=development \
        UPLOAD_FOLDER=$UPLOAD_DIR \
        nohup $command > "$log_file" 2>&1 &
        
        # Store the PID
        echo $! > "$pid_file"
        
        # Wait a moment for the process to start
        sleep 2
        
        # Check if process started successfully
        if ps -p $(cat "$pid_file") > /dev/null 2>&1; then
            echo "$name started with PID $(cat $pid_file)"
            return 0
        else
            echo "❌ Failed to start $name. Check logs at $log_file"
            rm -f "$pid_file"
            return 1
        fi
    fi
    echo "Failed to start $name"
    return 1
}

# Kill existing processes
echo "Checking for existing processes..."
for service in rasa rasa_actions file_server celery flower; do
    if [ -f "$LOG_DIR/${service}.pid" ]; then
        kill $(cat "$LOG_DIR/${service}.pid") 2>/dev/null
        rm "$LOG_DIR/${service}.pid"
    fi
done

# Start services in order
echo -e "\nStarting services..."

# 1. Start Redis
if ! start_redis; then
    echo "❌ Failed to start Redis. Exiting..."
    exit 1
fi

# 2. Clean up all Celery workers before starting
echo "Cleaning up all Celery workers..."
cleanup_celery_worker "default"
cleanup_celery_worker "llm_queue"

# 3. Start Celery workers
echo "Starting Celery workers..."
if ! start_celery_worker "default" 2; then
    echo "❌ Failed to start default Celery worker. Exiting..."
    exit 1
fi

# Wait a moment before starting the next worker
sleep 5

if ! start_celery_worker "llm_queue" 6; then
    echo "❌ Failed to start LLM Celery worker. Exiting..."
    exit 1
fi

# 4. Start other services
for service in "rasa_actions" "rasa" "flask_server" "flower"; do
    case $service in
        "rasa_actions")
            if ! start_service "$service" "rasa run actions --debug"; then
                echo "❌ Failed to start $service. Exiting..."
                exit 1
            fi
            ;;
        "rasa")
            if ! start_service "$service" "rasa run --enable-api --cors \"*\" --debug"; then
                echo "❌ Failed to start $service. Exiting..."
                exit 1
            fi
            ;;
        "flask_server")
            if ! start_service "$service" "python3 actions_server/app.py"; then
                echo "❌ Failed to start $service. Exiting..."
                exit 1
            fi
            ;;
        "flower")
            if ! start_service "$service" "celery -A task_queue --broker=redis://:3fduLmg25%40k@localhost:6379/0 flower --port=5555 --broker_api=redis://:3fduLmg25%40k@localhost:6379/0 --logging=info"; then
                echo "❌ Failed to start $service. Exiting..."
                exit 1
            fi
            ;;
    esac
done

# Wait for all services to be ready
echo "Waiting for all services to be ready..."
sleep 10

# Check service status
echo -e "\nChecking service status:"
for service in redis rasa rasa_actions flask_server flower celery_default celery_llm_queue; do
    if [ -f "$LOG_DIR/${service}.pid" ]; then
        pid=$(cat "$LOG_DIR/${service}.pid")
        if ps -p $pid > /dev/null 2>&1; then
            if [[ $service == celery_* ]]; then
                if grep -q "celery@.*ready" "$LOG_DIR/${service}.log" 2>/dev/null; then
                    echo "✅ $service is running and ready (PID: $pid)"
                else
                    echo "❌ $service is running but not ready"
                fi
            elif [[ $service == "flower" ]]; then
                if grep -q "Visit me at http://" "$LOG_DIR/${service}.log" 2>/dev/null; then
                    echo "✅ $service is running and ready (PID: $pid)"
                else
                    echo "❌ $service is running but not ready"
                fi
            else
                echo "✅ $service is running (PID: $pid)"
            fi
        else
            echo "❌ $service failed to start"
        fi
    else
        echo "❌ $service failed to start"
    fi
done

echo -e "\nAll services have been started. Logs can be found in $LOG_DIR"
echo "To stop all services, run: ./scripts/stop_servers.sh" 