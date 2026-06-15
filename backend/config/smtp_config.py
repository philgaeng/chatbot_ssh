"""
Shared SMTP settings from env.

Used by the Messaging API (complainant/report email) and Keycloak realm setup
(officer invite emails). Primary mailbox: SMTP_*; optional fallback: TEMP_SMTP_*.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

SmtpProfileLabel = Literal["primary", "fallback"]


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


def _resolve_prefixed_smtp_config(prefix: str) -> SmtpConfig | None:
    """Build SMTP config for SMTP_* (prefix '') or TEMP_SMTP_* (prefix 'TEMP_')."""
    host = _first_nonempty(os.getenv(f"{prefix}SMTP_SERVER"))
    port_raw = _first_nonempty(os.getenv(f"{prefix}SMTP_PORT")) or "587"
    username = _first_nonempty(os.getenv(f"{prefix}SMTP_USERNAME"))
    password = _first_nonempty(os.getenv(f"{prefix}SMTP_PASSWORD"))
    from_addr = _first_nonempty(
        os.getenv(f"{prefix}SMTP_FROM"),
        os.getenv(f"{prefix}SMTP_USERNAME"),
    )
    from_display = (
        _first_nonempty(os.getenv(f"{prefix}SMTP_FROM_DISPLAY")) or "GRM Ticketing"
    )

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


def resolve_smtp_config() -> SmtpConfig | None:
    """Official DOR / production mailbox (SMTP_*). Used by Keycloak realm SMTP."""
    return _resolve_prefixed_smtp_config("")


def resolve_temp_smtp_config() -> SmtpConfig | None:
    """Temporary fallback mailbox (TEMP_SMTP_*) when official relay is unreachable."""
    return _resolve_prefixed_smtp_config("TEMP_")


def resolve_smtp_delivery_configs() -> list[tuple[SmtpProfileLabel, SmtpConfig]]:
    """Primary first, then optional fallback — for Messaging API send with retry."""
    profiles: list[tuple[SmtpProfileLabel, SmtpConfig]] = []
    primary = resolve_smtp_config()
    if primary:
        profiles.append(("primary", primary))
    fallback = resolve_temp_smtp_config()
    if fallback:
        profiles.append(("fallback", fallback))
    return profiles


def _config_snapshot(cfg: SmtpConfig) -> dict[str, Any]:
    return {
        "host": cfg.host,
        "port": cfg.port,
        "username": cfg.username,
        "from_addr": cfg.from_addr,
        "from_display": cfg.from_display,
    }


def missing_smtp_env_fields() -> list[str]:
    """Human-readable names of unset required primary SMTP env vars."""
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
    """Non-secret snapshot for primary SMTP (legacy callers / Keycloak checks)."""
    cfg = resolve_smtp_config()
    if not cfg:
        return {"configured": False}
    return {"configured": True, **_config_snapshot(cfg)}


def smtp_delivery_summary() -> dict[str, Any]:
    """Non-secret snapshot of primary + fallback mailboxes for Messaging API logs."""
    profiles = resolve_smtp_delivery_configs()
    if not profiles:
        return {"configured": False}
    return {
        "configured": True,
        "profiles": [
            {"label": label, **_config_snapshot(cfg)} for label, cfg in profiles
        ],
    }
