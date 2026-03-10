"""
Helpers for Modify grievance – Add missing info (Flow B).

Spec 13: missing fields order and UI pagination (≤4 on one screen; >4 → 3 + See more).
"""

from typing import Any, Dict, List, Tuple

# Order of contact/location fields for "Add missing info" (Spec 13)
MODIFY_CONTACT_FIELD_ORDER = [
    "complainant_phone",
    "complainant_full_name",
    "complainant_province",
    "complainant_district",
    "complainant_municipality",
    "complainant_village",
    "complainant_ward",
    "complainant_address",
    "complainant_email",
]

# Slot names that may be stored with _temp / _confirmed variants in DB or slots
SLOT_TO_SOURCE_KEYS: Dict[str, List[str]] = {
    "complainant_phone": ["complainant_phone"],
    "complainant_full_name": ["complainant_full_name"],
    "complainant_province": ["complainant_province"],
    "complainant_district": ["complainant_district"],
    "complainant_municipality": ["complainant_municipality"],
    "complainant_village": ["complainant_village"],
    "complainant_ward": ["complainant_ward"],
    "complainant_address": ["complainant_address"],
    "complainant_email": ["complainant_email", "complainant_email_temp"],
}


def _is_empty(val: Any) -> bool:
    """Treat None, empty string, and SKIP_VALUE-style as empty."""
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def get_missing_contact_fields(slots_or_complainant: Dict[str, Any]) -> List[str]:
    """
    Return the ordered list of contact/location field names that are missing
    (empty or not provided). Uses MODIFY_CONTACT_FIELD_ORDER.

    slots_or_complainant: dict of slot names -> values (e.g. from tracker or DB row).
    """
    missing: List[str] = []
    for field in MODIFY_CONTACT_FIELD_ORDER:
        keys = SLOT_TO_SOURCE_KEYS.get(field, [field])
        value = None
        for k in keys:
            if k in slots_or_complainant:
                value = slots_or_complainant[k]
                break
        if _is_empty(value):
            missing.append(field)
    return missing


def get_missing_fields_page(
    missing_fields: List[str],
    page_index: int = 0,
) -> Tuple[List[str], bool]:
    """
    Return one "page" of missing fields for the UI (Spec 13).

    - If ≤4 missing: return all on one page, has_more=False.
    - If >4: first page returns first 3 + has_more=True; subsequent pages
      return up to 3 each until ≤4 remain, then return all remaining.

    Returns:
        (list of field names for this page, has_more)
    """
    if not missing_fields:
        return [], False
    if len(missing_fields) <= 4:
        return missing_fields, False
    # >4: page 0 = first 3; later pages = next 3 from rest until remainder ≤4
    if page_index == 0:
        return missing_fields[:3], True
    rest = missing_fields[3:]
    chunk_start = (page_index - 1) * 3
    if chunk_start >= len(rest):
        return [], False
    chunk = rest[chunk_start : chunk_start + 3]
    remaining_after = rest[chunk_start + 3 :]
    has_more = len(remaining_after) > 0
    return chunk, has_more
