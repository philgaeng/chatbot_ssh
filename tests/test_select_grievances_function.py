"""
Tests for ValidateFormStatusCheck.select_grievances_from_full_name_list.

Production passes (1) a list of matched full-name strings from helpers.match_full_name_list,
(2) grievance dicts with complainant_full_name and grievance_status, matching base_mixins.
"""

from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from backend.actions.forms.form_status_check import ValidateFormStatusCheck


class _MockHelpers:
    def match_full_name(self, input_name: str, reference_name: str) -> bool:
        return input_name.lower().strip() == reference_name.lower().strip()


def _grievance(
    gid: str,
    full_name: str,
    grievance_status: str,
    created: datetime,
    description: str = "",
) -> Dict[str, Any]:
    return {
        "grievance_id": gid,
        "complainant_full_name": full_name,
        "grievance_status": grievance_status,
        "grievance_creation_date": created,
        "description": description,
    }


def _sample_grievances() -> List[Dict[str, Any]]:
    return [
        _grievance("GRIE-001", "John Smith", "OPEN", datetime(2024, 1, 15), "First grievance"),
        _grievance("GRIE-002", "John Smith", "IN_PROGRESS", datetime(2024, 1, 20), "Second grievance"),
        _grievance("GRIE-003", "John Smith", "CLOSED", datetime(2024, 1, 10), "Third grievance (closed)"),
        _grievance("GRIE-004", "Jane Doe", "OPEN", datetime(2024, 1, 25), "Different person"),
        _grievance("GRIE-005", "John Smith", "CLOSED", datetime(2024, 1, 5), "Another closed grievance"),
        _grievance("GRIE-006", "john smith", "PENDING", datetime(2024, 1, 30), "Case insensitive test"),
    ]


@pytest.fixture
def validator() -> ValidateFormStatusCheck:
    instance = ValidateFormStatusCheck()
    instance.helpers = _MockHelpers()

    def mock_match_full_name(input_name: str, reference_name: str) -> bool:
        return instance.helpers.match_full_name(input_name, reference_name)

    instance.match_full_name = mock_match_full_name
    return instance


@pytest.fixture
def dispatcher() -> Mock:
    return Mock()


def test_select_grievances_basic_functionality(validator: ValidateFormStatusCheck, dispatcher: Mock):
    """Multiple matches: non-closed first (newest first), then closed (newest first)."""
    sample = _sample_grievances()
    matches = ["John Smith", "john smith"]
    result = validator.select_grievances_from_full_name_list(matches, sample, dispatcher)

    assert len(result) == 5  # John Smith variants; Jane Doe excluded

    non_closed = [g for g in result if g["grievance_status"] != "CLOSED"]
    closed = [g for g in result if g["grievance_status"] == "CLOSED"]
    assert len(non_closed) == 3
    assert len(closed) == 2

    for group in (non_closed, closed):
        for i in range(len(group) - 1):
            assert group[i]["grievance_creation_date"] >= group[i + 1]["grievance_creation_date"]


def test_select_grievances_no_matches(validator: ValidateFormStatusCheck, dispatcher: Mock):
    assert validator.select_grievances_from_full_name_list(
        ["Non Existent Person"], _sample_grievances(), dispatcher
    ) == []


def test_select_grievances_empty_input_list(validator: ValidateFormStatusCheck, dispatcher: Mock):
    assert validator.select_grievances_from_full_name_list(["John Smith"], [], dispatcher) == []


def test_select_grievances_single_match(validator: ValidateFormStatusCheck, dispatcher: Mock):
    result = validator.select_grievances_from_full_name_list(
        ["Jane Doe"], _sample_grievances(), dispatcher
    )
    assert len(result) == 1
    assert result[0]["complainant_full_name"] == "Jane Doe"


def test_sorting_order(validator: ValidateFormStatusCheck, dispatcher: Mock):
    test_grievances = [
        _grievance("A", "Test User", "CLOSED", datetime(2024, 1, 1), "Oldest closed"),
        _grievance("B", "Test User", "OPEN", datetime(2024, 1, 15), "Middle open"),
        _grievance("C", "Test User", "CLOSED", datetime(2024, 1, 20), "Newest closed"),
        _grievance("D", "Test User", "IN_PROGRESS", datetime(2024, 1, 10), "Oldest open"),
        _grievance("E", "Test User", "PENDING", datetime(2024, 1, 25), "Newest open"),
    ]
    result = validator.select_grievances_from_full_name_list(
        ["Test User"], test_grievances, dispatcher
    )
    assert [g["grievance_id"] for g in result] == ["E", "B", "D", "C", "A"]
