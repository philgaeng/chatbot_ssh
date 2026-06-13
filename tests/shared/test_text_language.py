"""Text language detection for location validation."""

from backend.shared_functions.text_language import detect_app_language, language_candidates


def test_devanagari_is_nepali():
    assert detect_app_language("भद्रपुर नगरपालिका") == "ne"
    assert detect_app_language("झापा") == "ne"


def test_latin_defaults_english():
    assert detect_app_language("Bhadrapur") == "en"
    assert detect_app_language("Jhapa") == "en"


def test_language_candidates_order():
    assert language_candidates("भद्रपुर") == ["ne", "en"]
    assert language_candidates("Jhapa") == ["en", "ne"]
