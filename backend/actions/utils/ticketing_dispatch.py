"""Fire-and-forget HTTP dispatch: chatbot action server → ticketing API.

Called after a grievance is successfully written to the DB.
Never raises — a ticketing failure must never block grievance submission.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

_TICKETING_API_URL = os.environ.get("TICKETING_API_URL", "http://ticketing_api:5002")
_TICKETING_SECRET_KEY = os.environ.get("TICKETING_SECRET_KEY", "")

_NOT_PROVIDED = "NOT_PROVIDED"


def _clean(val):
    """Return None for sentinel NOT_PROVIDED / empty strings so the ticketing API gets clean nulls."""
    if val is None or val == _NOT_PROVIDED or val == "":
        return None
    return val


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
            "✅ Ticketing dispatch OK: grievance_id=%s ticket_id=%s",
            grievance_id,
            ticket_id,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "⚠️ Ticketing dispatch failed (non-blocking): grievance_id=%s error=%s",
            grievance_id,
            exc,
        )
