# SPDX-License-Identifier: Apache-2.0

"""
ticketing.organizations

Location model has moved to country.py (full redesign with multilingual support).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Org-tree domain values (doc 16 §3.1). Kept here so models/tests can import the
# canonical tuples; the router + services import the same via ticketing.services.org_tree.
ORG_CATEGORIES = ("government", "local_government", "donor", "third_party")
UNIT_TYPES = (
    "ministry",
    "department",
    "directorate",
    "provincial_office",
    "division_office",
    "company",
    "development_partner",
    "province_assembly",
    "municipality",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "ticketing"}

    # PK is assigned at insert: explicit admin value or auto via
    # ticketing.utils.organization_identifier.suggested_organization_id +
    # allocate_unique_organization_id.
    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable: cross-country orgs (e.g. ADB) have no single country
    country_code: Mapped[str | None] = mapped_column(
        String(8),
        ForeignKey("ticketing.countries.country_code", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Language preference for this org's officers. 'ne' = Nepali-first (DOR), 'en' = English-first (ADB).
    # Individual officers can override via ticketing.user_roles.preferred_language.
    default_language: Mapped[str] = mapped_column(String(8), nullable=False, default="ne")

    # ── Org tree (OC-01, doc 16 §3.1) ──────────────────────────────────────────
    # Self-FK; NULL = root. The org forest: GoN reporting line is one rooted subtree;
    # contractors (company) and donors (development_partner) are independent roots.
    parent_organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
    )
    # Coarse actor type — inherited from root (authoritative), denormalized onto every
    # node. NOT NULL. default here mirrors the migration backfill so pre-OC-01 construction
    # sites (seeds/tests that omit it) keep working; the router sets it explicitly.
    org_category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="government"
    )
    # Fine-grained per-node sub-type (nullable). Domain enforced by a DB CHECK.
    unit_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Optional office territory — makes the unit routable (doc 16 §5.2). FK into
    # ticketing.locations (same schema; not a public.* FK).
    territory_location_code: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.locations.location_code", ondelete="SET NULL"),
        nullable=True,
    )
    territory_includes_children: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    display_name_ne: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Owned third_party authorship (Gap A, 2026-07-24) ───────────────────────
    # A contractor an org_admin creates is a `third_party` root (parent NULL) that sits
    # outside every subtree, so the plain subtree guard would let only super_admin edit it.
    # This stamps the creator's org node so the creator + any ancestor-org admin can still
    # maintain it (authority = owner ∈ caller subtree). NULL = not owned (institutional
    # roots, seeded orgs). Mirrors the catalog owner_organization_id on
    # workflow_definitions / roles / position_types.
    owner_organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Duplicate-candidate signals (SH-4, migration k1m3o5q7) ─────────────────
    # Added to the DB by SH-4 but previously left unmapped; mapped here so the model
    # reflects the table (autogenerate no longer emits spurious drops for these).
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Self-referential tree relationships (read convenience; subtree queries use the
    # recursive CTE in ticketing.services.org_tree, not these). Since Gap A added a second
    # self-FK (owner_organization_id), these must name parent_organization_id explicitly —
    # otherwise SQLAlchemy can't pick between the two FK paths and the mapper fails to init.
    parent: Mapped["Organization | None"] = relationship(
        "Organization",
        remote_side=[organization_id],
        foreign_keys=[parent_organization_id],
        back_populates="children",
    )
    children: Mapped[list["Organization"]] = relationship(
        "Organization",
        foreign_keys=[parent_organization_id],
        back_populates="parent",
    )
