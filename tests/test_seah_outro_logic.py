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


def _run_seah_outro(slots, providers=None):
    import asyncio

    from backend.actions.action_outro import ActionSeahOutro
    from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker

    action = ActionSeahOutro()
    if providers is not None:
        action.find_seah_service_providers_for_tracker = lambda _tracker: providers
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots=slots, sender_id="seah-outro-split-test")
    asyncio.run(action.execute_action(dispatcher, tracker, {}))
    return dispatcher.messages


def test_seah_outro_splits_contact_center_and_closing():
    providers = [
        {
            "seah_center_name": "Jagaran Nepal (JN)",
            "address": "Jhapa",
            "phone": "01-5705439",
            "seah_service_provider_id": "prov-1",
        },
        {
            "seah_center_name": "Shakti Samuha",
            "address": "Jhapa",
            "phone": "01-4578117",
        },
    ]
    messages = _run_seah_outro(
        {
            "language_code": "en",
            "seah_contact_provided": True,
            "complainant_phone": "9841234567",
        },
        providers=providers,
    )
    texts = [m.get("text", "") for m in messages if m.get("text")]
    assert len(texts) == 2
    assert "contact details you provided" in texts[0]
    assert "support centre near you" in texts[1]
    assert "Jagaran Nepal (JN)" in texts[1]
    assert "Shakti Samuha" not in texts[1]
    assert messages[-1].get("buttons")


def test_seah_outro_no_contact_uses_referral_line():
    messages = _run_seah_outro(
        {
            "language_code": "en",
            "seah_contact_provided": False,
        },
        providers=[
            {
                "seah_center_name": "LACC",
                "address": "Jhapa",
                "phone": "977-9842773255",
            }
        ],
    )
    texts = [m.get("text", "") for m in messages if m.get("text")]
    assert "did not share contact details" in texts[0]
    assert "LACC" in texts[1]


def test_seah_outro_focal_skips_thank_you_and_centre_lookup():
    messages = _run_seah_outro(
        {
            "language_code": "en",
            "seah_victim_survivor_role": "focal_point",
            "seah_contact_provided": True,
            "complainant_phone": "9841234567",
        },
        providers=[
            {
                "seah_center_name": "Jagaran Nepal (JN)",
                "address": "Jhapa",
                "phone": "01-5705439",
            }
        ],
    )
    texts = [m.get("text", "") for m in messages if m.get("text")]
    assert len(texts) == 1
    assert "designated SEAH focal point" in texts[0]
    assert "Jagaran Nepal" not in texts[0]
    assert "confidential. We may use the contact details" not in texts[0]
    assert messages[-1].get("buttons")
