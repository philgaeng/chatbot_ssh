import pytest

from backend.actions.utils.seah_outro_logic import (
    compute_seah_contact_provided,
    resolve_seah_outro_variant,
    seah_contact_provided_update,
)


def test_resolve_focal_default():
    assert (
        resolve_seah_outro_variant(
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
    assert resolve_seah_outro_variant(slots) == expected


def test_compute_seah_contact_provided_valid_phone():
    assert compute_seah_contact_provided({"complainant_phone": "9841234567"})


def test_seah_contact_provided_update_only_seah_intake():
    cur = {"complainant_phone": "9841234567", "complainant_email": None}
    assert seah_contact_provided_update("new_grievance", cur, {}) == {}
    assert seah_contact_provided_update("seah_intake", cur, {})["seah_contact_provided"] is True
