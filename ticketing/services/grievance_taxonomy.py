"""Grievance category options from public.grievance_classification_taxonomy (read-only)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from ticketing.models.base import engine

logger = logging.getLogger(__name__)

_TAXONOMY_SELECT = text("""
    SELECT
        category_key,
        classification,
        generic_grievance_name,
        high_priority
    FROM public.grievance_classification_taxonomy
    ORDER BY classification, category_key
""")


def list_grievance_category_options() -> list[dict[str, Any]]:
    """Return sorted category options for officer classification UI (TP-14)."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(_TAXONOMY_SELECT).mappings().all()
    except Exception as exc:
        logger.warning("list_grievance_category_options failed: %s", exc)
        return []

    return [
        {
            "key": row["category_key"],
            "label": row["category_key"],
            "classification": row["classification"] or "",
            "generic_name": row["generic_grievance_name"] or "",
            "high_priority": bool(row["high_priority"]),
        }
        for row in rows
    ]
