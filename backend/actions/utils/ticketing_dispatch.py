"""Fire-and-forget HTTP dispatch: chatbot action server → ticketing API.

Called after a grievance is successfully written to the DB.
Never raises — a ticketing failure must never block grievance submission.
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TICKETING_API_URL = os.environ.get("TICKETING_API_URL", "http://ticketing_api:5002")
_TICKETING_SECRET_KEY = os.environ.get("TICKETING_SECRET_KEY", "")

_NOT_PROVIDED = "NOT_PROVIDED"
_SCAN_TIMEOUT_SECONDS = float(os.environ.get("TICKETING_SCAN_TIMEOUT", "3"))


def _clean(val):
    """Return None for sentinel NOT_PROVIDED / empty strings so the ticketing API gets clean nulls."""
    if val is None or val == _NOT_PROVIDED or val == "":
        return None
    return val


def fetch_qr_scan(token: str) -> Optional[dict]:
    """Resolve a QR token via GET /api/v1/scan/{token}.

    Returns the parsed JSON dict on 200 (with keys: project_code, package_id,
    location_code, label) or None when the token is missing/invalid/revoked or
    the lookup fails. Never raises — callers must fall back to asking the user
    for geography as today.
    """
    if not token or not isinstance(token, str):
        return None

    cleaned = token.strip()
    if not cleaned or len(cleaned) > 64:
        return None

    url = f"{_TICKETING_API_URL}/api/v1/scan/{cleaned}"
    try:
        resp = requests.get(url, timeout=_SCAN_TIMEOUT_SECONDS)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "⚠️ QR scan call failed (non-blocking): token=%s error=%s",
            cleaned,
            exc,
        )
        return None

    if resp.status_code in (404, 410):
        logger.info("QR scan token rejected: token=%s status=%s", cleaned, resp.status_code)
        return None

    if resp.status_code != 200:
        logger.warning(
            "⚠️ QR scan returned unexpected status: token=%s status=%s body=%s",
            cleaned,
            resp.status_code,
            resp.text[:200],
        )
        return None

    try:
        data = resp.json()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("⚠️ QR scan returned non-JSON body: token=%s error=%s", cleaned, exc)
        return None

    if not isinstance(data, dict):
        return None

    return {
        "project_code": _clean(data.get("project_code")),
        "package_id": _clean(data.get("package_id")),
        "location_code": _clean(data.get("location_code")),
        "label": _clean(data.get("label")),
    }


def dispatch_ticket(
    grievance_id: str,
    complainant_id: str | None,
    session_id: str | None,
    is_seah: bool,
    priority: str,
    location_code: str | None,
    project_code: str,
    grievance_summary: str | None,
    grievance_categories=None,
    grievance_location: str | None = None,
    organization_id: str = "DOR",
    package_id: str | None = None,
) -> None:
    """POST to /api/v1/tickets.  Never raises; logs warning on failure."""
    # Normalise categories: ticketing API expects a JSON string or None
    cats = _clean(grievance_categories)
    if cats is not None and not isinstance(cats, str):
        import json as _json
        cats = _json.dumps(cats)

    payload = {
        "grievance_id": grievance_id,
        "complainant_id": _clean(complainant_id),
        "session_id": _clean(session_id),
        "chatbot_id": "nepal_grievance_bot",
        "country_code": "NP",
        "organization_id": organization_id,
        "location_code": _clean(location_code),
        "project_code": project_code,
        "priority": priority,
        "is_seah": is_seah,
        "grievance_summary": _clean(grievance_summary),
        "grievance_categories": cats,
        "grievance_location": _clean(grievance_location),
        "package_id": _clean(package_id),
    }

    url = f"{_TICKETING_API_URL}/api/v1/tickets"
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "x-api-key": _TICKETING_SECRET_KEY,
                "Content-Type": "application/json",
            },
            timeout=5,
        )
        resp.raise_for_status()
        ticket_id = resp.json().get("ticket_id", "?")
        logger.info(
            "✅ Ticketing dispatch OK: grievance_id=%s ticket_id=%s package_id=%s",
            grievance_id,
            ticket_id,
            payload["package_id"],
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "⚠️ Ticketing dispatch failed (non-blocking): grievance_id=%s error=%s",
            grievance_id,
            exc,
        )
