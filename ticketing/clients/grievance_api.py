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


# ── Vault reveal session ──────────────────────────────────────────────────────

# TTL in seconds for reveal sessions by sensitivity class
_REVEAL_TTL: dict[str, int] = {
    "standard": 120,
    "seah": 60,
}


def begin_reveal_session(
    grievance_id: str,
    reason_code: str,
    reason_text: str = "",
    actor_id: str = "",
    case_sensitivity: str = "standard",
) -> dict[str, Any]:
    """
    Open a short-lived vault reveal session for a grievance.

    INTEGRATION POINT: backend/api/routers/grievances.py
        POST /api/grievance/{grievance_id}/reveal
        Request:  { reason_code, reason_text, client_context }
        Response: { granted, reveal_session_id, expires_at_utc,
                    content_token, watermark_text }
                  or { granted: false, deny_code }

    Proto fallback: calls GET /api/grievance/{id} (which already exists) and
    constructs a synthetic session.  Replace this block once the real reveal
    endpoint is implemented in backend/api/.
    """
    # ── PROTO FALLBACK ────────────────────────────────────────────────────────
    # Remove when POST /api/grievance/{id}/reveal is implemented.
    import uuid as _uuid
    from datetime import datetime, timezone, timedelta

    try:
        detail = get_grievance_detail(grievance_id)
    except Exception as exc:
        logger.warning("begin_reveal_session: backend unavailable — %s", exc)
        return {"granted": False, "deny_code": f"backend_unavailable: {exc}"}

    ttl = _REVEAL_TTL.get(case_sensitivity, 120)
    session_id = str(_uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    watermark_text = f"{actor_id} · {ts_str} · case:{grievance_id}"

    return {
        "granted": True,
        "reveal_session_id": session_id,
        "expires_at_utc": expires_at.isoformat(),
        "ttl_seconds": ttl,
        "content": detail,           # proto only — real API returns content_token
        "watermark_text": watermark_text,
        "_proto_mode": True,
    }
    # ── END PROTO FALLBACK ────────────────────────────────────────────────────


def close_reveal_session(
    grievance_id: str,
    reveal_session_id: str,
    close_reason: str = "user_closed",
) -> dict[str, Any]:
    """
    Close a vault reveal session.

    INTEGRATION POINT: backend/api/routers/grievances.py
        POST /api/grievance/{grievance_id}/reveal/close
        Request:  { reveal_session_id, close_reason }
        Response: { ok: true }

    Proto fallback: no-op (session was never opened on backend side).
    """
    # INTEGRATION POINT — wire to real endpoint when backend/api/ is ready
    logger.info(
        "reveal_close [proto no-op]: grievance=%s session=%s reason=%s",
        grievance_id, reveal_session_id, close_reason,
    )
    return {"ok": True, "_proto_mode": True}
