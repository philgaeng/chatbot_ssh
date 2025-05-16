# Nepal Chatbot - Technical Documentation

## System Overview

The Nepal Chatbot is a conversational AI application built using Rasa, designed to handle grievance reporting, status checks, and user interactions in both English and Nepali languages. The system includes an accessible interface for users with disabilities and supports voice-based interactions.
å
## Architecture

The system is composed of several core components that work together:

```
+-------------------+        +-------------------+        +-------------------+
|                   |        |                   |        |                   |
|   Rasa Server     |<------>|   Action Server   |<------>|   PostgreSQL DB   |
|                   |        |                   |        |                   |
+-------------------+        +-------------------+        +-------------------+
         ^                           ^
         |                           |
         v                           v
+-------------------+        +-------------------+
|                   |        |                   |
|   Web Interface   |        |  File Server &    |
|   (Webchat)       |        |  Accessible App   |
|                   |        |                   |
+-------------------+        +-------------------+
                                      ^
                                      |
                                      v
                             +-------------------+
                             |                   |
                             |   Voice/File      |
                             |   Processing      |
                             |                   |
                             +-------------------+
```

### Core Components

1. **Rasa Server**: Main NLU and dialogue management server (port 5005)
2. **Rasa Action Server**: Custom actions implementation (port 5050)
3. **File Server**: Handles file uploads for grievances (port 5001)
4. **Accessible App**: Interface for users with disabilities (port 5006)
5. **PostgreSQL Database**: Stores grievances, user information, and files
6. **Web Interface**: Standard web chat interface for most users

## Directory Structure

```
nepal_chatbot/
├── actions/                  # Rasa custom actions implementation
├── actions_server/           # Shared functionality between Rasa and accessible interface
├── accessible_server/        # Accessible interface specific code
├── aws/                      # AWS deployment files
├── channels/                 # Web chat and accessible interfaces
│   ├── accessible/           # Accessible interface frontend
│   ├── webchat/              # Standard web chat interface
│   └── shared/               # Shared frontend components
├── data/                     # Rasa training data
│   ├── nlu/                  # NLU training data
│   ├── rules/                # Rasa rules
│   └── stories/              # Conversation paths
├── dev_utils/                # Development utilities
├── models/                   # Trained Rasa models
├── nginx/                    # Nginx configuration
├── resources/                # Static resources
├── rasa/                     # Rasa configuration
├── uploads/                  # File upload storage
├── .env                      # Environment variables
├── config.yml                # Rasa NLU config
├── credentials.yml           # Rasa credentials
├── domain.yml                # Rasa domain definition
├── endpoints.yml             # Rasa endpoint config
├── run_servers.py            # Main script to start all components 
└── requirements.txt          # Python dependencies
```

## Component Overview

### 1. Rasa Server

The core NLU and dialogue management server, responsible for:
- Processing user messages
- Managing conversation flow
- Coordinating with the action server

Configuration files:
- `config.yml`: NLU pipeline and policy configuration
- `domain.yml`: Intents, entities, slots, and responses
- `credentials.yml`: Channel credentials
- `endpoints.yml`: Action server and other endpoints

### 2. Action Server

Implements custom actions in response to user messages:
- Form handling for collecting grievance information
- Integration with database for storing and retrieving information
- Status checking functionality
- Menu system

Key files:
- `actions/base_classes.py`: Base classes for all actions
- `actions/form_grievance.py`: Grievance submission form handling
- `actions/check_status.py`: Status checking functionality
- `actions/form_contact.py`: Contact information collection
- `actions/utterance_mapping_rasa.py`: Response templates

### 3. File Server & Database Integration

Handles file uploads and database operations:
- File uploads for grievance attachments
- Database operations for storing/retrieving grievances
- Shared between Rasa and accessible interface

Key files:
- `actions_server/db_manager.py`: Database operations
- `actions_server/file_server.py`: File upload/download handling
- `actions_server/constants.py`: System constants
- `actions_server/helpers.py`: Utility functions

### 4. Accessible Interface

Provides voice-based and accessible interface for users with disabilities:
- Voice recording and transcription
- Voice-based grievance submission
- Integration with OpenAI for speech-to-text

Key files:
- `accessible_server/voice_grievance.py`: Voice processing functionality
- `channels/accessible/`: Frontend for accessible interface

### 5. Web Chat Interface

Standard web interface for text-based interactions:
- Text-based chat interface
- File upload capability
- Status checking


### 6. Ticketing System
Manages and tracks grievances through a ticketing workflow:
- Automated ticket creation from grievances
- Priority-based routing and assignment
- SLA monitoring and escalation
- Status tracking and updates
- Notification system for stakeholders

