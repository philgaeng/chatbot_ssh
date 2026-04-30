"""
Store for sensitive content detection results from the background Celery task.

The task writes here when it completes; the form/orchestrator reads on Submit details.
Keys: session_id (primary; from flask_session_id or sender_id) and optionally grievance_id.
Choice: in-memory dict for single-process deployment. For production with Celery workers
in a separate process, use Redis or a DB table keyed by session_id/grievance_id (see spec 14).
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# In-memory: (session_id or grievance_id) -> {detected, level, message, grievance_sensitive_issue, ...}
_store: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
# Optional TTL (seconds); None = no expiry. Not used in minimal implementation.
_RESULT_TTL_SEC = 300


def _key(session_id: Optional[str], grievance_id: Optional[str]) -> str:
    """Prefer grievance_id if available so one grievance has one result; else session_id."""
    if grievance_id:
        return f"g:{grievance_id}"
    if session_id:
        return f"s:{session_id}"
    return ""


def set_result(
    session_id: Optional[str],
    grievance_id: Optional[str],
    result: Dict[str, Any],
) -> None:
    """Persist detection result for later read by form/orchestrator."""
    key = _key(session_id, grievance_id)
    if not key:
        logger.warning("sensitive_detection_store.set_result: no session_id or grievance_id")
        return
    with _lock:
        _store[key] = dict(result)


def get_result(
    session_id: Optional[str],
    grievance_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Return latest stored result for this session/grievance, or None."""
    keys = []
    if grievance_id:
        keys.append(f"g:{grievance_id}")
    if session_id:
        keys.append(f"s:{session_id}")
    with _lock:
        for k in keys:
            if k in _store:
                return dict(_store[k])
    return None


def clear_result(session_id: Optional[str], grievance_id: Optional[str]) -> None:
    """Remove stored result (e.g. after form has consumed it)."""
    key = _key(session_id, grievance_id)
    with _lock:
        if key in _store:
            del _store[key]
