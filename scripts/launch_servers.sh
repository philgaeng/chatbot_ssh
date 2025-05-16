#!/bin/bash

# Set the base directory
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
mkdir -p "$LOG_DIR"
mkdir -p "$UPLOAD_DIR"

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
        # Wait for the process to stop
        for i in {1..5}; do
            if ! sudo lsof -i:$port > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        # Force kill if still running
        if sudo lsof -i:$port > /dev/null 2>&1; then
            echo "Force stopping process on port $port..."
            sudo kill -9 $pid
            # Wait again after force kill
            for i in {1..5}; do
                if ! sudo lsof -i:$port > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
        fi
        # Verify the process is actually stopped
        if ! sudo lsof -i:$port > /dev/null 2>&1; then
            echo "✅ Process on port $port stopped"
            return 0
        else
            echo "❌ Failed to stop process on port $port"
            return 1
        fi
    else
        echo "✅ No process running on port $port"
        return 0
    fi
}

# Function to start Redis server
start_redis() {
    local host=${REDIS_HOST:-localhost}
    local port=${REDIS_PORT:-6379}
    local password=${REDIS_PASSWORD:-""}
    local redis_cli_cmd="redis-cli"
    local pid_file="$LOG_DIR/redis.pid"
    local log_file="$LOG_DIR/redis.log"
    
    if [ ! -z "$password" ]; then
        redis_cli_cmd="$redis_cli_cmd -a $password"
    fi
    if [ "$host" != "localhost" ]; then
        redis_cli_cmd="$redis_cli_cmd -h $host"
    fi
    if [ "$port" != "6379" ]; then
        redis_cli_cmd="$redis_cli_cmd -p $port"
    fi

    if ! command -v redis-cli &> /dev/null; then
        echo "❌ Redis CLI not found. Please install Redis."
        return 1
    fi
    
    # First, try to stop any existing Redis process
    echo "Checking for existing Redis processes..."
    
    # Try to stop Redis gracefully first
    if command -v redis-cli &> /dev/null; then
        $redis_cli_cmd shutdown 2>/dev/null
        sleep 2
    fi
    
    # Find and kill all Redis-related processes
    echo "Searching for Redis processes..."
    local redis_pids=$(pgrep -f "redis-server" 2>/dev/null)
    if [ ! -z "$redis_pids" ]; then
        echo "Found Redis processes: $redis_pids"
        for pid in $redis_pids; do
            echo "Stopping Redis process $pid..."
            # Try to stop system Redis service first
            if [ -f "/etc/init.d/redis-server" ]; then
                sudo service redis-server stop
                sleep 2
            fi
            # Then kill the process
            sudo kill $pid 2>/dev/null
        done
        sleep 2
        
        # Force kill any remaining Redis processes
        redis_pids=$(pgrep -f "redis-server" 2>/dev/null)
        if [ ! -z "$redis_pids" ]; then
            echo "Force stopping remaining Redis processes..."
            for pid in $redis_pids; do
                sudo kill -9 $pid 2>/dev/null
            done
            sleep 2
        fi
    fi
    
    # Double check port is free
    local port_pid=$(sudo lsof -t -i:$port 2>/dev/null)
    if [ ! -z "$port_pid" ]; then
        echo "Found process using port $port (PID: $port_pid). Stopping it..."
        sudo kill -9 $port_pid 2>/dev/null
        sleep 2
    fi
    
    # Remove any stale PID file
    if [ -f "$pid_file" ]; then
        echo "Removing stale Redis PID file..."
        rm -f "$pid_file"
    fi
    
    # Clear any existing Redis log
    if [ -f "$log_file" ]; then
        echo "Clearing Redis log file..."
        rm -f "$log_file"
    fi
    
    # Final check if port is free
    if sudo lsof -i:$port > /dev/null 2>&1; then
        echo "❌ Port $port is still in use. Please check system processes manually."
        return 1
    fi
    
    echo "Starting Redis server..."
    if [ "$host" = "localhost" ] && command -v redis-server &> /dev/null; then
        # Start Redis server with explicit log and PID file locations
        redis-server --daemonize yes \
                    --port $port \
                    ${password:+"--requirepass" "$password"} \
                    --pidfile "$pid_file" \
                    --logfile "$log_file" \
                    --loglevel notice
        sleep 5
        
        # Verify Redis started
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if ps -p $pid > /dev/null 2>&1 && $redis_cli_cmd ping &> /dev/null; then
                echo "✅ Redis server started (PID: $pid)"
                return 0
            fi
        fi
        
        # If we get here, Redis failed to start
        echo "❌ Failed to start Redis server. Check $log_file for details."
        if [ -f "$log_file" ]; then
            echo "Last few lines of Redis log:"
            tail -n 5 "$log_file"
        fi
        return 1
    fi
    
    echo "❌ Cannot start Redis server (not localhost or redis-server not found)"
    return 1
}

