# Nepal Chatbot - Grievance Reporting System

A multilingual conversational AI system for grievance reporting and management in Nepal, built with Rasa, Django, and modern web technologies.

## 🌟 Features

- **Multilingual Support**: Full support for English and Nepali languages
- **AI-Powered Classification**: Automatic grievance categorization and summarization using OpenAI
- **Accessible Interface**: Voice-based interaction for users with disabilities
- **Multiple Channels**: Web chat, WhatsApp, and Facebook integration
- **Ticketing System**: Django-based helpdesk with SLA monitoring and escalation workflows
- **File Attachments**: Support for photos, documents, and voice recordings
- **Real-time Processing**: Async task processing with Celery and Redis
- **Status Tracking**: Users can check grievance status via phone number or ID
- **OTP Verification**: Phone number verification for authentic submissions

## 📋 Prerequisites

- Python 3.10
- PostgreSQL 13+
- Redis 6+
- Nginx (for production)
- Node.js 14+ (for frontend development)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/philgaeng/chatbot_ssh.git nepal_chatbot
cd nepal_chatbot

# Create virtual environment
python3 -m venv rasa-env
source rasa-env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp env.local .env

# Edit .env with your credentials
nano .env
```

Required environment variables:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - Database credentials
- `OPENAI_API_KEY` - For AI classification and transcription
- `REDIS_HOST`, `REDIS_PASSWORD` - Redis configuration
- `DB_ENCRYPTION_KEY` - For encrypting sensitive data

### 3. Initialize Database (Docker)

```bash
docker compose --profile init run --rm db_init
```

### 4. Train Rasa Model

```bash
cd rasa_chatbot
rasa train
cd ..
```

### 5. Start Services

```bash
docker compose up -d --build
```

### 6. Access the System

- **Web Interface**: http://localhost:5002
- **Rasa API**: http://localhost:5005
- **Flask Server**: http://localhost:5001
- **Django Admin**: http://localhost:8000/admin

## 📚 Documentation

Complete documentation is available in the `docs/` directory:

- **[Setup Guide](docs/SETUP.md)** - Detailed installation and deployment instructions
- **[Architecture](docs/ARCHITECTURE.md)** - System components and data flow
- **[Backend Guide](docs/BACKEND.md)** - Flask, Django, Celery, and database documentation
- **[Rasa Guide](docs/RASA.md)** - Conversation flows, forms, and NLU training
- **[Integrations](docs/INTEGRATIONS.md)** - GRM, Google Sheets, and OAuth setup
- **[Operations](docs/OPERATIONS.md)** - Monitoring, troubleshooting, and maintenance
- **[Migrations Policy](docs/MIGRATIONS_POLICY.md)** - Two-stream DB policy: **Alembic for `ticketing.*` only**; `public.*` / chatbot rules and cross-worktree traceability

## 🏗️ System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Webchat   │────▶│     Nginx    │────▶│    Rasa     │
│  Interface  │     │  (Reverse    │     │   Server    │
└─────────────┘     │   Proxy)     │     └─────────────┘
                    └──────────────┘            │
                                                │
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  WhatsApp   │────▶│    Flask     │────▶│   Action    │
│   Channel   │     │    Server    │     │   Server    │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                     │
                           │                     │
                    ┌──────────────┐     ┌─────────────┐
                    │    Redis     │     │ PostgreSQL  │
                    │   + Celery   │     │  Database   │
                    └──────────────┘     └─────────────┘
                           │
                    ┌──────────────┐
                    │   Django     │
                    │  Helpdesk    │
                    └──────────────┘
```

## 🔑 Key Components

### 1. **Rasa Core** (Port 5005)

- Natural language understanding and dialogue management
- Handles conversation flow and intent recognition
- Supports English and Nepali with transliteration

### 2. **Action Server** (Port 5055)

- Custom actions and form validations
- Database operations
- Business logic implementation

### 3. **Flask Server** (Port 5001)

- File upload handling
- WebSocket connections for real-time updates
- API endpoints for frontend

### 4. **Django Helpdesk** (Port 8000)

- Ticket management and workflow
- User hierarchy (PD, PM, Contractor)
- SLA monitoring and escalation
- Email notifications

### 5. **Celery Workers**

- Async task processing (classification, transcription)
- File processing
- Email notifications
- Background jobs

### 6. **PostgreSQL Database**

- Stores grievances, users, and tickets
- Field-level encryption for sensitive data
- Shared between all components

### 7. **Redis**

- Message broker for Celery
- Caching layer
- Session management

## 🛠️ Common Tasks

### Training the Model

```bash
cd rasa_chatbot
rasa train
```

### Restarting Services

```bash
docker compose down
docker compose up -d --build
```

### Viewing Logs

```bash
# All logs
tail -f logs/*.log

# Specific component
tail -f logs/rasa_server.log
tail -f logs/celery_llm_queue.log
```

### Database Backup

```bash
# Backup database
pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d).sql

# Backup files
tar -czf uploads_$(date +%Y%m%d).tar.gz uploads/
```

## 🧪 Development

### Project Structure

```
nepal_chatbot/
├── rasa_chatbot/           # Rasa configuration and training data
│   ├── actions/            # Custom actions
│   ├── data/               # NLU, stories, and rules
│   └── domain.yml          # Domain definition
├── backend/                # Backend services
│   ├── services/           # Database, integration services
│   └── config/             # Configuration files
├── channels/               # Frontend interfaces
│   ├── webchat/            # Web chat interface
│   └── accessible/         # Accessible interface
├── scripts/                # Utility scripts
├── docs/                   # Documentation
└── logs/                   # Log files
```

### Running Tests

```bash
# Rasa tests
cd rasa_chatbot
rasa test

# Python tests
pytest tests/

# Frontend tests
npm test
```

### Adding New Intents

1. Add examples to `rasa_chatbot/data/nlu/nlu.yml`
2. Add stories to `rasa_chatbot/data/stories/`
3. Update domain in `rasa_chatbot/domain.yml`
4. Retrain: `rasa train`

## 🌍 Deployment

### Production Deployment

1. **Update configurations** in `nginx/` folder
2. **Set environment variables** for production
3. **Configure SSL** with Let's Encrypt
4. **Set up systemd services** for auto-restart
5. **Configure backups** and monitoring

See [Setup Guide](docs/SETUP.md) for detailed deployment instructions.

## 🔐 Security

- **Encrypted Database Fields**: Sensitive data encrypted at rest
- **OTP Verification**: Phone number verification
- **Bearer Token Auth**: API authentication
- **HTTPS**: SSL/TLS encryption in production
- **CORS**: Configured for specific domains

## 📊 Monitoring

- **Logs**: All components log to `logs/` directory
- **Health Checks**: `/health` endpoints on all services
- **Celery Flower**: Task monitoring UI
- **PostgreSQL**: Query performance monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

This project is developed for the Nepal Government grievance reporting system.

## 📧 Support

- **Documentation**: See `docs/` folder
- **Issues**: GitHub Issues
- **Email**: philgaeng@pm.me
- **Repository**: https://github.com/philgaeng/chatbot_ssh

## 🙏 Acknowledgments

Built with:

- [Rasa](https://rasa.com/) - Conversational AI framework
- [Django](https://www.djangoproject.com/) - Web framework
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Redis](https://redis.io/) - Message broker
- [Celery](https://docs.celeryproject.org/) - Task queue
- [OpenAI](https://openai.com/) - AI services

---

For detailed documentation, please refer to the [docs/](docs/) directory.
