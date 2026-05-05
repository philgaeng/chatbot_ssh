"""
Auth for POST /api/messaging/* — only intended callers: ticketing and chatbot stacks.

Environment (see also ticketing MESSAGING_API_KEY in env):
  MESSAGING_API_AUTH_DISABLED=true   # local only; skips all checks
  MESSAGING_API_KEY                # shared secret; any caller with key + X-Messaging-Source
  MESSAGING_API_KEY_TICKETING       # per-stack secrets (recommended for split deploy)
  MESSAGING_API_KEY_CHATBOT

When any MESSAGING_API_KEY* is set (and auth not disabled):
  - Require header x-api-key
  - Require header X-Messaging-Source: ticketing | chatbot
  - Key must match the secret for that source (or legacy single key for both)

When no keys are configured and auth is not disabled:
  - Allow requests but log a one-time warning (backward-compatible dev default).

Future: ticketing "notifications settings" can rotate keys here or via shared config service.
"""

from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)
_warned_open_api = False


def _const_eq(a: str, b: str) -> bool:
    if not a or not b or len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _strip(name: str) -> str:
    return (os.getenv(name) or "").strip()


@dataclass(frozen=True)
class MessagingApiCaller:
    """Validated caller identity for logging / downstream use."""

    source: str  # ticketing | chatbot | unknown | disabled


def messaging_api_guard(
    x_api_key: Annotated[Optional[str], Header(alias="x-api-key")] = None,
    x_messaging_source: Annotated[Optional[str], Header(alias="X-Messaging-Source")] = None,
) -> MessagingApiCaller:
    global _warned_open_api

    if _strip("MESSAGING_API_AUTH_DISABLED").lower() in ("1", "true", "yes"):
        return MessagingApiCaller(source="disabled")

    kt = _strip("MESSAGING_API_KEY_TICKETING")
    kc = _strip("MESSAGING_API_KEY_CHATBOT")
    kl = _strip("MESSAGING_API_KEY")
    keys_configured = bool(kt or kc or kl)

    if not keys_configured:
        if not _warned_open_api:
            logger.warning(
                "Messaging API has no MESSAGING_API_KEY* set — accepting all requests. "
                "Set MESSAGING_API_KEY_TICKETING / MESSAGING_API_KEY_CHATBOT (or MESSAGING_API_KEY) "
                "for production."
            )
            _warned_open_api = True
        return MessagingApiCaller(source=x_messaging_source or "unknown")

    src = (x_messaging_source or "").strip().lower()
    if src not in ("ticketing", "chatbot"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "FAILED",
                "error_code": "FORBIDDEN",
                "error": "Header X-Messaging-Source must be 'ticketing' or 'chatbot'",
            },
        )

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "FAILED",
                "error_code": "UNAUTHORIZED",
                "error": "Missing x-api-key",
            },
        )

    if kt or kc:
        if src == "ticketing":
            expected = kt or kl
        else:
            expected = kc or kl
        if not expected or not _const_eq(x_api_key, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "FAILED",
                    "error_code": "UNAUTHORIZED",
                    "error": "Invalid API key for this source",
                },
            )
        return MessagingApiCaller(source=src)

    if kl and _const_eq(x_api_key, kl):
        return MessagingApiCaller(source=src)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "FAILED",
            "error_code": "UNAUTHORIZED",
            "error": "Invalid API key",
        },
    )
