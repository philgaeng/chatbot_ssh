"""Location validator uses detected script/language, not session language only."""

import pytest

from backend.shared_functions.location_validator import ContactLocationValidator


@pytest.fixture(scope="module")
def validator():
    v = ContactLocationValidator()
    rows = v._load_province_district_municipality_from_db()
    if not rows:
        pytest.skip("ticketing.locations not seeded")
    return v


def test_nepali_municipality_with_english_qr_hints(validator):
    """Nepali input must resolve even when province/district slots are English."""
    validator._initialize_constants("en")
    result = validator.validate_municipality_input(
        "भद्रपुर नगरपालिका",
        "Koshi",
        "Jhapa",
    )
    assert result == "भद्रपुर"


def test_nepali_municipality_ne_tree(validator):
    validator._initialize_constants("ne")
    result = validator.validate_municipality_input(
        "भद्रपुर नगरपालिका",
        "कोशी",
        "झापा",
    )
    assert result == "भद्रपुर"
