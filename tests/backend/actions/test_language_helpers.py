"""Unit tests for extracted action helper modules."""

import pytest

from backend.actions.services.status_check.grievance_lookup import (
    standardize_grievance_id_response,
    validate_grievance_id_format,
)
from backend.actions.utils import language as lang


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", "en"),
        ("hello world", "en"),
        ("नमस्ते", "ne"),
    ],
)
def test_detect_language(text, expected):
    assert lang.detect_language(text) == expected


@pytest.mark.parametrize(
    "text,is_skip,needs_confirm",
    [
        ("skip", True, False),
        ("/skip", False, False),
        ("please skip this", True, False),
        ("continue", False, False),
    ],
)
def test_is_skip_instruction(text, is_skip, needs_confirm):
    result_skip, result_confirm, _ = lang.is_skip_instruction(text)
    assert result_skip == is_skip
    assert result_confirm == needs_confirm


@pytest.mark.parametrize(
    "text,valid",
    [
        ("AB-1234", True),
        ("B-GR-20260609-KOJH-069F", True),
        ("B-GR-20260609-KOJH-069F-B", True),
        ("XY", False),
        ("", False),
    ],
)
def test_validate_grievance_id_format(text, valid):
    assert validate_grievance_id_format(text) == valid


def test_standardize_grievance_id_response():
    assert standardize_grievance_id_response("KOJH-069F") == "JH-069F"
    assert standardize_grievance_id_response("B-GR-20260609-KOJH-069F") == "JH-069F"
