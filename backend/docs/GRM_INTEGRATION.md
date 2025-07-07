# GRM System Integration Guide

This document explains how to integrate your chatbot with the legacy GRM (Grievance Management System) that uses PHP/MySQL.

## Overview

The GRM integration allows your Python chatbot to:

- **Sync grievances** from your system to the GRM database
- **Retrieve status updates** from the GRM system
- **Update grievance status** in the GRM system
- **Work with remote databases** via direct connection or SSH tunnel

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Chatbot       │    │   GRM Integration │    │   GRM System    │
│   (Python)      │◄──►│   Layer           │◄──►│   (PHP/MySQL)   │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Components

1. **MySQL Database Service** (`mysql_services.py`)

   - Handles direct MySQL connections
   - Connection pooling for performance
   - Error handling and logging

2. **SSH Tunnel Service** (`ssh_tunnel.py`)

   - Secure remote connections
   - Port forwarding for database access
   - Authentication via SSH keys or passwords

3. **GRM Integration Service** (`grm_integration_service.py`)

   - Orchestrates data synchronization
   - Maps data between systems
   - Handles batch operations

4. **Configuration Management** (`grm_config.py`)
   - Environment-based configuration
   - Field mapping definitions
   - Status mapping logic

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements_grm.txt
```

### 2. Configure Environment

Copy the example configuration:

```bash
cp env.grm.example .env
```

Edit `.env` with your GRM system details:

```env
# GRM MySQL Database
GRM_MYSQL_HOST=your_grm_server_ip
GRM_MYSQL_DB=grm_database
GRM_MYSQL_USER=grm_user
GRM_MYSQL_PASSWORD=your_password
GRM_MYSQL_PORT=3306

# Enable integration
GRM_INTEGRATION_ENABLED=true
```

### 3. Database Permissions

Ensure your MySQL user has proper permissions:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON grm_database.* TO 'grm_user'@'%';
FLUSH PRIVILEGES;
```

## Connection Options

### Option 1: Direct Connection (Same Network)

If both systems are on the same network:

```env
GRM_MYSQL_HOST=192.168.1.100
GRM_MYSQL_DB=grievance_system
GRM_MYSQL_USER=grm_admin
GRM_MYSQL_PASSWORD=secure_password
```

### Option 2: SSH Tunnel (Remote/Cloud)

For secure remote connections:

```env
# Enable SSH tunnel
GRM_SSH_TUNNEL_ENABLED=true
GRM_SSH_HOST=203.0.113.10
GRM_SSH_USER=admin
GRM_SSH_KEY_PATH=/home/user/.ssh/grm_key

# Connect through tunnel
GRM_MYSQL_HOST=localhost
GRM_MYSQL_DB=grm_production
GRM_MYSQL_USER=grm_user
GRM_MYSQL_PASSWORD=db_password
```

### Option 3: Same Server

If deploying on the same server as GRM:

```env
GRM_MYSQL_HOST=localhost
GRM_MYSQL_DB=grm_database
GRM_MYSQL_USER=root
GRM_MYSQL_PASSWORD=
```

## Usage

### Basic Integration

```python
from backend.services.integration.grm_integration_service import (
    get_grm_orchestrator, initialize_grm_integration
)

# Initialize the integration
orchestrator = get_grm_orchestrator()
if initialize_grm_integration():
    print("GRM integration ready")
else:
    print("GRM integration failed")

# Sync a grievance
grievance_data = {
    'grievance_id': 'GRV-001',
    'user_full_name': 'John Doe',
    'user_contact_phone': '+9771234567890',
    'grievance_details': 'Water supply issue in ward 5',
    'grievance_location': 'Kathmandu',
    'classification_status': 'pending'
}

result = orchestrator.process_grievance(grievance_data)
print(f"Sync result: {result.status.value}")
```

### Batch Operations

```python
# Sync multiple grievances
grievances = [
    grievance_data_1,
    grievance_data_2,
    grievance_data_3
]

results = orchestrator.process_grievances_batch(grievances)
success_count = sum(1 for r in results if r.success)
print(f"Successfully synced {success_count}/{len(grievances)} grievances")
```

### Status Updates

```python
# Get status from GRM system
status = orchestrator.get_grievance_status('GRV-001')
if status:
    print(f"Grievance status: {status.get('classification_status')}")

# Update status in GRM system
success = orchestrator.update_grievance_status(
    'GRV-001',
    'resolved',
    'Issue resolved by water department'
)
```

### Integration Status

```python
# Check integration health
status = orchestrator.get_integration_status()
print(f"Integration enabled: {status['enabled']}")
print(f"Initialized: {status['initialized']}")
print(f"Sync stats: {status['sync_stats']}")
```

## Data Mapping

### Field Mapping

The system automatically maps fields between your chatbot and the GRM system:

