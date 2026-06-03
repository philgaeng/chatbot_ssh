"""Shareable report links — internal (officers) and public (complainant-safe) snapshots (TP-05)."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ticketing.models.settings import Settings

SETTING_KEY = "report_share_links"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(db: Session) -> list[dict[str, Any]]:
    row = db.get(Settings, SETTING_KEY)
    if row and isinstance(row.value, list):
        return [x for x in row.value if isinstance(x, dict)]
    return []


def _save(db: Session, items: list[dict[str, Any]], updated_by: str) -> None:
    row = db.get(Settings, SETTING_KEY)
    if row:
        row.value = items
        row.updated_by = updated_by
    else:
        db.add(Settings(key=SETTING_KEY, value=items, updated_by=updated_by))
    db.commit()


def create_report_share(
    db: Session,
    *,
    name: str,
    report_kind: str,
    filters: dict[str, Any],
    rows_internal: list[dict[str, Any]],
    rows_public: list[dict[str, Any]],
    columns_internal: list[str],
    columns_public: list[str],
    created_by: str,
    library_item_id: str | None = None,
) -> dict[str, Any]:
    item = {
        "id": str(uuid.uuid4()),
        "name": name.strip() or "GRM report",
        "report_kind": report_kind,
        "filters": filters,
        "rows_internal": rows_internal,
        "rows_public": rows_public,
        "columns_internal": columns_internal,
        "columns_public": columns_public,
        "internal_token": secrets.token_urlsafe(24),
        "public_token": secrets.token_urlsafe(24),
        "created_by": created_by,
        "created_at": _now_iso(),
        "library_item_id": library_item_id,
    }
    items = _load(db)
    items.insert(0, item)
    # Keep last 50 shares
    _save(db, items[:50], created_by)
    return item


def get_share_by_token(db: Session, token: str) -> dict[str, Any] | None:
    for item in _load(db):
        if item.get("internal_token") == token or item.get("public_token") == token:
            return item
    return None


def list_shares_for_library(db: Session, library_item_id: str) -> list[dict[str, Any]]:
    return [x for x in _load(db) if x.get("library_item_id") == library_item_id]


def attach_tokens_to_library_items(db: Session, library_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shares = _load(db)
    by_lib: dict[str, dict[str, Any]] = {}
    for s in shares:
        lid = s.get("library_item_id")
        if lid and lid not in by_lib:
            by_lib[lid] = s
    out = []
    for item in library_items:
        enriched = dict(item)
        share = by_lib.get(item.get("id", ""))
        if share:
            enriched["internal_link_token"] = share.get("internal_token")
            enriched["public_link_token"] = share.get("public_token")
        out.append(enriched)
    return out
