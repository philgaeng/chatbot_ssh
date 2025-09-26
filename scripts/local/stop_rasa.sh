#!/bin/bash

# Set the base directory and environment variables
BASE_DIR="/home/philg/projects/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"

echo "Stopping Rasa services..."

# Function to stop a service
stop_service() {
    local service=$1
    local pid_file="$LOG_DIR/${service}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        echo "Stopping $service (PID: $pid)..."
        
        # Try graceful shutdown first
        kill $pid 2>/dev/null
        
        # Wait for process to stop
        local wait_time=0
        while ps -p $pid > /dev/null 2>&1 && [ $wait_time -lt 5 ]; do
            sleep 1
            wait_time=$((wait_time + 1))
        done
        
        # Force kill if still running
        if ps -p $pid > /dev/null 2>&1; then
            echo "Force stopping $service..."
            kill -9 $pid 2>/dev/null
            sleep 1
        fi
        
        # Remove PID file
        rm -f "$pid_file"
        
        # Verify process is stopped
        if ! ps -p $pid > /dev/null 2>&1; then
            echo "✅ $service stopped successfully"
            return 0
        else
            echo "❌ Failed to stop $service"
            return 1
        fi
    else
        echo "No PID file found for $service"
        return 0
    fi
}

# Stop Rasa services
stop_service "rasa"
stop_service "rasa_actions"
stop_service "flask_server"

echo -e "\nChecking if any Rasa processes are still running..."
if pgrep -f "rasa run" > /dev/null; then
    echo "Found remaining Rasa processes, force stopping..."
    pkill -f "rasa run"
    sleep 2
fi

# Check for any remaining file server processes
if pgrep -f "file_server.py" > /dev/null; then
    echo "Found remaining file server processes, force stopping..."
    pkill -f "file_server.py"
    sleep 2
fi

# Final verification
if ! pgrep -f "rasa run" > /dev/null && ! pgrep -f "file_server.py" > /dev/null; then
    echo "✅ All services have been stopped"
else
    echo "❌ Some processes could not be stopped"
fi 