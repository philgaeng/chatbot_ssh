"""
HTTP client for the Backend Messaging API.

Used for:
  1. SMS fallback to complainant when chatbot session has expired.
  2. Quarterly report delivery by email to senior roles.

Base URL: settings.backend_grievance_base_url
Auth:     x-api-key: settings.messaging_api_key

INTEGRATION POINT: backend/api/routers/messaging.py
  POST /api/messaging/send-sms   — AWS SNS, works internationally
  POST /api/messaging/send-email — AWS SES
"""
from __future__ import annotations

import logging

import httpx

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.backend_grievance_base_url,
        headers={"x-api-key": settings.messaging_api_key},
        timeout=15.0,
    )


def send_sms(phone_number: str, body: str, template_id: str | None = None) -> dict:
    """
    Send SMS to complainant via AWS SNS through the backend Messaging API.

    Use this as fallback when session_id is expired / unavailable.
    Phone number must include country code (e.g. +977XXXXXXXXXX for Nepal).
    """
    payload: dict = {"recipient": phone_number, "body": body}
    if template_id:
        payload["template_id"] = template_id

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
    Send email via AWS SES through the backend Messaging API.

    Used for quarterly report delivery to senior roles.
    """
    payload: dict = {
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "body": body,
    }
    if attachments:
        payload["attachments"] = attachments

    with _client() as client:
        try:
            resp = client.post("/api/messaging/send-email", json=payload)
            resp.raise_for_status()
            logger.info("Email sent to %s", to)
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("Email delivery failed: %s", exc)
            raise
