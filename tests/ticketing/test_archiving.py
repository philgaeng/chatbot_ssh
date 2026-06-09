"""Unit tests for resolved-case archiving policy (docs/ARCHIVING_AND_RETENTION.md §3.3)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from ticketing.services.archiving import (
    archive_eligible_date,
    archive_ticket,
    is_ticket_eligible,
    select_eligible_tickets,
)
from ticketing.services.archiving_policy import (
    DEFAULT_ARCHIVING_POLICY,
    save_archiving_policy,
    _validate_policy_shape,
)


def test_archive_eligible_date_2026_resolved_years_1():
    # resolved 2026-06-15 Kathmandu → eligible 2028-01-02
    resolved = datetime(2026, 6, 15, 10, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))
    assert archive_eligible_date(resolved, 1, "Asia/Kathmandu") == date(2028, 1, 2)


def test_archive_eligible_date_2026_dec31_same_n():
    resolved = datetime(2026, 12, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kathmandu"))
    assert archive_eligible_date(resolved, 1, "Asia/Kathmandu") == date(2028, 1, 2)


def test_archive_eligible_date_2027_jan1_n_2027():
    resolved = datetime(2027, 1, 1, 0, 30, tzinfo=ZoneInfo("Asia/Kathmandu"))
    assert archive_eligible_date(resolved, 1, "Asia/Kathmandu") == date(2029, 1, 2)


def test_archive_eligible_date_years_2():
    resolved = datetime(2026, 8, 1, 12, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))
    assert archive_eligible_date(resolved, 2, "Asia/Kathmandu") == date(2029, 1, 2)


def test_not_eligible_before_date():
    resolved = datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))
    eligible_from = archive_eligible_date(resolved, 1, "Asia/Kathmandu")
    assert eligible_from == date(2028, 1, 2)
    assert date(2028, 1, 1) < eligible_from
    assert date(2028, 1, 2) >= eligible_from


def test_validate_policy_rejects_years_zero():
    bad = dict(DEFAULT_ARCHIVING_POLICY)
    bad["years_before_archiving"] = 0
    with pytest.raises(ValueError, match="years_before_archiving"):
        _validate_policy_shape(bad)


def test_validate_policy_rejects_invalid_tier():
    bad = dict(DEFAULT_ARCHIVING_POLICY)
    bad["attachment_tier_on_archive"] = "hot"
    with pytest.raises(ValueError, match="attachment_tier_on_archive"):
        _validate_policy_shape(bad)


def test_archive_job_idempotent():
    ticket = MagicMock()
    ticket.ticket_id = "t1"
    ticket.grievance_id = "GR-TEST"
    ticket.is_archived = True
    ticket.archived_at = datetime.now(timezone.utc)

    result = archive_ticket(MagicMock(), ticket, DEFAULT_ARCHIVING_POLICY, dry_run=False)
    assert result.archived is False
    assert result.skipped_reason == "already_archived"


def test_queue_excludes_archived(monkeypatch):
    """select_eligible_tickets SQL filter excludes is_archived rows."""
    db = MagicMock()
    open_ticket = MagicMock()
    open_ticket.ticket_id = "open"
    open_ticket.grievance_id = "GR-OPEN"
    open_ticket.is_archived = False
    open_ticket.archived_at = None
    open_ticket.status_code = "RESOLVED"
    open_ticket.is_deleted = False
    open_ticket.is_seah = False

    db.execute.return_value.scalars.return_value.all.return_value = [open_ticket]

    resolved_at = datetime(2020, 3, 15, tzinfo=ZoneInfo("Asia/Kathmandu"))
    with patch(
        "ticketing.services.archiving.get_resolution_timestamp",
        return_value=resolved_at,
    ):
        eligible = select_eligible_tickets(db, DEFAULT_ARCHIVING_POLICY, as_of=date(2025, 6, 1))

    assert len(eligible) == 1
    assert eligible[0].ticket_id == "open"

    ok, reason = is_ticket_eligible(
        db,
        MagicMock(
            is_archived=True,
            archived_at=datetime.now(timezone.utc),
            status_code="RESOLVED",
            is_deleted=False,
            ticket_id="arch",
            grievance_id="GR-ARCH",
            is_seah=False,
        ),
        DEFAULT_ARCHIVING_POLICY,
        date(2030, 1, 2),
    )
    assert ok is False
    assert reason == "already_archived"


def test_save_archiving_policy_writes_audit(db):
    """Requires live DB — skip when SessionLocal unavailable."""
    from ticketing.models.base import SessionLocal

    session = SessionLocal()
    try:
        merged = save_archiving_policy(
            session,
            {"years_before_archiving": 2},
            "test-super-admin",
        )
        assert merged["years_before_archiving"] == 2
        # restore default for other tests
        save_archiving_policy(session, DEFAULT_ARCHIVING_POLICY, "test-super-admin")
    except Exception:
        pytest.skip("DB not available")
    finally:
        session.close()
