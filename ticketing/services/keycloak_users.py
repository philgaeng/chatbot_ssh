# SPDX-License-Identifier: Apache-2.0

"""Read-only Keycloak user lookups for admin roster display."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeycloakUserProfile:
    email: str
    display_name: str
    enabled: bool
    role_keys: tuple[str, ...] = ()
    organization_id: str = ""
    phone_number: str = ""


@dataclass(frozen=True)
class _KcSnapshot:
    """One realm scan → everything the roster needs, so nothing is fetched per-officer."""
    profiles: dict[str, KeycloakUserProfile] = field(default_factory=dict)  # grm_roles-bearing
    onboarding_pending: dict[str, bool] = field(default_factory=dict)       # ALL users by email


# The roster used to hit Keycloak once per officer — _keycloak_find_user (with a fresh admin
# re-auth) for every row's Invited/Active badge, plus another per-officer call in the
# invited→active sync loop. On a large realm that's dozens of round trips per page load → 30s+.
# This snapshot fetches the whole realm ONCE (get_users), derives both the display profiles and a
# bulk {email: setup-pending} map, and caches it. Mutations (invite / remove) call
# invalidate_officer_profiles_cache().
_SNAPSHOT_TTL_SECONDS = 30.0
_SNAPSHOT_LOCK = threading.Lock()
_snapshot_cache: _KcSnapshot | None = None
_snapshot_cached_at = 0.0


def keycloak_configured() -> bool:
    return bool(get_settings().keycloak_admin_url)


def _admin():
    from keycloak import KeycloakAdmin, KeycloakOpenIDConnection

    settings = get_settings()
    conn = KeycloakOpenIDConnection(
        server_url=settings.keycloak_admin_url.rstrip("/") + "/",
        username="admin",
        password=settings.keycloak_admin_password,
        realm_name="grm",
        user_realm_name="master",
        verify=True,
    )
    return KeycloakAdmin(connection=conn)


def _fetch_snapshot() -> _KcSnapshot:
    """One get_users scan → profiles (grm_roles-bearing) + onboarding-pending for every user.

    Pending mirrors officer_invite_setup_pending's Keycloak branch exactly: not-enabled OR any
    requiredActions OR email not verified. A user absent from this map is treated as pending by
    callers (parity with _keycloak_find_user returning None)."""
    admin = _admin()
    profiles: dict[str, KeycloakUserProfile] = {}
    pending: dict[str, bool] = {}
    for user in admin.get_users({}):
        email = (user.get("email") or user.get("username") or "").strip().lower()
        if not email:
            continue
        enabled = bool(user.get("enabled", True))
        required = bool(user.get("requiredActions") or [])
        email_verified = bool(user.get("emailVerified", False))
        pending[email] = (not enabled) or required or (not email_verified)
        if not enabled:
            continue
        attrs = user.get("attributes") or {}
        roles_raw = (attrs.get("grm_roles") or [""])[0]
        role_keys = tuple(r.strip() for r in roles_raw.split(",") if r.strip())
        if not role_keys:
            continue  # role-free invitees show via officer_positions (DB), not the profile map
        first = (user.get("firstName") or "").strip()
        last = (user.get("lastName") or "").strip()
        display = f"{first} {last}".strip() or email.split("@", 1)[0]
        org = (attrs.get("organization_id") or [""])[0]
        phone = (attrs.get("phone_number") or [""])[0].strip()
        profiles[email] = KeycloakUserProfile(
            email=email,
            display_name=display,
            enabled=enabled,
            role_keys=role_keys,
            organization_id=org,
            phone_number=phone,
        )
    return _KcSnapshot(profiles=profiles, onboarding_pending=pending)


def _get_snapshot(*, force: bool = False) -> _KcSnapshot | None:
    """Cached realm snapshot, or None when Keycloak isn't configured (bypass builds)."""
    global _snapshot_cache, _snapshot_cached_at
    if not keycloak_configured():
        return None

    cached = _snapshot_cache
    if not force and cached is not None and (time.monotonic() - _snapshot_cached_at) < _SNAPSHOT_TTL_SECONDS:
        return cached
    try:
        snap = _fetch_snapshot()
        with _SNAPSHOT_LOCK:
            _snapshot_cache = snap
            _snapshot_cached_at = time.monotonic()
        return snap
    except Exception as exc:
        logger.warning("Keycloak roster enrichment skipped: %s", exc)
        return cached  # serve a stale snapshot on a transient Keycloak error (may be None)


def invalidate_officer_profiles_cache() -> None:
    """Drop the cached realm snapshot so the next read re-fetches. Call after any officer
    mutation (invite / assign position / remove) so a change shows immediately."""
    global _snapshot_cache, _snapshot_cached_at
    with _SNAPSHOT_LOCK:
        _snapshot_cache = None
        _snapshot_cached_at = 0.0


def list_grm_officer_profiles(*, force: bool = False) -> dict[str, KeycloakUserProfile]:
    """
    All enabled realm users with a grm_roles attribute (demo + invited officers).
    Keyed by email / username. Backed by the cached realm snapshot.
    """
    snap = _get_snapshot(force=force)
    return snap.profiles if snap else {}


def keycloak_onboarding_pending_map(*, force: bool = False) -> dict[str, bool]:
    """Bulk {email: setup-pending} for the whole realm — one Keycloak call, cached. Lets the
    roster resolve every Invited/Active badge without a per-officer lookup (kills the N+1).
    Empty when Keycloak isn't configured (callers then fall back to the DB onboarding row)."""
    snap = _get_snapshot(force=force)
    return snap.onboarding_pending if snap else {}


def profiles_for_user_ids(user_ids: list[str]) -> dict[str, KeycloakUserProfile]:
    """Subset lookup by email user_id."""
    if not user_ids:
        return {}
    all_profiles = list_grm_officer_profiles()
    wanted = {uid.lower() for uid in user_ids if "@" in uid}
    return {email: p for email, p in all_profiles.items() if email in wanted}
