"""
Orchestrator FastAPI app: POST /message, GET /health.
"""

import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Configure logging early so application logs are visible and third-party noise is reduced.
# Without this, botocore/boto3 DEBUG floods the log and buries orchestrator/rasa_chatbot logs.
def _configure_orchestrator_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    for name in ("botocore", "boto3", "urllib3", "s3transfer"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # Application loggers: keep DEBUG for form flow and actions (set via LOG_LEVEL if desired)
    log_level = os.environ.get("ORCHESTRATOR_LOG_LEVEL", "DEBUG").upper()
    level = getattr(logging, log_level, logging.INFO)
    for name in ("rasa_chatbot", "orchestrator", "backend"):
        logging.getLogger(name).setLevel(level)


_configure_orchestrator_logging()

# Load env.local so ENABLE_CELERY_CLASSIFICATION etc. are set (orchestrator is often
# started by uvicorn without sourcing env.local)
_env_local = _REPO_ROOT / "env.local"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local)
    except ImportError:
        pass
_RASA_DIR = _REPO_ROOT / "rasa_chatbot"
if str(_RASA_DIR) not in sys.path:
    sys.path.insert(0, str(_RASA_DIR))

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from starlette.applications import Starlette
from starlette.routing import Mount

from backend.orchestrator.session_store import get_session, save_session, create_session
from backend.orchestrator.state_machine import run_flow_turn
from backend.orchestrator.config_loader import load_config
from backend.orchestrator.socket_server import socket_app

app = FastAPI(title="Orchestrator", version="0.1.0")

# Config and domain loaded at startup
_CONFIG: Dict[str, Any] = {}
_DOMAIN: Dict[str, Any] = {}


def _load_domain() -> Dict[str, Any]:
    """Load Rasa domain.yml as dict."""
    path = _REPO_ROOT / "rasa_chatbot" / "domain.yml"
    if not path.exists():
        return {"slots": {}}
    with open(path) as f:
        return yaml.safe_load(f) or {}


@app.on_event("startup")
def startup() -> None:
    global _CONFIG, _DOMAIN
    _CONFIG = load_config()
    _DOMAIN = _load_domain()
    cel = os.environ.get("ENABLE_CELERY_CLASSIFICATION", "").strip().lower()
    if cel in ("1", "true", "yes"):
        print("Orchestrator: ENABLE_CELERY_CLASSIFICATION=1 — grievance LLM classification will run via Celery when user clicks 'File as is'.")
    else:
        print("Orchestrator: ENABLE_CELERY_CLASSIFICATION not set — grievance classification is stubbed (no LLM). Set in env.local and restart to enable.")


class MessageRequest(BaseModel):
    user_id: str
    message_id: Optional[str] = None
    text: str = ""
    payload: Optional[str] = None
    channel: Optional[str] = None


class MessageResponse(BaseModel):
    messages: List[Dict[str, Any]]
    next_state: str
    expected_input_type: str


@app.post("/message", response_model=MessageResponse)
async def post_message(req: MessageRequest) -> MessageResponse:
    """Handle user message: load session, run flow, return messages and state."""
    session = get_session(req.user_id)
    if not session:
        slot_defaults = _CONFIG.get("slot_defaults", {})
        session = create_session(req.user_id, slot_defaults)

    text = req.text or ""
    payload = req.payload

    _log = logging.getLogger(__name__)
    try:
        messages, next_state, expected_input_type = await run_flow_turn(
            session, text, payload, _DOMAIN
        )
    except Exception as e:
        _log.exception(
            "post_message failed: user_id=%s text=%s payload=%s: %s",
            req.user_id,
            text[:50] if text else "",
            payload,
            e,
        )
        raise HTTPException(status_code=500, detail=str(e))

    save_session(session)

    return MessageResponse(
        messages=messages,
        next_state=next_state,
        expected_input_type=expected_input_type,
    )


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# Combined ASGI app that serves both the FastAPI HTTP API and the Socket.IO bridge.
# To run both on a single port, point your ASGI server at `orchestrator.main:asgi`.
asgi = Starlette(
    routes=[
        Mount("/socket.io", app=socket_app),
        Mount("/", app=app),
    ]
)
