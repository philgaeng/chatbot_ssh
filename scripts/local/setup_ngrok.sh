#!/bin/bash

# Setup script for ngrok tunnel for local Google Sheets monitoring
# This script helps expose your local Flask API to Google Sheets

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NGROK_PORT=5001
NGROK_CONFIG_DIR="$HOME/.ngrok2"
NGROK_CONFIG_FILE="$NGROK_CONFIG_DIR/ngrok.yml"

echo -e "${BLUE}🚀 Setting up ngrok for local Google Sheets monitoring${NC}"
echo

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo -e "${YELLOW}⚠️  ngrok is not installed. Installing...${NC}"
    
    # Install ngrok (for Ubuntu/Debian)
    if command -v apt &> /dev/null; then
        curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
        echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
        sudo apt update && sudo apt install ngrok
    else
        echo -e "${RED}❌ Please install ngrok manually: https://ngrok.com/download${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ ngrok is installed${NC}"

# Check if ngrok is authenticated
if [ ! -f "$NGROK_CONFIG_FILE" ]; then
    echo -e "${YELLOW}⚠️  ngrok needs to be authenticated${NC}"
    echo -e "${BLUE}Please visit: https://dashboard.ngrok.com/get-started/your-authtoken${NC}"
    echo -e "${BLUE}Then run: ngrok config add-authtoken YOUR_AUTH_TOKEN${NC}"
    echo
    read -p "Have you set up your ngrok authtoken? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Please set up ngrok authtoken first${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ ngrok authentication configured${NC}"

# Function to start ngrok tunnel
start_ngrok() {
    echo -e "${BLUE}🌐 Starting ngrok tunnel on port $NGROK_PORT...${NC}"
    
    # Kill any existing ngrok processes
    pkill -f "ngrok.*http.*$NGROK_PORT" || true
    
    # Start ngrok in background
    ngrok http $NGROK_PORT --log=stdout > /tmp/ngrok.log 2>&1 &
    NGROK_PID=$!
    
    # Wait for ngrok to start
    sleep 5
    
    # Get the public URL (without jq dependency)
    echo "Checking ngrok API..."
    NGROK_RESPONSE=$(curl -s http://localhost:4040/api/tunnels)
    echo "ngrok API response: $NGROK_RESPONSE"
    NGROK_URL=$(echo "$NGROK_RESPONSE" | grep -o '"public_url":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ -n "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ]; then
        echo -e "${GREEN}✅ ngrok tunnel started successfully!${NC}"
        echo -e "${BLUE}🌍 Public URL: $NGROK_URL${NC}"
        echo -e "${YELLOW}📝 Use this URL in your Google Sheets configuration${NC}"
        echo
        
        # Create a simple status file
        cat > /tmp/ngrok_status.txt << EOF
NGROK_PID=$NGROK_PID
NGROK_URL=$NGROK_URL
NGROK_PORT=$NGROK_PORT
STARTED_AT=$(date)
EOF
        
        echo -e "${BLUE}📊 To check status: ./scripts/local/check_ngrok.sh${NC}"
        echo -e "${BLUE}🛑 To stop: ./scripts/local/stop_ngrok.sh${NC}"
        
    else
        echo -e "${RED}❌ Failed to get ngrok URL. Check if your Flask server is running on port $NGROK_PORT${NC}"
        echo -e "${YELLOW}💡 Make sure to start your local servers first: ./scripts/local/launch_servers.sh${NC}"
        kill $NGROK_PID 2>/dev/null || true
        exit 1
    fi
}

# Function to stop ngrok
stop_ngrok() {
    echo -e "${BLUE}🛑 Stopping ngrok tunnel...${NC}"
    
    if [ -f /tmp/ngrok_status.txt ]; then
        source /tmp/ngrok_status.txt
        if [ -n "$NGROK_PID" ]; then
            kill $NGROK_PID 2>/dev/null || true
        fi
    fi
    
    pkill -f "ngrok.*http.*$NGROK_PORT" || true
    rm -f /tmp/ngrok_status.txt
    
    echo -e "${GREEN}✅ ngrok tunnel stopped${NC}"
}

# Main script logic
case "${1:-start}" in
    "start")
        start_ngrok
        ;;
    "stop")
        stop_ngrok
        ;;
    "restart")
        stop_ngrok
        sleep 2
        start_ngrok
        ;;
    "status")
        if [ -f /tmp/ngrok_status.txt ]; then
            source /tmp/ngrok_status.txt
            echo -e "${BLUE}📊 ngrok Status:${NC}"
            echo -e "  PID: $NGROK_PID"
            echo -e "  URL: $NGROK_URL"
            echo -e "  Port: $NGROK_PORT"
            echo -e "  Started: $STARTED_AT"
            
            # Check if process is still running
            if ps -p $NGROK_PID > /dev/null 2>&1; then
                echo -e "  Status: ${GREEN}Running${NC}"
            else
                echo -e "  Status: ${RED}Stopped${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  No ngrok tunnel found${NC}"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo
        echo "  start   - Start ngrok tunnel (default)"
        echo "  stop    - Stop ngrok tunnel"
        echo "  restart - Restart ngrok tunnel"
        echo "  status  - Show tunnel status"
        exit 1
        ;;
esac
