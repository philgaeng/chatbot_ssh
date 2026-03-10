"""
Unit tests for Modify grievance – Add missing info helpers (Spec 13).

- get_missing_contact_fields: ordered list of empty contact/location fields.
- get_missing_fields_page: pagination (≤4 all at once; >4 → 3 + See more).
"""

import pytest

from backend.actions.forms.modify_contact_helpers import (
    get_missing_contact_fields,
    get_missing_fields_page,
    MODIFY_CONTACT_FIELD_ORDER,
)


def test_get_missing_contact_fields_all_empty():
    """All fields empty → returns full order."""
    slots = {}
    assert get_missing_contact_fields(slots) == MODIFY_CONTACT_FIELD_ORDER


def test_get_missing_contact_fields_none_missing():
    """All fields set → returns empty list."""
    slots = {f: "x" for f in MODIFY_CONTACT_FIELD_ORDER}
    assert get_missing_contact_fields(slots) == []


def test_get_missing_contact_fields_partial():
    """Only missing fields in order."""
    slots = {
        "complainant_phone": "9812345678",
        "complainant_full_name": None,
        "complainant_province": "Koshi",
        "complainant_district": "",
        "complainant_municipality": "Biratnagar",
    }
    got = get_missing_contact_fields(slots)
    assert got == [
        "complainant_full_name",
        "complainant_district",
        "complainant_village",
        "complainant_ward",
        "complainant_address",
        "complainant_email",
    ]


def test_get_missing_contact_fields_email_from_temp():
    """complainant_email can come from complainant_email_temp."""
    slots = {"complainant_email_temp": "a@b.com"}
    got = get_missing_contact_fields(slots)
    assert "complainant_email" not in got
    slots2 = {"complainant_email": ""}
    got2 = get_missing_contact_fields(slots2)
    assert "complainant_email" in got2


def test_get_missing_fields_page_zero_missing():
    """No missing → empty page, no more."""
    fields, has_more = get_missing_fields_page([], 0)
    assert fields == []
    assert has_more is False


def test_get_missing_fields_page_four_or_less_one_screen():
    """≤4 missing: all on one screen, no See more."""
    for n in (1, 2, 3, 4):
        missing = [f"f{i}" for i in range(n)]
        fields, has_more = get_missing_fields_page(missing, 0)
        assert fields == missing
        assert has_more is False


def test_get_missing_fields_page_five_first_page_three_plus_see_more():
    """>4 missing: first page = 3 + See more."""
    missing = ["a", "b", "c", "d", "e"]
    fields, has_more = get_missing_fields_page(missing, 0)
    assert fields == ["a", "b", "c"]
    assert has_more is True


def test_get_missing_fields_page_five_second_page_remaining_two():
    """5 missing: second page = remaining 2, no See more."""
    missing = ["a", "b", "c", "d", "e"]
    fields, has_more = get_missing_fields_page(missing, 1)
    assert fields == ["d", "e"]
    assert has_more is False


def test_get_missing_fields_page_seven_three_pages():
    """7 missing: page0=3, page1=3, page2=1."""
    missing = [f"f{i}" for i in range(7)]
    p0, more0 = get_missing_fields_page(missing, 0)
    assert p0 == ["f0", "f1", "f2"] and more0 is True
    p1, more1 = get_missing_fields_page(missing, 1)
    assert p1 == ["f3", "f4", "f5"] and more1 is True
    p2, more2 = get_missing_fields_page(missing, 2)
    assert p2 == ["f6"] and more2 is False


def test_get_missing_fields_page_past_end():
    """Page index past end → empty, no more."""
    missing = ["a", "b", "c", "d", "e"]
    fields, has_more = get_missing_fields_page(missing, 99)
    assert fields == []
    assert has_more is False
