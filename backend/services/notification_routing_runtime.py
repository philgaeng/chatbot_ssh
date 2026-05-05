"""
Resolve outbound SMS/email provider from ticketing.notification_routes (long-term D2).

Sources:
  - ``db`` (default): SQLAlchemy session to same Postgres as ticketing (``ticketing.*``).
  - ``http``: GET Ticketing API ``/api/v1/internal/notification-routes/effective`` when the
    messaging/notify host has **no** direct DB access to routing tables.

Env:
  NOTIFICATION_ROUTING_ENABLED   — default ``true``; set ``false`` to always use env providers only.
  NOTIFICATION_ROUTING_SOURCE    — ``db`` | ``http`` (default ``db``).
  NOTIFICATION_ROUTING_HTTP_BASE_URL — e.g. ``http://ticketing:5002`` when SOURCE=http.
  NOTIFICATION_ROUTING_HTTP_API_KEY  — optional; falls back to ``MESSAGING_API_KEY_TICKETING``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

logger = logging.getLogger(__name__)

Channel = Literal["sms", "email"]


@dataclass(frozen=True)
class EffectiveRoute:
    provider_key: str
    template_id: str | None = None
    secondary_template_id: str | None = None
    options_json: dict[str, Any] | None = None


def _routing_enabled() -> bool:
    return os.getenv("NOTIFICATION_ROUTING_ENABLED", "true").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _extract_country_and_project(ctx: Dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not ctx:
        return None, None
    cc = ctx.get("country_code")
    if cc is None and isinstance(ctx.get("extra"), dict):
        cc = ctx["extra"].get("country_code")
    pid = ctx.get("project_id")
    if pid is None and isinstance(ctx.get("extra"), dict):
        pid = ctx["extra"].get("project_id")
    if cc is not None:
        cc = str(cc).strip().upper()[:8] or None
    if pid is not None:
        pid = str(pid).strip() or None
    return cc, pid


def resolve_effective_route(
    channel: Channel,
    context: Dict[str, Any] | None,
) -> EffectiveRoute | None:
    """
    Return routed provider configuration when ``context`` includes ``country_code``
    (optional ``project_id`` for overrides). Otherwise ``None`` → caller uses env defaults.
    """
    if not _routing_enabled():
        return None

    country_code, project_id = _extract_country_and_project(context)
    if not country_code:
        return None

    source = os.getenv("NOTIFICATION_ROUTING_SOURCE", "db").strip().lower()
    try:
        if source == "http":
            return _resolve_http(channel, country_code, project_id)
        return _resolve_db(channel, country_code, project_id)
    except Exception as e:
        logger.warning(
            "Notification routing lookup failed (channel=%s country=%s): %s",
            channel,
            country_code,
            e,
        )
        return None


def _resolve_db(
    channel: Channel,
    country_code: str,
    project_id: str | None,
) -> EffectiveRoute | None:
    try:
        from ticketing.models.base import SessionLocal
        from ticketing.models.notification_route import resolve_notification_route
    except ImportError as e:
        logger.debug("Ticketing models not importable: %s", e)
        return None

    ch = "sms" if channel == "sms" else "email"
    with SessionLocal() as db:
        row = resolve_notification_route(
            db,
            country_code=country_code,
            channel=ch,
            project_id=project_id,
        )
    if row is None:
        return None
    opts = row.options_json if isinstance(row.options_json, dict) else None
    return EffectiveRoute(
        provider_key=str(row.provider_key).strip().lower(),
        template_id=row.template_id,
        secondary_template_id=row.secondary_template_id,
        options_json=opts,
    )


def _resolve_http(
    channel: Channel,
    country_code: str,
    project_id: str | None,
) -> EffectiveRoute | None:
    import httpx

    base = os.getenv("NOTIFICATION_ROUTING_HTTP_BASE_URL", "").strip().rstrip("/")
    if not base:
        logger.warning("NOTIFICATION_ROUTING_SOURCE=http but NOTIFICATION_ROUTING_HTTP_BASE_URL is empty")
        return None

    api_key = (
        os.getenv("NOTIFICATION_ROUTING_HTTP_API_KEY", "").strip()
        or os.getenv("MESSAGING_API_KEY_TICKETING", "").strip()
    )
    params: dict[str, str] = {
        "country_code": country_code,
        "channel": "sms" if channel == "sms" else "email",
    }
    if project_id:
        params["project_id"] = project_id

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    url = f"{base}/api/v1/internal/notification-routes/effective"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params, headers=headers)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        if not data.get("found"):
            return None
        pk = data.get("provider_key")
        if not pk:
            return None
        return EffectiveRoute(
            provider_key=str(pk).strip().lower(),
            template_id=data.get("template_id"),
            secondary_template_id=data.get("secondary_template_id"),
            options_json=data.get("options_json") if isinstance(data.get("options_json"), dict) else None,
        )
    except Exception as e:
        logger.warning("HTTP notification routing failed: %s", e)
        return None
