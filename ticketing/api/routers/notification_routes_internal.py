"""
Internal read-only API for effective notification routing (D2 pull).

Used when the messaging/notify service runs without direct DB access to ``ticketing.*``:
set ``NOTIFICATION_ROUTING_SOURCE=http`` and ``NOTIFICATION_ROUTING_HTTP_BASE_URL`` on the messaging host.

Auth: same ``x-api-key`` as inbound ticketing API (``TICKETING_SECRET_KEY``).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from ticketing.api.dependencies import get_db, verify_api_key
from ticketing.models.notification_route import resolve_notification_route

router = APIRouter(prefix="/internal/notification-routes", tags=["Internal — notification routing"])


class EffectiveRouteResponse(BaseModel):
    found: bool
    country_code: str
    project_id: Optional[str] = None
    channel: str = Field(description="sms | email")
    provider_key: Optional[str] = None
    template_id: Optional[str] = None
    secondary_template_id: Optional[str] = None
    options_json: Optional[dict[str, Any]] = None


@router.get("/effective", response_model=EffectiveRouteResponse)
def get_effective_route(
    country_code: str = Query(..., min_length=2, max_length=8),
    channel: Literal["sms", "email"] = Query(...),
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Resolve ``ticketing.notification_routes`` the same way as the messaging runtime (project override, then country default).
    """
    cc = country_code.strip().upper()[:8]
    ch = "sms" if channel.lower() == "sms" else "email"
    row = resolve_notification_route(
        db,
        country_code=cc,
        channel=ch,
        project_id=project_id.strip() if project_id else None,
    )
    if row is None:
        return EffectiveRouteResponse(
            found=False,
            country_code=cc,
            project_id=project_id,
            channel=ch,
        )
    opts = row.options_json if isinstance(row.options_json, dict) else None
    return EffectiveRouteResponse(
        found=True,
        country_code=row.country_code,
        project_id=row.project_id,
        channel=row.channel,
        provider_key=row.provider_key,
        template_id=row.template_id,
        secondary_template_id=row.secondary_template_id,
        options_json=opts,
    )