# Function to check if Redis is running
check_redis() {
    local host=${REDIS_HOST:-localhost}
    local port=${REDIS_PORT:-6379}
    local password=${REDIS_PASSWORD:-""}
    local redis_cli_cmd="redis-cli"
    
    if [ ! -z "$password" ]; then
        redis_cli_cmd="$redis_cli_cmd -a $password"
    fi
    if [ "$host" != "localhost" ]; then
        redis_cli_cmd="$redis_cli_cmd -h $host"
    fi
    if [ "$port" != "6379" ]; then
        redis_cli_cmd="$redis_cli_cmd -p $port"
    fi

    # Check if Redis is responding to PING
    if $redis_cli_cmd ping &> /dev/null; then
        return 0
    fi
    return 1
}

# Function to start a service
start_service() {
    local name=$1
    local command=$2
    local log_file="$LOG_DIR/${name}.log"
    
    echo "Starting $name..."
    if check_port $(echo $command | grep -oP '(?<=:)\d+'); then
        cd "$BASE_DIR" && source "$VENV_DIR/bin/activate" && nohup $command > "$log_file" 2>&1 &
        echo $! > "$LOG_DIR/${name}.pid"
        echo "$name started with PID $(cat $LOG_DIR/${name}.pid)"
    else
        echo "Failed to start $name"
        return 1
    fi
}

# Function to start Rasa Action Server
start_rasa_actions() {
    local log_file="$LOG_DIR/rasa_actions.log"
    echo "Starting Rasa Action Server..."
    
    # Check if already running
    if [ -f "$LOG_DIR/rasa_actions.pid" ]; then
        pid=$(cat "$LOG_DIR/rasa_actions.pid")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Rasa Action Server is already running with PID $pid"
            return 0
        else
            rm "$LOG_DIR/rasa_actions.pid"
        fi
    fi
    
    # Start Rasa Action Server
    cd "$BASE_DIR" && source "$VENV_DIR/bin/activate" && \
    PYTHONPATH=$BASE_DIR \
    rasa run actions --debug > "$log_file" 2>&1 &
    echo $! > "$LOG_DIR/rasa_actions.pid"
    
    # Wait a moment for the server to start
    sleep 2
    
    # Verify the server started
    if [ -f "$LOG_DIR/rasa_actions.pid" ]; then
        pid=$(cat "$LOG_DIR/rasa_actions.pid")
        if ps -p $pid > /dev/null 2>&1; then
            echo "✅ Rasa Action Server started with PID $pid"
            return 0
        fi
    fi
    
    echo "❌ Failed to start Rasa Action Server"
    return 1
}

# Function to start Celery worker
start_celery() {
    local log_file="$LOG_DIR/celery.log"
    echo "Starting Celery worker..."
    
    # Check Redis first with retries
    echo "Checking Redis connection..."
    local redis_ready=false
    for i in {1..5}; do
        if check_redis; then
            echo "✅ Redis is already running"
            redis_ready=true
            break
        fi
        echo "Waiting for Redis to be ready (attempt $i/5)..."
        sleep 5
    done
    
    # Only start Redis if it's not running after retries
    if ! $redis_ready; then
        echo "Redis not found running, attempting to start it..."
        if ! start_redis; then
            echo "❌ Cannot start Celery without Redis"
            return 1
        fi
    fi
    
    # More thorough cleanup of existing Celery processes
    echo "Cleaning up any existing Celery processes..."
    
    # Kill any existing Celery processes
    pkill -9 -f "celery.*worker" 2>/dev/null
    pkill -9 -f "celery.*flower" 2>/dev/null
    
    # Wait for processes to terminate
    sleep 5
    
    # Double check and force kill any remaining processes
    if pgrep -f "celery.*worker" > /dev/null; then
        echo "Force killing remaining Celery processes..."
        pkill -9 -f "celery.*worker"
        sleep 2
    fi
    
    # Remove PID file and log file
    rm -f "$LOG_DIR/celery.pid"
    rm -f "$log_file"
    
    # Start Celery with proper configuration
    cd "$BASE_DIR" && source "$VENV_DIR/bin/activate" && \
    PYTHONPATH=$BASE_DIR \
    celery -A task_queue worker \
        --loglevel=info \
        --concurrency=2 \
        --pidfile="$LOG_DIR/celery.pid" \
        --logfile="$log_file" \
        --include=task_queue.registered_tasks \
        > "$log_file" 2>&1 &
    
    # Store the PID for our wait loop
    local celery_pid=$!
    
    # Wait for the worker to start
    echo "Waiting for Celery worker to start..."
    for i in {1..30}; do
        if ps -p $celery_pid > /dev/null 2>&1; then
            # Check for successful configuration message
            if grep -q "task_queue.config.*Celery configured" "$log_file" 2>/dev/null; then
                echo "✅ Celery worker started with PID $celery_pid"
                return 0
            fi
        fi
        sleep 1
    done
    
    echo "❌ Failed to start Celery worker"
    return 1
}

