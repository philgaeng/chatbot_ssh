"""
ticketing.projects              — admin-managed project registry
ticketing.project_organizations — many-to-many projects ↔ organizations
ticketing.project_locations     — many-to-many projects ↔ specific location nodes
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("idx_projects_country", "country_code"),
        Index("idx_projects_short_code", "short_code"),
        {"schema": "ticketing"},
    )

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    country_code: Mapped[str] = mapped_column(
        String(8),
        ForeignKey("ticketing.countries.country_code", ondelete="RESTRICT"),
        nullable=False,
    )
    short_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # e.g. 'KL_ROAD'
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # URL of the local chatbot backend for this project (e.g. http://backend:5001).
    # Used to proxy complainant-info edits back to the chatbot's DB.
    # NULL = fall back to settings.backend_grievance_base_url (single-instance deploy).
    chatbot_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    organizations: Mapped[list["ProjectOrganization"]] = relationship(
        "ProjectOrganization", back_populates="project", cascade="all, delete-orphan"
    )
    locations: Mapped[list["ProjectLocation"]] = relationship(
        "ProjectLocation", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectOrganization(Base):
    """
    Many-to-many: multiple organizations can co-own a project.
    e.g. KL Road → DOR (implementing_agency) + ADB (donor)
    org_role references the vocabulary stored in ticketing.settings key 'org_roles'.
    """
    __tablename__ = "project_organizations"
    __table_args__ = (
        PrimaryKeyConstraint("project_id", "organization_id"),
        {"schema": "ticketing"},
    )

    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
    )
    # Role of this org in this project (e.g. "donor", "implementing_agency").
    # Nullable: role may be assigned later or left blank.
    org_role: Mapped[str | None] = mapped_column(String(64), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="organizations")


class ProjectLocation(Base):
    """
    Many-to-many: a project covers specific location nodes (e.g. 3 districts, not the whole province).
    Links to the exact level nodes — descendants implied by the tree but not auto-included here.
    """
    __tablename__ = "project_locations"
    __table_args__ = (
        PrimaryKeyConstraint("project_id", "location_code"),
        {"schema": "ticketing"},
    )

    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    location_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.locations.location_code", ondelete="CASCADE"),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="locations")
