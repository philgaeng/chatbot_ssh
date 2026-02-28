"""
Socket.IO bridge between channels/webchat and the orchestrator state machine.

Receives `complainant_uttered` events from the webchat client, calls
`run_flow_turn`, and emits `bot_uttered` events that are compatible with
existing webchat handlers.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import socketio
import yaml

from orchestrator.session_store import get_session, save_session, create_session
from orchestrator.state_machine import run_flow_turn
from orchestrator.config_loader import load_config

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_RASA_DIR = _REPO_ROOT / "rasa_chatbot"
if str(_RASA_DIR) not in sys.path:
    sys.path.insert(0, str(_RASA_DIR))


def _load_domain() -> Dict[str, Any]:
    """Load Rasa domain.yml as dict (mirrors orchestrator.main._load_domain)."""
    path = _REPO_ROOT / "rasa_chatbot" / "domain.yml"
    if not path.exists():
        return {"slots": {}}
    with open(path) as f:
        return yaml.safe_load(f) or {}


_CONFIG: Dict[str, Any] = {}
_DOMAIN: Dict[str, Any] = {}


def init_bridge() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Initialize bridge config and domain.

    This is idempotent and safe to call multiple times.
    """
    global _CONFIG, _DOMAIN
    if not _CONFIG:
        _CONFIG = load_config()
    if not _DOMAIN:
        _DOMAIN = _load_domain()
    return _CONFIG, _DOMAIN


# Async Socket.IO server and ASGI app
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio)


def _map_message_to_text_payload(message: str) -> Tuple[str, Optional[str]]:
    """
    Map incoming `message` string to (text, payload) for run_flow_turn.

    - If message starts with "/": treat as payload (slash command).
    - Else: treat as free-text user input.
    """
    message = message or ""
    if message.startswith("/"):
        return "", message
    return message, None


def _normalise_outgoing_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise orchestrator message dict into webchat-compatible bot_uttered payload.

    Expected keys from dispatcher messages:
      - "text": optional string
      - "buttons": optional list
      - "json_message" or "custom": optional dict
    """
    out: Dict[str, Any] = {}
    if "text" in raw and raw["text"] is not None:
        out["text"] = raw["text"]
    if "buttons" in raw and raw["buttons"]:
        out["buttons"] = raw["buttons"]
    # Support both `json_message` (Rasa style) and `custom`
    custom = raw.get("json_message") or raw.get("custom")
    if custom:
        out["custom"] = custom
    return out


@sio.event
async def connect(sid, environ, auth):
    # Allow all connections for now; auth can be added later if needed.
    await sio.save_session(sid, {"session_id": None})


@sio.event
async def disconnect(sid):
    # No per-connection state to clean up beyond what Socket.IO handles.
    pass


@sio.event
async def complainant_uttered(sid, data: Dict[str, Any]):
    """
    Handle inbound complainant_uttered from webchat.

    Expected payload:
        {
          "message": "string",
          "session_id": "string",
          "metadata": { ... }  # optional
        }
    """
    init_bridge()

    message = (data or {}).get("message", "") or ""
    session_id = (data or {}).get("session_id") or sid

    text, payload = _map_message_to_text_payload(message)

    session = get_session(session_id)
    if not session:
        slot_defaults = _CONFIG.get("slot_defaults", {})
        session = create_session(session_id, slot_defaults)

    try:
        messages, next_state, expected_input_type = await run_flow_turn(
        session=session,
        text=text,
        payload=payload,
        domain=_DOMAIN,
        )
    except Exception as e:
        error_payload = {"text": "Sorry, something went wrong.", "custom": {"error": str(e)}}
        await sio.emit("bot_uttered", error_payload, to=sid)
        return

    save_session(session)

    for m in messages:
        out = _normalise_outgoing_message(m)
        if not out:
            continue
        await sio.emit("bot_uttered", out, to=sid)


# Convenience alias so this module can be run directly by an ASGI server:
#   uvicorn orchestrator.socket_server:socket_app --port 8002
app = socket_app

