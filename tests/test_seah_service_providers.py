"""Tests for SEAH service provider lookup helpers."""
from backend.shared_functions.seah_service_providers import (
    format_details_utterance,
    format_recommendation_utterance,
    resolve_location_codes,
)


def test_resolve_location_codes_biratnagar():
    codes = resolve_location_codes("Koshi", "Morang", "Biratnagar Metropolitan City")
    assert codes["district_code"] == "P1_MOR"
    assert codes["municipality_code"] == "P1_MOR_BIR"


def test_format_recommendation_single_center_en():
    text = format_recommendation_utterance(
        [{"seah_center_name": "OCMC, Koshi Hospital"}],
        "en",
        municipality="Biratnagar",
    )
    assert "OCMC, Koshi Hospital" in text


def test_format_recommendation_multiple_centers_en():
    providers = [
        {"seah_center_name": "Centre A"},
        {"seah_center_name": "Centre B"},
    ]
    text = format_recommendation_utterance(providers, "en", municipality="Biratnagar")
    assert "Centre A" in text
    assert "Centre B" in text


def test_format_details_lists_all_providers():
    providers = [
        {
            "seah_center_name": "OCMC",
            "address": "Hospital Chowk",
            "phone": "021-530103",
            "municipality": "Biratnagar Metropolitan City",
            "district": "Morang",
        },
        {
            "seah_center_name": "Maiti Nepal",
            "address": "Sainik Tole",
            "phone": "021-435794",
            "municipality": "Biratnagar Metropolitan City",
            "district": "Morang",
        },
    ]
    text = format_details_utterance(providers, "en")
    assert "OCMC" in text
    assert "Maiti Nepal" in text
    assert "021-530103" in text
