#!/bin/bash

# Check the debug mode flag (default to false if not set)
DEBUG_MODE=${DEBUG_MODE:-true}

# Debugging
echo "Checking permissions for /app/actions..."
ls -ld /app/actions /app/actions/__init__.py

# Determine debug flag for Rasa servers
RASA_DEBUG_FLAG=""
if [ "$DEBUG_MODE" == "true" ]; then
    RASA_DEBUG_FLAG="--debug"
    echo "Debug mode enabled for both servers."
else
    echo "Running in production mode."
fi

# Start the Rasa server
echo "Starting Rasa server on port 5005..."
rasa run --enable-api --cors "*" --port 5005 $RASA_DEBUG_FLAG > /app/logs/rasa_server.log 2>&1 &
if [ $? -ne 0 ]; then
    echo "Error: Failed to start Rasa server."
    cat /app/logs/rasa_server.log
    exit 1
fi

# Start the Rasa action server
echo "Starting Rasa action server on port 5055..."
rasa run actions --actions actions --port 5055 $RASA_DEBUG_FLAG > /app/logs/rasa_actions.log 2>&1 &
if [ $? -ne 0 ]; then
    echo "Error: Failed to start Rasa action server."
    cat /app/logs/rasa_actions.log
    exit 1
fi

# Give servers time to start and check logs
sleep 5
if ! grep -q "Rasa server is up and running" /app/logs/rasa_server.log; then
    echo "Rasa server failed to start. Logs:"
    cat /app/logs/rasa_server.log
    exit 1
fi

if ! grep -q "Action endpoint is up and running" /app/logs/rasa_actions.log; then
    echo "Action server failed to start. Logs:"
    cat /app/logs/rasa_actions.log
    exit 1
fi

echo "Servers are running. Monitoring logs..."
tail -f /app/logs/rasa_server.log /app/logs/rasa_actions.log
