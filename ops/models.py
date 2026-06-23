"""
SQLAlchemy models for the dedicated `ops` schema.

Separate DeclarativeBase from ticketing — the ops module owns this schema and its
own Alembic stream (ops/migrations). All models use schema="ops".
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class OpsBase(DeclarativeBase):
    pass


class SystemHealthCheck(OpsBase):
    __tablename__ = "system_health_checks"
    __table_args__ = (
        Index("ix_health_checks_name_time", "check_name", "checked_at"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    check_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # ok | warn | critical
    value_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )


class DependencyFinding(OpsBase):
    __tablename__ = "dependency_findings"
    __table_args__ = ({"schema": "ops"},)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)  # pip-audit|npm|dependabot|trivy
    package: Mapped[str] = mapped_column(Text, nullable=False)
    installed_ver: Mapped[str | None] = mapped_column(Text, nullable=True)
    advisory_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fixed_in: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )
    last_seen: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
