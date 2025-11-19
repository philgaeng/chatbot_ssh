# Nepal Chatbot - System Architecture

Comprehensive overview of the Nepal Chatbot system architecture, components, and data flow.

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Message Queue Architecture](#message-queue-architecture)
- [Security Architecture](#security-architecture)
- [Scalability Considerations](#scalability-considerations)

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Webchat  │  │ WhatsApp │  │ Facebook │  │ Accessible   │   │
│  │          │  │          │  │          │  │ Interface    │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
└───────┼─────────────┼─────────────┼────────────────┼───────────┘
        │             │             │                │
        └─────────────┴─────────────┴────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │    Nginx          │
                    │  Reverse Proxy    │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌───────▼────────┐   ┌───────▼────────┐
│  Rasa Server   │   │  Flask Server  │   │ Django Helpdesk│
│  (Port 5005)   │   │  (Port 5001)   │   │  (Port 8000)   │
│                │   │                │   │   Option       │
│  - NLU         │   │  - File Upload │   │  - Ticketing   │
│  - Dialogue    │   │  - WebSocket   │   │  - User Mgmt   │
│  - Policies    │   │  - REST API    │   │  - Reporting   │
└───────┬────────┘   └───────┬────────┘   └───────┬────────┘
        │                    │                     │
        │            ┌───────▼────────┐            │
        │            │  Celery Workers│            │
        │            │                │            │
        │            │  - LLM Queue   │            │
        │            │  - File Queue  │            │
        │            │  - Email Queue │            │
        │            └───────┬────────┘            │
        │                    │                     │
┌───────▼────────┐   ┌───────▼────────┐           │
│ Action Server  │   │     Redis      │           │
│  (Port 5055)   │   │                │           │
│                │   │  - Broker      │           │
│  - Forms       │   │  - Cache       │           │
│  - Validation  │   │  - Sessions    │           │
│  - Business    │   └────────────────┘           │
│    Logic       │                                │
└───────┬────────┘                                │
        │                                         │
        └─────────────────┬───────────────────────┘
                          │
                  ┌───────▼────────┐
                  │  PostgreSQL    │
                  │   Database     │
                  │                │
                  │  - Grievances  │
                  │  - Users       │
                  │  - Tickets     │
                  │  - Files       │
                  └────────────────┘
```

## Core Components

### 1. Rasa Server (Port 5005)

**Purpose**: Natural language understanding and dialogue management

**Responsibilities:**

- Process user messages and extract intents/entities
- Manage conversation state and context
- Determine next actions based on policies
- Handle multi-turn dialogues
- Support English and Nepali languages

**Key Technologies:**

- Rasa 3.6.21
- spaCy for NLP
- TensorFlow for ML models

**Configuration Files:**

- `rasa_chatbot/config.yml` - NLU pipeline and policies
- `rasa_chatbot/domain.yml` - Intents, entities, slots, responses
- `rasa_chatbot/endpoints.yml` - External service connections

**API Endpoints:**

- `POST /webhooks/rest/webhook` - Send messages
- `GET /conversations/{conversation_id}/tracker` - Get conversation state
- `POST /conversations/{conversation_id}/execute` - Execute actions
- `GET /version` - Get Rasa version
- `GET /status` - Health check

### 2. Action Server (Port 5055)

**Purpose**: Execute custom actions and business logic

**Responsibilities:**

- Form handling and validation
- Database operations (CRUD)
- External API integrations
- Business rule implementation
- Response generation

**Key Actions:**

- **Form Actions**: Grievance details, contact info, OTP verification
- **Generic Actions**: Menu, language selection, goodbye
- **Status Actions**: Check status by ID or phone
- **Submission Actions**: Submit grievance, store files

**Location:** `rasa_chatbot/actions/`

**Structure:**

```
actions/
├── forms/                    # Form validation logic
│   ├── form_grievance.py     # Grievance submission forms
│   ├── form_contact.py       # Contact information forms
│   ├── form_status_check.py  # Status check forms
│   └── form_validation_*.py  # Form validation helpers
├── generic_actions.py        # Generic actions (menu, intro)
├── status_actions.py         # Status checking actions
└── base_classes.py           # Base action classes
```

### 3. Flask Server (Port 5001)

**Purpose**: File handling, WebSocket connections, and API endpoints

**Responsibilities:**

- Handle file uploads (images, documents, voice recordings)
- WebSocket connections for real-time updates
- REST API endpoints for frontend
- Task status tracking
- File validation and processing

**Key Endpoints:**

- `POST /upload` - File upload
- `GET /health` - Health check
- `POST /task-status` - Task status updates
- `GET /grievance/{id}` - Get grievance details
- `WebSocket /socket.io` - Real-time connections

**Location:** `backend/app.py`

### 4. Django Helpdesk (Port 8000) - option

**Purpose**: Ticket management and workflow system

**Responsibilities:**

- Ticket lifecycle management
- User hierarchy (PD, PM, Contractor)
- SLA monitoring and escalation
- Email notifications
- Reporting and analytics
- Admin interface

**Key Features:**

- Multi-level escalation (4 levels)
- Priority-based routing
- Automated notifications
- Custom workflows
- Audit trail

**Location:** `backend/django_helpdesk/`

### 5. Celery Workers

**Purpose**: Asynchronous task processing

**Queues:**

1. **LLM Queue** (6 workers)

   - AI classification and summarization
   - Language translation
   - Transcript processing
   - Follow-up question generation

2. **Default Queue** (4 workers)
   - File processing
   - Email notifications
   - SMS sending
   - Background jobs

**Configuration:**

- Broker: Redis
- Result Backend: Redis
- Task retry: 3 attempts
- Task timeout: 300 seconds (LLM tasks)

**Location:** `task_queue/`

### 6. PostgreSQL Database

**Purpose**: Primary data store

**Databases:**

- `grievance_db` - Main application database
- `helpdesk_db` - Django helpdesk database (future)

**Key Tables:**

- `grievances` - Grievance records
- `complainants` - User information (encrypted)
- `office_management` - Office assignments
- `office_user` - User accounts
- `file_attachments` - File metadata
- `status_history` - Status change log
- `task_tracking` - Celery task tracking

**Security Features:**

- Field-level encryption (pgcrypto)
- Row-level security (planned)
- Audit logging
- Connection pooling

### 7. Redis

**Purpose**: Message broker, cache, and session store

**Uses:**

- Celery message broker
- Task result backend
- Session storage
- Rate limiting
- Caching frequently accessed data

**Configuration:**

- Password protected
- Persistence enabled
- Max memory: 2GB
- Eviction policy: allkeys-lru

## Data Flow

### Grievance Submission Flow

```
┌──────────┐
│   User   │
└────┬─────┘
     │ 1. Start conversation
     ▼
┌──────────────┐
│   Webchat    │
└────┬─────────┘
     │ 2. Send message
     ▼
┌──────────────┐
│  Rasa Server │
└────┬─────────┘
     │ 3. Extract intent/entities
     ▼
┌──────────────────┐
│  Action Server   │
└────┬─────────────┘
     │ 4. Activate form
     │    (grievance_details_form)
     ▼
┌──────────────────┐
│  User provides   │
│  grievance text  │
└────┬─────────────┘
     │ 5. Submit details
     ▼
┌──────────────────┐
│  Action Server   │
│  - Validate      │
│  - Store temp    │
└────┬─────────────┘
     │ 6. Trigger async classification
     ▼
┌──────────────────┐
│  Celery (LLM)    │
│  - OpenAI API    │
│  - Classify      │
│  - Summarize     │
└────┬─────────────┘
     │ 7. Classification complete
     ▼
┌──────────────────┐
│  Webchat         │
│  - Show results  │
│  - Send to Rasa  │
└────┬─────────────┘
     │ 8. User confirms
     ▼
┌──────────────────┐
│  Contact Form    │
│  - Name          │
│  - Phone         │
│  - Location      │
└────┬─────────────┘
     │ 9. OTP verification
     ▼
┌──────────────────┐
│  Submit to DB    │
│  - Encrypt data  │
│  - Store files   │
│  - Generate ID   │
└────┬─────────────┘
     | 10. Confirmation
     ▼
┌──────────────┐
│   User gets  │
│ Grievance ID │
└──────────────┘
```

### Status Check Flow

```
┌──────────┐
│   User   │
│ requests │
│  status  │
└────┬─────┘
     │ 1. Send grievance ID or phone
     ▼
┌──────────────┐
│ Rasa Server  │
│ (intent:     │
│  check_status)
└────┬─────────┘
     │ 2. Trigger action
     ▼
┌──────────────────┐
│  Action Server   │
│ - Query DB       │
└────┬─────────────┘
     │ 3. Retrieve data
     ▼
┌──────────────────┐
│  PostgreSQL      │
│ - Find grievance │
│ - Get status     │
│ - Get history    │
└────┬─────────────┘
     │ 4. Format response
     ▼
┌──────────────────┐
│  Action Server   │
│ - Build message  │
│ - Include files  │
└────┬─────────────┘
     │ 5. Send to user
     ▼
┌──────────────┐
│   Webchat    │
│ Display info │
└──────────────┘
```

### File Upload Flow

```
┌──────────┐
│   User   │
│  selects │
│   file   │
└────┬─────┘
     │ 1. Upload file
     ▼
┌──────────────┐
│ Flask Server │
│ - Validate   │
│ - Save temp  │
└────┬─────────┘
     │ 2. Queue processing
     ▼
┌──────────────────┐
│  Celery Worker   │
│ - Check format   │
│ - Resize (img)   │
│ - Scan malware   │
└────┬─────────────┘
     │ 3. Move to permanent storage
     ▼
┌──────────────────┐
│  File System     │
│  uploads/        │
│  └─ grievance_id/│
│     ├─ images/   │
│     ├─ docs/     │
│     └─ voice/    │
└────┬─────────────┘
     │ 4. Update database
     ▼
┌──────────────────┐
│  PostgreSQL      │
│  file_attachments│
│  - file_id       │
│  - file_path     │
│  - file_type     │
└──────────────────┘
```

## Database Schema

### Core Tables

#### grievances

```sql
CREATE TABLE grievances (
    grievance_id VARCHAR(50) PRIMARY KEY,
    complainant_id INTEGER REFERENCES complainants(complainant_id),
    grievance_description TEXT NOT NULL,
    grievance_summary TEXT,
    grievance_categories TEXT[],
    grievance_location TEXT,
    classification_status VARCHAR(50),
    priority_level VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(255),
    language VARCHAR(10),
    sensitive_issue BOOLEAN DEFAULT FALSE,
    high_priority BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_grievances_complainant ON grievances(complainant_id);
CREATE INDEX idx_grievances_status ON grievances(classification_status);
CREATE INDEX idx_grievances_created ON grievances(created_at);
```

#### complainants (with encryption)

```sql
CREATE TABLE complainants (
    complainant_id SERIAL PRIMARY KEY,
    complainant_full_name BYTEA,  -- Encrypted
    complainant_phone BYTEA,      -- Encrypted
    complainant_email BYTEA,      -- Encrypted
    complainant_address BYTEA,    -- Encrypted
    complainant_province VARCHAR(50),
    complainant_district VARCHAR(50),
    complainant_municipality VARCHAR(100),
    complainant_ward INTEGER,
    complainant_village VARCHAR(100),
    phone_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_complainants_phone ON complainants(complainant_phone);
CREATE INDEX idx_complainants_municipality ON complainants(complainant_municipality);
```

#### file_attachments

```sql
CREATE TABLE file_attachments (
    file_id VARCHAR(50) PRIMARY KEY,
    grievance_id VARCHAR(50) REFERENCES grievances(grievance_id),
    file_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(255),
    file_path TEXT NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_files_grievance ON file_attachments(grievance_id);
```

#### status_history

```sql
CREATE TABLE status_history (
    history_id SERIAL PRIMARY KEY,
    grievance_id VARCHAR(50) REFERENCES grievances(grievance_id),
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_by VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_status_history_grievance ON status_history(grievance_id);
```

#### office_management

```sql
CREATE TABLE office_management (
    office_id VARCHAR(50) PRIMARY KEY,
    office_name TEXT NOT NULL,
    office_address TEXT,
    office_email VARCHAR(255),
    office_pic_name TEXT,
    office_phone VARCHAR(20),
    district VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### office_municipality_ward (junction table)

```sql
CREATE TABLE office_municipality_ward (
    id SERIAL PRIMARY KEY,
    office_id VARCHAR(50) REFERENCES office_management(office_id),
    municipality VARCHAR(100) NOT NULL,
    ward INTEGER NOT NULL,
    village VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(office_id, municipality, ward, village)
);

CREATE INDEX idx_office_muni_ward ON office_municipality_ward(office_id, municipality, ward);
```

### Relationships

```
complainants (1) ──────────────── (many) grievances
                                     │
                                     │ (many)
                                     ▼
                            file_attachments
                                     │
                                     │ (many)
                                     ▼
                             status_history

office_management (1) ─────── (many) office_municipality_ward
        │
        │ (1)
        ▼
   office_user
```

## Message Queue Architecture

### Queue Types

1. **LLM Queue** (`llm_queue`)

   - Priority: High
   - Concurrency: 6 workers
   - Timeout: 300 seconds
   - Tasks: AI classification, summarization, translation

2. **Default Queue** (`default`)

   - Priority: Medium
   - Concurrency: 4 workers
   - Timeout: 60 seconds
   - Tasks: File processing, emails, SMS

3. **Notification Queue** (`notifications`)
   - Priority: Low
   - Concurrency: 2 workers
   - Timeout: 30 seconds
   - Tasks: Email, SMS notifications

### Task Flow

```
┌───────────────┐
│ Web Request   │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Create Task   │
│ (Celery)      │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Redis Queue   │
└───────┬───────┘
        │
        ▼
┌───────────────────────────────┐
│ Celery Worker                 │
│ 1. Fetch task from queue      │
│ 2. Execute task               │
│ 3. Store result in Redis      │
│ 4. Send status update         │
└───────┬───────────────────────┘
        │
        ├─────────────┬─────────────┐
        │             │             │
        ▼             ▼             ▼
┌────────────┐ ┌──────────┐ ┌──────────────┐
│ PostgreSQL │ │  Redis   │ │  WebSocket   │
│  (result)  │ │ (status) │ │  (notify)    │
└────────────┘ └──────────┘ └──────────────┘
```

### Retry Strategy

- **Max Retries**: 3
- **Retry Delay**: Exponential backoff (2^retry \* 60 seconds)
- **Dead Letter Queue**: Failed tasks after max retries

## Security Architecture

### Authentication & Authorization

1. **User Authentication**

   - Session-based (Rasa conversations)
   - Phone OTP verification
   - Admin: Django authentication

2. **API Authentication**
   - Bearer token (Google Sheets integration)
   - API keys (external services)

### Data Protection

1. **At Rest**

   - Database field-level encryption (pgcrypto)
   - Encrypted sensitive fields:
     - `complainant_full_name`
     - `complainant_phone`
     - `complainant_email`
     - `complainant_address`

2. **In Transit**

   - HTTPS/TLS for all connections
   - WebSocket secure (wss://)
   - Database SSL connections

3. **File Security**
   - File type validation
   - Size limits (10MB per file)
   - Virus scanning (planned)
   - Secure file paths (no direct access)

### Network Security

```
Internet
   │
   ▼
┌────────────────┐
│  Firewall      │
│  - Port 80/443 │
│  - Rate limit  │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│  Nginx         │
│  - SSL term    │
│  - CORS        │
│  - Headers     │
└────────┬───────┘
         │
         ├───────────────────────┐
         │                       │
         ▼                       ▼
┌────────────────┐      ┌────────────────┐
│  Application   │      │  Application   │
│  Servers       │      │  Servers       │
│  (Internal)    │      │  (Internal)    │
└────────┬───────┘      └────────┬───────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
            ┌────────────────┐
            │  PostgreSQL    │
            │  (localhost)   │
            └────────────────┘
```

## Scalability Considerations

### Current Capacity

- **Concurrent Users**: ~100
- **Daily Grievances**: ~50
- **File Uploads**: ~300 per day
- **Database Size**: ~10 GB

### Scaling Strategy

#### Horizontal Scaling

1. **Rasa Server**

   - Load balancer (Nginx)
   - Multiple Rasa instances
   - Shared Redis for state

2. **Celery Workers**

   - Additional worker nodes
   - Queue-based distribution
   - Auto-scaling based on queue length

3. **Database**
   - Read replicas for reports
   - Connection pooling
   - Query optimization

#### Vertical Scaling

1. **Increase Server Resources**

   - RAM: 8GB → 16GB
   - CPU: 4 cores → 8 cores
   - Storage: SSD recommended

2. **Database Optimization**
   - Indexing frequently queried fields
   - Partitioning large tables
   - Vacuuming and maintenance

#### Caching Strategy

1. **Redis Caching**

   - User sessions
   - Frequently accessed grievances
   - Location data
   - Category mappings

2. **Application Caching**
   - Response templates
   - Static resources
   - API responses (short TTL)

### Performance Targets

- **Response Time**: < 2 seconds (95th percentile)
- **Availability**: 99.5% uptime
- **Throughput**: 1000 requests/minute
- **Database Queries**: < 100ms average

---

For implementation details, see:

- [Backend Guide](BACKEND.md)
- [Rasa Guide](RASA.md)
- [Operations Guide](OPERATIONS.md)
