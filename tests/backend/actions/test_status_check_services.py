"""Unit tests for status-check service modules."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backend.actions.services.status_check import name_matching, phone_retrieval
from backend.config.constants import DEFAULT_VALUES


def _grievance(gid: str, name: str, status: str, created: datetime) -> dict:
    return {
        "grievance_id": gid,
        "complainant_full_name": name,
        "grievance_status": status,
        "grievance_creation_date": created,
    }


def test_select_grievances_orders_open_before_closed():
    sample = [
        _grievance("G1", "John Smith", "CLOSED", datetime(2024, 1, 10)),
        _grievance("G2", "John Smith", "OPEN", datetime(2024, 1, 20)),
        _grievance("G3", "Jane Doe", "OPEN", datetime(2024, 1, 25)),
    ]
    result = name_matching.select_grievances_from_full_name_list(
        ["John Smith"], sample, None
    )
    assert len(result) == 2
    assert result[0]["grievance_status"] == "OPEN"
    assert result[1]["grievance_status"] == "CLOSED"


def test_convert_grievance_datetime_to_string():
    rows = [_grievance("G1", "A", "OPEN", datetime(2024, 1, 1))]
    out = name_matching.convert_grievance_datetime_to_string(rows)
    assert out[0]["grievance_creation_date"] == "2024-01-01T00:00:00"


def test_extract_unique_full_names_excludes_not_provided():
    not_provided = DEFAULT_VALUES["NOT_PROVIDED"]
    rows = [
        _grievance("G1", "Alice", "OPEN", datetime(2024, 1, 1)),
        _grievance("G2", not_provided, "OPEN", datetime(2024, 1, 2)),
    ]
    names = name_matching.extract_unique_full_names_from_list(
        rows, not_provided=not_provided
    )
    assert names == ["Alice"]


def test_retrieve_grievances_by_phone_skip():
    tracker = MagicMock()
    tracker.get_slot.return_value = DEFAULT_VALUES["SKIP_VALUE"]
    result = phone_retrieval.retrieve_grievances_by_phone(
        tracker,
        MagicMock(),
        skip_value=DEFAULT_VALUES["SKIP_VALUE"],
        not_provided=DEFAULT_VALUES["NOT_PROVIDED"],
    )
    assert result["status_check_retrieve_grievances"] == DEFAULT_VALUES["SKIP_VALUE"]


def test_retrieve_grievances_by_phone_single_match():
    tracker = MagicMock()
    tracker.get_slot.return_value = "+9779800000000"
    db = MagicMock()
    db.get_grievance_by_complainant_phone.return_value = [
        _grievance("G1", "Alice", "OPEN", datetime(2024, 1, 1)),
    ]
    result = phone_retrieval.retrieve_grievances_by_phone(
        tracker,
        db,
        skip_value=DEFAULT_VALUES["SKIP_VALUE"],
        not_provided=DEFAULT_VALUES["NOT_PROVIDED"],
    )
    assert result["status_check_grievance_id_selected"] == "G1"


def test_retrieve_grievances_by_phone_no_results():
    tracker = MagicMock()
    tracker.get_slot.return_value = "+9779800000001"
    db = MagicMock()
    db.get_grievance_by_complainant_phone.return_value = []
    result = phone_retrieval.retrieve_grievances_by_phone(
        tracker,
        db,
        skip_value=DEFAULT_VALUES["SKIP_VALUE"],
        not_provided=DEFAULT_VALUES["NOT_PROVIDED"],
    )
    assert result["status_check_complainant_phone_valid"] == "no_phone_found"
    assert result["complainant_phone"] is None
