#!/bin/bash

# Define a log file for capturing output
LOG_FILE="/app/logs/train.log"

# Debugging: Check if /app exists and permissions
echo "Checking if /app directory exists and its permissions..."
ls -ld /app || { echo "Error: /app directory does not exist."; exit 1; }

echo "Checking if /app/logs exists..."
if [ ! -d "/app/logs" ]; then
    echo "Creating /app/logs directory..."
    mkdir -p /app/logs
    if [ $? -eq 0 ]; then
        echo "/app/logs directory created successfully."
    else
        echo "Error: Failed to create /app/logs directory."
        exit 1
    fi
else
    echo "/app/logs directory already exists."
fi

# Verify the existence of the /app/logs directory again
if [ -d "/app/logs" ]; then
    echo "Confirmed: /app/logs directory is present."
else
    echo "Error: /app/logs directory is missing despite earlier check."
    exit 1
fi

# Debugging: Log directory structure and permissions
echo "Checking permissions for /app and /app/logs..." | tee -a $LOG_FILE
ls -ld /app /app/logs | tee -a $LOG_FILE

# Check for required files
for file in "/app/config.yml" "/app/domain" "/app/data"; do
    if [ ! -e "$file" ]; then
        echo "Error: Required file or directory '$file' not found!" | tee -a $LOG_FILE
        exit 1
    fi
done

# Train the model
echo "Starting Rasa training process..." | tee -a $LOG_FILE
rasa train --domain /app/domain --data /app/data --config /app/config.yml --out /app/models/ >> $LOG_FILE 2>&1

# Check if the training process succeeded
if [ $? -eq 0 ]; then
    echo "Training completed successfully. Model saved to /app/models." | tee -a $LOG_FILE
else
    echo "Error: Training failed. See logs for details." | tee -a $LOG_FILE
    exit 1
fi