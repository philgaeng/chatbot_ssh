"""
ticketing.countries            — country registry
ticketing.location_level_defs  — admin level names per country (Province, District, …)
ticketing.locations            — hierarchical adjacency-list tree (redesigned)
ticketing.location_translations — multilingual names for every location node
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Countries ─────────────────────────────────────────────────────────────────

class Country(Base):
    __tablename__ = "countries"
    __table_args__ = {"schema": "ticketing"}

    country_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    level_defs: Mapped[list["LocationLevelDef"]] = relationship(
        "LocationLevelDef", back_populates="country", lazy="select"
    )
    locations: Mapped[list["Location"]] = relationship(
        "Location", back_populates="country", lazy="select"
    )


# ── Location level definitions ────────────────────────────────────────────────

class LocationLevelDef(Base):
    """
    Defines what each level number means for a given country.
    e.g.  NP / 1 / Province / प्रदेश
          NP / 2 / District  / जिल्ला
          NP / 3 / Municipality / नगरपालिका
    """
    __tablename__ = "location_level_defs"
    __table_args__ = (
        PrimaryKeyConstraint("country_code", "level_number"),
        {"schema": "ticketing"},
    )

    country_code: Mapped[str] = mapped_column(
        String(8),
        ForeignKey("ticketing.countries.country_code", ondelete="CASCADE"),
        nullable=False,
    )
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    level_name_en: Mapped[str] = mapped_column(Text, nullable=False)          # "Province"
    level_name_local: Mapped[str | None] = mapped_column(Text, nullable=True)  # "प्रदेश"

    country: Mapped["Country"] = relationship("Country", back_populates="level_defs")


# ── Locations (adjacency-list tree) ───────────────────────────────────────────

class Location(Base):
    """
    One row per administrative node at any level.
    Names are NOT stored here — use location_translations for multilingual names.

    location_code: human-readable PK, e.g. NP_P1, NP_D001, NP_M0001
    level_number:  matches location_level_defs for the same country_code
    parent_location_code: NULL for root nodes (level 1)
    source_id:     original numeric ID from the import dataset (for re-sync)
    includes_children flag lives on officer_scopes, not here.
    """
    __tablename__ = "locations"
    __table_args__ = (
        Index("idx_locations_country_level", "country_code", "level_number"),
        Index("idx_locations_parent", "parent_location_code"),
        {"schema": "ticketing"},
    )

    location_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    country_code: Mapped[str] = mapped_column(
        String(8),
        ForeignKey("ticketing.countries.country_code", ondelete="RESTRICT"),
        nullable=False,
    )
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_location_code: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("ticketing.locations.location_code", ondelete="SET NULL"),
        nullable=True,
    )
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    country: Mapped["Country"] = relationship("Country", back_populates="locations")
    translations: Mapped[list["LocationTranslation"]] = relationship(
        "LocationTranslation", back_populates="location", lazy="select", cascade="all, delete-orphan"
    )
    children: Mapped[list["Location"]] = relationship(
        "Location",
        primaryjoin="Location.parent_location_code == Location.location_code",
        foreign_keys="[Location.parent_location_code]",
        lazy="select",
    )

    def name(self, lang: str = "en") -> str | None:
        """Convenience: return name for a given lang, or None."""
        for t in self.translations:
            if t.lang_code == lang:
                return t.name
        return next((t.name for t in self.translations), None)


# ── Location translations ─────────────────────────────────────────────────────

class LocationTranslation(Base):
    """
    Multilingual names for each location node.
    (location_code, lang_code) is the composite PK.
    """
    __tablename__ = "location_translations"
    __table_args__ = (
        PrimaryKeyConstraint("location_code", "lang_code"),
        {"schema": "ticketing"},
    )

    location_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ticketing.locations.location_code", ondelete="CASCADE"),
        nullable=False,
    )
    lang_code: Mapped[str] = mapped_column(String(8), nullable=False)  # 'en', 'ne', 'fr' …
    name: Mapped[str] = mapped_column(Text, nullable=False)

    location: Mapped["Location"] = relationship("Location", back_populates="translations")
