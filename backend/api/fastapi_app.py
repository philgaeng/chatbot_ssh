"""
FastAPI backend app (Phase 1–2). Replaces Flask for backend API.
Run: uvicorn backend.api.fastapi_app:app --port 5001
"""

import logging
import os
import sys
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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from backend.api.routers import grievance, files, voice_grievance, gsheet

app = FastAPI(title="Backend API", version="0.1.0")

# Same CORS policy as Flask: allow all origins for /*
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
