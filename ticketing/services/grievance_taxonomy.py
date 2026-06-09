"""Grievance category options for officer classification UI (TP-14)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def list_grievance_category_options(db: Session | None = None) -> list[dict[str, Any]]:
    """Return sorted category options from settings catalog (fallback: public DB / defaults)."""
    try:
        if db is None:
            from ticketing.models.base import SessionLocal

            with SessionLocal() as session:
                return _options_from_catalog(session)
        return _options_from_catalog(db)
    except Exception as exc:
        logger.warning("list_grievance_category_options failed: %s", exc)
        return []


def _options_from_catalog(db: Session) -> list[dict[str, Any]]:
    from ticketing.services.grievance_categories_catalog import load_grievance_categories_catalog

    catalog = load_grievance_categories_catalog(db)
    categories = catalog.get("categories") or []
    sorted_entries = sorted(
        categories,
        key=lambda c: (c.get("classification") or "", c.get("category_key") or ""),
    )
    return [
        {
            "key": entry["category_key"],
            "label": entry["category_key"],
            "classification": entry.get("classification") or "",
            "generic_name": entry.get("generic_grievance_name") or "",
            "high_priority": bool(entry.get("high_priority")),
        }
        for entry in sorted_entries
        if entry.get("category_key")
    ]
