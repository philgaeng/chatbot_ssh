### Prerequisites

- Python 3.10
- Rasa 3.6.21
- PostgreSQL database
- Redis server
- Celery
- Django 4.2+

## System Architecture

The Nepal Chatbot is a multi-component conversational AI system built with the following architecture:

### Core Components

1. **Rasa Core (NLP Engine)**
   - Handles natural language understanding and processing
   - Manages conversation flows and dialogue management
   - Supports both English and Nepali language processing
   - Runs on port 5005

2. **Action Server**
   - Executes custom actions and business logic
   - Handles database operations and external API integrations
   - Runs on port 5055

3. **Accessible Server**
   - Provides accessibility features for users with disabilities
   - Supports voice-based interactions
   - Runs on port 5001

4. **Web Interface**
   - Custom webchat interface for user interactions
   - Supports both text and voice input
   - Accessible design patterns implemented

5. **Flask Server**
   - Handles file uploads and management
   - Manages WebSocket connections for real-time communication
   - Processes voice recordings and file conversions
   - Serves as a bridge between frontend and backend services
   - Runs on port 5002

6. **Django Helpdesk**
   - Ticket management and workflow
   - User hierarchy management (PD, PM, Contractor)
   - Project type categorization
   - Automated reminders and notifications
   - Admin interface for ticket management
   - Runs on port 8000

### Supporting Infrastructure

1. **Nginx Web Server**
   - Acts as reverse proxy
   - Handles SSL/TLS termination
   - Routes requests to appropriate services
   - Manages static file serving

2. **PostgreSQL Database**
   - Stores user interactions and grievance data
   - Maintains conversation history
   - Handles data persistence
   - Shared database for both Rasa and Django Helpdesk

3. **Redis Server**
   - Message broker for Celery tasks
   - Caching layer for frequently accessed data
   - Session management
   - Real-time data storage for WebSocket connections

4. **Celery Task Queue**
   - Asynchronous task processing
   - Background job management
   - Handles long-running operations:
     - File processing
     - Voice transcription
     - Report generation
     - Email notifications
     - Ticket reminders and alerts
   - Distributed task execution

5. **File System**
   - Manages voice recordings and uploads
   - Organized directory structure for different file types
   - Secure file handling and permissions

### System Integration

- All components communicate via REST APIs
- WebSocket connections for real-time chat
- Secure data transmission using HTTPS
- Centralized logging system for monitoring and debugging
- Redis-based task queue for asynchronous operations
- Celery workers for distributed task processing
- Shared database access between Rasa and Django Helpdesk
- Django Admin interface for system management

### Process Management

1. **systemd Service Management**
   - Automated service startup and recovery
   - Process monitoring and automatic restarts
   - Service dependencies management
   - Log rotation and management
   - Environment-specific service configurations

2. **Service Configuration**
   - Individual systemd service files for each component
   - Environment-specific service parameters
   - Resource limits and constraints
   - Automatic restart policies
   - Health check monitoring

### Deployment Architecture

- Production, Testing, and Development environments
- Separate Nginx configurations for each environment
- Environment-specific domain routing
- Automated server management through run_servers.py
- Redis and Celery configuration per environment
- systemd service management across environments
- Django Helpdesk deployment per environment

## Complete Technical Documentation

Use the files [DOCUMENTATION.md](./DOCUMENTATION.md), [CONVERSATION_FLOW.md](./CONVERSATION_FLOW.md) and [SERVER_README.md](./SERVER_README.md) for complete instructions.


## Basic Commands

### Process Management:
1. **Kill all running server processes**:
   ```bash
   # Kill all Python processes related to the project
   pkill -f run_servers.py
   
   # If needed, kill with force
   pkill -9 -f run_servers.py
   ```

2. **Restart all servers**:
   ```bash
   cd /home/ubuntu/nepal_chatbot
   pkill -f run_servers.py; sleep 2; python3 run_servers.py --all
   ```

### Server Controls:
1. **Restart Nginx**:
   ```bash
   sudo systemctl restart nginx
   ```
2. **Check Nginx Status**:
   ```bash
   sudo systemctl status nginx
   ```
3. **Activate Virtual Environment** (if not using run_servers.py):
   ```bash
   source /home/ubuntu/nepal_chatbot/rasa-env/bin/activate
   ```
4. **Start Rasa Server manually**:
   ```bash
   rasa run --enable-api --cors "*" --debug
   # or without debug mode
   rasa run --enable-api --cors "*"
   ```

