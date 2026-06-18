"""Unit tests for intake ID ensure helpers."""

from unittest.mock import MagicMock

from backend.actions.grievance_intake.ensure_records import (
    ensure_intake_records_for_attachment,
    resolve_intake_slot_ids,
)


def test_resolve_intake_slot_ids_generates_when_missing():
    db = MagicMock()
    db.generate_grievance_id.return_value = "GR-NEW-B"
    db.generate_complainant_id.return_value = "CP-NEW-B"
    gid, cid = resolve_intake_slot_ids(
        db,
        existing_grievance_id=None,
        existing_complainant_id=None,
    )
    assert gid == "GR-NEW-B"
    assert cid == "CP-NEW-B"


def test_resolve_intake_slot_ids_reuse_only_when_requested():
    db = MagicMock()
    gid, cid = resolve_intake_slot_ids(
        db,
        existing_grievance_id="GR-EXIST-B",
        existing_complainant_id="CP-EXIST-B",
        reuse_existing=True,
    )
    assert gid == "GR-EXIST-B"
    assert cid == "CP-EXIST-B"
    db.generate_grievance_id.assert_not_called()


def test_resolve_intake_slot_ids_ignores_existing_without_reuse_flag():
    db = MagicMock()
    db.generate_grievance_id.return_value = "GR-FRESH-B"
    db.generate_complainant_id.return_value = "CP-FRESH-B"
    gid, cid = resolve_intake_slot_ids(
        db,
        existing_grievance_id="GR-EXIST-B",
        existing_complainant_id="CP-EXIST-B",
        reuse_existing=False,
    )
    assert gid == "GR-FRESH-B"
    assert cid == "CP-FRESH-B"


def test_ensure_intake_records_creates_stub_rows():
    db = MagicMock()
    db.generate_grievance_id.return_value = "GR-STUB-B"
    db.generate_complainant_id.return_value = "CP-STUB-B"
    result = ensure_intake_records_for_attachment(db)
    assert result["grievance_id"] == "GR-STUB-B"
    assert result["complainant_id"] == "CP-STUB-B"
    db.create_or_update_complainant.assert_called_once()
    db.create_or_update_grievance.assert_called_once()
