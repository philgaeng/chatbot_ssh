"""
HTTP client for chatbot / workers when messaging runs on a separate host.

Set:
  MESSAGING_USE_REMOTE_API=true
  MESSAGING_REMOTE_BASE_URL=http://backend-host:5001   # optional; falls back to BACKEND_GRIEVANCE_BASE_URL
  MESSAGING_API_KEY_CHATBOT=<same secret as backend expects for chatbot>

Always sends X-Messaging-Source: chatbot so the messaging API can audit callers.
"""

from __future__ import annotations

import logging
import os
from typing import List

import httpx

from backend.services.messaging_providers import format_phone_number_ph

logger = logging.getLogger(__name__)


class RemoteMessagingAPI:
    """Same surface as Messaging for actions / Celery — calls POST /api/messaging/*."""

    def __init__(self) -> None:
        self.base_url = (
            os.getenv("MESSAGING_REMOTE_BASE_URL", "").strip()
            or os.getenv("BACKEND_GRIEVANCE_BASE_URL", "http://localhost:5001").strip()
        ).rstrip("/")
        self.api_key = os.getenv("MESSAGING_API_KEY_CHATBOT", "").strip()
        if not self.api_key:
            logger.warning(
                "MESSAGING_API_KEY_CHATBOT is empty; remote messaging API calls will fail auth"
            )
        self._source = "chatbot"
        self.logger = logging.getLogger(__name__)

    def send_sms(self, phone_number: str, message: str) -> bool:
        url = f"{self.base_url}/api/messaging/send-sms"
        payload = {
            "to": phone_number,
            "text": message,
            "context": {"source_system": self._source},
        }
        return self._post_ok(url, payload)

    def send_email(self, to_emails: List[str], subject: str, body: str) -> bool:
        url = f"{self.base_url}/api/messaging/send-email"
        payload = {
            "to": to_emails,
            "subject": subject,
            "html_body": body,
            "context": {"source_system": self._source},
        }
        return self._post_ok(url, payload)

    def test_sms_connection(self, test_phone_number: str) -> bool:
        return self.send_sms(
            test_phone_number,
            "This is a test message from your chatbot.",
        )

    def format_phone_number(self, phone_number: str) -> str:
        return format_phone_number_ph(phone_number)

    def _post_ok(self, url: str, json_body: dict) -> bool:
        headers = {
            "X-Messaging-Source": self._source,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(url, json=json_body, headers=headers)
            if r.status_code >= 400:
                self.logger.error(
                    "Messaging API error %s %s: %s",
                    r.status_code,
                    url,
                    r.text[:500],
                )
                return False
            data = r.json()
            return (data or {}).get("status") == "SUCCESS"
        except Exception as e:
            self.logger.error("Messaging API request failed %s: %s", url, e)
            return False
