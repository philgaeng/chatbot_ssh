#!/bin/bash

# Set the base directory
BASE_DIR="/home/ubuntu/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"
VENV_DIR="/home/ubuntu/rasa-env-21"

# Function to stop a service
stop_service() {
    local name=$1
    if [ -f "$LOG_DIR/${name}.pid" ]; then
        pid=$(cat "$LOG_DIR/${name}.pid")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Stopping $name (PID: $pid)..."
            kill $pid
            # Wait for the process to stop
            for i in {1..5}; do
                if ! ps -p $pid > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo "Force stopping $name..."
                kill -9 $pid
            fi
            rm "$LOG_DIR/${name}.pid"
            echo "✅ $name stopped"
        else
            echo "❌ $name is not running"
            rm "$LOG_DIR/${name}.pid"
        fi
    else
        echo "❌ No PID file found for $name"
    fi
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
        else
            echo "❌ Failed to stop process on port $port"
            return 1
        fi
    else
        echo "✅ No process running on port $port"
    fi
}

# Function to stop Celery worker
stop_celery() {
    echo "Stopping Celery worker..."
    local pid_file="$LOG_DIR/celery.pid"
    local success=false

    # First try graceful shutdown if PID file exists
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Sending TERM signal to Celery worker (PID: $pid)..."
            kill -TERM $pid
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p $pid > /dev/null 2>&1; then
                    success=true
                    break
                fi
                sleep 1
            done
            
            # Force kill if still running
            if ! $success; then
                echo "Force stopping Celery worker..."
                kill -9 $pid 2>/dev/null
                success=true
            fi
            
            rm -f "$pid_file"
            echo "✅ Celery worker stopped"
        else
            echo "Celery worker PID $pid not found"
            rm -f "$pid_file"
        fi
    else
        echo "No PID file found for Celery worker"
    fi

    # Cleanup any remaining Celery processes
    echo "Cleaning up remaining Celery processes..."
    
    # Find all Celery-related processes
    local celery_pids=$(pgrep -f "celery|celeryd|celerybeat" 2>/dev/null)
    
    if [ ! -z "$celery_pids" ]; then
        echo "Found Celery processes: $celery_pids"
        
        # First try graceful shutdown
        for pid in $celery_pids; do
            echo "Sending TERM signal to Celery process $pid..."
            kill -TERM $pid 2>/dev/null
        done
        
        # Wait for processes to stop
        sleep 2
        
        # Check if any processes are still running
        celery_pids=$(pgrep -f "celery|celeryd|celerybeat" 2>/dev/null)
        if [ ! -z "$celery_pids" ]; then
            echo "Some Celery processes still running, force stopping..."
            for pid in $celery_pids; do
                echo "Force stopping Celery process $pid..."
                kill -9 $pid 2>/dev/null
            done
        fi
    fi

    # Final verification
    if ! pgrep -f "celery|celeryd|celerybeat" > /dev/null; then
        echo "✅ All Celery processes stopped"
        return 0
    else
        echo "❌ Failed to stop all Celery processes"
        return 1
    fi
}

# Function to stop Flower monitoring
stop_flower() {
    echo "Stopping Flower monitoring..."
    local pid_file="$LOG_DIR/flower.pid"
    
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Stopping Flower (PID: $pid)..."
            kill $pid
            
            # Wait for graceful shutdown
            for i in {1..5}; do
                if ! ps -p $pid > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo "Force stopping Flower..."
                kill -9 $pid
            fi
            
            rm -f "$pid_file"
            echo "✅ Flower stopped"
        else
            echo "Flower PID $pid not found"
            rm -f "$pid_file"
        fi
    else
        echo "No PID file found for Flower"
    fi
}

# Function to stop Redis server
stop_redis() {
    echo "Stopping Redis server..."
    local pid_file="$LOG_DIR/redis.pid"
    local port=6379
    
    # Try to stop Redis gracefully first
    if command -v redis-cli &> /dev/null; then
        echo "Attempting graceful shutdown..."
        redis-cli shutdown 2>/dev/null
        sleep 2
    fi
    
    # Try to stop system Redis service
    if [ -f "/etc/init.d/redis-server" ]; then
        echo "Stopping system Redis service..."
        sudo service redis-server stop
        sleep 2
    fi
    
    # Check PID file
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Stopping Redis process (PID: $pid)..."
            kill $pid
            # Wait for the process to stop
            for i in {1..5}; do
                if ! ps -p $pid > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo "Force stopping Redis..."
                kill -9 $pid
            fi
            rm -f "$pid_file"
        else
            echo "Redis PID $pid not found"
            rm -f "$pid_file"
        fi
    fi
    
    # Find and kill any remaining Redis processes
    local redis_pids=$(pgrep -f "redis-server" 2>/dev/null)
    if [ ! -z "$redis_pids" ]; then
        echo "Found remaining Redis processes: $redis_pids"
        for pid in $redis_pids; do
            echo "Stopping Redis process $pid..."
            sudo kill $pid 2>/dev/null
        done
        sleep 2
        
        # Force kill any still running
        redis_pids=$(pgrep -f "redis-server" 2>/dev/null)
        if [ ! -z "$redis_pids" ]; then
            echo "Force stopping remaining Redis processes..."
            for pid in $redis_pids; do
                sudo kill -9 $pid 2>/dev/null
            done
        fi
    fi
    
    # Check if port is still in use
    if sudo lsof -i:$port > /dev/null 2>&1; then
        echo "❌ Port $port is still in use"
        return 1
    fi
    
    echo "✅ Redis server stopped"
    return 0
}

