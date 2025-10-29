# Nepal Chatbot - Integrations Guide

External integrations including GRM system, Google Sheets, and OAuth authentication.

## Table of Contents

- [GRM System Integration](#grm-system-integration)
- [Google Sheets Integration](#google-sheets-integration)
- [OAuth Authentication](#oauth-authentication)
- [WhatsApp Integration](#whatsapp-integration)
- [SMS Integration](#sms-integration)

## GRM System Integration

### Overview

Integration with legacy PHP/MySQL Grievance Redress Mechanism (GRM) system for bidirectional data synchronization.

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Chatbot       │    │   GRM Integration │    │   GRM System    │
│   (Python)      │◄──►│   Layer           │◄──►│   (PHP/MySQL)   │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Components

1. **MySQL Database Service** (`mysql_services.py`)

   - Direct MySQL connections
   - Connection pooling
   - Error handling and logging

2. **SSH Tunnel Service** (`ssh_tunnel.py`)

   - Secure remote connections
   - Port forwarding
   - Key-based authentication

3. **GRM Integration Service** (`grm_integration_service.py`)
   - Data synchronization orchestration
   - Field mapping
   - Batch operations

### Installation

```bash
# Install dependencies
cd backend
pip install -r requirements_grm.txt

# Copy configuration
cp env.grm.example .env

# Edit GRM configuration
nano .env
```

### Configuration

**Environment Variables:**

```bash
# GRM MySQL Database
GRM_MYSQL_HOST=your_grm_server_ip
GRM_MYSQL_DB=grm_database
GRM_MYSQL_USER=grm_user
GRM_MYSQL_PASSWORD=your_password
GRM_MYSQL_PORT=3306

# Enable integration
GRM_INTEGRATION_ENABLED=true

# Auto-sync settings
GRM_SYNC_INTERVAL_MINUTES=5
GRM_AUTO_SYNC_GRIEVANCES=true
GRM_MAX_RETRY_ATTEMPTS=3

# SSH Tunnel (for remote connections)
GRM_SSH_TUNNEL_ENABLED=false
GRM_SSH_HOST=203.0.113.10
GRM_SSH_USER=admin
GRM_SSH_KEY_PATH=/home/user/.ssh/grm_key
```

### Connection Options

#### Option 1: Direct Connection (Same Network)

```env
GRM_MYSQL_HOST=192.168.1.100
GRM_MYSQL_DB=grievance_system
GRM_MYSQL_USER=grm_admin
GRM_MYSQL_PASSWORD=secure_password
```

#### Option 2: SSH Tunnel (Remote/Cloud)

```env
GRM_SSH_TUNNEL_ENABLED=true
GRM_SSH_HOST=203.0.113.10
GRM_SSH_USER=admin
GRM_SSH_KEY_PATH=/home/user/.ssh/grm_key

GRM_MYSQL_HOST=localhost
GRM_MYSQL_DB=grm_production
GRM_MYSQL_USER=grm_user
GRM_MYSQL_PASSWORD=db_password
```

### Usage

#### Basic Integration

```python
from backend.services.integration.grm_integration_service import (
    get_grm_orchestrator, initialize_grm_integration
)

# Initialize
orchestrator = get_grm_orchestrator()
if initialize_grm_integration():
    print("GRM integration ready")
else:
    print("GRM integration failed")

# Sync a grievance
grievance_data = {
    'grievance_id': 'GRV-001',
    'complainant_full_name': 'John Doe',
    'complainant_phone': '+9771234567890',
    'grievance_description': 'Water supply issue in ward 5',
    'grievance_location': 'Kathmandu',
    'classification_status': 'pending'
}

result = orchestrator.process_grievance(grievance_data)
print(f"Sync result: {result.status.value}")
```

#### Batch Operations

```python
# Sync multiple grievances
grievances = [grievance_data_1, grievance_data_2, grievance_data_3]

results = orchestrator.process_grievances_batch(grievances)
success_count = sum(1 for r in results if r.success)
print(f"Successfully synced {success_count}/{len(grievances)} grievances")
```

#### Status Updates

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

### Data Mapping

#### Field Mapping

| Chatbot Field           | GRM Field               | Description                    |
| ----------------------- | ----------------------- | ------------------------------ |
| `complainant_full_name` | `complainant_name`      | User's full name               |
| `complainant_phone`     | `contact_phone`         | Contact phone number           |
| `grievance_description` | `grievance_description` | Detailed grievance description |
| `grievance_location`    | `location`              | Location of the issue          |
| `classification_status` | `status`                | Processing status              |

#### Status Mapping

| Chatbot Status     | GRM Status         | Description         |
| ------------------ | ------------------ | ------------------- |
| `pending`          | `pending`          | Awaiting processing |
| `submitted`        | `submitted`        | Submitted to GRM    |
| `under_evaluation` | `under_evaluation` | Being evaluated     |
| `resolved`         | `resolved`         | Issue resolved      |
| `denied`           | `denied`           | Request denied      |

#### Custom Field Mapping

Edit `backend/config/grm_config.py`:

```python
GRM_FIELD_MAPPING = {
    'complainant_full_name': 'complainant_name',
    'complainant_phone': 'contact_phone',
    'custom_field': 'grm_custom_field',
}
```

### Testing

```bash
# Test connection
cd backend
python -m backend.config.grm_config

# Test SSH tunnel
python -m backend.services.database_services.ssh_tunnel

# Test full integration
python -m backend.services.integration.grm_integration_service
```

### Troubleshooting

#### Connection Refused

- Check if MySQL server is running
- Verify host and port settings
- Check firewall rules

#### Authentication Failed

- Verify username and password
- Check MySQL user permissions
- Ensure user can connect from your IP

#### SSH Tunnel Issues

- Verify SSH key permissions (chmod 600)
- Check SSH server configuration
- Ensure SSH user has access

## Google Sheets Integration

### Overview

Real-time monitoring dashboard using Google Sheets with automatic data refresh and role-based filtering.

### Features

- **Real-time Data**: Automatic refresh from PostgreSQL
- **Role-based Access**: Office-specific data filtering
- **Authentication**: Bearer token authentication
- **Custom Reports**: Configurable columns and filters

### Local Development Setup

#### Prerequisites

- WSL2 with Nepal Chatbot running
- Flask backend on port 5001
- Google account
- ngrok account (free tier)

#### Step 1: Configure Environment

```bash
# Edit env.local
nano /home/philg/projects/nepal_chatbot/env.local

# Add bearer token
GSHEET_BEARER_TOKEN=dev_gsheet_2024_abc123xyz
```

#### Step 2: Install ngrok

```bash
# Download and install
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Set auth token
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### Step 3: Start ngrok Tunnel

```bash
# Make scripts executable
chmod +x scripts/local/setup_ngrok.sh
chmod +x scripts/local/check_ngrok.sh
chmod +x scripts/local/stop_ngrok.sh

# Start tunnel
./scripts/local/setup_ngrok.sh

# Output:
# 🌍 Public URL: https://abc123.ngrok.io
# 📝 Use this URL in your Google Sheets configuration
```

#### Step 4: Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create new spreadsheet: "Nepal Chatbot - Local Monitoring"
3. Go to **Extensions** → **Apps Script**
4. Delete default code
5. Paste contents from `scripts/local/google_sheets_local.js`
6. Save script (Ctrl+S)

#### Step 5: Configure Sheet

1. New menu appears: **Nepal Chatbot - Local Dev**
2. Click **Setup Configuration**
3. Enter API token (same as `GSHEET_BEARER_TOKEN`)
4. Enter ngrok URL

#### Step 6: Test

1. Click **Test Connection**
2. Click **Refresh Data**
3. Sheet populates with grievance data

### Managing ngrok

```bash
# Check status
./scripts/local/check_ngrok.sh

# Stop tunnel
./scripts/local/stop_ngrok.sh

# Restart
./scripts/local/setup_ngrok.sh restart
```

### Office Authentication Setup

#### User Accounts

| Username  | Password | Access Level | Municipality       |
| --------- | -------- | ------------ | ------------------ |
| pd_office | 1234     | Admin        | All municipalities |
| adb_hq    | 1234     | Admin        | All municipalities |
| office_1  | 1234     | Office User  | Birtamod           |
| office_2  | 1234     | Office User  | Mechinagar         |
| office_3  | 1234     | Office User  | [As configured]    |

#### Database Setup

```bash
cd /home/philg/projects/nepal_chatbot
python scripts/database/create_office_management_table.py
```

This creates:

- `office_management` table
- `office_municipality_ward` junction table
- User accounts in `office_user` table

#### API Authentication

```javascript
headers: {
  "Authorization": "Bearer office_1",
  "Content-Type": "application/json"
}
```

#### Filtering

- **Admin users** (`pd_office`, `adb_hq`): See all grievances
- **Office users**: Only see grievances from their municipality

### Field Mapping

| Column | Database Field            | Description       |
| ------ | ------------------------- | ----------------- |
| A      | complainant_id            | User ID           |
| B      | grievance_id              | Grievance ID      |
| C      | complainant_full_name     | Full Name         |
| D      | complainant_phone         | Contact Phone     |
| E      | complainant_municipality  | Municipality      |
| F      | complainant_village       | Village           |
| G      | complainant_address       | Address           |
| H      | grievance_description     | Grievance Details |
| I      | grievance_summary         | Summary           |
| J      | grievance_categories      | Categories        |
| K      | grievance_creation_date   | Creation Date     |
| L      | status                    | Status            |
| M      | grievance_sensitive_issue | Sensitive Issue   |
| N      | grievance_high_priority   | High Priority     |

### Troubleshooting

#### Connection Failed

- Check Flask server: `curl http://localhost:5001/health`
- Verify ngrok: `./scripts/local/check_ngrok.sh`
- Check ngrok URL in Google Sheets

#### Invalid Token

- Verify `GSHEET_BEARER_TOKEN` in env.local
- Match token in Google Sheets configuration
- Restart Flask server

#### No Data

- Check if grievances exist in database
- View Apps Script logs: **View** → **Logs**
- Test API: `curl -H "Authorization: Bearer TOKEN" https://ngrok-url/gsheet-get-grievances`

## OAuth Authentication

### Overview

OAuth 2.0 authentication setup for Google Sheets and other Google services.

### Google Cloud Setup

1. **Create Project**

   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create new project or select existing
   - Enable Google Sheets API

2. **Create OAuth Credentials**

   - Navigate to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth client ID**
   - Select **Web application**
   - Add authorized redirect URIs
   - Download credentials JSON

3. **Configure OAuth Consent Screen**
   - Navigate to **OAuth consent screen**
   - Select **External** or **Internal**
   - Fill in application details
   - Add scopes: `https://www.googleapis.com/auth/spreadsheets`

### Environment Configuration

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5001/oauth/callback

# Google Sheets
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_SHEETS_SCOPES=https://www.googleapis.com/auth/spreadsheets
```

### Implementation

```python
# backend/services/oauth/google_oauth.py

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

def get_oauth_flow():
    """Create OAuth flow."""
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
        redirect_uri='http://localhost:5001/oauth/callback'
    )
    return flow

def get_authorization_url():
    """Get OAuth authorization URL."""
    flow = get_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return authorization_url, state

def exchange_code_for_token(code):
    """Exchange authorization code for access token."""
    flow = get_oauth_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return credentials
```

### Flask OAuth Routes

```python
@app.route('/oauth/authorize')
def oauth_authorize():
    """Start OAuth flow."""
    authorization_url, state = get_authorization_url()
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback."""
    code = request.args.get('code')
    credentials = exchange_code_for_token(code)

    # Save credentials
    save_credentials(credentials)

    return redirect('/dashboard')
```

## WhatsApp Integration

### Overview

WhatsApp Business API integration for receiving and responding to grievances.

### Setup

```bash
# Install dependencies
pip install twilio

# Configure
export TWILIO_ACCOUNT_SID=your_account_sid
export TWILIO_AUTH_TOKEN=your_auth_token
export TWILIO_PHONE_NUMBER=+1234567890
export TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
```

### Webhook Configuration

```python
# backend/app.py

@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages."""
    from_number = request.form.get('From')
    message_body = request.form.get('Body')

    # Process message with Rasa
    response = requests.post(
        'http://localhost:5005/webhooks/rest/webhook',
        json={
            'sender': from_number,
            'message': message_body
        }
    )

    # Send response via WhatsApp
    bot_response = response.json()[0]['text']
    send_whatsapp_message(from_number, bot_response)

    return '', 200
```

### Sending Messages

```python
from twilio.rest import Client

def send_whatsapp_message(to, message):
    """Send WhatsApp message via Twilio."""
    client = Client(
        os.getenv('TWILIO_ACCOUNT_SID'),
        os.getenv('TWILIO_AUTH_TOKEN')
    )

    message = client.messages.create(
        from_=f"whatsapp:{os.getenv('TWILIO_WHATSAPP_NUMBER')}",
        to=f"whatsapp:{to}",
        body=message
    )

    return message.sid
```

### Rasa Channel Configuration

**credentials.yml:**

```yaml
twilio:
  account_sid: "your_account_sid"
  auth_token: "your_auth_token"
  twilio_number: "+1234567890"
```

## SMS Integration

### Overview

SMS notifications via Twilio for OTP verification and status updates.

### Configuration

```python
# backend/services/sms/twilio_service.py

from twilio.rest import Client

class SMSService:
    def __init__(self):
        self.client = Client(
            os.getenv('TWILIO_ACCOUNT_SID'),
            os.getenv('TWILIO_AUTH_TOKEN')
        )
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')

    def send_sms(self, to, message):
        """Send SMS message."""
        try:
            message = self.client.messages.create(
                to=to,
                from_=self.from_number,
                body=message
            )
            return {'status': 'success', 'sid': message.sid}
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def send_otp(self, phone, otp):
        """Send OTP via SMS."""
        message = f"Your OTP for grievance submission is: {otp}. Valid for 10 minutes."
        return self.send_sms(phone, message)
```

### Celery Task

```python
# task_queue/tasks/notifications.py

@app.task(bind=True, max_retries=3)
def send_sms_task(self, phone, message):
    """Send SMS notification."""
    try:
        sms_service = SMSService()
        result = sms_service.send_sms(phone, message)
        return result
    except Exception as e:
        logger.error(f"SMS task failed: {e}")
        raise self.retry(exc=e, countdown=60)
```

### Usage

```python
# Send OTP
from task_queue.tasks.notifications import send_sms_task

send_sms_task.delay('+9771234567890', 'Your OTP is: 123456')

# Send status update
message = f"Your grievance {grievance_id} has been updated. Status: {status}"
send_sms_task.delay(phone, message)
```

---

For additional configuration and troubleshooting, see:

- [Backend Guide](BACKEND.md)
- [Operations Guide](OPERATIONS.md)
