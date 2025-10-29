# Nepal Chatbot - Setup Guide

Complete installation and deployment guide for the Nepal Chatbot system.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Server Deployment](#server-deployment)
- [Environment Configuration](#environment-configuration)
- [Service Management](#service-management)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python 3.10** - Main programming language
- **PostgreSQL 13+** - Primary database
- **Redis 6+** - Message broker and cache
- **Nginx** - Web server and reverse proxy (production only)
- **Node.js 14+** - For frontend development
- **Git** - Version control

### Required API Keys

- **OpenAI API Key** - For AI classification, summarization, and transcription
- **Google API Key** - For location services (optional)
- **AWS Credentials** - For S3 storage (optional)
- **Twilio Credentials** - For SMS/WhatsApp (optional)

### System Requirements

**Minimum (Development):**

- 4 GB RAM
- 2 CPU cores
- 20 GB disk space

**Recommended (Production):**

- 8 GB RAM
- 4 CPU cores
- 50 GB disk space
- SSD storage

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/philgaeng/chatbot_ssh.git nepal_chatbot
cd nepal_chatbot
```

### 2. Install PostgreSQL

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**

```bash
brew install postgresql@13
brew services start postgresql@13
```

**Windows (WSL2):**

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo service postgresql start
```

### 3. Install Redis

**Ubuntu/Debian:**

```bash
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS:**

```bash
brew install redis
brew services start redis
```

**Windows (WSL2):**

```bash
sudo apt install redis-server
sudo service redis-server start
```

### 4. Create Database

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE grievance_db;
CREATE USER nepal_grievance_admin WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE grievance_db TO nepal_grievance_admin;

# Enable pgcrypto extension (for encryption)
\c grievance_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;
\q
```

### 5. Python Environment

```bash
# Create virtual environment
python3 -m venv rasa-env

# Activate virtual environment
source rasa-env/bin/activate  # Linux/macOS
# or
rasa-env\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Rasa chatbot dependencies
pip install -r rasa_chatbot/requirements.txt

# Install backend dependencies
pip install -r backend/requirements.txt
```

### 6. Configure Environment Variables

```bash
# Copy example environment file
cp env.local .env

# Edit configuration
nano .env
```

**Minimal Configuration:**

```bash
# Database
POSTGRES_DB=grievance_db
POSTGRES_USER=nepal_grievance_admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Encryption
DB_ENCRYPTION_KEY=your_generated_encryption_key

# Server Ports
RASA_PORT=5005
ACTION_PORT=5055
FLASK_PORT=5001
ACCESSIBLE_PORT=5006
```

Generate encryption key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 7. Initialize Database Schema

```bash
# Run database initialization
python scripts/database/init.py

# Verify tables created
psql -U nepal_grievance_admin -d grievance_db -c "\dt"
```

### 8. Train Rasa Model

```bash
cd rasa_chatbot
rasa train
cd ..
```

This will create a trained model in `rasa_chatbot/models/`.

### 9. Start Services

**Option A: Use Launch Script (Recommended)**

```bash
# Make script executable
chmod +x scripts/local/launch_servers.sh

# Start all services
./scripts/local/launch_servers.sh
```

**Option B: Start Manually**

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Rasa server
cd rasa_chatbot
rasa run --enable-api --cors "*" --port 5005

# Terminal 3: Start Action server
cd rasa_chatbot
rasa run actions --port 5055

# Terminal 4: Start Flask server
python backend/app.py

# Terminal 5: Start Celery worker (LLM queue)
celery -A task_queue worker -Q llm_queue --loglevel=INFO

# Terminal 6: Start Celery worker (default queue)
celery -A task_queue worker --loglevel=INFO
```

### 10. Verify Installation

```bash
# Check Rasa server
curl http://localhost:5005/

# Check Action server
curl http://localhost:5055/health

# Check Flask server
curl http://localhost:5001/health

# Check Redis
redis-cli ping
# Should return: PONG

# Check PostgreSQL
psql -U nepal_grievance_admin -d grievance_db -c "SELECT version();"
```

### 11. Access the Application

Open your browser and navigate to:

- **Web Interface**: http://localhost:5001 or http://localhost:5002
- **Accessible Interface**: http://localhost:5006

## Server Deployment

### 1. Server Setup (Ubuntu 20.04/22.04)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3.10 python3.10-venv python3-pip \
    postgresql postgresql-contrib redis-server nginx \
    git supervisor build-essential libpq-dev

# Create application user
sudo useradd -m -s /bin/bash ubuntu
sudo usermod -aG sudo ubuntu
```

### 2. Clone and Setup

```bash
# Switch to application user
sudo su - ubuntu

# Clone repository
git clone https://github.com/philgaeng/chatbot_ssh.git nepal_chatbot
cd nepal_chatbot

# Create virtual environment
python3.10 -m venv rasa-env
source rasa-env/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r rasa_chatbot/requirements.txt
pip install -r backend/requirements.txt
```

### 3. Configure Nginx

```bash
# Copy nginx configuration
sudo cp nginx/nepal_chatbot-prod.conf /etc/nginx/sites-available/

# Update server_name and IP in the config
sudo nano /etc/nginx/sites-available/nepal_chatbot-prod.conf

# Enable site
sudo ln -s /etc/nginx/sites-available/nepal_chatbot-prod.conf /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

**Example Nginx Configuration:**

```nginx
server {
    listen 80;
    server_name chatbot.example.com;

    # Static files
    location /static {
        alias /home/ubuntu/nepal_chatbot/channels/webchat;
    }

    # Webchat interface
    location / {
        proxy_pass http://localhost:5002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Rasa webhooks
    location /webhooks {
        proxy_pass http://localhost:5005;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Flask API
    location /api {
        proxy_pass http://localhost:5001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

### 4. Configure Systemd Services

Create systemd service files for automatic startup and management.

**Rasa Server Service:**

```bash
sudo nano /etc/systemd/system/nepal-rasa.service
```

```ini
[Unit]
Description=Nepal Chatbot Rasa Server
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/nepal_chatbot/rasa_chatbot
Environment="PATH=/home/ubuntu/nepal_chatbot/rasa-env/bin"
ExecStart=/home/ubuntu/nepal_chatbot/rasa-env/bin/rasa run --enable-api --cors "*" --port 5005
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Action Server Service:**

```bash
sudo nano /etc/systemd/system/nepal-actions.service
```

```ini
[Unit]
Description=Nepal Chatbot Action Server
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/nepal_chatbot/rasa_chatbot
Environment="PATH=/home/ubuntu/nepal_chatbot/rasa-env/bin"
ExecStart=/home/ubuntu/nepal_chatbot/rasa-env/bin/rasa run actions --port 5055
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Flask Server Service:**

```bash
sudo nano /etc/systemd/system/nepal-flask.service
```

```ini
[Unit]
Description=Nepal Chatbot Flask Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/nepal_chatbot
Environment="PATH=/home/ubuntu/nepal_chatbot/rasa-env/bin"
EnvironmentFile=/home/ubuntu/nepal_chatbot/.env
ExecStart=/home/ubuntu/nepal_chatbot/rasa-env/bin/python backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Celery Worker Service (LLM Queue):**

```bash
sudo nano /etc/systemd/system/nepal-celery-llm.service
```

```ini
[Unit]
Description=Nepal Chatbot Celery Worker (LLM Queue)
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/nepal_chatbot
Environment="PATH=/home/ubuntu/nepal_chatbot/rasa-env/bin"
EnvironmentFile=/home/ubuntu/nepal_chatbot/.env
ExecStart=/home/ubuntu/nepal_chatbot/rasa-env/bin/celery -A task_queue worker -Q llm_queue --loglevel=INFO --concurrency=6
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and Start Services:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable nepal-rasa
sudo systemctl enable nepal-actions
sudo systemctl enable nepal-flask
sudo systemctl enable nepal-celery-llm

# Start services
sudo systemctl start nepal-rasa
sudo systemctl start nepal-actions
sudo systemctl start nepal-flask
sudo systemctl start nepal-celery-llm

# Check status
sudo systemctl status nepal-rasa
sudo systemctl status nepal-actions
sudo systemctl status nepal-flask
sudo systemctl status nepal-celery-llm
```

### 5. Set Up File Permissions

```bash
# Change group ownership to www-data (nginx)
sudo chown -R ubuntu:www-data /home/ubuntu/nepal_chatbot

# Set directory permissions
sudo chmod -R 775 /home/ubuntu/nepal_chatbot

# Set setgid bit for new files
sudo chmod g+s /home/ubuntu/nepal_chatbot

# Create and configure uploads directory
mkdir -p /home/ubuntu/nepal_chatbot/uploads/voice_recordings
chmod -R 775 /home/ubuntu/nepal_chatbot/uploads
```

### 6. Configure Firewall

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### 7. SSL/HTTPS Setup (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d chatbot.example.com

# Test auto-renewal
sudo certbot renew --dry-run
```

## Environment Configuration

### Development Environment (env.local)

```bash
# Application Environment
ENVIRONMENT=development
DEBUG=true

# Database
POSTGRES_DB=grievance_db
POSTGRES_USER=nepal_grievance_admin
POSTGRES_PASSWORD=dev_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=your_dev_api_key
OPENAI_MODEL=gpt-4

# Encryption
DB_ENCRYPTION_KEY=your_dev_encryption_key

# Server Configuration
RASA_PORT=5005
ACTION_PORT=5055
FLASK_PORT=5001
ACCESSIBLE_PORT=5006

# Logging
LOG_LEVEL=DEBUG
LOG_RETENTION_DAYS=30
```

### Production Environment (.env)

```bash
# Application Environment
ENVIRONMENT=production
DEBUG=false

# Database (Use strong passwords!)
POSTGRES_DB=grievance_db
POSTGRES_USER=nepal_grievance_admin
POSTGRES_PASSWORD=very_strong_production_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis (Enable password protection)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis_strong_password

# Celery
CELERY_BROKER_URL=redis://:redis_strong_password@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:redis_strong_password@localhost:6379/0

# OpenAI
OPENAI_API_KEY=your_production_api_key
OPENAI_MODEL=gpt-4

# Encryption (NEVER reuse dev key!)
DB_ENCRYPTION_KEY=your_production_encryption_key

# Server Configuration
RASA_PORT=5005
ACTION_PORT=5055
FLASK_PORT=5001
ACCESSIBLE_PORT=5006

# Domain Configuration
DOMAIN=https://chatbot.example.com
ALLOWED_ORIGINS=https://chatbot.example.com

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_email_password
SMTP_FROM=noreply@example.com

# SMS Configuration (Twilio)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Logging
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=90

# Security
SECRET_KEY=your_django_secret_key
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

## Service Management

### Using systemctl (Production)

```bash
# Start services
sudo systemctl start nepal-rasa
sudo systemctl start nepal-actions
sudo systemctl start nepal-flask
sudo systemctl start nepal-celery-llm

# Stop services
sudo systemctl stop nepal-rasa
sudo systemctl stop nepal-actions
sudo systemctl stop nepal-flask
sudo systemctl stop nepal-celery-llm

# Restart services
sudo systemctl restart nepal-rasa
sudo systemctl restart nepal-actions
sudo systemctl restart nepal-flask
sudo systemctl restart nepal-celery-llm

# Check status
sudo systemctl status nepal-rasa
sudo systemctl status nepal-actions
sudo systemctl status nepal-flask
sudo systemctl status nepal-celery-llm

# View logs
sudo journalctl -u nepal-rasa -f
sudo journalctl -u nepal-actions -f
sudo journalctl -u nepal-flask -f
sudo journalctl -u nepal-celery-llm -f
```

### Using run_servers.py (Development)

```bash
# Kill all processes
pkill -f run_servers.py

# Start all servers
python run_servers.py --all

# Start specific servers
python run_servers.py --rasa-server-only
python run_servers.py --rasa-action-only
python run_servers.py --file-server-only

# Use custom ports
python run_servers.py --all --rasa-server-port 5010

# Skip database initialization
python run_servers.py --all --skip-db-init
```

### Using Launch Scripts

```bash
# Local development
./scripts/local/launch_servers.sh

# Production (with environment)
./scripts/prod/launch_servers.sh
```

## Production Deployment

### Deployment Checklist

- [ ] Update `.env` with production credentials
- [ ] Generate strong passwords for database and Redis
- [ ] Configure Nginx with correct domain
- [ ] Set up SSL certificates with Let's Encrypt
- [ ] Enable firewall (ufw)
- [ ] Configure file permissions correctly
- [ ] Set up systemd services for auto-start
- [ ] Configure log rotation
- [ ] Set up database backups
- [ ] Test all endpoints and functionality
- [ ] Configure monitoring and alerts
- [ ] Set up email notifications
- [ ] Test SMS/WhatsApp integration (if using)
- [ ] Review security settings
- [ ] Document server IP and credentials (securely)

### Post-Deployment Steps

1. **Verify all services are running:**

```bash
sudo systemctl status nepal-rasa nepal-actions nepal-flask nepal-celery-llm
```

2. **Test health endpoints:**

```bash
curl https://chatbot.example.com/health
curl https://chatbot.example.com/api/health
```

3. **Check logs for errors:**

```bash
sudo journalctl -u nepal-rasa --since "10 minutes ago"
sudo journalctl -u nepal-actions --since "10 minutes ago"
```

4. **Test database connection:**

```bash
psql -U nepal_grievance_admin -d grievance_db -c "SELECT COUNT(*) FROM grievances;"
```

5. **Verify Redis connection:**

```bash
redis-cli -a your_redis_password ping
```

6. **Test complete grievance submission flow**

7. **Set up monitoring and alerts**

### Updating the Application

```bash
# Switch to application user
sudo su - ubuntu
cd nepal_chatbot

# Backup database
pg_dump -U nepal_grievance_admin grievance_db > backup_$(date +%Y%m%d).sql

# Pull latest changes
git pull origin main

# Activate virtual environment
source rasa-env/bin/activate

# Update dependencies
pip install -r requirements.txt --upgrade

# Run database migrations (if any)
python scripts/database/migrate.py

# Retrain Rasa model (if NLU data changed)
cd rasa_chatbot
rasa train
cd ..

# Restart services
sudo systemctl restart nepal-rasa
sudo systemctl restart nepal-actions
sudo systemctl restart nepal-flask
sudo systemctl restart nepal-celery-llm

# Verify services started correctly
sudo systemctl status nepal-rasa nepal-actions nepal-flask nepal-celery-llm
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Find process using port
sudo lsof -i :5005

# Kill process
sudo kill -9 <PID>

# Or kill all Python processes
pkill -f run_servers.py
```

#### 2. Database Connection Error

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection settings
psql -U nepal_grievance_admin -d grievance_db

# Check if database exists
sudo -u postgres psql -c "\l"

# Reset password if needed
sudo -u postgres psql
ALTER USER nepal_grievance_admin WITH PASSWORD 'new_password';
```

#### 3. Redis Connection Error

```bash
# Check Redis is running
sudo systemctl status redis-server

# Test connection
redis-cli ping

# Check Redis logs
sudo journalctl -u redis-server
```

#### 4. Rasa Model Not Found

```bash
# Check if model exists
ls -la rasa_chatbot/models/

# Retrain model
cd rasa_chatbot
rasa train

# Verify model created
ls -la models/
```

#### 5. Permission Denied Errors

```bash
# Fix permissions
sudo chown -R ubuntu:www-data /home/ubuntu/nepal_chatbot
sudo chmod -R 775 /home/ubuntu/nepal_chatbot
sudo chmod g+s /home/ubuntu/nepal_chatbot

# Fix uploads directory
chmod -R 775 /home/ubuntu/nepal_chatbot/uploads
```

#### 6. Nginx 502 Bad Gateway

```bash
# Check if backend services are running
curl http://localhost:5005/
curl http://localhost:5001/health

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

#### 7. Celery Tasks Not Processing

```bash
# Check Celery worker status
celery -A task_queue inspect active

# Check Redis queue
redis-cli LLEN celery

# Restart Celery workers
sudo systemctl restart nepal-celery-llm

# Check logs
tail -f logs/celery_llm_queue.log
```

### Log Locations

- **Rasa Server**: `logs/rasa_server.log` or `journalctl -u nepal-rasa`
- **Action Server**: `logs/actions_server.log` or `journalctl -u nepal-actions`
- **Flask Server**: `logs/flask_server.log` or `journalctl -u nepal-flask`
- **Celery Workers**: `logs/celery_llm_queue.log` or `journalctl -u nepal-celery-llm`
- **Nginx**: `/var/log/nginx/error.log` and `/var/log/nginx/access.log`
- **PostgreSQL**: `/var/log/postgresql/postgresql-13-main.log`

### Getting Help

1. Check this documentation
2. Review log files for error messages
3. Search GitHub issues
4. Contact support: philgaeng@pm.me

---

For additional information, see:

- [Architecture Guide](ARCHITECTURE.md)
- [Operations Guide](OPERATIONS.md)
- [Backend Guide](BACKEND.md)
