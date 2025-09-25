#!/bin/bash

# Quick script to stop ngrok tunnel

echo "🛑 Stopping ngrok tunnel..."

if [ -f /tmp/ngrok_status.txt ]; then
    source /tmp/ngrok_status.txt
    kill $NGROK_PID 2>/dev/null || true
    rm -f /tmp/ngrok_status.txt
    echo "✅ ngrok tunnel stopped"
else
    pkill -f "ngrok.*http.*5001" || true
    echo "✅ Any running ngrok tunnels stopped"
fi
