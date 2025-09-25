#!/bin/bash

# Quick script to check ngrok status

if [ -f /tmp/ngrok_status.txt ]; then
    source /tmp/ngrok_status.txt
    echo "🌍 ngrok URL: $NGROK_URL"
    echo "🔄 Status: $(ps -p $NGROK_PID > /dev/null 2>&1 && echo "Running" || echo "Stopped")"
else
    echo "⚠️  No ngrok tunnel found"
fi
