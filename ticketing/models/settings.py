"""
ticketing.settings — key/value config store.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Settings(Base):
    __tablename__ = "settings"
    __table_args__ = {"schema": "ticketing"}

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
