#!/bin/bash
# Launch servers on remote AWS server via SSH
# Usage: ./scripts/servers/launch-servers-remote.sh [--background] [--stop-first]

set -e

AWS_SERVER_IP="18.141.5.167"
SSH_KEY="${HOME}/.ssh/aws-key.pem"
PROJECT_DIR="/home/ubuntu/nepal_chatbot"
LAUNCH_SCRIPT="$PROJECT_DIR/scripts/servers/launch_servers.sh"
BACKGROUND=false
STOP_FIRST=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --background)
            BACKGROUND=true
            shift
            ;;
        --stop-first)
            STOP_FIRST=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--background] [--stop-first]"
            exit 1
            ;;
    esac
done

echo "🚀 Launching servers on remote server"
echo "======================================"
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
    echo "   Please check:"
    echo "   - Server is running"
    echo "   - SSH key permissions: chmod 600 $SSH_KEY"
    echo "   - Firewall allows SSH (port 22)"
    exit 1
fi

echo "✅ SSH connection successful"
echo ""

# Check if launch script exists on server
echo "📋 Checking launch script on server..."
if ! ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP "test -f $LAUNCH_SCRIPT"; then
    echo "❌ Error: Launch script not found at $LAUNCH_SCRIPT on server"
    exit 1
fi

echo "✅ Launch script found"
echo ""

# Stop existing services if requested
if [ "$STOP_FIRST" == "true" ]; then
    echo "🛑 Stopping existing services..."
    ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP << 'STOP_EOF'
    cd /home/ubuntu/nepal_chatbot
    
    # Kill processes by PID files
    if [ -d "logs" ]; then
        for pid_file in logs/*.pid; do
            if [ -f "$pid_file" ]; then
                pid=$(cat "$pid_file" 2>/dev/null)
                if ps -p "$pid" > /dev/null 2>&1; then
                    echo "Stopping process $pid from $pid_file..."
                    kill "$pid" 2>/dev/null || true
                fi
            fi
        done
    fi
    
    # Kill by process name patterns
    pkill -f "rasa run" 2>/dev/null || true
    pkill -f "celery.*worker" 2>/dev/null || true
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "http.server" 2>/dev/null || true
    
    # Stop Redis if running
    redis-cli -a "3fduLmg25@k" shutdown 2>/dev/null || true
    
    sleep 3
    echo "✅ Services stopped"
STOP_EOF
    echo ""
fi

# Launch servers
if [ "$BACKGROUND" == "true" ]; then
    echo "🚀 Launching servers in background..."
    ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP << EOF
    cd $PROJECT_DIR
    nohup bash $LAUNCH_SCRIPT > /tmp/launch_servers.log 2>&1 &
    echo "Launch script started in background (PID: \$!)"
    echo "Logs: /tmp/launch_servers.log"
EOF
    echo ""
    echo "✅ Servers are starting in background"
    echo ""
    echo "📋 To check status:"
    echo "   ssh -i $SSH_KEY ubuntu@$AWS_SERVER_IP 'tail -f /tmp/launch_servers.log'"
    echo ""
    echo "📋 To check service status:"
    echo "   ssh -i $SSH_KEY ubuntu@$AWS_SERVER_IP 'cd $PROJECT_DIR && ./scripts/servers/launch_servers.sh' # (will show status)"
else
    echo "🚀 Launching servers..."
    echo "   (Press Ctrl+C to stop - this will only stop the SSH connection, not the servers)"
    echo ""
    
    # Run in foreground with output
    ssh -i "$SSH_KEY" -t ubuntu@$AWS_SERVER_IP << EOF
    cd $PROJECT_DIR
    bash $LAUNCH_SCRIPT
EOF
    
    echo ""
    echo "✅ Launch script completed"
fi

echo ""
echo "📋 Summary:"
echo "   - Servers launched on $AWS_SERVER_IP"
if [ "$BACKGROUND" == "true" ]; then
    echo "   - Running in background"
fi
if [ "$STOP_FIRST" == "true" ]; then
    echo "   - Previous services stopped first"
fi
echo ""
echo "🚀 Next steps:"
echo "   - Check server logs: ssh -i $SSH_KEY ubuntu@$AWS_SERVER_IP 'tail -f $PROJECT_DIR/logs/*.log'"
echo "   - Check service status: ssh -i $SSH_KEY ubuntu@$AWS_SERVER_IP 'ps aux | grep -E \"rasa|celery|flask\"'"

