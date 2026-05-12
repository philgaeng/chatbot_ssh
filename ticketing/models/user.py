"""
ticketing.roles and ticketing.user_roles

Roles are defined here. Users are Cognito identities — only their Cognito sub
(user_id) is stored; no PII in ticketing.*.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# Role keys — locked per CLAUDE.md
ROLE_KEYS = [
    "super_admin",
    "local_admin",
    "site_safeguards_focal_person",
    "pd_piu_safeguards_focal",
    "grc_chair",
    "grc_member",
    "adb_national_project_director",
    "adb_hq_safeguards",
    "adb_hq_project",
    "seah_national_officer",
    "seah_hq_officer",
    "adb_hq_exec",
]

# SEAH-only roles — tickets with is_seah=True are only visible to these roles
SEAH_ROLES = {"seah_national_officer", "seah_hq_officer"}

# Roles that can see both standard and SEAH
BOTH_WORKFLOWS_ROLES = {"super_admin", "adb_hq_exec"}


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "ticketing"}

    role_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    role_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Admin UI / docs — seeded from ticketing.constants.grm_role_catalog
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    permissions: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="role", lazy="select"
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        Index(
            "idx_user_roles_user_org_loc",
            "user_id",
            "organization_id",
            "location_code",
        ),
        {"schema": "ticketing"},
    )

    user_role_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.roles.role_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    location_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Per-officer language override. NULL = use organisation default.
    # 'en' = English-first (show translation chips inline),
    # 'ne' = Nepali-first (hide inline chips; use translation panel for review).
    preferred_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")
