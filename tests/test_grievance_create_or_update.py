"""Tests for grievance create_or_update and classification retrieve helpers."""

from unittest.mock import MagicMock, patch

import pytest

from backend.orchestrator.form_loop import _classification_consent_already_prompted
from backend.services.database_services.postgres_services import DatabaseManager


def test_create_or_update_updates_when_row_exists():
    db = DatabaseManager.__new__(DatabaseManager)
    db.logger = MagicMock()
    db.check_entry_exists_for_entity_key = MagicMock(return_value=True)
    db.update_grievance = MagicMock(return_value=True)
    db.create_grievance = MagicMock()

    data = {
        "grievance_id": "B-GR-20260605-KOJH-1F2D",
        "complainant_id": "B-CM-20260605-KOJH-3348",
        "grievance_description": "noise complaint",
        "grievance_classification_status": "pending",
    }
    result = DatabaseManager.create_or_update_grievance(db, data)

    assert result == "B-GR-20260605-KOJH-1F2D"
    db.update_grievance.assert_called_once_with("B-GR-20260605-KOJH-1F2D", data)
    db.create_grievance.assert_not_called()


def test_create_or_update_recovers_from_duplicate_insert():
    db = DatabaseManager.__new__(DatabaseManager)
    db.logger = MagicMock()
    db.check_entry_exists_for_entity_key = MagicMock(return_value=False)
    db.update_grievance = MagicMock(return_value=True)
    db.create_grievance = MagicMock(
        side_effect=Exception(
            'duplicate key value violates unique constraint "grievances_pkey"'
        )
    )

    data = {
        "grievance_id": "B-GR-20260605-KOJH-1F2D",
        "grievance_description": "noise complaint",
    }
    result = DatabaseManager.create_or_update_grievance(db, data)

    assert result == "B-GR-20260605-KOJH-1F2D"
    db.update_grievance.assert_called_once_with("B-GR-20260605-KOJH-1F2D", data)


@pytest.mark.parametrize(
    "slots,expected",
    [
        (
            {
                "grievance_complainant_review": True,
                "grievance_summary_temp": "Summary text",
                "grievance_categories": [],
            },
            True,
        ),
        (
            {
                "grievance_complainant_review": True,
                "grievance_summary_temp": "",
                "grievance_categories": [],
            },
            False,
        ),
        (
            {
                "grievance_complainant_review": True,
                "grievance_categories": ["Environmental - Noise Pollution"],
            },
            True,
        ),
    ],
)
def test_classification_consent_skip_only_with_llm_content(slots, expected):
    assert (
        _classification_consent_already_prompted(slots, "grievance_classification_consent")
        is expected
    )
