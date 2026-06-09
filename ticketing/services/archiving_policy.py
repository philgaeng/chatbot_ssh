"""
Archiving policy — super-admin JSON (ticketing.settings.archiving_policy).

See docs/ARCHIVING_AND_RETENTION.md §4.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.settings import Settings

SETTING_KEY = "archiving_policy"

DEFAULT_ARCHIVING_POLICY: dict[str, Any] = {
    "enabled": True,
    "years_before_archiving": 1,
    "archive_run_month": 1,
    "archive_run_day": 2,
    "timezone": "Asia/Kathmandu",
    "attachment_tier_on_archive": "none",
    "allow_complainant_download_when_archived": False,
    "seah_years_before_archiving": None,
}

_VALID_TIERS = frozenset({"none", "cold", "glacier"})


def _merge_policy(raw: dict | None) -> dict[str, Any]:
    out = dict(DEFAULT_ARCHIVING_POLICY)
    if raw:
        out.update({k: v for k, v in raw.items() if v is not None})
    return out


def load_archiving_policy(db: Session) -> dict[str, Any]:
    row = db.get(Settings, SETTING_KEY)
    if not row or not isinstance(row.value, dict):
        return dict(DEFAULT_ARCHIVING_POLICY)
    return _merge_policy(row.value)


def save_archiving_policy(
    db: Session,
    value: dict[str, Any],
    updated_by: str,
) -> dict[str, Any]:
    merged = _merge_policy(value)
    _validate_policy_shape(merged)
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
    db.add(
        AdminAuditLog(
            actor_user_id=updated_by,
            action="archiving_policy_updated",
            payload={"key": SETTING_KEY, "value": merged},
        )
    )
    db.commit()
    return merged


def _validate_policy_shape(policy: dict[str, Any]) -> None:
    years = policy.get("years_before_archiving")
    if not isinstance(years, int) or years < 1:
        raise ValueError("years_before_archiving must be an integer >= 1")

    month = policy.get("archive_run_month")
    day = policy.get("archive_run_day")
    if not isinstance(month, int) or not (1 <= month <= 12):
        raise ValueError("archive_run_month must be an integer between 1 and 12")
    if not isinstance(day, int) or not (1 <= day <= 31):
        raise ValueError("archive_run_day must be an integer between 1 and 31")

    tz = policy.get("timezone")
    if not isinstance(tz, str) or not tz.strip():
        raise ValueError("timezone must be a non-empty string")

    tier = policy.get("attachment_tier_on_archive")
    if tier not in _VALID_TIERS:
        raise ValueError(f"attachment_tier_on_archive must be one of: {', '.join(sorted(_VALID_TIERS))}")

    if not isinstance(policy.get("enabled"), bool):
        raise ValueError("enabled must be true or false")

    if not isinstance(policy.get("allow_complainant_download_when_archived"), bool):
        raise ValueError("allow_complainant_download_when_archived must be true or false")

    seah_years = policy.get("seah_years_before_archiving")
    if seah_years is not None:
        if not isinstance(seah_years, int) or seah_years < 1:
            raise ValueError("seah_years_before_archiving must be null or an integer >= 1")
