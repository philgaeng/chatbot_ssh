"""
HTTP client for the Backend Messaging API.

Used for:
  1. SMS fallback to complainant when chatbot session has expired.
  2. Quarterly report delivery by email to senior roles.

Base URL: settings.backend_grievance_base_url
Auth:     x-api-key: TICKETING_SECRET_KEY (or MESSAGING_API_KEY fallback)

INTEGRATION POINT: backend/api/routers/messaging.py
  POST /api/messaging/send-sms   — DOIT gateway (Nepal) or AWS SNS fallback
  POST /api/messaging/send-email — SMTP mailbox relay
"""
from __future__ import annotations

import logging

import httpx

from ticketing.clients.backend_auth import service_integration_api_key
from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)


def _client() -> httpx.Client:
    settings = get_settings()
    headers: dict[str, str] = {}
    api_key = service_integration_api_key()
    if api_key:
        headers["x-api-key"] = api_key
    return httpx.Client(
        base_url=settings.backend_grievance_base_url,
        headers=headers,
        timeout=15.0,
    )


def send_sms(phone_number: str, body: str, template_id: str | None = None) -> dict:
    """
    Send SMS to complainant via AWS SNS through the backend Messaging API.

    Use this as fallback when session_id is expired / unavailable.
    Phone number must include country code (e.g. +977XXXXXXXXXX for Nepal).
    """
    payload: dict = {"to": phone_number, "text": body}
    if template_id:
        payload.setdefault("context", {})["template_id"] = template_id

    with _client() as client:
        try:
            resp = client.post("/api/messaging/send-sms", json=payload)
            resp.raise_for_status()
            logger.info("SMS sent to %s", phone_number[:7] + "***")
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("SMS delivery failed: %s", exc)
            raise


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    attachments: list[dict] | None = None,
) -> dict:
    """
    Send email through the backend Messaging API (SMTP by default).

    Used for quarterly report delivery, officer password reset, etc.
    """
    payload: dict = {
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html_body": body,
    }
    if attachments:
        payload.setdefault("context", {})["attachments"] = attachments

    with _client() as client:
        try:
            resp = client.post("/api/messaging/send-email", json=payload)
            resp.raise_for_status()
            logger.info("Email sent to %s", to)
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("Email delivery failed: %s", exc)
            raise
