"""Unit tests for grievance_sync Option A (update-only + delayed backfill)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ticketing.services.grievance_sync_policy import (
    grievance_age_seconds,
    should_attempt_backfill,
)
from ticketing.services.ticket_intake import build_backfill_payload_from_grievance_row


def test_grievance_age_seconds_with_timezone_naive():
    created = datetime(2026, 6, 10, 12, 0, 0)
    now = datetime(2026, 6, 10, 12, 3, 0, tzinfo=timezone.utc)
    assert grievance_age_seconds(created, now=now) == 180.0


def test_should_attempt_backfill_false_within_grace():
    created = datetime.now(timezone.utc) - timedelta(seconds=30)
    g = {"grievance_id": "G-1", "grievance_creation_date": created}
    assert should_attempt_backfill(g, grace_seconds=180) is False


def test_should_attempt_backfill_true_after_grace():
    created = datetime.now(timezone.utc) - timedelta(seconds=300)
    g = {"grievance_id": "G-1", "grievance_creation_date": created}
    assert should_attempt_backfill(g, grace_seconds=180) is True


def test_build_backfill_payload_uses_complainant_location():
    g = {
        "grievance_id": "B-GR-TEST-1",
        "complainant_id": "B-CM-1",
        "grievance_sensitive_issue": False,
        "grievance_high_priority": False,
        "grievance_summary": "Dust on road",
        "grievance_categories": '["Road Hazard - Dust"]',
        "grievance_location": "Morang",
        "location_code": "P1_MOR",
    }
    payload = build_backfill_payload_from_grievance_row(g)
    assert payload.grievance_id == "B-GR-TEST-1"
    assert payload.location_code == "P1_MOR"
    assert payload.organization_id == "DOR"
    assert payload.package_id is None


def test_build_backfill_payload_strips_not_provided_location():
    g = {
        "grievance_id": "B-GR-TEST-2",
        "grievance_sensitive_issue": False,
        "grievance_high_priority": False,
        "location_code": "Not provided",
    }
    payload = build_backfill_payload_from_grievance_row(g)
    assert payload.location_code is None
