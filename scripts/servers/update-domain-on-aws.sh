#!/bin/bash
# Update AWS server configuration for new domain: stratcon.facets-ai.com
# This script updates nginx configuration and restarts services

set -e

DOMAIN="stratcon.facets-ai.com"
AWS_SERVER_IP="52.221.59.184"
SSH_KEY="${HOME}/.ssh/aws-key.pem"

echo "🌐 Updating AWS server for domain: $DOMAIN"
echo "=========================================="
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ Error: SSH key not found at $SSH_KEY"
    exit 1
fi

echo "📝 Step 1: Updating Nginx configuration on AWS..."
ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP << 'EOF'
set -e
DOMAIN="stratcon.facets-ai.com"

# Backup current config
sudo cp /etc/nginx/sites-available/stratcon /etc/nginx/sites-available/stratcon.backup.$(date +%Y%m%d_%H%M%S)

# Update nginx config with new domain
sudo tee /etc/nginx/sites-available/stratcon > /dev/null << 'NGINX_EOF'
# Upstream definitions
upstream backend_api {
    server 127.0.0.1:8000;
}

upstream frontend_app {
    server 127.0.0.1:3000;
}

# HTTP server (redirects to HTTPS)
server {
    listen 80;
    server_name stratcon.facets-ai.com 52.221.59.184;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name stratcon.facets-ai.com 52.221.59.184;

    # SSL configuration
    ssl_certificate /etc/nginx/ssl/stratcon.crt;
    ssl_certificate_key /etc/nginx/ssl/stratcon.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Frontend (Next.js)
    location / {
        proxy_pass http://frontend_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend_api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Direct API access (for backward compatibility)
    location ~ ^/(clients|buildings|tenants|reports|settings|meters)/ {
        proxy_pass http://backend_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_EOF

echo "✅ Nginx configuration updated"
EOF

echo ""
echo "🧪 Step 2: Testing Nginx configuration..."
ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP "sudo nginx -t"

echo ""
echo "🔄 Step 3: Reloading Nginx..."
ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP "sudo systemctl reload nginx"

echo ""
echo "🔍 Step 4: Checking frontend service status..."
ssh -i "$SSH_KEY" ubuntu@$AWS_SERVER_IP << 'EOF'
# Check if frontend is running
if pgrep -f "next.*start" > /dev/null || pgrep -f "node.*3000" > /dev/null; then
    echo "✅ Frontend process is running"
    ps aux | grep -E "next|node.*3000" | grep -v grep | head -2
else
    echo "⚠️  Frontend is not running. Starting it..."
    cd ~/stratcon/website
    if [ -f .env.local ]; then
        export $(cat .env.local | grep -v '^#' | xargs)
    fi
    # Start in background
    nohup npm run start > /tmp/frontend.log 2>&1 &
    echo "✅ Frontend started (check /tmp/frontend.log for output)"
fi

# Check if port 3000 is listening
if sudo ss -tlnp | grep -q ":3000"; then
    echo "✅ Port 3000 is listening"
    sudo ss -tlnp | grep ":3000"
else
    echo "⚠️  Port 3000 is not listening"
fi
EOF

echo ""
echo "=========================================="
echo "✅ Domain update complete!"
echo "=========================================="
echo ""
echo "🌐 Access your application at:"
echo "   https://$DOMAIN"
echo ""
echo "📋 Next steps:"
echo "   1. Update Cognito redirect URIs to include:"
echo "      - https://$DOMAIN/login"
echo "   2. Test the application at https://$DOMAIN"
echo ""

