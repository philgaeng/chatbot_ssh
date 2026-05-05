"""
Grievance / GRM paths send SMS and email through the same contract as external clients.

**Default delivery:** ``MESSAGING_GRIEVANCE_DELIVERY`` unset → **inprocess** (calls
``Messaging()`` directly — avoids single-worker uvicorn self-HTTP deadlock).

Set ``MESSAGING_GRIEVANCE_DELIVERY=http`` for production / split notify: POST to
``MESSAGING_REMOTE_BASE_URL`` with ``X-Messaging-Source: ticketing`` and
``MESSAGING_API_KEY_TICKETING`` (requires enough workers if URL points at same app).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


def _public_base_url() -> str:
    return (
        os.getenv("MESSAGING_REMOTE_BASE_URL", "").strip()
        or os.getenv("BACKEND_GRIEVANCE_BASE_URL", "http://127.0.0.1:5001").strip()
    ).rstrip("/")


def _ticketing_api_key() -> str:
    return (
        os.getenv("MESSAGING_API_KEY_TICKETING", "").strip()
        or os.getenv("MESSAGING_API_KEY", "").strip()
    )


def _use_inprocess() -> bool:
    v = os.getenv("MESSAGING_GRIEVANCE_DELIVERY", "inprocess").strip().lower()
    if v == "http":
        return False
    return True


def grievance_dispatch_send_sms(
    to: str,
    text: str,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    if _use_inprocess():
        from backend.services.messaging import Messaging

        return Messaging().send_sms(to, text)

    url = f"{_public_base_url()}/api/messaging/send-sms"
    body: Dict[str, Any] = {"to": to, "text": text}
    if context is not None:
        body["context"] = context
    return _post_json_ok(url, body)


def grievance_dispatch_send_email(
    to_emails: List[str],
    subject: str,
    html_body: str,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    if _use_inprocess():
        from backend.services.messaging import Messaging

        return Messaging().send_email(to_emails, subject, html_body)

    url = f"{_public_base_url()}/api/messaging/send-email"
    body: Dict[str, Any] = {
        "to": to_emails,
        "subject": subject,
        "html_body": html_body,
    }
    if context is not None:
        body["context"] = context
    return _post_json_ok(url, body)


def _post_json_ok(url: str, json_body: Dict[str, Any]) -> bool:
    headers = {"X-Messaging-Source": "ticketing"}
    key = _ticketing_api_key()
    if key:
        headers["x-api-key"] = key
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=json_body, headers=headers)
        if r.status_code >= 400:
            logger.error("Messaging HTTP %s %s: %s", r.status_code, url, r.text[:500])
            return False
        data = r.json()
        return (data or {}).get("status") == "SUCCESS"
    except Exception as e:
        logger.error("Messaging HTTP failed %s: %s", url, e)
        return False
