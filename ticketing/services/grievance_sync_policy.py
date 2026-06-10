"""Pure helpers for grievance_sync backfill timing (no Celery / DB imports)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

_DEFAULT_BACKFILL_GRACE_SECONDS = 180


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def grievance_age_seconds(creation_date: Optional[datetime], *, now: Optional[datetime] = None) -> float:
    """Age of grievance in seconds; 0 when creation_date missing."""
    if not creation_date:
        return 0.0
    ref = now or datetime.now(timezone.utc)
    return max(0.0, (ref - _as_utc(creation_date)).total_seconds())


def should_attempt_backfill(
    grievance_row: dict,
    *,
    now: Optional[datetime] = None,
    grace_seconds: int = _DEFAULT_BACKFILL_GRACE_SECONDS,
) -> bool:
    """True when sync may create a ticket because the webhook likely never ran."""
    grace = max(60, grace_seconds)
    return grievance_age_seconds(grievance_row.get("grievance_creation_date"), now=now) >= grace
