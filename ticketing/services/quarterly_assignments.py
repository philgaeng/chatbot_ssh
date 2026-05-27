"""
Quarterly report assignments: up to N saved reports per role per calendar quarter.

Stored in ticketing.settings key ``quarterly_report_assignments`` (JSON list).
Local admins create assignments; Celery sends one email per assignment on schedule.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ticketing.models.settings import Settings
from ticketing.services.report_limits import load_report_limits, validate_recipient_roles

SETTING_ASSIGNMENTS = "quarterly_report_assignments"
SETTING_SCHEDULE = "report_schedule"

DEFAULT_SCHEDULE: dict[str, Any] = {
    "frequency": "quarterly",
    "day_of_month": 5,
}


def quarter_key_from_date(d: date | None = None) -> str:
    d = d or date.today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def quarter_date_range(quarter_key: str) -> tuple[date, date]:
    """Inclusive range for a calendar quarter key like 2026-Q1."""
    try:
        year_s, q_s = quarter_key.upper().split("-Q", 1)
        year = int(year_s)
        q = int(q_s)
        if q < 1 or q > 4:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid quarter_key: {quarter_key!r} (expected e.g. 2026-Q1)") from exc
    start_month = (q - 1) * 3 + 1
    d_from = date(year, start_month, 1)
    if q == 4:
        d_to = date(year, 12, 31)
    else:
        d_to = date(year, start_month + 3, 1) - timedelta(days=1)
    return d_from, d_to


def _get_list(db: Session) -> list[dict[str, Any]]:
    row = db.get(Settings, SETTING_ASSIGNMENTS)
    if not row or not isinstance(row.value, list):
        return []
    return [a for a in row.value if isinstance(a, dict)]


def _save_list(db: Session, items: list[dict[str, Any]], updated_by: str) -> None:
    row = db.get(Settings, SETTING_ASSIGNMENTS)
    if row:
        row.value = items
        row.updated_by_user_id = updated_by
    else:
        db.add(
            Settings(
                key=SETTING_ASSIGNMENTS,
                value=items,
                updated_by_user_id=updated_by,
            )
        )
    db.commit()


def load_schedule(db: Session) -> dict[str, Any]:
    row = db.get(Settings, SETTING_SCHEDULE)
    if row and isinstance(row.value, dict):
        return {**DEFAULT_SCHEDULE, **row.value}
    return dict(DEFAULT_SCHEDULE)


def save_schedule(db: Session, schedule: dict[str, Any], updated_by: str) -> dict[str, Any]:
    merged = {**DEFAULT_SCHEDULE, **schedule}
    row = db.get(Settings, SETTING_SCHEDULE)
    if row:
        row.value = merged
        row.updated_by_user_id = updated_by
    else:
        db.add(
            Settings(
                key=SETTING_SCHEDULE,
                value=merged,
                updated_by_user_id=updated_by,
            )
        )
    db.commit()
    return merged


def count_active_for_role(db: Session, quarter_key: str, role_key: str) -> int:
    return sum(
        1
        for a in _get_list(db)
        if a.get("quarter_key") == quarter_key
        and a.get("role_key") == role_key
        and a.get("active", True)
    )


def max_slots_per_role(db: Session) -> int:
    return int(load_report_limits(db).get("max_reports_per_role_per_quarter", 3))


def assert_slot_available(db: Session, quarter_key: str, role_key: str) -> None:
    cap = max_slots_per_role(db)
    n = count_active_for_role(db, quarter_key, role_key)
    if n >= cap:
        raise ValueError(
            f"Role {role_key} already has {cap} quarterly reports for {quarter_key}. "
            "Remove or replace one in Settings → Quarterly reports."
        )


def list_assignments(
    db: Session,
    *,
    quarter_key: str | None = None,
    role_key: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    items = _get_list(db)
    out = []
    for a in items:
        if quarter_key and a.get("quarter_key") != quarter_key:
            continue
        if role_key and a.get("role_key") != role_key:
            continue
        if active_only and not a.get("active", True):
            continue
        out.append(a)
    return sorted(out, key=lambda x: (x.get("role_key", ""), x.get("name", "")))


def get_assignment(db: Session, assignment_id: str) -> dict[str, Any] | None:
    for a in _get_list(db):
        if a.get("id") == assignment_id:
            return a
    return None


def create_assignment(
    db: Session,
    *,
    quarter_key: str,
    role_key: str,
    name: str,
    template: dict[str, Any],
    updated_by: str,
) -> dict[str, Any]:
    validate_recipient_roles(db, [role_key])
    assert_slot_available(db, quarter_key, role_key)
    assignment = {
        "id": str(uuid.uuid4()),
        "quarter_key": quarter_key,
        "role_key": role_key,
        "name": name.strip() or "Quarterly report",
        "template": template,
        "active": True,
    }
    items = _get_list(db)
    items.append(assignment)
    _save_list(db, items, updated_by)
    return assignment


def create_assignments_for_roles(
    db: Session,
    *,
    quarter_key: str,
    role_keys: list[str],
    name: str,
    template: dict[str, Any],
    updated_by: str,
) -> list[dict[str, Any]]:
    """Same template saved once per role (each consumes one slot)."""
    if not role_keys:
        raise ValueError("At least one role is required")
    validate_recipient_roles(db, role_keys)
    for rk in role_keys:
        assert_slot_available(db, quarter_key, rk)
    created = []
    items = _get_list(db)
    for role_key in role_keys:
        assignment = {
            "id": str(uuid.uuid4()),
            "quarter_key": quarter_key,
            "role_key": role_key,
            "name": name.strip() or "Quarterly report",
            "template": template,
            "active": True,
        }
        items.append(assignment)
        created.append(assignment)
    _save_list(db, items, updated_by)
    return created


def update_assignment(
    db: Session,
    assignment_id: str,
    *,
    name: str | None = None,
    template: dict[str, Any] | None = None,
    active: bool | None = None,
    updated_by: str,
) -> dict[str, Any]:
    items = _get_list(db)
    for a in items:
        if a.get("id") != assignment_id:
            continue
        if name is not None:
            a["name"] = name.strip() or a.get("name", "Quarterly report")
        if template is not None:
            a["template"] = template
        if active is not None:
            a["active"] = active
        _save_list(db, items, updated_by)
        return a
    raise ValueError(f"Assignment not found: {assignment_id}")


def delete_assignment(db: Session, assignment_id: str, updated_by: str) -> None:
    items = _get_list(db)
    new_items = [a for a in items if a.get("id") != assignment_id]
    if len(new_items) == len(items):
        raise ValueError(f"Assignment not found: {assignment_id}")
    _save_list(db, new_items, updated_by)


def plan_summary(db: Session, quarter_key: str) -> dict[str, Any]:
    """Per-role slot usage for UI."""
    limits = load_report_limits(db)
    cap = int(limits.get("max_reports_per_role_per_quarter", 3))
    assignments = list_assignments(db, quarter_key=quarter_key, active_only=True)
    by_role: dict[str, list[dict]] = {}
    for a in assignments:
        rk = a.get("role_key", "")
        by_role.setdefault(rk, []).append(a)
    roles_summary = [
        {
            "role_key": rk,
            "count": len(rows),
            "max": cap,
            "assignments": rows,
        }
        for rk, rows in sorted(by_role.items())
    ]
    return {
        "quarter_key": quarter_key,
        "max_per_role": cap,
        "schedule": load_schedule(db),
        "roles": roles_summary,
    }
