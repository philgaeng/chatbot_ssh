#!/bin/bash

# Set environment variables
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=test_password
export UPLOAD_FOLDER=/tmp/uploads
export ALLOWED_EXTENSIONS=wav,mp3,mp4

# Run the tests
python -m unittest task_queue/test_tasks.py 