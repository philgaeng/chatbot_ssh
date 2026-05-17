"""
HTTP client for the Backend Messaging API (POST /api/messaging/send-sms, send-email).

Callers (chatbot actions, Celery tasks) use this instead of importing
backend.services.messaging.Messaging directly — delivery stays behind one API.

See docs/ticketing_system/09_messaging_api_spec.md and backend/api/routers/messaging.py.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from backend.config.constants import BACKEND_HTTP_URL

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return BACKEND_HTTP_URL.rstrip("/")


def _headers() -> dict[str, str]:
    key = (os.getenv("MESSAGING_API_KEY") or os.getenv("TICKETING_SECRET_KEY") or "").strip()
    if key:
        return {"x-api-key": key}
    return {}


def send_sms(
    to: str,
    text: str,
    *,
    context: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"to": to, "text": text}
    if context:
        payload["context"] = context

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{_base_url()}/api/messaging/send-sms",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "SUCCESS":
            raise RuntimeError(data.get("error") or "SMS delivery failed")
        return data


def send_email(
    to: str | list[str],
    subject: str,
    html_body: str,
    *,
    context: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    recipients = [to] if isinstance(to, str) else list(to)
    payload: dict[str, Any] = {
        "to": recipients,
        "subject": subject,
        "html_body": html_body,
    }
    if context:
        payload["context"] = context

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{_base_url()}/api/messaging/send-email",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "SUCCESS":
            raise RuntimeError(data.get("error") or "Email delivery failed")
        logger.info("Messaging API email sent to %s", recipients)
        return data
