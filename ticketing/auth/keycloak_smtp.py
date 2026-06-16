"""
Apply shared SMTP env to the Keycloak grm realm (officer invite / execute-actions).

Reads SMTP_* via backend.config.smtp_config — same mailbox as the Messaging API.
"""
from __future__ import annotations

from backend.config.smtp_config import SmtpConfig, missing_smtp_env_fields, resolve_smtp_config

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
    from backend.config.smtp_config import resolve_smtp_delivery_configs

    profiles = resolve_smtp_delivery_configs()
    if not profiles:
        return None

    def _to_keycloak(cfg: SmtpConfig) -> dict[str, str]:
        return {
            "host": cfg.host,
            "port": str(cfg.port),
            "from": cfg.from_addr,
            "fromDisplayName": cfg.from_display,
            # Match backend/services/messaging.py: SMTPS on 465, STARTTLS elsewhere.
            "ssl": "true" if cfg.port == 465 else "false",
            "starttls": "false" if cfg.port == 465 else "true",
            "auth": "true",
            "user": cfg.username,
            "password": cfg.password,
        }

    import socket

    for _label, cfg in profiles:
        try:
            with socket.create_connection((cfg.host, cfg.port), timeout=5):
                return _to_keycloak(cfg)
        except OSError:
            continue

    # None reachable — still apply primary/fallback config so Keycloak has settings
    # (invite may fail until network/firewall is fixed).
    return _to_keycloak(profiles[0][1])
