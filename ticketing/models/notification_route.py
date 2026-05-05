"""
ticketing.notification_routes — per-country (and optional per-project) outbound
notification policy: which provider and template ids to use for SMS / email.

No PII: only country_code, project_id, channel, provider keys, template references,
and non-secret JSON options (e.g. provider profile labels).

Resolution order (see ``resolve_notification_route``):
  1. Active row for (project_id, channel) if ``project_id`` is set
  2. Else active country default row (project_id IS NULL) for (country_code, channel)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class NotificationRoute(Base):
    """
    One row defines SMS or email routing for a country default or a project override.

    ``provider_key`` values align with notify / backend env (e.g. sns, ses, noop,
    local_sms, local_email — extensible as adapters are added).
    """

    __tablename__ = "notification_routes"
    __table_args__ = (
        Index(
            "uq_notif_routes_country_channel_default",
            "country_code",
            "channel",
            unique=True,
            postgresql_where=text("project_id IS NULL"),
        ),
        Index(
            "uq_notif_routes_project_channel",
            "project_id",
            "channel",
            unique=True,
            postgresql_where=text("project_id IS NOT NULL"),
        ),
        Index("idx_notif_routes_country_project", "country_code", "project_id", "channel", "is_active"),
        {"schema": "ticketing"},
    )

    route_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(
        String(8),
        ForeignKey("ticketing.countries.country_code", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.projects.project_id", ondelete="CASCADE"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)  # 'sms' | 'email'
    provider_key: Mapped[str] = mapped_column(String(32), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    secondary_template_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    options_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # admin-only description, non-PII


NotificationChannel = Literal["sms", "email"]


def resolve_notification_route(
    session: Session,
    *,
    country_code: str,
    channel: NotificationChannel,
    project_id: str | None = None,
) -> NotificationRoute | None:
    """
    Return the effective routing row: project override first, else country default.
    """
    cc = (country_code or "").strip().upper()[:8]
    ch = channel.lower()
    if ch not in ("sms", "email"):
        return None

    if project_id:
        row = session.scalar(
            select(NotificationRoute).where(
                NotificationRoute.project_id == project_id,
                NotificationRoute.channel == ch,
                NotificationRoute.is_active.is_(True),
            )
        )
        if row is not None:
            return row

    return session.scalar(
        select(NotificationRoute).where(
            NotificationRoute.country_code == cc,
            NotificationRoute.project_id.is_(None),
            NotificationRoute.channel == ch,
            NotificationRoute.is_active.is_(True),
        )
    )
