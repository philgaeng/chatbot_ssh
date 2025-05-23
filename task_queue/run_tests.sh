#!/bin/bash

# Set environment variables
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export REDIS_DB="0"
export REDIS_PASSWORD=${REDIS_PASSWORD:-"test_password"}

# Print environment variables
echo "Environment variables:"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PORT: $REDIS_PORT"
echo "REDIS_DB: $REDIS_DB"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"

# Construct Redis URL with password only
REDIS_URL="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
echo -e "\nRedis URL: $REDIS_URL"

# Export Redis URL for Celery
export CELERY_BROKER_URL=$REDIS_URL
export CELERY_RESULT_BACKEND=$REDIS_URL

# Run tests
echo -e "\n########################################################"
echo "Running TestGrievanceWorkflow tests"
echo "########################################################"
python -m unittest task_queue.test_tasks.TestGrievanceWorkflow
echo -e "\n--------------------------------------------------------"
echo "All tests completed"
echo "--------------------------------------------------------"