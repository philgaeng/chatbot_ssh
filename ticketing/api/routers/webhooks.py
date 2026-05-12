"""
Inbound webhooks (Keycloak → ticketing).

INTEGRATION POINT: configure your Keycloak HTTP event listener to POST here with
X-Keycloak-Webhook-Secret matching KEYCLOAK_WEBHOOK_SECRET.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ticketing.api.dependencies import get_db
from ticketing.config.settings import get_settings
from ticketing.models.officer_onboarding import OfficerOnboarding
from ticketing.services.keycloak_webhook import (
    keycloak_admin_from_settings,
    resolve_ticketing_user_id,
    should_activate_onboarding,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_webhook_secret(request: Request) -> None:
    settings = get_settings()
    secret = (settings.keycloak_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KEYCLOAK_WEBHOOK_SECRET is not set — webhook disabled",
        )
    got = (
        request.headers.get("X-Keycloak-Webhook-Secret")
        or request.headers.get("X-Webhook-Secret")
        or ""
    ).strip()
    if got != secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


@router.post(
    "/webhooks/keycloak",
    summary="Keycloak event webhook (invited → active)",
)
async def keycloak_event_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Accepts JSON event bodies from a Keycloak HTTP event-listener extension.

    When Keycloak emits a successful UPDATE_PASSWORD (or mark_active test payload),
    sets ticketing.officer_onboarding.status to active for the resolved user_id.
    """
    _verify_webhook_secret(request)

    try:
        body: Any = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}") from exc

    payloads: list[dict[str, Any]]
    if isinstance(body, list):
        payloads = [x for x in body if isinstance(x, dict)]
    elif isinstance(body, dict):
        payloads = [body]
    else:
        raise HTTPException(status_code=422, detail="Expected JSON object or array")

    processed: list[dict[str, Any]] = []
    admin = None

    for payload in payloads:
        if not should_activate_onboarding(payload):
            processed.append({"ignored": True, "hint": payload.get("type")})
            continue

        if admin is None:
            admin = keycloak_admin_from_settings()

        tid = resolve_ticketing_user_id(payload, admin)
        if not tid:
            logger.warning("Could not resolve ticketing user_id from payload keys=%s", list(payload.keys()))
            processed.append({"ignored": True, "reason": "unresolved_identity"})
            continue

        row = db.get(OfficerOnboarding, tid)
        now = datetime.now(timezone.utc)
        if row:
            if row.status != "active":
                row.status = "active"
                row.updated_at = now
        else:
            db.add(OfficerOnboarding(user_id=tid, status="active", updated_at=now))

        processed.append({"ok": True, "user_id": tid, "status": "active"})
        logger.info("Officer onboarding activated via Keycloak event user_id=%s", tid)

    db.commit()
    return {"ok": True, "results": processed}