### Logs and Monitoring:
1. **View Nginx Logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```
2. **View Application Logs**:
   ```bash
   # For general logs
   tail -f /home/ubuntu/nepal_chatbot/logs/*.log
   
   # For specific server logs
   tail -f /home/ubuntu/nepal_chatbot/logs/actions_server.log
   tail -f /home/ubuntu/nepal_chatbot/logs/accessible_server.log
   tail -f /home/ubuntu/nepal_chatbot/logs/rasa_server.log
   ```

3. **Monitor PostgreSQL Database**:
   ```bash
   # Connect to PostgreSQL
   sudo -u postgres psql
   
   # List databases
   \l
   
   # Connect to the grievance database
   \c grievance_db
   
   # List tables
   \dt
   ```

### File Management:
1. **Create uploads directory** (if needed):
   ```bash
   # Create directory structure for uploads
   mkdir -p /home/ubuntu/nepal_chatbot/uploads/voice_recordings
   
   # Set appropriate permissions
   chmod -R 775 /home/ubuntu/nepal_chatbot/uploads
   chown -R ubuntu:www-data /home/ubuntu/nepal_chatbot/uploads
   ```

## Steps to Configure the Project

### 1. Update the Server Public IP in Nginx Configuration

we use the following extensions:
 - prod: production
 - test: testing
 - dev: development

1. Load the files from Github
The project is available at https://github.com/philgaeng/chatbot_ssh/tree/main
 
1. Open the Nginx configuration file:
The configurations files are copied in the nginx folder in the git repository. 
One needs to update them there and then copy paste them in /etc/nginx/sites-available/
   ```bash
   sudo nano /etc/nginx/sites-available/nepal_chatbot-{extension}.conf
   ```
2. Update the domain if necessary, as well as the elastic   IP address in the `server_name` directive.
3. Save and exit the file (`Ctrl+O`, then `Enter`, followed by `Ctrl+X`).
4. Provide read write execute rights to nginx (to be made the first time)
Steps to Grant Nginx (www-data) Permissions
   a. Change the Group Ownership to www-data
   Assign the www-data group to the directory and its contents:
   ```bash
   sudo chown -R ubuntu:www-data /home/ubuntu/nepal_chatbot
   ```
   Explanation: ubuntu remains the owner (primary user), www-data becomes the group owner, allowing Nginx to access it.

   b. Set Directory Permissions : Grant read, write, and execute permissions to the www-data group:
   ```bash
   sudo chmod -R 775 /home/ubuntu/nepal_chatbot
   ```

   c. Set the setgid Bit
   Ensure all new files and directories created in /home/ubuntu/nepal_chatbot/ automatically inherit the www-data group:
   ```bash
   sudo chmod g+s /home/ubuntu/nepal_chatbot
   ```
  
   d. Verify Permissions
   Check the directory's ownership and permissions:
   ```bash
   ls -ld /home/ubuntu/nepal_chatbot
   ```
   Expected output: drwxrwsr-x 2 ubuntu www-data 4096 Jan 30 02:55 /home/ubuntu/nepal_chatbot
   ubuntu is the owner, www-data is the group with read, write, and execute permissions.

5. Restart the Nginx service:
   ```bash
   sudo systemctl restart nginx
   ```

### 2. Update the Server Public IP in `config.js`
1. Navigate to the project directory:
   ```bash
   cd /home/ubuntu/nepal_chatbot/channels/webchat
   ```
2. Open the `config.js` file:
   ```bash
   nano config.js
   ```
3. Replace the domain with the updated domain and elastic IP if necessary:
   ```javascript
   // Server Configuration
const SERVER_CONFIG = {
    HOST: 'chatbot-dev.facets-ai.com',
   ```
4. Save and exit the file.


### 3. Start All Services with the run_servers.py Script
1. First, kill any existing server processes:
   ```bash
   # Kill any running Python processes related to our application
   pkill -f run_servers.py
   
   # Give processes time to terminate gracefully
   sleep 2
   
   # To forcefully kill any remaining processes (if needed)
   # pkill -9 -f run_servers.py
   ```

2. Start all servers using the run_servers.py script:
   ```bash
   cd /home/ubuntu/nepal_chatbot
   python3 run_servers.py --all
   ```

3. To start specific servers only, use the appropriate flags:
   ```bash
   # Start only the actions server
   python3 run_servers.py --actions
   
   # Start only the accessible server
   python3 run_servers.py --accessible
   
   # Start only the Rasa server
   python3 run_servers.py --rasa
   ```

4. Verify all servers are running:
   ```bash
   ps aux | grep python
   ```



--- 

## Notes
- Ensure all required ports (e.g., 5001 for the accessible server, 5005 for Rasa, 5055 for actions, 80/443 for Nginx) are open in the server's security group.
- After any IP changes, ensure DNS records are updated if applicable.
- The uploads/ directory is excluded from Git tracking to avoid committing large files.
- For database issues, check PostgreSQL logs and connection settings.
- Use `sudo` wherever permissions are required.