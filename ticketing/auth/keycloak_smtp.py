"""
Apply shared SMTP env to the Keycloak grm realm (officer invite / execute-actions).

Reads SMTP_* via backend.config.smtp_config — same mailbox as the Messaging API.
"""
from __future__ import annotations

from backend.config.smtp_config import missing_smtp_env_fields, resolve_smtp_config

SMTP_SETUP_HINT = (
    "Set SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM in env.local, "
    "then run: python -m ticketing.auth.keycloak_setup"
)

INVITE_EMAIL_FAILURE_HINT = (
    "Keycloak could not send the invite email. Verify SMTP_* settings "
    "(run python -m ticketing.auth.keycloak_setup), then check Keycloak logs."
)


def resolved_keycloak_smtp_config() -> dict[str, str] | None:
    """Build Keycloak realm smtpServer dict, or None if required settings are missing."""
    cfg = resolve_smtp_config()
    if not cfg:
        return None

    return {
        "host": cfg.host,
        "port": str(cfg.port),
        "from": cfg.from_addr,
        "fromDisplayName": cfg.from_display,
        "ssl": "false",
        "starttls": "true",
        "auth": "true",
        "user": cfg.username,
        "password": cfg.password,
    }
