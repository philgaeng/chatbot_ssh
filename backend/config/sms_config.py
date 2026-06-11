"""
SMS provider settings from env.

Production Nepal: DOIT government gateway (sms.doit.gov.np).
Dev / international fallback: AWS SNS.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Literal

SmsProvider = Literal["doit", "aws_sns", "disabled"]

NEPAL_MOBILE_RE = re.compile(r"^(97|98)\d{8}$")
PH_E164_RE = re.compile(r"^\+63\d{10}$")


@dataclass(frozen=True)
class SmsConfig:
    provider: SmsProvider
    enabled: bool
    base_url: str
    bearer_token: str
    whitelist_only: bool


def _first_nonempty(*values: str | None) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def resolve_sms_config() -> SmsConfig:
    """Resolve SMS transport from env."""
    bearer_token = _first_nonempty(os.getenv("DOIT_SMS_BEARER_TOKEN"))
    base_url = _first_nonempty(os.getenv("DOIT_SMS_BASE_URL")) or "https://sms.doit.gov.np"
    provider_raw = _first_nonempty(os.getenv("SMS_PROVIDER")).lower()

    if provider_raw in ("doit", "aws_sns", "disabled"):
        provider: SmsProvider = provider_raw  # type: ignore[assignment]
    elif bearer_token:
        provider = "doit"
    else:
        provider = "aws_sns"

    if os.getenv("SMS_ENABLED") is not None:
        enabled = _env_bool("SMS_ENABLED")
    else:
        from backend.config.constants import SMS_ENABLED

        enabled = bool(SMS_ENABLED)

    if os.getenv("SMS_WHITELIST_ONLY") is not None:
        whitelist_only = _env_bool("SMS_WHITELIST_ONLY")
    else:
        whitelist_only = provider == "aws_sns"

    if provider == "doit" and not bearer_token:
        provider = "disabled"

    return SmsConfig(
        provider=provider,
        enabled=enabled,
        base_url=base_url.rstrip("/"),
        bearer_token=bearer_token,
        whitelist_only=whitelist_only,
    )


def normalize_nepal_mobile(phone_number: str) -> str:
    """
    Convert common Nepal phone inputs to DOIT's 10-digit mobile format (97/98…).
    """
    cleaned = re.sub(r"[^\d+]", "", phone_number.strip())
    if cleaned.startswith("+977"):
        cleaned = cleaned[4:]
    elif cleaned.startswith("977") and len(cleaned) >= 12:
        cleaned = cleaned[3:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]

    if not NEPAL_MOBILE_RE.match(cleaned):
        raise ValueError(f"Invalid Nepal mobile number: {phone_number}")

    return cleaned


def format_philippines_e164(phone_number: str) -> str:
    """Normalize Philippines numbers to E.164 (+63…) for AWS SNS dev testing."""
    cleaned = re.sub(r"[^\d+]", "", phone_number.strip())

    if PH_E164_RE.match(cleaned):
        return cleaned

    if cleaned.startswith("09"):
        formatted = "+63" + cleaned[1:]
    elif cleaned.startswith("63"):
        formatted = "+" + cleaned
    elif cleaned.startswith("0063"):
        formatted = "+" + cleaned[2:]
    else:
        raise ValueError(f"Invalid Philippines phone number format: {phone_number}")

    if not PH_E164_RE.match(formatted):
        raise ValueError(f"Invalid Philippines phone number format: {phone_number}")

    return formatted


def sms_config_summary() -> dict[str, Any]:
    """Non-secret snapshot for logs."""
    cfg = resolve_sms_config()
    return {
        "provider": cfg.provider,
        "enabled": cfg.enabled,
        "base_url": cfg.base_url if cfg.provider == "doit" else None,
        "token_configured": bool(cfg.bearer_token),
        "whitelist_only": cfg.whitelist_only,
    }
