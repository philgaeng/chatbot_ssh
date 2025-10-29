# Nepal Chatbot - Operations Guide

Complete operations guide covering monitoring, troubleshooting, maintenance, and common procedures.

## Table of Contents

- [Monitoring](#monitoring)
- [Log Management](#log-management)
- [Backup and Recovery](#backup-and-recovery)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Common Procedures](#common-procedures)
- [Security Operations](#security-operations)

## Monitoring

### Health Checks

#### Automated Health Checks

**Flask Health Endpoint:**

```bash
curl http://localhost:5001/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-01-30T10:00:00Z",
  "database": "connected",
  "redis": "connected",
  "celery_workers": 10
}
```

**Rasa Health Check:**

```bash
curl http://localhost:5005/

# Expected response:
{
  "version": "3.6.21",
  "minimum_compatible_version": "3.0.0"
}
```

**Database Health:**

```bash
psql -U nepal_grievance_admin -d grievance_db -c "SELECT version();"
```

**Redis Health:**

```bash
redis-cli ping
# Expected: PONG
```

#### Health Check Script

```bash
#!/bin/bash
# health_check.sh

echo "Checking Nepal Chatbot services..."

# Check Rasa
if curl -s http://localhost:5005/ > /dev/null; then
    echo "✓ Rasa server is running"
else
    echo "✗ Rasa server is down"
fi

# Check Action server
if curl -s http://localhost:5055/health > /dev/null; then
    echo "✓ Action server is running"
else
    echo "✗ Action server is down"
fi

# Check Flask
if curl -s http://localhost:5001/health > /dev/null; then
    echo "✓ Flask server is running"
else
    echo "✗ Flask server is down"
fi

# Check PostgreSQL
if psql -U nepal_grievance_admin -d grievance_db -c "SELECT 1" > /dev/null 2>&1; then
    echo "✓ PostgreSQL is running"
else
    echo "✗ PostgreSQL is down"
fi

# Check Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis is running"
else
    echo "✗ Redis is down"
fi

# Check Celery workers
active_workers=$(celery -A task_queue inspect active_queues 2>/dev/null | grep -c "llm_queue\|default")
if [ $active_workers -gt 0 ]; then
    echo "✓ Celery workers are running ($active_workers active)"
else
    echo "✗ Celery workers are down"
fi
```

### System Monitoring

#### Resource Usage

**Check System Resources:**

```bash
# CPU and memory
htop

# Disk usage
df -h

# Disk I/O
iostat -x 1

# Network
netstat -tulpn
```

**Monitor Specific Processes:**

```bash
# Python processes
ps aux | grep python

# Memory usage per process
ps aux --sort=-%mem | head -10

# CPU usage per process
ps aux --sort=-%cpu | head -10
```

#### Database Monitoring

**Connection Count:**

```sql
SELECT count(*) FROM pg_stat_activity;
```

**Active Queries:**

```sql
SELECT pid, usename, application_name, client_addr, query_start, query
FROM pg_stat_activity
WHERE state = 'active';
```

**Database Size:**

```sql
SELECT pg_size_pretty(pg_database_size('grievance_db'));
```

**Table Sizes:**

```sql
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Slow Queries:**

```sql
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

#### Redis Monitoring

```bash
# Connect to Redis CLI
redis-cli

# Check info
INFO

# Memory usage
INFO memory

# Connected clients
INFO clients

# Check specific keys
KEYS *

# Monitor commands in real-time
MONITOR
```

#### Celery Monitoring

**Check Active Tasks:**

```bash
celery -A task_queue inspect active
```

**Check Registered Tasks:**

```bash
celery -A task_queue inspect registered
```

**Check Worker Stats:**

```bash
celery -A task_queue inspect stats
```

**Check Queue Length:**

```bash
redis-cli LLEN celery
redis-cli LLEN llm_queue
```

**Flower Web UI:**

```bash
# Install Flower
pip install flower

# Start Flower
celery -A task_queue flower --port=5555

# Access at: http://localhost:5555
```

### Application Metrics

#### Grievance Statistics

```sql
-- Total grievances
SELECT COUNT(*) FROM grievances;

-- Grievances by status
SELECT classification_status, COUNT(*)
FROM grievances
GROUP BY classification_status;

-- Grievances by date
SELECT DATE(created_at), COUNT(*)
FROM grievances
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY DATE(created_at);

-- Grievances by municipality
SELECT c.complainant_municipality, COUNT(*)
FROM grievances g
JOIN complainants c ON g.complainant_id = c.complainant_id
GROUP BY c.complainant_municipality
ORDER BY COUNT(*) DESC;

-- Average resolution time
SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as avg_hours
FROM grievances
WHERE classification_status = 'resolved';
```

#### File Upload Statistics

```sql
-- Total files
SELECT COUNT(*) FROM file_attachments;

-- Files by type
SELECT file_type, COUNT(*), SUM(file_size)
FROM file_attachments
GROUP BY file_type;

-- Storage usage
SELECT pg_size_pretty(SUM(file_size))
FROM file_attachments;
```

### Alerting

#### Email Alerts

```python
# scripts/monitoring/alerts.py

import smtplib
from email.mime.text import MIMEText

def send_alert(subject, message):
    """Send email alert."""
    msg = MIMEText(message)
    msg['Subject'] = f'[Nepal Chatbot Alert] {subject}'
    msg['From'] = 'alerts@example.com'
    msg['To'] = 'admin@example.com'

    smtp = smtplib.SMTP('smtp.gmail.com', 587)
    smtp.starttls()
    smtp.login('alerts@example.com', 'password')
    smtp.send_message(msg)
    smtp.quit()

# Check disk usage
disk_usage = os.statvfs('/')
percent_used = (disk_usage.f_blocks - disk_usage.f_bfree) / disk_usage.f_blocks * 100

if percent_used > 90:
    send_alert('Disk Usage Critical', f'Disk usage at {percent_used:.1f}%')
```

#### Monitoring Script

```bash
#!/bin/bash
# monitor.sh - Run every 5 minutes via cron

LOG_FILE="/var/log/nepal_chatbot_monitor.log"

# Check disk usage
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 90 ]; then
    echo "$(date): CRITICAL - Disk usage at ${DISK_USAGE}%" >> $LOG_FILE
    # Send alert
fi

# Check service status
systemctl is-active --quiet nepal-rasa || echo "$(date): ERROR - Rasa service down" >> $LOG_FILE
systemctl is-active --quiet nepal-actions || echo "$(date): ERROR - Actions service down" >> $LOG_FILE
systemctl is-active --quiet nepal-flask || echo "$(date): ERROR - Flask service down" >> $LOG_FILE

# Check database connections
DB_CONN=$(psql -U nepal_grievance_admin -d grievance_db -t -c "SELECT count(*) FROM pg_stat_activity;")
if [ $DB_CONN -gt 50 ]; then
    echo "$(date): WARNING - High database connections: $DB_CONN" >> $LOG_FILE
fi
```

**Add to crontab:**

```bash
crontab -e

# Add line:
*/5 * * * * /home/ubuntu/nepal_chatbot/scripts/monitoring/monitor.sh
```

## Log Management

### Log Locations

**Application Logs:**

```
logs/
├── rasa_server.log           # Rasa server
├── actions_server.log         # Action server
├── flask_server.log           # Flask server
├── celery_llm_queue.log       # Celery LLM worker
├── celery_default.log         # Celery default worker
├── server_manager.log         # Server orchestration
├── mysql_operations.log       # MySQL operations
└── mysql_migrations.log       # Database migrations
```

**System Logs:**

```bash
# Systemd service logs
sudo journalctl -u nepal-rasa -f
sudo journalctl -u nepal-actions -f
sudo journalctl -u nepal-flask -f
sudo journalctl -u nepal-celery-llm -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-13-main.log
```

### Viewing Logs

**Follow logs in real-time:**

```bash
# All logs
tail -f logs/*.log

# Specific log
tail -f logs/rasa_server.log

# Last 100 lines
tail -n 100 logs/actions_server.log

# Search logs
grep "ERROR" logs/flask_server.log

# Search with context
grep -C 5 "ERROR" logs/flask_server.log
```

**Using journalctl:**

```bash
# Follow service log
sudo journalctl -u nepal-rasa -f

# Last 1 hour
sudo journalctl -u nepal-rasa --since "1 hour ago"

# Last 100 lines
sudo journalctl -u nepal-rasa -n 100

# Filter by priority
sudo journalctl -u nepal-rasa -p err

# Show only today
sudo journalctl -u nepal-rasa --since today
```

### Log Rotation

**Configure logrotate:**

```bash
sudo nano /etc/logrotate.d/nepal-chatbot
```

**Configuration:**

```
/home/ubuntu/nepal_chatbot/logs/*.log {
    daily
    rotate 90
    compress
    delaycompress
    notifempty
    create 0644 ubuntu ubuntu
    sharedscripts
    postrotate
        # Restart services if needed
        systemctl reload nepal-rasa
    endscript
}
```

**Test configuration:**

```bash
sudo logrotate -d /etc/logrotate.d/nepal-chatbot
```

**Force rotation:**

```bash
sudo logrotate -f /etc/logrotate.d/nepal-chatbot
```

### Log Analysis

**Error Count:**

```bash
# Count errors in last hour
find logs/ -name "*.log" -mmin -60 -exec grep -c "ERROR" {} \;

# Unique errors
grep "ERROR" logs/*.log | cut -d':' -f3- | sort | uniq -c | sort -rn
```

**Response Time Analysis:**

```bash
# Average response time from nginx logs
awk '{print $10}' /var/log/nginx/access.log | awk '{sum+=$1; count++} END {print sum/count}'
```

**Failed Requests:**

```bash
# Count 5xx errors
grep " 50[0-9] " /var/log/nginx/access.log | wc -l
```

## Backup and Recovery

### Database Backup

#### Manual Backup

```bash
# Full database backup
pg_dump -U nepal_grievance_admin -d grievance_db -F c -f backup_$(date +%Y%m%d_%H%M%S).dump

# SQL format
pg_dump -U nepal_grievance_admin -d grievance_db -f backup_$(date +%Y%m%d).sql

# Specific tables
pg_dump -U nepal_grievance_admin -d grievance_db -t grievances -t complainants -f backup_tables.sql

# Schema only
pg_dump -U nepal_grievance_admin -d grievance_db --schema-only -f schema_backup.sql
```

#### Automated Backup Script

```bash
#!/bin/bash
# backup_database.sh

BACKUP_DIR="/home/ubuntu/backups/database"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/grievance_db_$DATE.dump"

# Create backup directory
mkdir -p $BACKUP_DIR

# Perform backup
pg_dump -U nepal_grievance_admin -d grievance_db -F c -f $BACKUP_FILE

# Compress old backups (older than 7 days)
find $BACKUP_DIR -name "*.dump" -mtime +7 -exec gzip {} \;

# Delete very old backups (older than 90 days)
find $BACKUP_DIR -name "*.dump.gz" -mtime +90 -delete

# Log
echo "$(date): Database backup completed: $BACKUP_FILE" >> /var/log/nepal_chatbot_backup.log
```

**Schedule daily backups:**

```bash
crontab -e

# Daily at 2 AM
0 2 * * * /home/ubuntu/nepal_chatbot/scripts/backup/backup_database.sh
```

#### Restore Database

```bash
# Restore from custom format
pg_restore -U nepal_grievance_admin -d grievance_db -c backup.dump

# Restore from SQL
psql -U nepal_grievance_admin -d grievance_db -f backup.sql

# Restore specific table
pg_restore -U nepal_grievance_admin -d grievance_db -t grievances backup.dump
```

### File Backup

```bash
#!/bin/bash
# backup_files.sh

BACKUP_DIR="/home/ubuntu/backups/files"
DATE=$(date +%Y%m%d)
BACKUP_FILE="$BACKUP_DIR/uploads_$DATE.tar.gz"

# Create backup
tar -czf $BACKUP_FILE /home/ubuntu/nepal_chatbot/uploads/

# Delete old backups (older than 30 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "$(date): File backup completed: $BACKUP_FILE" >> /var/log/nepal_chatbot_backup.log
```

### Backup to Remote Server

```bash
# Using rsync
rsync -avz -e "ssh -i ~/.ssh/backup_key.pem" \
    /home/ubuntu/backups/ \
    backup@backup-server:/backups/nepal_chatbot/

# Using scp
scp -i ~/.ssh/backup_key.pem backup.dump backup@backup-server:/backups/
```

### Disaster Recovery

#### Full System Recovery

1. **Restore Server**

   ```bash
   # Install dependencies
   sudo apt update
   sudo apt install postgresql redis-server nginx python3.10
   ```

2. **Restore Application**

   ```bash
   # Clone repository
   git clone https://github.com/philgaeng/chatbot_ssh.git nepal_chatbot
   cd nepal_chatbot

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Restore Database**

   ```bash
   # Create database
   sudo -u postgres psql -c "CREATE DATABASE grievance_db;"

   # Restore backup
   pg_restore -U nepal_grievance_admin -d grievance_db backup.dump
   ```

4. **Restore Files**

   ```bash
   # Extract files
   tar -xzf uploads_backup.tar.gz -C /home/ubuntu/nepal_chatbot/
   ```

5. **Configure and Start Services**

   ```bash
   # Copy environment file
   cp .env.backup .env

   # Start services
   systemctl start nepal-rasa
   systemctl start nepal-actions
   systemctl start nepal-flask
   ```

## Performance Optimization

### Database Optimization

#### Indexing

```sql
-- Add indexes for frequently queried fields
CREATE INDEX IF NOT EXISTS idx_grievances_status
ON grievances(classification_status);

CREATE INDEX IF NOT EXISTS idx_grievances_created
ON grievances(created_at);

CREATE INDEX IF NOT EXISTS idx_complainants_municipality
ON complainants(complainant_municipality);

CREATE INDEX IF NOT EXISTS idx_files_grievance
ON file_attachments(grievance_id);
```

#### Query Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM grievances WHERE classification_status = 'pending';

-- Update statistics
ANALYZE grievances;
ANALYZE complainants;

-- Vacuum database
VACUUM ANALYZE;
```

#### Connection Pooling

```python
# backend/services/database_services/connection_pool.py

import psycopg2
from psycopg2 import pool

connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=20,  # Adjust based on load
    host=os.getenv('POSTGRES_HOST'),
    port=os.getenv('POSTGRES_PORT'),
    database=os.getenv('POSTGRES_DB'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD')
)
```

### Caching Strategy

#### Redis Caching

```python
import redis
import json

redis_client = redis.Redis(
    host='localhost',
    port=6379,
    password=os.getenv('REDIS_PASSWORD'),
    decode_responses=True
)

def get_grievance_cached(grievance_id):
    """Get grievance with caching."""
    # Check cache
    cache_key = f"grievance:{grievance_id}"
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # Query database
    grievance = db_manager.get_grievance_by_id(grievance_id)

    # Cache for 5 minutes
    redis_client.setex(cache_key, 300, json.dumps(grievance))

    return grievance
```

### Celery Optimization

**Worker Configuration:**

```bash
# Adjust concurrency based on CPU cores
celery -A task_queue worker -Q llm_queue --loglevel=INFO --concurrency=6

# Optimize prefetch
celery -A task_queue worker --prefetch-multiplier=1

# Set max tasks per child
celery -A task_queue worker --max-tasks-per-child=1000
```

### Nginx Optimization

```nginx
# nginx.conf optimization

http {
    # Enable gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_types text/plain text/css application/json application/javascript;

    # Connection pooling
    keepalive_timeout 65;
    keepalive_requests 100;

    # Buffer sizes
    client_body_buffer_size 10K;
    client_header_buffer_size 1k;
    client_max_body_size 10m;
    large_client_header_buffers 2 1k;

    # Caching
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g;
}
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Check logs:**

```bash
sudo journalctl -u nepal-rasa -n 50 --no-pager
```

**Common causes:**

- Port already in use
- Configuration error
- Missing dependencies
- Database connection failed

**Solutions:**

```bash
# Kill process using port
sudo lsof -i :5005
sudo kill -9 <PID>

# Check configuration
rasa run --debug

# Test database connection
psql -U nepal_grievance_admin -d grievance_db -c "SELECT 1;"
```

#### 2. High Memory Usage

**Check memory:**

```bash
free -h
ps aux --sort=-%mem | head -10
```

**Solutions:**

```bash
# Restart services
sudo systemctl restart nepal-rasa
sudo systemctl restart nepal-celery-llm

# Clear cache
redis-cli FLUSHALL

# Vacuum database
psql -U nepal_grievance_admin -d grievance_db -c "VACUUM FULL;"
```

#### 3. Slow Response Times

**Check bottlenecks:**

```bash
# Database
psql -U nepal_grievance_admin -d grievance_db -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# CPU usage
top

# Network
netstat -i
```

**Solutions:**

- Add database indexes
- Implement caching
- Optimize queries
- Scale horizontally

#### 4. Classification Failures

**Check Celery:**

```bash
celery -A task_queue inspect active
tail -f logs/celery_llm_queue.log
```

**Common causes:**

- OpenAI API key invalid
- Rate limit exceeded
- Network issues

**Solutions:**

```bash
# Verify API key
python -c "import openai; openai.api_key='KEY'; print(openai.Model.list())"

# Check rate limits
# Implement exponential backoff
# Use different API key
```

#### 5. Database Connection Errors

**Check connections:**

```sql
SELECT count(*) FROM pg_stat_activity;
```

**Solutions:**

```bash
# Increase max connections in postgresql.conf
sudo nano /etc/postgresql/13/main/postgresql.conf
# max_connections = 200

# Restart PostgreSQL
sudo systemctl restart postgresql

# Use connection pooling
# Reduce connection timeout
```

### Debug Commands

```bash
# Check all services
./scripts/monitoring/health_check.sh

# Test Rasa
rasa shell --debug

# Test API
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "hello"}'

# Check database
psql -U nepal_grievance_admin -d grievance_db

# Check Redis
redis-cli INFO

# Monitor Celery
celery -A task_queue events
```

## Common Procedures

### Restart Services

```bash
# Restart all services
sudo systemctl restart nepal-rasa nepal-actions nepal-flask nepal-celery-llm

# Restart individually
sudo systemctl restart nepal-rasa
sudo systemctl restart nepal-actions
sudo systemctl restart nepal-flask

# Check status
sudo systemctl status nepal-rasa nepal-actions nepal-flask
```

### Deploy Updates

```bash
#!/bin/bash
# deploy_update.sh

# Stop services
sudo systemctl stop nepal-rasa nepal-actions nepal-flask nepal-celery-llm

# Backup
pg_dump -U nepal_grievance_admin -d grievance_db -F c -f backup_pre_update.dump

# Pull updates
git pull origin main

# Update dependencies
source rasa-env/bin/activate
pip install -r requirements.txt --upgrade

# Run migrations
python scripts/database/migrate.py

# Retrain Rasa (if needed)
cd rasa_chatbot
rasa train
cd ..

# Start services
sudo systemctl start nepal-rasa nepal-actions nepal-flask nepal-celery-llm

# Verify
sleep 10
./scripts/monitoring/health_check.sh
```

### Clear Cache

```bash
# Clear Redis cache
redis-cli FLUSHALL

# Clear application cache
rm -rf /tmp/nepal_chatbot_cache/*

# Clear Nginx cache
sudo rm -rf /var/cache/nginx/*
sudo systemctl reload nginx
```

### Reset Database (Development Only!)

```bash
# WARNING: This will delete all data!

# Drop and recreate database
sudo -u postgres psql -c "DROP DATABASE grievance_db;"
sudo -u postgres psql -c "CREATE DATABASE grievance_db;"

# Initialize schema
python scripts/database/init.py

# Restart services
sudo systemctl restart nepal-rasa nepal-actions nepal-flask
```

## Security Operations

### Security Checklist

- [ ] All services running as non-root user
- [ ] Firewall configured (ufw)
- [ ] SSL/HTTPS enabled
- [ ] Database passwords strong and rotated
- [ ] Redis password protected
- [ ] File upload validation enabled
- [ ] Rate limiting configured
- [ ] Logs monitored for suspicious activity
- [ ] Backups encrypted
- [ ] API keys rotated regularly

### Security Monitoring

```bash
# Check failed login attempts
sudo grep "Failed password" /var/log/auth.log

# Check unusual database activity
psql -U nepal_grievance_admin -d grievance_db -c "
SELECT client_addr, count(*)
FROM pg_stat_activity
GROUP BY client_addr
ORDER BY count(*) DESC;
"

# Check large file uploads
find uploads/ -type f -size +100M

# Monitor API usage
grep "POST /upload" /var/log/nginx/access.log | wc -l
```

### Incident Response

1. **Detect**: Monitor logs and alerts
2. **Isolate**: Stop affected services
3. **Investigate**: Analyze logs and system state
4. **Remediate**: Fix vulnerability or issue
5. **Recover**: Restore services
6. **Document**: Record incident and response

---

For system setup and architecture details, see:

- [Setup Guide](SETUP.md)
- [Architecture Guide](ARCHITECTURE.md)
- [Backend Guide](BACKEND.md)
