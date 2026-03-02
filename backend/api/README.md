# Backend API

The **live backend** is the **FastAPI** app in `fastapi_app.py`.

- **Run (production):** `uvicorn backend.api.fastapi_app:app --host 0.0.0.0 --port 5001`
- **Flask** (`app.py`) is **deprecated for production** and kept for reference or rollback.
- **Environment:** Use the **chatbot-rest** env for running and testing (e.g. `conda activate chatbot-rest`). Backend tests: `PYTHONPATH=. pytest tests/backend/test_fastapi_grievance.py -v`

See [docs/BACKEND.md](../../docs/BACKEND.md) for full API and deployment details.
