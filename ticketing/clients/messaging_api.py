"""
HTTP client for the Backend Messaging API.

Used for:
  1. SMS fallback to complainant when chatbot session has expired.
  2. Quarterly report delivery by email to senior roles.

Base URL: ``settings.messaging_api_base_url`` (``MESSAGING_REMOTE_BASE_URL`` or ``backend_grievance_base_url``).

Auth: ``x-api-key`` = ``settings.messaging_api_key`` (must match ``MESSAGING_API_KEY_TICKETING`` on the API host).

Header: ``X-Messaging-Source: ticketing`` (required when messaging API auth keys are set).

INTEGRATION POINT: ``backend/api/routers/messaging.py``
  POST /api/messaging/send-sms   — provider via notify/backend
  POST /api/messaging/send-email
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)


def _headers(settings) -> dict[str, str]:
    h: dict[str, str] = {"X-Messaging-Source": "ticketing"}
    if settings.messaging_api_key:
        h["x-api-key"] = settings.messaging_api_key
    return h


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.messaging_api_base_url,
        headers=_headers(settings),
        timeout=15.0,
    )


def send_sms(
    phone_number: str,
    body: str,
    template_id: str | None = None,
    *,
    country_code: str | None = None,
    project_id: str | None = None,
) -> dict:
    """
    Send SMS via messaging API. Phone should include country code (e.g. +977…).

    Pass ``country_code`` / ``project_id`` so the messaging API can resolve
    ``ticketing.notification_routes`` (when enabled).
    """
    payload: dict[str, Any] = {"to": phone_number, "text": body}
    ctx: dict[str, Any] = {
        "source_system": "ticketing",
        "purpose": "sms_fallback",
    }
    if country_code:
        ctx["country_code"] = country_code.strip().upper()[:8]
    if project_id:
        ctx["project_id"] = project_id.strip()
    if template_id:
        ctx.setdefault("extra", {})["template_id"] = template_id
    if len(ctx) > 2 or template_id:
        payload["context"] = ctx

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
    *,
    country_code: str | None = None,
    project_id: str | None = None,
) -> dict:
    """
    Send email via messaging API. ``body`` is sent as HTML (``html_body`` in API).
    Attachments are not supported by the API in v1 — if passed, they are ignored.
    """
    ctx: dict[str, Any] = {
        "source_system": "ticketing",
        "purpose": "ticketing_email",
    }
    if country_code:
        ctx["country_code"] = country_code.strip().upper()[:8]
    if project_id:
        ctx["project_id"] = project_id.strip()
    payload: dict[str, Any] = {
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html_body": body,
        "context": ctx,
    }
    if attachments:
        logger.warning("messaging_api.send_email: attachments ignored (not supported in API v1)")

    with _client() as client:
        try:
            resp = client.post("/api/messaging/send-email", json=payload)
            resp.raise_for_status()
            logger.info("Email sent to %s", to)
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("Email delivery failed: %s", exc)
            raise