Features:
- Configurable workflow stages and transitions
- Role-based access control for different user types
- Automated assignment rules based on categories/location
- Performance metrics and reporting
- Integration with email notifications
- Audit trail of all ticket activities

Technical components:
- Workflow engine for ticket routing
- Queue management system
- SLA monitoring service
- Notification dispatcher
- Reporting and analytics module

Key files:
- `channels/webchat/`: Frontend for web chat interface

## Message Queue Implementation

### 1. Architecture Overview

The system implements an asynchronous message queue architecture to handle various processing tasks:

```
[Client] -> [Flask App] -> [Message Queue] -> [Processing Workers]
```

This architecture ensures:
- Reliable processing of long-running tasks
- Better resource utilization
- Improved system scalability
- Enhanced error handling and recovery

### 2. Queue Types and Purposes

The system maintains separate queues for different types of tasks:

1. **Voice Processing Queue**
   - Handles voice recording transcriptions
   - Manages language detection
   - Processes audio file conversions
   - Priority: High (user-facing feature)

2. **File Processing Queue**
   - Validates uploaded files
   - Processes image conversions
   - Manages file storage
   - Priority: Medium

3. **Grievance Processing Queue**
   - Processes new grievance submissions
   - Updates grievance status
   - Manages workflow transitions
   - Priority: High

4. **Notification Queue**
   - Sends user notifications
   - Handles officer alerts
   - Manages email communications 
   - Generates and sends OTP codes
   - Verifies OTP submissions
   - Priority: Low

5. **Generative AI Queue**
   - Manages calls to OpenAI or other Generative AI APIs
   - Classification of grievances from the webchat
   - Classification of Transcripts and Summaries in local language
   - Follow up questions
   - Translation from local language to English

### 3. System Behavior

#### 3.1 Task Processing
- Tasks are processed asynchronously
- Each task type has its own worker pool
- Failed tasks are automatically retried
- Dead letter queue for failed tasks
- Maximum retry attempts: 3
- Retry delay increases with each attempt

#### 3.2 Error Handling
- Automatic retry for transient failures
- Dead letter queue for permanent failures
- Error logging and monitoring
- Alert system for critical failures
- Manual intervention for dead letter queue

#### 3.3 Performance Management
- Rate limiting per queue
- Resource limits per worker
- Queue size monitoring
- Performance metrics collection
- Automatic scaling triggers

### 4. Monitoring and Maintenance

#### 4.1 Health Monitoring
- Queue length monitoring
- Worker status tracking
- Processing time metrics
- Error rate monitoring
- Resource utilization tracking

#### 4.2 Maintenance Procedures
- Regular queue cleanup
- Worker pool management
- Performance optimization
- Capacity planning
- System health checks

### 5. Scalability Strategy

#### 5.1 Current Implementation
- Redis-based message broker
- Multiple worker processes
- Separate queues for different tasks
- Basic load balancing

#### 5.2 Future Scaling
- Migration to RabbitMQ for larger scale
- Horizontal scaling of workers
- Advanced load balancing
- Geographic distribution
- High availability setup

### 6. Implementation Considerations

#### 6.1 Current Requirements
- Few cases per week
- ~100 concurrent submissions
- 6 audio recordings per submission
- 2-3 pictures per submission
- Response time < 5 seconds for user-facing operations

#### 6.2 Future Requirements
- Multiple projects across Nepal
- Increased concurrent users
- Additional file types
- Real-time processing needs
- Enhanced monitoring requirements

### 7. Integration Points

#### 7.1 System Integration
- Flask application integration
- Database operations
- File storage system
- Notification system
- Monitoring system

#### 7.2 External Systems
- Voice processing services
- File storage services
- Email services
- SMS services
- Monitoring services

### 8. Security Considerations

#### 8.1 Queue Security
- Secure message broker
- Worker authentication
- Message encryption
- Access control
- Audit logging

#### 8.2 Data Protection
- Sensitive data handling
- Data retention policies
- Privacy compliance
- Security monitoring
- Incident response

## Setup and Deployment

### Prerequisites

- Python 3.10
- PostgreSQL database
- Nginx web server
- Required API keys:
  - OpenAI API key (for voice transcription)
  - OpenAI API key (for translation, summary and categorization)
  - Google API key (for location services)
  - AWS credentials (for optional AWS services)

### Environment Configuration

1. Create and configure `.env` file with:
   - Database credentials
   - API keys
   - SMTP settings for email notifications
   - AWS credentials (if using AWS services)

