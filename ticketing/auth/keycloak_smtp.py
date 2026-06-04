"""
Keycloak realm SMTP for officer invite / execute-actions emails.

Uses a standard mailbox (local provider in Nepal production, e.g. Infomaniak on staging).
Not AWS SES — complainant and report email stay on the Messaging API.
"""
from __future__ import annotations

import os

from ticketing.config.settings import get_settings

SMTP_SETUP_HINT = (
    "Set KEYCLOAK_SMTP_HOST, KEYCLOAK_SMTP_USER, KEYCLOAK_SMTP_PASSWORD, and "
    "KEYCLOAK_SMTP_FROM in env.local, then run: python -m ticketing.auth.keycloak_setup"
)

INVITE_EMAIL_FAILURE_HINT = (
    "Keycloak could not send the invite email. Verify KEYCLOAK_SMTP_* and realm SMTP "
    "(run python -m ticketing.auth.keycloak_setup), then check Keycloak logs."
)


def missing_smtp_env_fields() -> list[str]:
    """Env vars required before keycloak_setup can configure realm SMTP."""
    fields: list[str] = []
    settings = get_settings()
    if not (settings.keycloak_smtp_host or os.getenv("KEYCLOAK_SMTP_HOST", "")).strip():
        fields.append("KEYCLOAK_SMTP_HOST")
    if not (settings.keycloak_smtp_user or os.getenv("KEYCLOAK_SMTP_USER", "")).strip():
        fields.append("KEYCLOAK_SMTP_USER")
    if not (settings.keycloak_smtp_password or os.getenv("KEYCLOAK_SMTP_PASSWORD", "")).strip():
        fields.append("KEYCLOAK_SMTP_PASSWORD")
    if not (settings.keycloak_smtp_from or os.getenv("KEYCLOAK_SMTP_FROM", "")).strip():
        fields.append("KEYCLOAK_SMTP_FROM")
    return fields


def resolved_keycloak_smtp_config() -> dict[str, str] | None:
    """Build Keycloak realm smtpServer dict, or None if required settings are missing."""
    settings = get_settings()

    host = (settings.keycloak_smtp_host or os.getenv("KEYCLOAK_SMTP_HOST") or "").strip()
    port = str(
        settings.keycloak_smtp_port or os.getenv("KEYCLOAK_SMTP_PORT") or "587"
    ).strip()
    from_addr = (settings.keycloak_smtp_from or os.getenv("KEYCLOAK_SMTP_FROM") or "").strip()
    display = (settings.keycloak_smtp_from_display or "GRM Ticketing").strip()
    user = (settings.keycloak_smtp_user or os.getenv("KEYCLOAK_SMTP_USER") or "").strip()
    password = (
        settings.keycloak_smtp_password or os.getenv("KEYCLOAK_SMTP_PASSWORD") or ""
    ).strip()

    if not host or not from_addr or not user or not password:
        return None

    return {
        "host": host,
        "port": port,
        "from": from_addr,
        "fromDisplayName": display,
        "ssl": "false",
        "starttls": "true",
        "auth": "true",
        "user": user,
        "password": password,
    }
