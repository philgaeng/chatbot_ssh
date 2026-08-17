# SPDX-License-Identifier: Apache-2.0

"""In-process TTL cache for the per-request officer onboarding-status sync (H2-05).

``get_current_user`` calls ``sync_officer_onboarding_status`` on every authenticated request
(``dependencies.py``). For an already-active officer that is one ``officer_onboarding`` read;
for a not-yet-active / legacy officer it is a **Keycloak admin round-trip** and a possible
write on *every* call — 10–30% of p50 latency per the backend review.

This throttles the sync to at most once per ``TICKETING_AUTH_SYNC_TTL_SECONDS`` (default 300,
``0`` disables) per officer, per worker process. The sync is idempotent, so per-worker
duplication under multiple uvicorn workers is fine — no shared store (Redis) needed. Any
onboarding-status write invalidates the officer's entry, so an invite/activation takes effect
on that officer's very next request rather than after a TTL wait.

Keying: the officer's normalized id (``email.strip().lower()``), matching
``officer_admin._normalize_officer_email`` so the dependency's lookup and the writers'
invalidation land on the same key.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

_lock = threading.Lock()
# key (normalized officer id) -> monotonic timestamp of the last completed sync
_last_synced: dict[str, float] = {}

_DEFAULT_TTL_SECONDS = 300


def _now() -> float:
    """Monotonic clock (patchable in tests; monotonic avoids wall-clock jumps)."""
    return time.monotonic()


def _ttl_seconds() -> int:
    """TTL from settings, env-overridable without busting the lru_cached settings object."""
    try:
        from ticketing.config.settings import get_settings

        configured = get_settings().ticketing_auth_sync_ttl_seconds
    except Exception:
        configured = _DEFAULT_TTL_SECONDS
    raw = os.getenv("TICKETING_AUTH_SYNC_TTL_SECONDS", str(configured))
    try:
        return max(0, int(raw))
    except ValueError:
        return max(0, int(configured))


def _key(user_id: str) -> str:
    return (user_id or "").strip().lower()


def is_fresh(user_id: str, *, now: Optional[float] = None) -> bool:
    """True when this officer was synced within the TTL → the caller may skip the sync.

    Always False when the TTL is 0 (caching disabled) or the id is empty, so the sync runs
    exactly as it does today.
    """
    ttl = _ttl_seconds()
    if ttl <= 0:
        return False
    key = _key(user_id)
    if not key:
        return False
    ref = _now() if now is None else now
    with _lock:
        ts = _last_synced.get(key)
    return ts is not None and (ref - ts) < ttl


def mark_synced(user_id: str, *, now: Optional[float] = None) -> None:
    """Stamp an officer as synced-now (called after a successful sync run)."""
    key = _key(user_id)
    if not key:
        return
    ref = _now() if now is None else now
    with _lock:
        _last_synced[key] = ref


def invalidate(user_id: str) -> None:
    """Drop an officer's entry so their next request re-syncs immediately."""
    key = _key(user_id)
    if not key:
        return
    with _lock:
        _last_synced.pop(key, None)


def clear() -> None:
    """Reset the whole cache (test hook / ops reset)."""
    with _lock:
        _last_synced.clear()
