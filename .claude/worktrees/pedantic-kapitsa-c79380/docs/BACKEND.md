# Nepal Chatbot - Backend Guide

Complete backend documentation covering the Orchestrator (FastAPI), Flask backend API, Celery, and database services.

**Current architecture (post-refactor):** We do **not** run the full Rasa server. Conversation is driven by the **Orchestrator** (FastAPI), which uses **Rasa SDK** actions (same Python code as before) and a direct **REST API** (`POST /message`). The REST webchat and any custom ticketing system call this API. See [Refactor specs (March 5)](Refactor%20specs/March%205/01_orchestrator.md) for details.

## Table of Contents

- [API Overview and Integration](#api-overview-and-integration)
- [Orchestrator (FastAPI)](#orchestrator-fastapi)
- [Flask Server](#flask-server)
- [Django Helpdesk](#django-helpdesk)
- [Celery Task Queue](#celery-task-queue)
- [Database Services](#database-services)
- [File Management](#file-management)
- [API Reference](#api-reference)

## API Overview and Integration

### Two entry points

| Service | Port / Mount | Role |
|--------|-------------|------|
| **Orchestrator** (FastAPI) | Configurable (e.g. same host under `/message`) | Conversation: receive user message, run state machine + Rasa SDK actions, return bot messages. |
| **Backend API** (FastAPI) | 5001 (default) | Files, grievance CRUD, status updates, WebSocket, gsheet, voice. *(Flask `app.py` is deprecated for production.)* |

- **Conversation:** All chat flows (webchat, future ticketing UI, etc.) should call the Orchestrator **POST /message** endpoint. The REST webchat already does this (see `channels/REST_webchat`).
- **Ticketing / external systems:** Use the Flask **grievance API** for data: `GET /api/grievance/<id>`, `POST /api/grievance/<id>/status`, `GET /api/grievance/statuses`. For “create conversation turn” from a ticketing system, call Orchestrator **POST /message** with the same request shape (e.g. `user_id`, `text`, `payload`).

### Exposing the API for a custom ticketing system

- **Grievance data:** Use Backend API `GET /api/grievance/<grievance_id>`, `POST /api/grievance/<grievance_id>/status`, `GET /api/grievance/statuses`. These are already REST and can be proxied or called directly.
- **Conversation (bot turns):** Use Orchestrator `POST /message` with `user_id` (e.g. ticket or session id), `text` and/or `payload`. Response: `messages`, `next_state`, `expected_input_type`.
- **File uploads:** Use Backend API `POST /upload-files` (with `grievance_id` and files). REST webchat uses this today.

### Messaging (SMS/email) and “all through API”

**Current state:** SMS and email are sent **in-process** only:

- **Backend API:** On grievance status update, `send_status_update_notifications` calls `messaging_service.send_email` and `messaging_service.send_sms` directly (same process).
- **Orchestrator / Rasa SDK actions:** OTP, submit confirmation, status-check follow-up, etc. call `self.messaging.send_sms` / `send_email` inside the action code (orchestrator process).

There is **no** HTTP API for “send SMS” or “send email” today. To have **all messaging go through an API**:

1. **Add a small Messaging API** (e.g. `POST /api/messaging/send-sms`, `POST /api/messaging/send-email`) on the Backend API (FastAPI) or a dedicated service.
2. **Backend API:** Change `send_status_update_notifications` to call this API (HTTP) instead of `messaging_service.send_*` in-process.
3. **Orchestrator / actions:** Replace direct `Messaging` usage with an HTTP client that calls the same Messaging API (or a shared client library used by both Flask and orchestrator).

Then the REST webchat continues to call Orchestrator only for conversation; any SMS/email triggered by the flow is sent via the Messaging API.

### Flask vs FastAPI

- **Orchestrator** is already **FastAPI** (`backend/orchestrator/main.py`). The messaging service (`backend/services/messaging.py`) is a **Python class**, not tied to a framework; it is used by both Flask and by Rasa SDK actions run inside the orchestrator.
- **Current state:** The **backend** has been migrated to FastAPI; keep **Flask** only for reference (deprecated for production). The live backend is FastAPI; run with: uvicorn backend.api.fastapi_app:app --port 5001..

#### Can FastAPI do everything Flask does here?

**Yes.** For this project, every capability the Flask backend uses has a direct FastAPI (or ASGI) equivalent:

| What Flask does | FastAPI / ASGI equivalent |
|-----------------|---------------------------|
| REST routes (`@app.route`, blueprints) | FastAPI `APIRouter`, `@app.get` / `@app.post`, dependency injection. Same or simpler. |
| JSON request/response | Pydantic models; automatic validation and OpenAPI. |
| CORS | `fastapi.middleware.cors.CORSMiddleware`. |
| File uploads (`request.files`, multipart) | `File()`, `UploadFile`; well documented. |
| Path/query params | Declared parameters or Pydantic; type-safe. |
| Blueprints (e.g. `FileServerAPI`, `gsheet_monitoring_bp`) | `APIRouter`; include with `app.include_router(router, prefix="...")`. |
| Socket.IO (Flask-SocketIO + Redis) | **python-socketio** has an ASGI app; you mount it next to the FastAPI app (we already do this in the orchestrator: `Mount("/socket.io", app=socket_app)`). So Socket.IO works with FastAPI; you’d use the same `python-socketio` server and optionally Redis for the message queue. |
| Running the app | `uvicorn backend.api.fastapi_app:app` (backend); Flask `app.py` deprecated for production. |

So you can run a **single FastAPI application** that mounts:

1. The **orchestrator** (conversation) at `/` or `/chat`.
2. The **backend** (files, grievance, gsheet, voice) at `/api`, `/upload-files`, etc.
3. A **Socket.IO** ASGI app at `/accessible-socket.io` (or current path).

Nothing in the current Flask backend requires Flask-specific behaviour you can’t replicate in FastAPI. The only migration work is rewriting routes and replacing `request`/`jsonify` with FastAPI’s style and Pydantic models.

#### Why migrate to FastAPI first (recommended)

- **One stack to troubleshoot:** The backend (files, grievance API, uploads) needs ongoing work. Keeping it in Flask while the orchestrator is FastAPI means two codebases and two runtimes. One FastAPI app simplifies debugging and deployment.
- **Bot + file integration:** The user interacts with the bot (orchestrator) and adds files in the same session. The webchat gets `grievance_id` from the orchestrator (custom payload `grievance_id_set`) and sends uploads to the backend with that id. Having both in one FastAPI app (or one deployment) gives shared middleware, logging, and error handling, and makes it easier to add real-time feedback (e.g. "File received" in the chat) or fix issues that span conversation and upload.
- **Build new features once:** Add the Messaging API (and other changes) on the FastAPI backend after migration, so you don't implement in Flask and then port.

**Alternative (short-term Flask):** Keep Flask and add the Messaging API there if you prefer the smallest change first; you can migrate to FastAPI later.


## Orchestrator (FastAPI)

### Overview

The Orchestrator (`orchestrator/main.py`) is a lightweight FastAPI service that handles conversation: it receives user input, runs the state machine, invokes Rasa SDK actions (no full Rasa server), and returns bot messages. Used by the REST webchat and any client that talks to `POST /message`.

### Endpoints

- **POST /message** – Send a user message and get bot replies.  
  Request: `{ "user_id": "string", "message_id": "string | null", "text": "string", "payload": "string | null", "channel": "string | null" }`  
  Response: `{ "messages": [...], "next_state": "string", "expected_input_type": "string" }`
- **GET /health** – Health check.

### Running

Typically run with uvicorn (e.g. `uvicorn orchestrator.main:app`). For Socket.IO bridge and HTTP on one app, use `orchestrator.main:asgi`. See refactor specs: [01_orchestrator.md](Refactor%20specs/March%205/01_orchestrator.md), [05_agent_specs_spike.md](Refactor%20specs/March%205/05_agent_specs_spike.md).

## Backend API (FastAPI)

### Overview

The **Backend API** (`backend/api/fastapi_app.py`) is the live backend for file uploads, WebSocket (Socket.IO), grievance API, voice, gsheet, and REST endpoints. The former Flask server (`backend/api/app.py`) is **deprecated for production** and kept for reference or rollback.

**Port**: 5001 (default)

### Key Features

- File upload and validation
- WebSocket (Socket.IO) for real-time updates
- Task status tracking
- Health monitoring
- CORS configuration
- Grievance API, voice grievance, gsheet monitoring

### Starting the Backend (FastAPI)

```bash
# Production / development
uvicorn backend.api.fastapi_app:app --host 0.0.0.0 --port 5001
```

### Configuration

**Environment Variables:**

```bash
FLASK_PORT=5001
FLASK_DEBUG=false
FLASK_SECRET_KEY=your_secret_key
MAX_CONTENT_LENGTH=10485760  # 10MB
UPLOAD_FOLDER=./uploads
ALLOWED_EXTENSIONS=jpg,jpeg,png,pdf,mp3,wav,ogg
```

### Endpoints

#### 1. File Upload

```http
POST /upload
Content-Type: multipart/form-data

Parameters:
  - file: File to upload
  - grievance_id: Associated grievance ID
  - file_type: Type (image, document, voice)

Response:
{
  "status": "success",
  "file_id": "file_uuid",
  "file_path": "/uploads/grievance_id/file.jpg",
  "file_type": "image"
}
```

**Example:**

```python
import requests

files = {'file': open('image.jpg', 'rb')}
data = {'grievance_id': 'GRV001', 'file_type': 'image'}
response = requests.post('http://localhost:5001/upload', files=files, data=data)
```

#### 2. Health Check

```http
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2025-01-30T10:00:00Z",
  "database": "connected",
  "redis": "connected"
}
```

#### 3. Task Status

```http
POST /task-status
Content-Type: application/json

Body:
{
  "task_id": "task_uuid",
  "status": "SUCCESS",
  "result": {...}
}

Response:
{
  "status": "acknowledged"
}
```

#### 4. Get Grievance

```http
GET /grievance/{grievance_id}

Response:
{
  "grievance_id": "GRV001",
  "status": "pending",
  "description": "...",
  "summary": "...",
  "categories": ["Environmental"],
  "files": [...]
}
```

### WebSocket Events

**Connection:**

```javascript
const socket = io("http://localhost:5001");
```

**Events:**

1. **connect**

```javascript
socket.on("connect", () => {
  console.log("Connected to server");
});
```

2. **task_status**

```javascript
socket.on("task_status", (data) => {
  console.log("Task status:", data);
  // data: { task_id, status, result, ... }
});
```

3. **classification_complete**

```javascript
socket.on("classification_complete", (data) => {
  console.log("Classification:", data);
  // data: { grievance_id, categories, summary }
});
```

4. **disconnect**

```javascript
socket.on("disconnect", () => {
  console.log("Disconnected from server");
});
```

### File Validation

**Allowed File Types:**

- Images: JPG, JPEG, PNG (max 5MB each)
- Documents: PDF (max 10MB)
- Audio: MP3, WAV, OGG (max 10MB)

**Validation Logic:**

```python
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'mp3', 'wav', 'ogg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_size(file):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= MAX_FILE_SIZE
```

### Error Handling

```python
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal error: {error}')
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(RequestEntityTooLarge)
def file_too_large(error):
    return jsonify({'error': 'File too large'}), 413
```

## Celery Task Queue

### Overview

Asynchronous task processing using Celery with Redis as the message broker.

### Configuration

**File:** `task_queue/celery_config.py`

```python
from celery import Celery

app = Celery(
    'task_queue',
    broker='redis://:password@localhost:6379/0',
    backend='redis://:password@localhost:6379/0'
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kathmandu',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Queue configuration
app.conf.task_routes = {
    'task_queue.tasks.classify_*': {'queue': 'llm_queue'},
    'task_queue.tasks.process_file': {'queue': 'default'},
    'task_queue.tasks.send_email': {'queue': 'notifications'},
}
```

### Task Queues

#### 1. LLM Queue (High Priority)

**Purpose:** AI-powered tasks (classification, summarization)

**Configuration:**

```python
# Start worker
celery -A task_queue worker -Q llm_queue --loglevel=INFO --concurrency=6
```

**Tasks:**

- `classify_and_summarize_grievance_task`
- `translate_text_task`
- `generate_follow_up_questions_task`

#### 2. Default Queue

**Purpose:** General background tasks

**Configuration:**

```python
# Start worker
celery -A task_queue worker --loglevel=INFO --concurrency=4
```

**Tasks:**

- `process_file_task`
- `validate_file_task`
- `resize_image_task`

#### 3. Notifications Queue (Low Priority)

**Purpose:** Email and SMS notifications

**Configuration:**

```python
# Start worker
celery -A task_queue worker -Q notifications --loglevel=INFO --concurrency=2
```

**Tasks:**

- `send_email_task`
- `send_sms_task`
- `send_whatsapp_message_task`

### Task Examples

#### Classification Task

```python
# task_queue/tasks/classification.py

from celery import Task
from task_queue.celery_config import app

@app.task(bind=True, max_retries=3)
def classify_and_summarize_grievance_task(self, grievance_data):
    """Classify and summarize grievance using OpenAI."""
    try:
        # Call OpenAI API
        classification = classify_grievance(
            grievance_data['description'],
            grievance_data['language']
        )

        summary = summarize_grievance(
            grievance_data['description'],
            grievance_data['language']
        )

        return {
            'categories': classification['categories'],
            'summary': summary,
            'status': 'SUCCESS'
        }

    except Exception as e:
        logger.error(f'Classification failed: {e}')
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 60)
```

#### File Processing Task

```python
@app.task(bind=True)
def process_file_task(self, file_path, file_type):
    """Process uploaded file."""
    try:
        if file_type == 'image':
            # Resize and optimize image
            resize_image(file_path, max_width=1920, quality=85)

        elif file_type == 'voice':
            # Transcribe voice recording
            transcript = transcribe_audio(file_path)
            return {'transcript': transcript}

        return {'status': 'SUCCESS'}

    except Exception as e:
        logger.error(f'File processing failed: {e}')
        raise
```

#### Email Task

```python
@app.task(bind=True, max_retries=5)
def send_email_task(self, to_email, subject, message):
    """Send email notification."""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return {'status': 'SUCCESS'}

    except Exception as e:
        logger.error(f'Email sending failed: {e}')
        raise self.retry(exc=e, countdown=60)
```

### Calling Tasks

```python
# Synchronous execution (blocks)
result = classify_and_summarize_grievance_task(grievance_data)

# Asynchronous execution (non-blocking)
task = classify_and_summarize_grievance_task.delay(grievance_data)

# Get task ID
task_id = task.id

# Check task status
status = task.status  # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE'

# Get task result (blocks until complete)
result = task.get(timeout=300)

# Check if task is ready
if task.ready():
    result = task.result
```

### Monitoring

```bash
# Check active tasks
celery -A task_queue inspect active

# Check registered tasks
celery -A task_queue inspect registered

# Check worker stats
celery -A task_queue inspect stats

# Purge all tasks
celery -A task_queue purge
```

### Flower (Web UI)

```bash
# Install Flower
pip install flower

# Start Flower
celery -A task_queue flower --port=5555

# Access at: http://localhost:5555
```

## Database Services

### Overview

Database abstraction layer with managers for different entities.

**Location:** `backend/services/database_services/`

### Database Managers

#### 1. ComplainantDbManager

Manages user/complainant information with encryption.

```python
from backend.services.database_services import db_manager

# Create complainant
complainant_data = {
    'complainant_full_name': 'John Doe',
    'complainant_phone': '+9771234567890',
    'complainant_email': 'john@example.com',
    'complainant_municipality': 'Kathmandu'
}
complainant_id = db_manager.create_complainant(complainant_data)

# Get complainant (decrypts automatically)
complainant = db_manager.get_complainant_by_id(complainant_id)

# Search by phone (encrypted search)
complainants = db_manager.get_complainant_by_phone('+9771234567890')

# Update complainant
db_manager.update_complainant(complainant_id, {'complainant_email': 'new@example.com'})
```

#### 2. GrievanceDbManager

Manages grievance records.

```python
from backend.services.database_services import grievance_manager

# Create grievance
grievance_data = {
    'grievance_id': 'GRV001',
    'complainant_id': 123,
    'grievance_description': 'Water supply issue...',
    'grievance_summary': 'Water shortage in ward 5',
    'grievance_categories': ['Environmental', 'Water Supply'],
    'classification_status': 'pending'
}
grievance_manager.create_grievance(grievance_data)

# Get grievance
grievance = grievance_manager.get_grievance_by_id('GRV001')

# Update status
grievance_manager.update_grievance_status('GRV001', 'under_evaluation')

# Get grievances by complainant
grievances = grievance_manager.get_grievances_by_complainant(complainant_id)

# Search grievances
results = grievance_manager.search_grievances(
    status='pending',
    municipality='Kathmandu',
    date_from='2025-01-01'
)
```

#### 3. FileDbManager

Manages file attachments.

```python
from backend.services.database_services import file_manager

# Save file metadata
file_data = {
    'file_id': 'file_uuid',
    'grievance_id': 'GRV001',
    'file_type': 'image',
    'file_path': '/uploads/GRV001/image.jpg',
    'file_name': 'image.jpg',
    'file_size': 1024000,
    'mime_type': 'image/jpeg'
}
file_manager.save_file(file_data)

# Get files for grievance
files = file_manager.get_files_by_grievance('GRV001')

# Delete file
file_manager.delete_file('file_uuid')
```

### Database Encryption

#### Setup

```bash
# Generate encryption key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set environment variable
export DB_ENCRYPTION_KEY='your_generated_key'

# Enable pgcrypto extension
psql -U postgres -d grievance_db -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
```

#### How It Works

1. **Encryption** (on write):

```sql
INSERT INTO complainants (complainant_phone)
VALUES (pgp_sym_encrypt('+9771234567890', :encryption_key));
```

2. **Decryption** (on read):

```sql
SELECT pgp_sym_decrypt(complainant_phone::bytea, :encryption_key)
FROM complainants WHERE complainant_id = :id;
```

3. **Encrypted Search**:

```sql
SELECT * FROM complainants
WHERE complainant_phone = pgp_sym_encrypt(:phone, :encryption_key);
```

**Encrypted Fields:**

- `complainant_full_name`
- `complainant_phone`
- `complainant_email`
- `complainant_address`

### Connection Pooling

```python
from backend.services.database_services.connection_pool import get_connection

# Get connection from pool
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM grievances")
        results = cur.fetchall()

# Connection automatically returned to pool
```

**Configuration:**

```python
# backend/services/database_services/connection_pool.py

connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=20,
    host=os.getenv('POSTGRES_HOST'),
    port=os.getenv('POSTGRES_PORT'),
    database=os.getenv('POSTGRES_DB'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD')
)
```

## File Management

### Directory Structure

```
uploads/
├── voice_recordings/
│   ├── GRV001/
│   │   ├── recording_1.wav
│   │   └── recording_2.wav
│   └── GRV002/
│       └── recording_1.mp3
├── images/
│   ├── GRV001/
│   │   ├── photo_1.jpg
│   │   └── photo_2.jpg
│   └── GRV002/
│       └── photo_1.png
└── documents/
    ├── GRV001/
    │   └── document.pdf
    └── GRV002/
        └── report.pdf
```

### File Upload Process

1. **Receive file** → Flask `/upload` endpoint
2. **Validate** → Check type, size, format
3. **Save temporarily** → `/tmp` directory
4. **Queue processing** → Celery task
5. **Process file** → Resize, convert, validate
6. **Move to permanent storage** → `/uploads` directory
7. **Save metadata** → PostgreSQL database
8. **Return file ID** → Response to client

### File Utilities

```python
# backend/services/file_services.py

def save_uploaded_file(file, grievance_id, file_type):
    """Save uploaded file to permanent storage."""
    # Generate unique file ID
    file_id = str(uuid.uuid4())

    # Create directory if not exists
    upload_dir = os.path.join(UPLOAD_FOLDER, file_type, grievance_id)
    os.makedirs(upload_dir, exist_ok=True)

    # Save file
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_dir, f"{file_id}_{filename}")
    file.save(file_path)

    return file_id, file_path

def delete_file(file_path):
    """Delete file from storage."""
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False

def get_file_url(file_path):
    """Generate URL for file access."""
    return f"/files/{file_path}"
```

## API Reference

### REST API Endpoints

#### Orchestrator (FastAPI; port/host configurable, often same host as frontend)

| Method | Endpoint   | Description                          |
| ------ | ---------- | ------------------------------------ |
| POST   | `/message` | Send user message; get bot messages  |
| GET    | `/health`  | Health check                         |

#### Flask Server (Port 5001)

| Method | Endpoint                          | Description                    |
| ------ | --------------------------------- | ----------------------------- |
| GET    | `/health`                          | Health check                  |
| POST   | `/upload-files`                    | Upload file(s) for grievance  |
| GET    | `/api/grievance/<id>`              | Get grievance details         |
| POST   | `/api/grievance/<id>/status`       | Update grievance status       |
| GET    | `/api/grievance/statuses`          | List available statuses       |
| POST   | `/task-status`                     | Task status callback          |
| GET    | `/files/<grievance_id>`, etc.       | List/download files           |

### Response Formats

**Success Response:**

```json
{
  "status": "success",
  "data": {...},
  "message": "Operation completed successfully"
}
```

**Error Response:**

```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description"
  }
}
```

---

For integration with external systems, see:

- [Integrations Guide](INTEGRATIONS.md)
- [Operations Guide](OPERATIONS.md)