# Function to start Flower monitoring
start_flower() {
    local log_file="$LOG_DIR/flower.log"
    local pid_file="$LOG_DIR/flower.pid"
    
    echo "Starting Flower monitoring..."
    
    # Check if Flower is already running
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Flower is already running with PID $pid"
            return 0
        else
            rm "$pid_file"
        fi
    fi
    
    # Start Flower
    cd "$BASE_DIR" && source "$VENV_DIR/bin/activate" && \
    PYTHONPATH=$BASE_DIR \
    celery -A task_queue --broker="$CELERY_BROKER_URL" flower \
        --port=5555 \
        --logfile="$log_file" \
        --pidfile="$pid_file" \
        > "$log_file" 2>&1 &
    
    # Store the PID
    echo $! > "$pid_file"
    
    # Wait a moment for Flower to start
    sleep 2
    
    # Verify Flower started
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "✅ Flower started with PID $pid"
            return 0
        fi
    fi
    
    echo "❌ Failed to start Flower"
    return 1
}

# Kill existing processes if they exist
echo "Checking for existing processes..."
for service in rasa rasa_actions file_server celery flower; do
    if [ -f "$LOG_DIR/${service}.pid" ]; then
        pid=$(cat "$LOG_DIR/${service}.pid")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Stopping existing $service process (PID: $pid)..."
            kill $pid
            rm "$LOG_DIR/${service}.pid"
        fi
    fi
done

# Start services in order
echo -e "\nStarting services..."

# 1. Start Redis (if not running)
start_redis || exit 1

# 2. Start Celery worker
start_celery

# 3. Start Rasa Action Server
start_rasa_actions

# 4. Start Rasa server
start_service "rasa" "rasa run --enable-api --cors \"*\" --debug"

# 5. Start File Server (now launches the Flask app with blueprints used for voice grievance and file upload)
start_service "flask_server" "env PYTHONPATH=$BASE_DIR UPLOAD_FOLDER=$UPLOAD_DIR python3 actions_server/app.py"

# 6. Start Flower monitoring
start_flower

# Wait a moment for services to start
sleep 5

# Check if services are running
echo -e "\nChecking service status:"
services=(
    "redis"
    "rasa"
    "rasa_actions"
    "flask_server"
    "flower"
)

for service in "${services[@]}"; do
    if [ -f "$LOG_DIR/${service}.pid" ]; then
        pid=$(cat "$LOG_DIR/${service}.pid")
        if ps -p $pid > /dev/null 2>&1; then
            echo "✅ $service is running (PID: $pid)"
        else
            echo "❌ $service failed to start"
        fi
    else
        echo "❌ $service failed to start"
    fi
done

# Special check for Celery
if [ -f "$LOG_DIR/celery.pid" ]; then
    pid=$(cat "$LOG_DIR/celery.pid")
    if ps -p $pid > /dev/null 2>&1; then
        if grep -q "task_queue.config.*Celery configured" "$LOG_DIR/celery.log" 2>/dev/null; then
            echo "✅ celery is running (PID: $pid)"
        else
            echo "❌ celery is running but not ready"
        fi
    else
        echo "❌ celery failed to start"
    fi
else
    echo "❌ celery failed to start"
fi

echo -e "\nAll services have been started. Logs can be found in $LOG_DIR"
echo "To stop all services, run: ./scripts/stop_servers.sh" 