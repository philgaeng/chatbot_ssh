"""Fire-and-forget HTTP dispatch: chatbot action server → ticketing API.

Called after a grievance is successfully written to the DB.
Never raises — a ticketing failure must never block grievance submission.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Mapping, Optional

import requests
from rasa_sdk import Tracker

from backend.config.constants import CLASSIFICATION_DATA

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


def _load_grievance_cache_fields(grievance_id: str) -> dict:
    """Read summary/categories/location from DB when session slots are empty."""
    try:
        from backend.services.database_services.postgres_services import DatabaseManager
        import json as _json

        row = DatabaseManager().get_grievance_by_id(grievance_id) or {}
        cats = row.get("grievance_categories")
        if cats is not None and not isinstance(cats, str):
            cats = _json.dumps(cats)
        return {
            "grievance_summary": row.get("grievance_summary"),
            "grievance_categories": cats,
            "grievance_location": row.get("grievance_location"),
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "ticketing_dispatch: could not load grievance %s from DB: %s",
            grievance_id,
            exc,
        )
        return {}


def categories_high_priority(grievance_categories: Any) -> bool:
    """True when any selected category is marked high_priority in CLASSIFICATION_DATA."""
    categories = grievance_categories
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except (json.JSONDecodeError, TypeError):
            categories = [categories]
    if not isinstance(categories, list):
        return False
    for category in categories:
        if category in CLASSIFICATION_DATA:
            if CLASSIFICATION_DATA[category].get("high_priority", False):
                return True
    return False


_ACTIVE_INTAKE_ROUTES = frozenset({
    "new_grievance",
    "seah_intake",
    "road_hazard_grievance",
})

_INTAKE_ROUTE_ALIASES = {
    "grievance_new": "new_grievance",
    "standard_grievance": "new_grievance",
    "grievance_submission": "new_grievance",
    "seah": "seah_intake",
    "dust": "road_hazard_grievance",
    "dust_grievance": "road_hazard_grievance",
    "fast_track": "road_hazard_grievance",
    "road_hazard": "road_hazard_grievance",
}


def normalize_story_main_intake_route(story_main: Any) -> Optional[str]:
    """Map chatbot story_main slot to ticketing intake_route (canonical story_main values)."""
    if story_main is None:
        return None
    key = str(story_main).strip().lower()
    if not key:
        return None
    if key in _ACTIVE_INTAKE_ROUTES:
        return key
    return _INTAKE_ROUTE_ALIASES.get(key)


def dispatch_grievance_from_tracker(
    tracker: Tracker,
    grievance_data: Optional[Mapping[str, Any]] = None,
    *,
    log: Optional[logging.Logger] = None,
    organization_id: str = "DOR",
    grievance_id: Optional[str] = None,
    complainant_id: Optional[str] = None,
    is_seah: Optional[bool] = None,
    priority: Optional[str] = None,
) -> None:
    """
    Build POST /api/v1/tickets payload from tracker slots (+ optional grievance dict).

    Shared by BaseActionSubmit, road-hazard fast path, and other intake helpers.
    Never raises.
    """
    active_log = log or logger
    g = dict(grievance_data or {})

    gid = grievance_id or g.get("grievance_id") or tracker.get_slot("grievance_id")
    cid = complainant_id or g.get("complainant_id") or tracker.get_slot("complainant_id")
    sensitive = (
        is_seah
        if is_seah is not None
        else bool(
            g.get("grievance_sensitive_issue")
            or tracker.get_slot("grievance_sensitive_issue")
        )
    )
    categories = g.get("grievance_categories") or tracker.get_slot("grievance_categories")
    if priority is None:
        priority = "HIGH" if categories_high_priority(categories) else "NORMAL"
    if sensitive and priority != "HIGH":
        priority = "HIGH"

    package_id = tracker.get_slot("package_id")
    location_code = g.get("location_code") or tracker.get_slot("location_code")
    intake_route = normalize_story_main_intake_route(tracker.get_slot("story_main"))

    dispatch_ticket(
        grievance_id=gid,
        complainant_id=cid,
        session_id=tracker.sender_id,
        is_seah=sensitive,
        priority=priority,
        location_code=location_code,
        project_code=tracker.get_slot("project_code") or "KL_ROAD",
        grievance_summary=g.get("grievance_summary") or tracker.get_slot("grievance_summary"),
        grievance_categories=categories,
        grievance_location=g.get("grievance_location") or tracker.get_slot("grievance_location"),
        organization_id=organization_id,
        package_id=package_id,
        intake_route=intake_route,
    )
    active_log.info(
        "ticketing dispatch queued: grievance_id=%s intake_route=%s package_id=%s location_code=%s",
        gid,
        intake_route,
        package_id,
        location_code,
    )


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
    intake_route: str | None = None,
) -> None:
    """POST to /api/v1/tickets.  Never raises; logs warning on failure."""
    if not _clean(grievance_summary) and grievance_categories in (None, "", []):
        cached = _load_grievance_cache_fields(grievance_id)
        if not _clean(grievance_summary):
            grievance_summary = cached.get("grievance_summary")
        if grievance_categories in (None, "", []):
            grievance_categories = cached.get("grievance_categories")
        if not _clean(grievance_location):
            grievance_location = cached.get("grievance_location")

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
    if intake_route:
        payload["intake_route"] = intake_route

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
