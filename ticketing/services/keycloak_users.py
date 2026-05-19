"""Read-only Keycloak user lookups for admin roster display."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeycloakUserProfile:
    email: str
    display_name: str
    enabled: bool
    role_keys: tuple[str, ...] = ()
    organization_id: str = ""


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


def list_grm_officer_profiles() -> dict[str, KeycloakUserProfile]:
    """
    All enabled realm users with a grm_roles attribute (demo + invited officers).
    Keyed by email / username.
    """
    if not keycloak_configured():
        return {}
    try:
        admin = _admin()
        profiles: dict[str, KeycloakUserProfile] = {}
        for user in admin.get_users({}):
            attrs = user.get("attributes") or {}
            roles_raw = (attrs.get("grm_roles") or [""])[0]
            role_keys = tuple(r.strip() for r in roles_raw.split(",") if r.strip())
            if not role_keys:
                continue
            email = (user.get("email") or user.get("username") or "").strip().lower()
            if not email:
                continue
            first = (user.get("firstName") or "").strip()
            last = (user.get("lastName") or "").strip()
            display = f"{first} {last}".strip() or email.split("@", 1)[0]
            org = (attrs.get("organization_id") or [""])[0]
            profiles[email] = KeycloakUserProfile(
                email=email,
                display_name=display,
                enabled=bool(user.get("enabled", True)),
                role_keys=role_keys,
                organization_id=org,
            )
        return profiles
    except Exception as exc:
        logger.warning("Keycloak roster enrichment skipped: %s", exc)
        return {}


def profiles_for_user_ids(user_ids: list[str]) -> dict[str, KeycloakUserProfile]:
    """Subset lookup by email user_id."""
    if not user_ids:
        return {}
    all_profiles = list_grm_officer_profiles()
    wanted = {uid.lower() for uid in user_ids if "@" in uid}
    return {email: p for email, p in all_profiles.items() if email in wanted}
