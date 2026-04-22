"""
HTTP client for the Backend Grievance API.

Used when an officer opens a ticket detail view — fetches fresh PII (name,
contact) that is NOT stored in ticketing.* per CLAUDE.md rules.

Base URL: settings.backend_grievance_base_url  (default http://localhost:5001)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)

# INTEGRATION POINT: backend/api/ — existing FastAPI endpoints
# GET  /api/grievance/{grievance_id}
# POST /api/grievance/{grievance_id}/status
# GET  /api/grievance/statuses


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.backend_grievance_base_url,
        timeout=10.0,
    )


def get_grievance_detail(grievance_id: str) -> dict[str, Any]:
    """
    Fetch full grievance detail from the backend, including PII fields
    (name, phone, email) decrypted server-side.

    Returns the raw JSON dict from GET /api/grievance/{grievance_id}.
    Raises httpx.HTTPError on failure — callers should handle gracefully.
    """
    with _client() as client:
        resp = client.get(f"/api/grievance/{grievance_id}")
        resp.raise_for_status()
        return resp.json()


def get_grievance_statuses() -> list[dict[str, Any]]:
    """Fetch list of grievance status codes from the backend."""
    with _client() as client:
        resp = client.get("/api/grievance/statuses")
        resp.raise_for_status()
        return resp.json()


def update_grievance_status(grievance_id: str, status: str, note: str = "") -> dict[str, Any]:
    """
    Update the grievance status on the backend (e.g. when ticket is resolved).

    INTEGRATION POINT: backend/api/routers/grievances.py
    POST /api/grievance/{grievance_id}/status
    """
    with _client() as client:
        resp = client.post(
            f"/api/grievance/{grievance_id}/status",
            json={"status": status, "note": note},
        )
        resp.raise_for_status()
        return resp.json()
