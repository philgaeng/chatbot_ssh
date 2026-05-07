"""
ticketing.qr_tokens — opaque scan tokens that link a QR code to a package.

Each package can have multiple tokens (one per field site / notice board).
Tokens can be revoked without changing the QR URL infrastructure.

Scan flow:
  GET /api/v1/scan/{token}
  → returns { project_code, package_id, package_code, location_code, label }
  → chatbot pre-fills location slots and skips geo questions
  → ticket created with package_id set
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token() -> str:
    """8-char hex token, e.g. 'a3f9b2c1'. Short enough for a clean QR."""
    return secrets.token_hex(4)


class QrToken(Base):
    __tablename__ = "qr_tokens"
    __table_args__ = (
        Index("idx_qr_tokens_package", "package_id"),
        {"schema": "ticketing"},
    )

    # Primary key — the opaque token embedded in the QR URL (?t=a3f9b2c1)
    token: Mapped[str] = mapped_column(String(32), primary_key=True, default=_token)

    # The package this token resolves to (UUID FK to project_packages)
    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.project_packages.package_id", ondelete="CASCADE"),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Optional expiry — NULL means the token never expires
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
