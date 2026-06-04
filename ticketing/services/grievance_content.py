"""
Read and merge non-PII grievance fields from public.grievances (no is_temporary filter).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ticketing.constants.classification import (
    normalize_classification_status,
    officer_validation_required,
    classification_validated,
)
from ticketing.models.ticket import Ticket

logger = logging.getLogger(__name__)

_GRIEVANCE_SELECT = text("""
    SELECT
        grievance_id,
        grievance_summary,
        grievance_categories,
        grievance_description,
        grievance_location,
        grievance_classification_status,
        grievance_high_priority,
        grievance_sensitive_issue,
        grievance_modification_date
    FROM public.grievances
    WHERE grievance_id = :grievance_id
""")


def fetch_grievance_row(db: Session, grievance_id: str) -> Optional[dict[str, Any]]:
    row = db.execute(_GRIEVANCE_SELECT, {"grievance_id": grievance_id}).mappings().first()
    return dict(row) if row else None


def _coerce_categories(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, str):
        return val.strip() or None
    try:
        return json.dumps(val)
    except (TypeError, ValueError):
        return str(val)


def _prefer(new_val: Any, cached: Any) -> Any:
    if new_val is None:
        return cached
    if isinstance(new_val, str) and not new_val.strip():
        return cached
    return new_val


def merge_grievance_into_ticket(ticket: Ticket, g: dict[str, Any]) -> dict[str, Any]:
    """Return display fields merged from grievance row over ticket cache."""
    status = normalize_classification_status(g.get("grievance_classification_status"))
    summary = _prefer(g.get("grievance_summary"), ticket.grievance_summary)
    categories = _prefer(_coerce_categories(g.get("grievance_categories")), ticket.grievance_categories)
    description = g.get("grievance_description")
    location = _prefer(g.get("grievance_location"), ticket.grievance_location)
    return {
        "grievance_summary": summary,
        "grievance_categories": categories,
        "grievance_description": description,
        "grievance_location": location,
        "grievance_classification_status": status,
        "classification_validated_by_complainant": status == "complainant_confirmed",
        "classification_validated_by_officer": status == "officer_confirmed",
        "classification_officer_validation_required": officer_validation_required(status),
        "classification_validated": classification_validated(status),
    }


def refresh_ticket_cache_from_grievance(db: Session, ticket: Ticket, g: dict[str, Any]) -> bool:
    """Persist non-empty grievance fields onto ticketing.tickets when cache is stale."""
    merged = merge_grievance_into_ticket(ticket, g)
    changed = False
    for field in ("grievance_summary", "grievance_categories", "grievance_location"):
        new_val = merged.get(field)
        if new_val and getattr(ticket, field) != new_val:
            setattr(ticket, field, new_val)
            changed = True
    return changed
