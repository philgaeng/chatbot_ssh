# Nepal Chatbot System Specifications

## 1. System Overview

### 1.1 Current System Components
- Rasa Core (NLP Engine)
- Action Server
- Accessible Server
- Flask Server (File handling)
- Task Management System
- PostgreSQL Database (grievances_db)

### 1.2 New Components
- Django Helpdesk
- New PostgreSQL Database (helpdesk_db)
- API Gateway (if needed)

## 2. Database Architecture

### 2.1 Task Database (helpdesk_db)
```sql
-- Core Tables
CREATE TABLE tasks (
    task_id VARCHAR(50) PRIMARY KEY,
    task_name VARCHAR(100),
    status_code VARCHAR(20),
    retry_count INT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    result JSONB,
    error_message TEXT
);

CREATE TABLE task_logs (
    log_id SERIAL PRIMARY KEY,
    task_id VARCHAR(50),
    event_type VARCHAR(50),
    event_data JSONB,
    created_at TIMESTAMP
);

CREATE TABLE file_processing (
    file_id VARCHAR(50) PRIMARY KEY,
    task_id VARCHAR(50),
    file_type VARCHAR(50),
    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE system_monitoring (
    monitor_id SERIAL PRIMARY KEY,
    service_name VARCHAR(50),
    event_type VARCHAR(50),
    event_data JSONB,
    created_at TIMESTAMP
);
```

### 2.2 Grievance Database (grievances_db)
```sql
-- Core Tables
CREATE TABLE grievances (
    grievance_id VARCHAR(50) PRIMARY KEY,
    user_id INT,
    project_type VARCHAR(50),
    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    -- Additional fields from current schema
);

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20),
    name VARCHAR(100),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE file_attachments (
    file_id VARCHAR(50) PRIMARY KEY,
    grievance_id VARCHAR(50),
    file_type VARCHAR(50),
    file_path VARCHAR(255),
    created_at TIMESTAMP
);

CREATE TABLE status_history (
    history_id SERIAL PRIMARY KEY,
    grievance_id VARCHAR(50),
    status VARCHAR(20),
    notes TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP
);
```

## 3. API Specifications

### 3.1 Django Helpdesk API Endpoints

#### Grievance Management
```python
# POST /api/grievances/
{
    "grievance_id": "string",
    "user_info": {
        "phone_number": "string",
        "name": "string"
    },
    "project_type": "string",
    "description": "string",
    "files": [
        {
            "file_id": "string",
            "file_type": "string",
            "file_data": "base64"
        }
    ]
}

# GET /api/grievances/{grievance_id}/
# PUT /api/grievances/{grievance_id}/
# GET /api/grievances/{grievance_id}/status/
# PUT /api/grievances/{grievance_id}/status/
```

#### User Management
```python
# POST /api/users/
{
    "phone_number": "string",
    "name": "string",
    "role": "string"
}

# GET /api/users/{user_id}/
# PUT /api/users/{user_id}/
```

#### File Management
```python
# POST /api/files/
{
    "grievance_id": "string",
    "file_type": "string",
    "file_data": "base64"
}

# GET /api/files/{file_id}/
```

## 4. Integration Points

### 4.1 Rasa Custom Actions
```python
class GrievanceAction(Action):
    def run(self, dispatcher, tracker, domain):
        # New grievance creation
        if self.is_new_feature(tracker):
            return self.create_via_django_api(tracker)
        # Existing grievance handling
        return self.create_via_existing_system(tracker)
```

### 4.2 Task Management
```python
class TaskManager:
    def handle_task_operation(self, input_data: dict) -> dict:
        # Task operations remain in current system
        # Only make API calls for grievance-related operations
        pass
```

## 5. Migration Strategy

### 5.1 Phase 1: Parallel Systems
- Set up Django with new database
- Implement basic API endpoints
- Keep existing system fully functional
- Start with new features in Django

### 5.2 Phase 2: Feature Migration
1. User Management
2. File Handling
3. Grievance Creation
4. Status Updates
5. Reporting

### 5.3 Phase 3: Data Synchronization
- Implement sync mechanism between databases
- Monitor for inconsistencies
- Handle edge cases

### 5.4 Phase 4: Complete Migration
- Move remaining features
- Verify all functionality
- Plan database consolidation

## 6. Security Considerations

### 6.1 Authentication
- JWT-based authentication
- Role-based access control
- API key management

### 6.2 Data Protection
- Encrypted data transmission
- Secure file storage
- Audit logging

## 7. Monitoring and Logging

### 7.1 System Monitoring
- Service health checks
- Performance metrics
- Error tracking

### 7.2 Logging
- Request/Response logging
- Error logging
- Audit logging

## 8. Deployment Architecture

### 8.1 Development Environment
- Local development setup
- Testing environment
- CI/CD pipeline

### 8.2 Production Environment
- Load balancing
- High availability
- Backup strategy

## 9. Testing Strategy

### 9.1 Unit Tests
- API endpoint testing
- Database operations
- Business logic

### 9.2 Integration Tests
- End-to-end testing
- System integration
- Performance testing

## 10. Documentation Requirements

### 10.1 Technical Documentation
- API documentation
- Database schema
- Deployment guide

### 10.2 User Documentation
- Admin guide
- User manual
- Troubleshooting guide 