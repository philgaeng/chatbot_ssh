#!/bin/bash

# Set the base directory and environment variables
BASE_DIR="/home/philg/projects/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"
VENV_DIR="/home/philg/projects/nepal_chatbot/rasa-env-21"

# Create necessary directories
mkdir -p "$LOG_DIR"

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

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        echo "Port $port is already in use. Attempting to free it..."
        if ! kill_process_by_port $port; then
            echo "❌ Could not free port $port. Please stop the service using this port manually."
            return 1
        fi
    fi
    return 0
}

# Function to start a service
start_service() {
    local name=$1
    local command=$2
    local port=$3
    local log_file="$LOG_DIR/${name}.log"
    local pid_file="$LOG_DIR/${name}.pid"
    
    echo "Starting $name..."
    if check_port $port; then
        cd "$BASE_DIR" && \
        PYTHONPATH=$BASE_DIR \
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
for service in rasa rasa_actions flask_server; do
    if [ -f "$LOG_DIR/${service}.pid" ]; then
        kill $(cat "$LOG_DIR/${service}.pid") 2>/dev/null
        rm "$LOG_DIR/${service}.pid"
    fi
done

# Check and stop systemd-managed flask server if running
if systemctl is-active --quiet flask_server; then
    echo "Stopping systemd-managed flask_server..."
    sudo systemctl stop flask_server
    sleep 2
fi

# Ensure ports are free
echo "Ensuring ports are free..."
kill_process_by_port 5005  # Rasa main server port
kill_process_by_port 5055  # Rasa actions server port
kill_process_by_port 5001  # Flask server port

# Start services
echo -e "\nStarting services..."

# Start Rasa Actions server
if ! start_service "rasa_actions" "rasa run actions --debug" 5055; then
    echo "❌ Failed to start rasa_actions. Exiting..."
    exit 1
fi

# Start Rasa server
if ! start_service "rasa" "rasa run --enable-api --cors \"*\" --debug" 5005; then
    echo "❌ Failed to start rasa. Exiting..."
    exit 1
fi

# Start Flask file server
if ! start_service "flask_server" "python actions_server/app.py" 5001; then
    echo "❌ Failed to start flask_server. Exiting..."
    exit 1
fi

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 5

# Check service status
echo -e "\nChecking service status:"
for service in rasa rasa_actions flask_server; do
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

echo -e "\nRasa services have been started. Logs can be found in $LOG_DIR" 