| Chatbot Field           | GRM Field               | Description                    |
| ----------------------- | ----------------------- | ------------------------------ |
| `user_full_name`        | `complainant_name`      | User's full name               |
| `user_contact_phone`    | `contact_phone`         | Contact phone number           |
| `grievance_details`     | `grievance_description` | Detailed grievance description |
| `grievance_location`    | `location`              | Location of the issue          |
| `classification_status` | `status`                | Processing status              |

### Status Mapping

| Chatbot Status     | GRM Status         | Description         |
| ------------------ | ------------------ | ------------------- |
| `pending`          | `pending`          | Awaiting processing |
| `submitted`        | `submitted`        | Submitted to GRM    |
| `under_evaluation` | `under_evaluation` | Being evaluated     |
| `resolved`         | `resolved`         | Issue resolved      |
| `denied`           | `denied`           | Request denied      |

## Configuration

### Environment Variables

| Variable                    | Default | Description                         |
| --------------------------- | ------- | ----------------------------------- |
| `GRM_INTEGRATION_ENABLED`   | `false` | Enable/disable integration          |
| `GRM_SYNC_INTERVAL_MINUTES` | `5`     | Sync interval in minutes            |
| `GRM_AUTO_SYNC_GRIEVANCES`  | `true`  | Auto-sync new grievances            |
| `GRM_MAX_RETRY_ATTEMPTS`    | `3`     | Max retry attempts for failed syncs |

### Customizing Field Mapping

Edit `backend/config/grm_config.py` to customize field mappings:

```python
GRM_FIELD_MAPPING = {
    'user_full_name': 'complainant_name',
    'user_contact_phone': 'contact_phone',
    # Add your custom mappings here
    'custom_field': 'grm_custom_field',
}
```

## Testing

### Test Connection

```bash
cd backend
python -m backend.config.grm_config
```

### Test SSH Tunnel

```bash
python -m backend.services.database_services.ssh_tunnel
```

### Test Full Integration

```bash
python -m backend.services.integration.grm_integration_service
```

## Monitoring and Logging

### Log Files

- `logs/mysql_operations.log` - MySQL operations
- `logs/mysql_migrations.log` - Database migrations
- `logs/mysql_backup.log` - Backup operations

### Integration Status

```python
# Get detailed status
status = orchestrator.get_integration_status()
print(json.dumps(status, indent=2))

# Get sync history
history = orchestrator.sync_manager.get_sync_history(limit=10)
for entry in history:
    print(f"{entry.timestamp}: {entry.status.value} - {entry.message}")
```

## Troubleshooting

### Common Issues

1. **Connection Refused**

   - Check if MySQL server is running
   - Verify host and port settings
   - Check firewall rules

2. **Authentication Failed**

   - Verify username and password
   - Check MySQL user permissions
   - Ensure user can connect from your IP

3. **SSH Tunnel Issues**

   - Verify SSH key permissions (should be 600)
   - Check SSH server configuration
   - Ensure SSH user has access

4. **Data Mapping Errors**
   - Check field mapping configuration
   - Verify GRM database schema
   - Review error logs for specific field issues

### Debug Mode

Enable debug logging by setting log level:

```python
import logging
logging.getLogger('backend.services.database_services.mysql_services').setLevel(logging.DEBUG)
logging.getLogger('backend.services.integration.grm_integration_service').setLevel(logging.DEBUG)
```

## Security Considerations

1. **Database Security**

   - Use strong passwords
   - Limit database user permissions
   - Use SSL connections when possible

2. **SSH Security**

   - Use SSH keys instead of passwords
   - Restrict SSH key permissions
   - Use dedicated SSH users with limited access

3. **Network Security**

   - Use VPN for remote connections
   - Implement firewall rules
   - Monitor connection logs

4. **Data Security**
   - Encrypt sensitive data
   - Implement audit logging
   - Regular security updates

## Performance Optimization

1. **Connection Pooling**

   - Configure appropriate pool size
   - Monitor connection usage
   - Adjust based on load

2. **Batch Operations**

   - Use batch sync for multiple grievances
   - Implement rate limiting
   - Monitor sync performance

3. **Caching**
   - Cache frequently accessed data
   - Implement status caching
   - Use Redis for session data

## Migration Guide

### From No Integration

1. Set up GRM integration configuration
2. Test connection and permissions
3. Implement gradual data migration
4. Monitor sync performance
5. Switch to full integration

### From Manual Integration

1. Review existing data mapping
2. Update configuration to match current setup
3. Test with sample data
4. Gradually migrate to new system
5. Monitor for data consistency

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review log files for errors
3. Test individual components
4. Contact system administrator

## Future Enhancements

- Real-time status updates via webhooks
- Advanced data validation
- Conflict resolution for concurrent updates
- Performance monitoring dashboard
- Automated backup and recovery
