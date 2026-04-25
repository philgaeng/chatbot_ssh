"""
ticketing.project_packages   — civil-works lots / packages within a project
ticketing.package_locations  — many-to-many: package ↔ location nodes

A project is divided into civil-works packages (lots/contracts).
Each package is awarded to one contractor and covers specific districts.
L1 GRM officers are scoped to a package — they only see tickets at locations
within their package's coverage area.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, PrimaryKeyConstraint,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ProjectPackage(Base):
    """
    A civil-works package (lot/contract) within a project.
    e.g. KL Road / Lot 1 = SHEP/OCB/KL/01 / Kakarbhitta–Sitapur / Km 0–45 / Contractor TBD
    """
    __tablename__ = "project_packages"
    __table_args__ = (
        UniqueConstraint("project_id", "package_code", name="uq_project_packages_code"),
        Index("idx_project_packages_project", "project_id"),
        Index("idx_project_packages_contractor", "contractor_org_id"),
        {"schema": "ticketing"},
    )

    package_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    # Official lot/contract number, e.g. 'SHEP/OCB/KL/01'
    package_code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Main contractor for this package (nullable — assigned later or unknown)
    # org_role on project_organizations determines the role; here we store the specific
    # contractor entity directly for fast L1 routing.
    contractor_org_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    locations: Mapped[list["PackageLocation"]] = relationship(
        "PackageLocation", back_populates="package", cascade="all, delete-orphan"
    )


class PackageLocation(Base):
    """
    Which location nodes (districts / municipalities) a package covers.
    Ticket routing: location X → find package whose coverage includes X → assign L1.
    """
    __tablename__ = "package_locations"
    __table_args__ = (
        PrimaryKeyConstraint("package_id", "location_code"),
        Index("idx_package_locations_location", "location_code"),
        {"schema": "ticketing"},
    )

    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticketing.project_packages.package_id", ondelete="CASCADE"),
        nullable=False,
    )
    location_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.locations.location_code", ondelete="CASCADE"),
        nullable=False,
    )

    package: Mapped["ProjectPackage"] = relationship("ProjectPackage", back_populates="locations")
