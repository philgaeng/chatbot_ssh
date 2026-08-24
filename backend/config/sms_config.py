# SPDX-License-Identifier: Apache-2.0

"""
SMS provider settings from env.

**One transport: the DOIT government gateway (sms.doit.gov.np), in Nepal.**

⚠ There is deliberately no cross-border fallback. An AWS SNS path existed until 2026-08-24 as demo
scaffolding — it could only format *Philippine* numbers, so it was never able to reach a Nepali
complainant. It was removed because SMS providers serving Nepal must be in Nepal, and a fallback that
routes a complainant's number and grievance text through Singapore is a cross-border transfer nobody
chose (privacy assessment F-12).

With no token configured the provider resolves to `disabled`, which sends nothing and says so. That
is the intended failure mode: **no SMS is better than SMS out of the country.**
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Literal

SmsProvider = Literal["doit", "disabled"]

NEPAL_MOBILE_RE = re.compile(r"^(97|98)\d{8}$")


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

    if provider_raw in ("doit", "disabled"):
        provider: SmsProvider = provider_raw  # type: ignore[assignment]
    elif bearer_token:
        provider = "doit"
    else:
        # ⚠ Was `aws_sns` until 2026-08-24 — a missing token silently routed SMS abroad.
        # Failing closed is the point: no SMS beats SMS out of the country.
        provider = "disabled"

    if os.getenv("SMS_ENABLED") is not None:
        enabled = _env_bool("SMS_ENABLED")
    else:
        from backend.config.constants import SMS_ENABLED

        enabled = bool(SMS_ENABLED)

    # Opt-in only. It used to default to true for the AWS SNS path; with that path gone there is
    # no provider it should switch itself on for. `SMS_ENABLED` is the gate that matters.
    whitelist_only = _env_bool("SMS_WHITELIST_ONLY")

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
