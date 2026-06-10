"""
Shared SMTP settings from env.

Used by the Messaging API (complainant/report email) and Keycloak realm setup
(officer invite emails). Single mailbox — configure once via SMTP_*.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_addr: str
    from_display: str


def _first_nonempty(*values: str | None) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def resolve_smtp_config() -> SmtpConfig | None:
    """Build SMTP config when host, credentials, and from-address are present."""
    host = _first_nonempty(os.getenv("SMTP_SERVER"))
    port_raw = _first_nonempty(os.getenv("SMTP_PORT")) or "587"
    username = _first_nonempty(os.getenv("SMTP_USERNAME"))
    password = _first_nonempty(os.getenv("SMTP_PASSWORD"))
    from_addr = _first_nonempty(os.getenv("SMTP_FROM"), os.getenv("SMTP_USERNAME"))
    from_display = _first_nonempty(os.getenv("SMTP_FROM_DISPLAY")) or "GRM Ticketing"

    if not host or not username or not password or not from_addr:
        return None

    try:
        port = int(port_raw)
    except ValueError:
        port = 587

    return SmtpConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        from_addr=from_addr,
        from_display=from_display,
    )


def missing_smtp_env_fields() -> list[str]:
    """Human-readable names of unset required SMTP env vars."""
    missing: list[str] = []
    if not _first_nonempty(os.getenv("SMTP_SERVER")):
        missing.append("SMTP_SERVER")
    if not _first_nonempty(os.getenv("SMTP_USERNAME")):
        missing.append("SMTP_USERNAME")
    if not _first_nonempty(os.getenv("SMTP_PASSWORD")):
        missing.append("SMTP_PASSWORD")
    if not _first_nonempty(os.getenv("SMTP_FROM"), os.getenv("SMTP_USERNAME")):
        missing.append("SMTP_FROM")
    return missing


def smtp_config_summary() -> dict[str, Any]:
    """Non-secret snapshot for logs."""
    cfg = resolve_smtp_config()
    if not cfg:
        return {"configured": False}
    return {
        "configured": True,
        "host": cfg.host,
        "port": cfg.port,
        "username": cfg.username,
        "from_addr": cfg.from_addr,
        "from_display": cfg.from_display,
    }
