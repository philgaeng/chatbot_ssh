#!/bin/bash
# Stop all servers on remote AWS server via SSH
# Usage: ./scripts/servers/stop-servers-remote.sh

set -e

AWS_SERVER_IP="18.141.5.167"
SSH_KEY="${HOME}/.ssh/aws-key.pem"
PROJECT_DIR="/home/ubuntu/nepal_chatbot"

echo "🛑 Stopping servers on remote server"
echo "===================================="
echo ""
echo "Server: $AWS_SERVER_IP"
echo "Project: $PROJECT_DIR"
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ Error: SSH key not found at $SSH_KEY"
    exit 1
fi

# Test SSH connection
echo "🔌 Testing SSH connection..."
if ! ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@$AWS_SERVER_IP "echo 'Connection successful'" 2>/dev/null; then
    echo "❌ Error: Cannot connect to server at $AWS_SERVER_IP"
    exit 1
fi

echo "✅ SSH connection successful"
echo ""

# Stop services
echo "🛑 Stopping all services..."
ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP << 'STOP_EOF'
set -e

cd /home/ubuntu/nepal_chatbot
LOG_DIR="logs"

echo "Checking for running services..."

# Kill processes by PID files
if [ -d "logs" ]; then
    for pid_file in logs/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file" 2>/dev/null || echo "")
            if [ ! -z "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
                service_name=$(basename "$pid_file" .pid)
                echo "Stopping $service_name (PID: $pid)..."
                kill "$pid" 2>/dev/null || true
                sleep 1
                if ps -p "$pid" > /dev/null 2>&1; then
                    echo "Force stopping $service_name..."
                    kill -9 "$pid" 2>/dev/null || true
                fi
                rm -f "$pid_file"
            fi
        fi
    done
fi

# Kill by process name patterns
echo "Stopping Rasa processes..."
pkill -f "rasa run" 2>/dev/null && echo "✅ Rasa processes stopped" || echo "ℹ️  No Rasa processes found"

echo "Stopping Celery workers..."
pkill -f "celery.*worker" 2>/dev/null && echo "✅ Celery workers stopped" || echo "ℹ️  No Celery workers found"

echo "Stopping Flask/Python app processes..."
pkill -f "python.*app.py" 2>/dev/null && echo "✅ Flask app stopped" || echo "ℹ️  No Flask app found"

echo "Stopping HTTP servers..."
pkill -f "http.server" 2>/dev/null && echo "✅ HTTP servers stopped" || echo "ℹ️  No HTTP servers found"

# Stop Redis gracefully
echo "Stopping Redis..."
redis-cli -a "3fduLmg25@k" shutdown 2>/dev/null && echo "✅ Redis stopped" || {
    pkill -f "redis-server" 2>/dev/null && echo "✅ Redis stopped (force)" || echo "ℹ️  No Redis process found"
}

sleep 2

# Verify all stopped
echo ""
echo "Verifying all services stopped..."
remaining=$(pgrep -f -c "rasa|celery|redis-server|http.server|app.py" 2>/dev/null || echo "0")
if [ "$remaining" -eq 0 ]; then
    echo "✅ All services stopped"
else
    echo "⚠️  Warning: $remaining processes still running"
    echo "Remaining processes:"
    pgrep -f "rasa|celery|redis-server|http.server|app.py" 2>/dev/null | xargs ps -p 2>/dev/null || true
fi
STOP_EOF

echo ""
echo "✅ Stop command completed"
echo ""
echo "📋 To verify:"
echo "   ssh -i $SSH_KEY ubuntu@$AWS_SERVER_IP 'ps aux | grep -E \"rasa|celery|redis|flask\"'"

