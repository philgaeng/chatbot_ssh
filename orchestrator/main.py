"""
Orchestrator FastAPI app: POST /message, GET /health.
"""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_RASA_DIR = _REPO_ROOT / "rasa_chatbot"
if str(_RASA_DIR) not in sys.path:
    sys.path.insert(0, str(_RASA_DIR))

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from orchestrator.session_store import get_session, save_session, create_session
from orchestrator.state_machine import run_flow_turn
from orchestrator.config_loader import load_config

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

    try:
        messages, next_state, expected_input_type = await run_flow_turn(
            session, text, payload, _DOMAIN
        )
    except Exception as e:
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