Example `.env` configuration:
```
# Database Configuration
POSTGRES_DB=grievance_db
POSTGRES_USER=nepal_grievance_admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# API Keys
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key

# AWS Configuration (if using)
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret

# Email Configuration
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_email_password
```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/nepal_chatbot.git
   cd nepal_chatbot
   ```

2. Create a virtual environment:
   ```bash
   python -m venv rasa-env
   source rasa-env/bin/activate  # On Windows: rasa-env\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python init_database.py
   ```

5. Train the Rasa model:
   ```bash
   rasa train
   ```

### Server Configuration

1. Nginx configuration:
   - Use the included config files in the `nginx/` directory
   - Update server IP addresses and ports as needed
   - Enable the configuration with:
     ```bash
     sudo ln -s /etc/nginx/sites-available/nepal-chatbot-test.conf
     sudo systemctl restart nginx
     ```


### Running the Application

Use the `run_servers.py` script to start all components:

```bash
# Start all servers
python run_servers.py --all

# Start only specific components
python run_servers.py --file-server-only
python run_servers.py --accessibility-only
python run_servers.py --rasa-action-only
python run_servers.py --rasa-server-only

# Customize ports
python run_servers.py --all --file-server-port 5001 --accessibility-port 5006 --rasa-action-port 5050 --rasa-server-port 5005
```

## Maintenance and Operations

### Training the Model

Use the provided script to train the Rasa model on a dedicated instance:

```bash
./train_rasa.sh
```

The script:
1. Starts a training EC2 instance
2. Syncs necessary files
3. Trains the model
4. Copies the model back to your server
5. Shuts down the training instance

### Updating the System

1. **Updating NLU data**:
   - Edit files in `data/nlu/` directory
   - Retrain the model with `rasa train`

2. **Adding new responses**:
   - Update `domain.yml` and `actions/utterance_mapping_rasa.py`
   - Retrain the model with `rasa train`

3. **Modifying database schema**:
   - Update `actions_server/db_manager.py`
   - Add new tables in the `_create_tables` method

4. **Updating frontend**:
   - Modify files in `channels/webchat/` or `channels/accessible/`
   - Restart the relevant servers

### Log Management

Logs are output to standard output and can be redirected to files:

```bash
# Run with logging to file
python run_servers.py --all > nepal_chatbot.log 2>&1
```

For production environments, consider using systemd services for better log management.

### Backup Procedures

1. **Database backup**:
   ```bash
   pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -f backup_$(date +%Y%m%d).sql
   ```

2. **File uploads backup**:
   ```bash
   tar -czf uploads_backup_$(date +%Y%m%d).tar.gz uploads/
   ```

3. **Complete system backup**:
   ```bash
   tar -czf nepal_chatbot_backup_$(date +%Y%m%d).tar.gz --exclude="models/*" --exclude="uploads/*" --exclude="rasa-env/*" .
   ```

### Common Issues and Troubleshooting

1. **Server won't start due to port conflicts**:
   - Check for processes using the required ports: `lsof -i:5005`
   - Kill conflicting processes: `kill -9 <PID>`
   - Use different ports: `python run_servers.py --all --rasa-server-port 5010`

2. **Database connection errors**:
   - Verify PostgreSQL is running: `systemctl status postgresql`
   - Check database credentials in `.env`
   - Ensure the database exists: `psql -U postgres -c "CREATE DATABASE grievance_db;"`

3. **Rasa model training errors**:
   - Check training data for syntax errors
   - Verify the pipeline configuration in `config.yml`
   - Try training with `--debug` flag: `rasa train --debug`

4. **Voice transcription not working**:
   - Verify OpenAI API key in `.env`
   - Check for network connectivity to OpenAI API
   - Verify file permissions in the uploads directory

## Security Considerations

1. **API Keys and Credentials**:
   - Store all API keys and passwords in `.env` file (not in version control)
   - Use limited-scope API keys when possible
   - Rotate keys periodically

2. **Database Security**:
   - Use strong passwords for PostgreSQL
   - Limit database access to localhost when possible
   - Regular security updates for PostgreSQL

3. **File Upload Security**:
   - Validate all file uploads (type, size, content)
   - Store files outside of web root
   - Scan uploads for malware if possible

4. **Web Security**:
   - Configure HTTPS in Nginx
   - Implement proper CORS settings
   - Keep Nginx, Python, and all dependencies updated

## Future Development Considerations

1. **Scaling**:
   - Implement load balancing for multiple Rasa instances
   - Consider containerization with Docker for easier deployment
   - Database sharding for larger installations

2. **Enhancements**:
   - Multi-language support beyond English and Nepali
   - Integration with more messaging platforms
   - Enhanced analytics and reporting

3. **Monitoring**:
   - Add Prometheus/Grafana monitoring
   - Implement automated alerts for system issues
   - Regular performance testing and optimization

## Contact and Support

For issues, questions, or contributions:
- https://github.com/philgaeng/chatbot_ssh/tree/main
- [Project documentation website]
- philgaeng@pm.me