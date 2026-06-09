"""
Grievance classification catalog — super-admin JSON (ticketing.settings.grievance_categories).

Source of truth for officer UI and synced to public.grievance_classification_taxonomy
so the chatbot LLM classifier uses the same taxonomy (see backend/config/constants.py).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.settings import Settings

SETTING_KEY = "grievance_categories"

_DEFAULT_JSON_PATH = (
    Path(__file__).resolve().parent.parent / "constants" / "grievance_categories_default.json"
)

_STRING_FIELDS = (
    "generic_grievance_name",
    "generic_grievance_name_ne",
    "short_description",
    "short_description_ne",
    "classification",
    "classification_ne",
    "description",
    "description_ne",
    "follow_up_question_description",
    "follow_up_question_description_ne",
    "follow_up_question_quantification",
    "follow_up_question_quantification_ne",
)


def derive_category_key(classification: str, generic_grievance_name: str) -> str:
    """Match dev-scripts/seed_reference_data.py and backend/config/constants.py."""
    return (
        f"{classification.replace('-', ' ').title()} - "
        f"{generic_grievance_name.replace('-', ' ').title()}"
    )


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def normalize_category_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one catalog entry; compute category_key when omitted."""
    classification = str(raw.get("classification") or "").strip()
    generic = str(raw.get("generic_grievance_name") or "").strip()
    if not classification or not generic:
        raise ValueError("Each category requires classification and generic_grievance_name")

    category_key = str(raw.get("category_key") or "").strip()
    if not category_key:
        category_key = derive_category_key(classification, generic)

    out: dict[str, Any] = {"category_key": category_key}
    for field in _STRING_FIELDS:
        out[field] = str(raw.get(field) or "")
    out["high_priority"] = _coerce_bool(raw.get("high_priority"))
    return out


def load_default_catalog() -> dict[str, Any]:
    """Bundled defaults from grievances_categorization_v1.1.csv (committed JSON)."""
    data = json.loads(_DEFAULT_JSON_PATH.read_text(encoding="utf-8"))
    categories = [normalize_category_entry(c) for c in data.get("categories", [])]
    return {"categories": categories}


def _normalize_catalog(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw or not isinstance(raw.get("categories"), list):
        return load_default_catalog()
    return {"categories": [normalize_category_entry(c) for c in raw["categories"] if isinstance(c, dict)]}


def _load_from_public_taxonomy(conn) -> dict[str, Any] | None:
    rows = conn.execute(
        text(
            """
            SELECT category_key, generic_grievance_name, generic_grievance_name_ne,
                   short_description, short_description_ne, classification, classification_ne,
                   description, description_ne, follow_up_question_description,
                   follow_up_question_description_ne, follow_up_question_quantification,
                   follow_up_question_quantification_ne, high_priority
            FROM public.grievance_classification_taxonomy
            ORDER BY classification, category_key
            """
        )
    ).mappings().all()
    if not rows:
        return None
    categories = []
    for row in rows:
        rd = dict(row)
        rd["high_priority"] = _coerce_bool(rd.get("high_priority"))
        categories.append(normalize_category_entry(rd))
    return {"categories": categories}


def load_grievance_categories_catalog(db: Session) -> dict[str, Any]:
    """Settings row → public taxonomy → bundled default JSON."""
    row = db.get(Settings, SETTING_KEY)
    if row and isinstance(row.value, dict) and row.value.get("categories"):
        return _normalize_catalog(row.value)

    try:
        from_public = _load_from_public_taxonomy(db)
        if from_public:
            return from_public
    except Exception:
        pass

    return load_default_catalog()


def _validate_catalog_shape(catalog: dict[str, Any]) -> None:
    categories = catalog.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError("categories must be a non-empty array")

    seen_keys: set[str] = set()
    for idx, entry in enumerate(categories):
        if not isinstance(entry, dict):
            raise ValueError(f"categories[{idx}] must be an object")
        key = entry.get("category_key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"categories[{idx}] is missing category_key")
        if key in seen_keys:
            raise ValueError(f"Duplicate category_key: {key}")
        seen_keys.add(key)


def sync_categories_to_public_taxonomy(db: Session, categories: list[dict[str, Any]]) -> None:
    """Replace public.grievance_classification_taxonomy rows (chatbot LLM reads this table)."""
    db.execute(text("DELETE FROM public.grievance_classification_taxonomy"))
    insert_sql = text(
        """
        INSERT INTO public.grievance_classification_taxonomy (
            category_key, generic_grievance_name, generic_grievance_name_ne,
            short_description, short_description_ne, classification, classification_ne,
            description, description_ne, follow_up_question_description,
            follow_up_question_description_ne, follow_up_question_quantification,
            follow_up_question_quantification_ne, high_priority
        ) VALUES (
            :category_key, :generic_grievance_name, :generic_grievance_name_ne,
            :short_description, :short_description_ne, :classification, :classification_ne,
            :description, :description_ne, :follow_up_question_description,
            :follow_up_question_description_ne, :follow_up_question_quantification,
            :follow_up_question_quantification_ne, :high_priority
        )
        """
    )
    for entry in categories:
        db.execute(insert_sql, entry)


def save_grievance_categories_catalog(
    db: Session,
    value: dict[str, Any],
    updated_by: str,
    *,
    sync_public: bool = True,
) -> dict[str, Any]:
    raw_categories = value.get("categories") if isinstance(value, dict) else None
    if not isinstance(raw_categories, list):
        raise ValueError("value must be an object with a categories array")

    normalized = {"categories": [normalize_category_entry(c) for c in raw_categories]}
    _validate_catalog_shape(normalized)

    row = db.get(Settings, SETTING_KEY)
    if row:
        row.value = normalized
        row.updated_by_user_id = updated_by
    else:
        db.add(
            Settings(
                key=SETTING_KEY,
                value=normalized,
                updated_by_user_id=updated_by,
            )
        )

    if sync_public:
        sync_categories_to_public_taxonomy(db, normalized["categories"])

    db.add(
        AdminAuditLog(
            actor_user_id=updated_by,
            action="grievance_categories_updated",
            payload={
                "key": SETTING_KEY,
                "category_count": len(normalized["categories"]),
            },
        )
    )
    db.commit()
    return normalized
