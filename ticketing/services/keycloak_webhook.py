"""
Parse Keycloak event payloads and resolve ticketing.user_id (email-style identity).

Supports common shapes from HTTP event-listener extensions and raw Keycloak event JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _keycloak_user_onboarding_complete(admin: Any, ticketing_user_id: str | None) -> bool:
    """True when Keycloak user is enabled with no pending required actions."""
    if admin is None or not ticketing_user_id:
        return False
    try:
        found = admin.get_users({"username": ticketing_user_id, "exact": True})
        if not found:
            found = admin.get_users({"email": ticketing_user_id, "exact": True})
        if not found:
            return False
        user = found[0]
        if not user.get("enabled", True):
            return False
        return not (user.get("requiredActions") or [])
    except Exception as exc:
        logger.warning("Could not read Keycloak user for %s: %s", ticketing_user_id, exc)
        return False


def should_activate_onboarding(
    payload: dict[str, Any],
    admin: Any = None,
    ticketing_user_id: str | None = None,
) -> bool:
    """Return True when onboarding is complete (password + profile/phone when required)."""
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
    if payload.get("error"):
        return False

    if t in ("LOGIN", "CODE_TO_TOKEN", "UPDATE_PROFILE", "UPDATE_PASSWORD"):
        return _keycloak_user_onboarding_complete(admin, ticketing_user_id)

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
