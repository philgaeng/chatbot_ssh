# Orchestrator

FastAPI service that drives the grievance details flow: intro → main_menu → form_grievance → done.

## Run

Use the **project's Python environment** (has rasa-sdk, backend, etc.):

```bash
# From project root
PYTHONPATH=$(pwd) uvicorn orchestrator.main:app --host 0.0.0.0 --port 8001
```

## API

- **POST /message** – Handle user message (see 01_orchestrator.md)
- **GET /health** – Health check

## Verify

```bash
# Health
curl http://localhost:8001/health

# Full flow
curl -X POST http://localhost:8001/message -H "Content-Type: application/json" -d '{"user_id":"u1","text":"hi"}'
curl -X POST http://localhost:8001/message -H "Content-Type: application/json" -d '{"user_id":"u1","payload":"/set_english"}'
curl -X POST http://localhost:8001/message -H "Content-Type: application/json" -d '{"user_id":"u1","payload":"/new_grievance"}'
curl -X POST http://localhost:8001/message -H "Content-Type: application/json" -d '{"user_id":"u1","text":"My complaint is about water supply"}'
curl -X POST http://localhost:8001/message -H "Content-Type: application/json" -d '{"user_id":"u1","payload":"/submit_details"}'
```

## Note

For the spike, set `LLM_CLASSIFICATION=False` in backend config to avoid Celery calls when the form completes.
