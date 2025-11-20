#!/bin/bash
# Sync server codebase with main branch from GitHub
# Usage: ./scripts/servers/sync-server-with-main.sh [--restart-services]

set -e

AWS_SERVER_IP="18.141.5.167"
SSH_KEY="${HOME}/.ssh/aws-key.pem"
PROJECT_DIR="/home/ubuntu/nepal_chatbot"
RESTART_SERVICES=false

# Parse arguments
if [ "$1" == "--restart-services" ]; then
    RESTART_SERVICES=true
fi

echo "🔄 Syncing server with main branch from GitHub"
echo "=============================================="
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

# Sync with main branch
echo "📥 Syncing with origin/main..."
ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP << EOF
set -e

cd $PROJECT_DIR

# Check if directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found at $PROJECT_DIR"
    exit 1
fi

# Check current branch
CURRENT_BRANCH=\$(git rev-parse --abbrev-ref HEAD)
echo "📍 Current branch: \$CURRENT_BRANCH"

# Fetch latest changes
echo "📥 Fetching latest changes from GitHub..."
git fetch origin main

# Check if we're on main branch
if [ "\$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Warning: Not on main branch. Switching to main..."
    git checkout main
fi

# Show status before pull
echo ""
echo "📊 Status before pull:"
git status --short

# Handle local changes (prefer remote version)
if [ -n "\$(git status --porcelain)" ]; then
    echo ""
    echo "⚠️  Local changes detected. Stashing to prefer remote version..."
    git stash push -m "Stashed before sync with main - \$(date +%Y%m%d_%H%M%S)"
    echo "✅ Local changes stashed (can recover with 'git stash list' and 'git stash pop' if needed)"
fi

# Pull latest changes (should be clean after stashing)
echo ""
echo "⬇️  Pulling latest changes from origin/main..."
if ! git pull origin main; then
    # If pull still fails, reset hard to match remote exactly
    echo "⚠️  Pull failed. Resetting to match origin/main exactly..."
    git reset --hard origin/main
    echo "✅ Reset to match origin/main"
fi

# Show status after pull
echo ""
echo "📊 Status after pull:"
git status --short

# Show last commit
echo ""
echo "📝 Latest commit:"
git log -1 --oneline

echo ""
echo "✅ Successfully synced with origin/main!"
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error: Sync failed"
    exit 1
fi

echo ""
echo "✅ Server successfully synced with main branch!"

# Optionally restart services
if [ "$RESTART_SERVICES" == "true" ]; then
    echo ""
    echo "🔄 Restarting services..."
    ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP << 'RESTART_EOF'
    cd /home/ubuntu/nepal_chatbot
    
    # Check if services are running via systemd
    if systemctl is-active --quiet nepal-rasa 2>/dev/null; then
        echo "🔄 Restarting systemd services..."
        sudo systemctl restart nepal-rasa nepal-actions nepal-flask nepal-celery-llm 2>/dev/null || echo "⚠️  Some services may not be managed by systemd"
    else
        echo "ℹ️  Services not managed by systemd. Please restart manually if needed."
    fi
    
    echo "✅ Service restart completed"
RESTART_EOF
fi

echo ""
echo "📋 Summary:"
echo "   - Server synced with origin/main"
if [ "$RESTART_SERVICES" == "true" ]; then
    echo "   - Services restarted"
fi
echo ""
echo "🚀 Next steps:"
echo "   - Verify deployment on server"
echo "   - Check logs if needed: ssh -i $SSH_KEY ubuntu@$AWS_SERVER_IP 'tail -f $PROJECT_DIR/logs/*.log'"

