"""
Parse Keycloak event payloads and resolve ticketing.user_id (email-style identity).

Supports common shapes from HTTP event-listener extensions and raw Keycloak event JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def should_activate_onboarding(payload: dict[str, Any]) -> bool:
    """Return True when the event indicates mandatory onboarding (password) completed."""
    if payload.get("mark_active") is True:
        return True
    if payload.get("ignored") is True:
        return False

    t = (
        payload.get("type")
        or payload.get("eventType")
        or payload.get("event_type")
        or ""
    )
    t = str(t).upper()
    if t == "UPDATE_PASSWORD" and not payload.get("error"):
        return True
    # VERIFY_EMAIL etc. — not used for password-first flow
    return False


def resolve_ticketing_user_id(payload: dict[str, Any], admin: Any) -> Optional[str]:
    """
    Map payload to ticketing user_id (typically email used as username).

    If only Keycloak UUID is present, requires KeycloakAdmin.get_user(uid).
    """
    for key in ("ticketing_user_id", "email"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()

    for key in ("username", "userName"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()

    details = payload.get("details")
    if isinstance(details, dict):
        for key in ("username", "email"):
            v = details.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

    rep = payload.get("representation")
    if isinstance(rep, str):
        try:
            rep = json.loads(rep)
        except json.JSONDecodeError:
            rep = None
    if isinstance(rep, dict):
        v = rep.get("email") or rep.get("username")
        if isinstance(v, str) and v.strip():
            return v.strip()

    uid = payload.get("userId") or payload.get("user_id")
    if isinstance(uid, str) and uid.strip():
        if admin is None:
            logger.warning("Keycloak event has userId=%s but admin client unavailable", uid)
            return None
        try:
            u = admin.get_user(uid)
            out = (u.get("email") or u.get("username") or "").strip()
            return out or None
        except Exception as exc:
            logger.warning("Keycloak get_user failed for %s: %s", uid, exc)
            return None

    return None


def keycloak_admin_from_settings():
    """Return KeycloakAdmin or None if not configured."""
    from ticketing.config.settings import get_settings

    settings = get_settings()
    if not settings.keycloak_admin_url:
        return None
    from keycloak import KeycloakAdmin, KeycloakOpenIDConnection

    conn = KeycloakOpenIDConnection(
        server_url=settings.keycloak_admin_url.rstrip("/") + "/",
        username="admin",
        password=settings.keycloak_admin_password,
        realm_name="grm",
        user_realm_name="master",
        verify=True,
    )
    return KeycloakAdmin(connection=conn)
