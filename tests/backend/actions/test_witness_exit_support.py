"""Characterization tests for SEAH witness early-exit support messaging."""
from backend.actions.services.seah.witness_exit import (
    build_witness_exit_no_location_message,
    build_witness_exit_support_message,
    has_location_context,
)


class _FakeTracker:
    def __init__(self, slots: dict):
        self._slots = slots

    def get_slot(self, name):
        return self._slots.get(name)


def test_has_location_context_true_when_district_set():
    tracker = _FakeTracker({"complainant_district": "Jhapa"})
    assert has_location_context(tracker) is True


def test_has_location_context_false_when_no_location_slots():
    tracker = _FakeTracker({})
    assert has_location_context(tracker) is False


def test_build_witness_exit_support_message_includes_centres():
    providers = [
        {
            "seah_center_name": "Maiti Nepal",
            "address": "Purano Bhansar",
            "phone": "023-562053",
            "municipality": "Mechinagar Municipality",
            "district": "Jhapa",
        }
    ]
    text = build_witness_exit_support_message(
        "en",
        providers,
        municipality="Mechinagar Municipality",
        district="Jhapa",
    )
    assert "Thank you." in text
    assert "Maiti Nepal" in text
    assert "023-562053" in text
    assert "[list to be provided]" not in text


def test_build_witness_exit_support_message_ne():
    text = build_witness_exit_support_message(
        "ne",
        [{"seah_center_name": "Caritas Nepal"}],
        district="Jhapa",
    )
    assert "धन्यवाद" in text
    assert "Caritas Nepal" in text


def test_build_witness_exit_no_location_message_en():
    text = build_witness_exit_no_location_message("en")
    assert "Thank you." in text
    assert "nwchelpline.gov.np" in text
