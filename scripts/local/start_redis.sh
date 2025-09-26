#!/bin/bash

# Set the base directory
BASE_DIR="/home/philg/projects/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"
REDIS_PASSWORD="3fduLmg25@k"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to check if Redis is already running
check_redis() {
    local redis_cli_cmd="redis-cli"
    if [ ! -z "$REDIS_PASSWORD" ]; then
        redis_cli_cmd="$redis_cli_cmd -a $REDIS_PASSWORD"
    fi
    $redis_cli_cmd ping &> /dev/null
}

# Stop any existing Redis processes
echo "Checking for existing Redis processes..."
if check_redis; then
    echo "Redis is already running. Stopping it first..."
    redis-cli -a "$REDIS_PASSWORD" shutdown
    sleep 2
fi

# Kill any remaining Redis processes
redis_pids=$(pgrep -f "redis-server" 2>/dev/null)
if [ ! -z "$redis_pids" ]; then
    echo "Stopping Redis processes: $redis_pids"
    sudo kill -9 $redis_pids 2>/dev/null
    sleep 2
fi

# Clear old files
rm -f "$LOG_DIR/redis.pid" "$LOG_DIR/redis.log"

# Start Redis server using the standalone config file
echo "Starting Redis server with standalone configuration..."
redis-server "$BASE_DIR/scripts/servers/redis.conf"

# Wait for Redis to start
echo "Waiting for Redis to start..."
sleep 3

# Test Redis connection
if check_redis; then
    echo "✅ Redis server started successfully"
    echo "Redis PID: $(cat $LOG_DIR/redis.pid 2>/dev/null || echo 'PID file not found')"
    echo "Redis log: $LOG_DIR/redis.log"
    echo "Test connection: redis-cli -a '$REDIS_PASSWORD' ping"
else
    echo "❌ Failed to start Redis server"
    echo "Check logs at: $LOG_DIR/redis.log"
    exit 1
fi 