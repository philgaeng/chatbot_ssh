"""
Alerting for the ops monitor — deduped email via the Messaging API (HTTP).

Dedup is in-process (per scheduler lifetime) keyed by a signature, so a flapping
disk doesn't flood the inbox. Sending failures never propagate — a monitor must
not crash because alerting is down.
"""
from __future__ import annotations

import logging
import time
from typing import Dict

import httpx

from ops.config import get_settings

logger = logging.getLogger("ops.alerts")

_last_sent: Dict[str, float] = {}


def _api_key(settings) -> str:
    return settings.messaging_api_key or settings.ticketing_secret_key


def send_alert(signature: str, subject: str, body_html: str) -> bool:
    """
    Send a deduped alert email. `signature` controls dedup (e.g. 'disk_check:critical').
    Returns True if an email was dispatched, False if suppressed/failed.
    """
    settings = get_settings()
    now = time.monotonic()
    last = _last_sent.get(signature)
    if last is not None and (now - last) < settings.alert_dedup_seconds:
        logger.info("Alert suppressed (dedup): %s", signature)
        return False

    recipient = settings.health_alert_email or settings.daily_report_email
    if not recipient:
        logger.warning("No HEALTH_ALERT_EMAIL configured; alert '%s' not sent", signature)
        return False

    payload = {
        "to": [recipient],
        "subject": f"[GRM ops] {subject}",
        "html_body": body_html,
        "context": {"source_system": "ops", "purpose": "health_alert"},
    }
    headers = {}
    key = _api_key(settings)
    if key:
        headers["x-api-key"] = key

    try:
        with httpx.Client(base_url=settings.messaging_api_url, timeout=15.0) as client:
            resp = client.post("/api/messaging/send-email", json=payload, headers=headers)
            resp.raise_for_status()
        _last_sent[signature] = now
        logger.info("Alert sent: %s", signature)
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Alert send failed for %s: %s", signature, exc)
        return False


def send_report(subject: str, body_html: str, attachments: list[dict] | None = None) -> bool:
    """Send the daily ops report (not deduped). Returns True on success."""
    settings = get_settings()
    recipient = settings.daily_report_email or settings.health_alert_email
    if not recipient:
        logger.warning("No DAILY_REPORT_EMAIL configured; report not sent")
        return False
    payload: dict = {
        "to": [recipient],
        "subject": subject,
        "html_body": body_html,
        "context": {"source_system": "ops", "purpose": "daily_report"},
    }
    if attachments:
        payload["context"]["attachments"] = attachments
    headers = {}
    key = _api_key(settings)
    if key:
        headers["x-api-key"] = key
    try:
        with httpx.Client(base_url=settings.messaging_api_url, timeout=30.0) as client:
            resp = client.post("/api/messaging/send-email", json=payload, headers=headers)
            resp.raise_for_status()
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Daily report send failed: %s", exc)
        return False
