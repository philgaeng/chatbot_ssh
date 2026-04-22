"""
HTTP client for the Chatbot Orchestrator.

Used when an officer replies to a complainant — delivers the message
into the active chatbot conversation identified by session_id.

Base URL: settings.orchestrator_base_url  (default http://localhost:8000)

INTEGRATION POINT: backend/orchestrator/main.py
  POST /message
  Body: { user_id: session_id, text: str, channel: "ticketing" }
"""
from __future__ import annotations

import logging
import uuid

import httpx

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.orchestrator_base_url,
        timeout=15.0,
    )


def send_message_to_complainant(
    session_id: str,
    text: str,
    chatbot_id: str = "nepal_grievance_bot",
) -> dict:
    """
    Push an officer message into the complainant's active chatbot conversation.

    Uses session_id stored on the ticket as user_id — this routes
    the message to the correct conversation in the orchestrator.

    Raises httpx.HTTPError if the orchestrator is unreachable; callers
    should catch this and fall back to SMS via messaging_api.send_sms().
    """
    payload = {
        "user_id": session_id,
        "message_id": str(uuid.uuid4()),
        "text": text,
        "channel": "ticketing",
        "chatbot_id": chatbot_id,
    }
    with _client() as client:
        resp = client.post("/message", json=payload)
        resp.raise_for_status()
        logger.info(
            "Message delivered via orchestrator: session_id=%s chars=%d",
            session_id[:12] + "...",
            len(text),
        )
        return resp.json()
