"""
FastAPI backend app (Phase 1–2). Production backend API.
Run: uvicorn backend.api.fastapi_app:app --port 5001
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _configure_backend_logging() -> None:
    """Reduce third-party log noise so backend logs stay readable."""
    for name in ("botocore", "boto3", "urllib3", "s3transfer"):
        logging.getLogger(name).setLevel(logging.WARNING)


_configure_backend_logging()

# Load env so backend config (e.g. DB, messaging) is available
_env_local = _REPO_ROOT / "env.local"
_env = _REPO_ROOT / ".env"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local)
    except ImportError:
        pass
elif _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.api.routers import grievance, files, voice_grievance, gsheet, messaging
from backend.api.websocket_fastapi import emit_status_update_accessible, socketio_app


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Wire real Socket.IO emit for accessible (grievance suffix A) on POST /task-status.
    files.set_emit_status_update_accessible(emit_status_update_accessible)
    yield


app = FastAPI(title="Backend API", version="0.1.0", lifespan=_lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure 500 and other unhandled errors return JSON so clients do not get plain 'Internal Server Error'."""
    logging.getLogger(__name__).exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )

# CORS: env-driven allowlist. Set CORS_ALLOWED_ORIGINS (comma-separated) in prod
# to lock this down (e.g. https://grm-chatbot.dor.gov.np). When unset (dev), fall
# back to "*" WITHOUT credentials — "*" + credentials is invalid per the CORS spec
# and was the prior misconfiguration (see docs/services/12_security_monitoring_service.md §3.2).
_cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
if _cors_env:
    _cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
    _cors_allow_credentials = True
else:
    _cors_origins = ["*"]
    _cors_allow_credentials = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_class=PlainTextResponse)
def health():
    """Health check; same contract as Flask: 200 with body 'OK' (plain text)."""
    return "OK"


# Grievance API: paths already include /api/grievance, so no prefix
app.include_router(grievance.router)
# File server: same paths as Flask FileServerAPI (no prefix)
app.include_router(files.router)
# Voice and gsheet: no prefix (paths are /accessible-file-upload, etc., and /gsheet-get-grievances)
app.include_router(voice_grievance.router)
app.include_router(gsheet.router)
# Messaging API: /api/messaging/*
app.include_router(messaging.router)

# Socket.IO ASGI app for accessible interface, mounted at /accessible-socket.io
app.mount("/accessible-socket.io", socketio_app)
