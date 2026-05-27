"""
Report limits — super-admin JSON (ticketing.settings.report_limits).

Slot cap for quarterly assignments is enforced at save time (local admin).
Export row cap enforced on download endpoints.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.settings import Settings

SETTING_KEY = "report_limits"

DEFAULT_REPORT_LIMITS: dict[str, Any] = {
    "max_export_rows": 100,
    "max_exports_per_user_per_hour": 10,
    "max_reports_per_role_per_quarter": 3,
    "quarterly_email_enabled": True,
    "allowed_recipient_roles": [
        "adb_national_project_director",
        "adb_hq_safeguards",
        "adb_hq_project",
        "mopit_rep",
        "dor_rep",
    ],
}


def _merge_limits(raw: dict | None) -> dict[str, Any]:
    out = dict(DEFAULT_REPORT_LIMITS)
    if raw:
        out.update({k: v for k, v in raw.items() if v is not None})
    return out


def load_report_limits(db: Session) -> dict[str, Any]:
    row = db.get(Settings, SETTING_KEY)
    if not row or not isinstance(row.value, dict):
        return dict(DEFAULT_REPORT_LIMITS)
    return _merge_limits(row.value)


def save_report_limits(db: Session, value: dict[str, Any], updated_by: str) -> dict[str, Any]:
    merged = _merge_limits(value)
    _validate_limits_shape(merged)
    row = db.get(Settings, SETTING_KEY)
    if row:
        row.value = merged
        row.updated_by_user_id = updated_by
    else:
        db.add(
            Settings(
                key=SETTING_KEY,
                value=merged,
                updated_by_user_id=updated_by,
            )
        )
    db.commit()
    return merged


def _validate_limits_shape(limits: dict[str, Any]) -> None:
    for key in ("max_export_rows", "max_exports_per_user_per_hour", "max_reports_per_role_per_quarter"):
        v = limits.get(key)
        if not isinstance(v, int) or v < 1:
            raise ValueError(f"{key} must be a positive integer")
    if not isinstance(limits.get("quarterly_email_enabled"), bool):
        raise ValueError("quarterly_email_enabled must be true or false")
    allowed = limits.get("allowed_recipient_roles")
    if allowed is not None and not isinstance(allowed, list):
        raise ValueError("allowed_recipient_roles must be a list of role keys or null")


def validate_recipient_roles(db: Session, role_keys: list[str]) -> None:
    allowed = load_report_limits(db).get("allowed_recipient_roles")
    if allowed:
        bad = [r for r in role_keys if r not in allowed]
        if bad:
            raise ValueError(
                f"Recipient roles not permitted: {', '.join(bad)}. "
                f"Allowed: {', '.join(allowed)}"
            )


def check_export_rate_limit(db: Session, actor_user_id: str) -> None:
    limits = load_report_limits(db)
    cap = limits["max_exports_per_user_per_hour"]
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    count = db.execute(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(
            AdminAuditLog.actor_user_id == actor_user_id,
            AdminAuditLog.action == "report_export",
            AdminAuditLog.created_at >= since,
        )
    ).scalar_one()
    if count >= cap:
        raise ValueError(
            f"Export limit reached ({cap} per hour). Try again later or narrow your filters."
        )


def log_report_export(db: Session, actor_user_id: str, *, export_kind: str, row_count: int) -> None:
    db.add(
        AdminAuditLog(
            actor_user_id=actor_user_id,
            action="report_export",
            payload={"kind": export_kind, "row_count": row_count},
        )
    )
    db.commit()


def quarterly_email_enabled(db: Session) -> bool:
    return bool(load_report_limits(db).get("quarterly_email_enabled", True))


def log_assignment_sent(
    db: Session,
    *,
    actor_user_id: str,
    assignment_id: str,
    quarter_key: str,
    role_key: str,
    recipient_emails: list[str],
    ticket_count: int,
    template_name: str,
) -> None:
    normalized = sorted({(e or "").strip().lower() for e in recipient_emails if e and "@" in e})
    db.add(
        AdminAuditLog(
            actor_user_id=actor_user_id,
            action="quarterly_assignment_sent",
            payload={
                "assignment_id": assignment_id,
                "quarter_key": quarter_key,
                "role_key": role_key,
                "recipient_emails": normalized,
                "ticket_count": ticket_count,
                "template_name": template_name,
            },
        )
    )
    db.commit()
