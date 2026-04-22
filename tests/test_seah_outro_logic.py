import pytest

from backend.actions.base_classes.base_classes import BaseAction


class _SeahLogicHarness(BaseAction):
    def name(self):
        return "test_seah_logic_harness"

    async def execute_action(self, dispatcher, tracker, domain):
        return []


def _logic() -> _SeahLogicHarness:
    h = _SeahLogicHarness()
    h.language_code = "en"
    return h


def test_resolve_focal_default():
    logic = _logic()
    assert (
        logic.resolve_seah_outro_variant(
            {"seah_victim_survivor_role": "focal_point"},
        )
        == "focal_default"
    )


@pytest.mark.parametrize(
    "slots,expected",
    [
        (
            {
                "seah_victim_survivor_role": "victim_survivor",
                "seah_anonymous_route": True,
                "seah_contact_provided": True,
                "complainant_consent": True,
                "seah_contact_consent_channel": "phone",
            },
            "victim_limited_contact",
        ),
        (
            {
                "seah_victim_survivor_role": "victim_survivor",
                "seah_anonymous_route": False,
                "seah_contact_provided": True,
                "complainant_consent": True,
                "seah_contact_consent_channel": "phone",
            },
            "victim_contact_ok",
        ),
        (
            {
                "seah_victim_survivor_role": "victim_survivor",
                "seah_anonymous_route": False,
                "seah_contact_provided": True,
                "complainant_consent": True,
                "seah_contact_consent_channel": "both",
            },
            "victim_contact_ok",
        ),
        (
            {
                "seah_victim_survivor_role": "victim_survivor",
                "seah_anonymous_route": False,
                "seah_contact_provided": True,
                "complainant_consent": True,
                "seah_contact_consent_channel": "email",
            },
            "victim_limited_contact",
        ),
        (
            {
                "seah_victim_survivor_role": "not_victim_survivor",
                "seah_anonymous_route": True,
            },
            "not_victim_anonymous",
        ),
        (
            {
                "seah_victim_survivor_role": "not_victim_survivor",
                "seah_anonymous_route": False,
            },
            "not_victim_identified",
        ),
    ],
)
def test_resolve_seah_matrix(slots, expected):
    logic = _logic()
    assert logic.resolve_seah_outro_variant(slots) == expected


def test_compute_seah_contact_provided_valid_phone():
    logic = _logic()
    assert logic.compute_seah_contact_provided({"complainant_phone": "9841234567"})


def test_get_available_seah_contact_channels_phone_only_db_placeholder_email():
    """DB stores literal 'Not provided' for skipped email; channel list must stay phone-only."""
    logic = _logic()
    channels = logic.get_available_seah_contact_channels(
        phone_value="9841234567",
        email_value="Not provided",
    )
    assert channels == ["phone", "none"]


def test_get_available_seah_contact_channels_non_string_email_ignored():
    logic = _logic()
    channels = logic.get_available_seah_contact_channels(
        phone_value="9841234567",
        email_value=False,
    )
    assert channels == ["phone", "none"]


def test_get_available_seah_contact_channels_phone_and_email():
    logic = _logic()
    channels = logic.get_available_seah_contact_channels(
        phone_value="9841234567",
        email_value="user@example.com",
    )
    assert set(channels) == {"phone", "email", "both", "none"}


def test_seah_contact_provided_update_only_seah_intake():
    logic = _logic()
    cur = {"complainant_phone": "9841234567", "complainant_email": None}
    assert logic.seah_contact_provided_update("new_grievance", cur, {}) == {}
    assert logic.seah_contact_provided_update("seah_intake", cur, {})["seah_contact_provided"] is True
