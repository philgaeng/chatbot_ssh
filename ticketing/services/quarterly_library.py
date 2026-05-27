"""Named report definitions for quarterly planning (reusable across roles)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ticketing.models.settings import Settings

SETTING_LIBRARY = "quarterly_report_library"


def list_library(db: Session) -> list[dict[str, Any]]:
    row = db.get(Settings, SETTING_LIBRARY)
    if row and isinstance(row.value, list) and row.value:
        return [x for x in row.value if isinstance(x, dict)]
    bootstrapped = _bootstrap_library_from_assignments(db)
    if bootstrapped:
        return bootstrapped
    return []


def _bootstrap_library_from_assignments(db: Session) -> list[dict[str, Any]]:
    """One-time: derive library entries from existing quarterly assignments."""
    from ticketing.services.quarterly_assignments import _get_list as _assignments

    assignments = _assignments(db)
    if not assignments:
        return []
    by_name: dict[str, dict[str, Any]] = {}
    for a in assignments:
        name = (a.get("name") or "Quarterly report").strip()
        if name not in by_name:
            by_name[name] = {
                "id": str(uuid.uuid4()),
                "name": name,
                "template": a.get("template") or {},
            }
    items = list(by_name.values())
    db.add(Settings(key=SETTING_LIBRARY, value=items))
    db.commit()
    return items


def get_library_item(db: Session, item_id: str) -> dict[str, Any] | None:
    for item in list_library(db):
        if item.get("id") == item_id:
            return item
    return None


def create_library_item(
    db: Session,
    *,
    name: str,
    template: dict[str, Any],
    updated_by: str,
) -> dict[str, Any]:
    item = {
        "id": str(uuid.uuid4()),
        "name": name.strip() or "Untitled report",
        "template": template,
    }
    items = list_library(db)
    items.append(item)
    _save(db, items, updated_by)
    return item


def update_library_item(
    db: Session,
    item_id: str,
    *,
    name: str | None = None,
    template: dict[str, Any] | None = None,
    updated_by: str,
) -> dict[str, Any]:
    items = list_library(db)
    for item in items:
        if item.get("id") != item_id:
            continue
        if name is not None:
            item["name"] = name.strip() or item.get("name", "Untitled report")
        if template is not None:
            item["template"] = template
        _save(db, items, updated_by)
        return item
    raise ValueError(f"Report not found: {item_id}")


def delete_library_item(db: Session, item_id: str, updated_by: str) -> None:
    items = list_library(db)
    new_items = [x for x in items if x.get("id") != item_id]
    if len(new_items) == len(items):
        raise ValueError(f"Report not found: {item_id}")
    _save(db, new_items, updated_by)


def _save(db: Session, items: list[dict[str, Any]], updated_by: str) -> None:
    row = db.get(Settings, SETTING_LIBRARY)
    if row:
        row.value = items
        row.updated_by_user_id = updated_by
    else:
        db.add(
            Settings(
                key=SETTING_LIBRARY,
                value=items,
                updated_by_user_id=updated_by,
            )
        )
    db.commit()