# Refactored function to stop a Celery worker for a given queue
stop_celery_worker() {
    local queue_name=$1
    local pid_file="$LOG_DIR/celery_${queue_name}.pid"
    echo "Stopping celery_$queue_name worker..."
    
    # First try graceful shutdown if PID file exists
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Sending TERM signal to celery_$queue_name (PID: $pid)..."
            kill -TERM $pid
            sleep 2
            if ps -p $pid > /dev/null 2>&1; then
                echo "Force stopping celery_$queue_name..."
                kill -9 $pid
                sleep 2
            fi
        fi
        rm -f "$pid_file"
    fi

    # Find and kill any processes by queue name
    local worker_pids=$(pgrep -f "celery.*worker.*$queue_name" 2>/dev/null)
    if [ ! -z "$worker_pids" ]; then
        echo "Found additional celery_$queue_name processes: $worker_pids"
        for pid in $worker_pids; do
            kill -9 $pid 2>/dev/null
        done
        sleep 2
    fi

    # Verify worker is stopped
    if ! pgrep -f "celery.*worker.*$queue_name" > /dev/null; then
        echo "✅ celery_$queue_name stopped"
        return 0
    else
        echo "❌ Failed to stop celery_$queue_name"
        return 1
    fi
}

# Stop all services
echo "Stopping all services..."

# Stop Redis first
stop_redis

# Stop main services
for service in rasa rasa_actions flask_server; do
    stop_service $service
done

# Stop Celery workers first
echo "Stopping Celery workers..."
stop_celery_worker "default"
stop_celery_worker "llm_queue"

# Stop Flower monitoring
stop_flower

# Kill processes on specific ports
echo -e "\nChecking for processes on specific ports..."
kill_process_by_port 5001  # Flask server
kill_process_by_port 5005  # Rasa server
kill_process_by_port 5055  # Action server
kill_process_by_port 5555  # Flower monitoring
kill_process_by_port 6379  # Redis server

# Final cleanup of any remaining Celery processes
echo "Performing final Celery cleanup..."
pkill -f "celery.*worker" 2>/dev/null
sleep 2
pkill -9 -f "celery.*worker" 2>/dev/null
sleep 2

# Verify all services are stopped
echo -e "\nVerifying all services are stopped..."
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
            echo "❌ $service is still running (PID: $pid)"
        else
            echo "✅ $service is stopped"
        fi
    else
        echo "✅ $service is stopped"
    fi
done

# Verify ports are free
echo -e "\nVerifying ports are free..."
for port in 5001 5005 5055 5555 6379; do
    if sudo lsof -i:$port > /dev/null 2>&1; then
        echo "❌ Port $port is still in use"
    else
        echo "✅ Port $port is free"
    fi
done

# Final verification of Celery workers
echo -e "\nFinal verification of Celery workers..."
if ! pgrep -f "celery.*worker" > /dev/null; then
    echo "✅ All Celery workers are stopped"
else
    echo "❌ Some Celery workers are still running:"
    ps -ef | grep "celery.*worker" | grep -v grep
fi

echo -e "\nAll services have been stopped"

# --- ADDITION: Ensure ports are truly free ---
ensure_port_free() {
    local port=$1
    local max_attempts=5
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if sudo lsof -i :$port > /dev/null 2>&1; then
            echo "Port $port is still in use. Attempting to kill process..."
            local pid=$(sudo lsof -t -i :$port)
            sudo kill $pid
            sleep 2
            # Force kill if still running
            if sudo lsof -i :$port > /dev/null 2>&1; then
                echo "Force killing process on port $port..."
                sudo kill -9 $pid
            fi
            sleep 2
        else
            echo "✅ Port $port is free (post-stop verification)"
            return 0
        fi
        attempt=$((attempt+1))
        sleep 2
    done
    # Final check
    if sudo lsof -i :$port > /dev/null 2>&1; then
        echo "❌ Port $port could not be freed after $max_attempts attempts. Manual intervention may be required."
    fi
}

# Call ensure_port_free for all relevant ports
for port in 5001 5005 5055 5555 6379; do
    ensure_port_free $port
done 