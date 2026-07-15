"""
T3-02 p2 — characterization tests for the three `add_*` branches of `run_flow_turn`.

CHARACTERIZATION, not specification. These record what the code does **today**, bugs
included, so that p3 (splitting `status_check_form`) and p4 (the handler table) can be
verified as behaviour-preserving. Where the current behaviour looks wrong, the test pins
the wrong behaviour and says so in a comment, and the bug is logged in PROGRESS.md ->
Deviations. Do not "fix" a pinned behaviour here — that would change behaviour under the
net that exists to detect exactly that.

Why these three: `add_more_info_flow` (47 lines), `add_missing_info_otp_flow` (102) and
`add_missing_info_flow` (53) had **zero state references in any test** — 202 lines of the
orchestrator's most stateful code, entirely uncharacterized.

Driven over HTTP (`post_turn` -> `/message`) per the spec, with the session seeded first
(the `test_introduce_after_done.py` precedent). `tests/test_modify_grievance_flow.py` is
the only precedent for calling `run_flow_turn` directly and both of its tests are xfail
aspirations, not records of behaviour.
"""

import pytest

from backend.orchestrator.session_store import create_session, save_session

from tests.orchestrator.flow_helpers import all_button_payloads, post_turn

GRIEVANCE_ID = "GR-TEST-1234-A"

BASE_SLOTS = {
    "story_main": "status_check",
    "language_code": "en",
    "status_check_grievance_id_selected": GRIEVANCE_ID,
}


def _seed(user_id: str, state: str, *, slots: dict, active_loop=None, requested_slot=None) -> None:
    session = create_session(user_id)
    session["state"] = state
    session["active_loop"] = active_loop
    session["requested_slot"] = requested_slot
    session["slots"].update(slots)
    save_session(session)


def _texts(body: dict) -> list[str]:
    return [m.get("text") for m in body.get("messages", []) if m.get("text")]


# ── add_more_info_flow (state_machine.py:1886-1932) ───────────────────────────────────


def test_add_more_info_entry_prompts_for_the_detail(client):
    """Fresh entry runs form_modify_grievance_details, which asks for the new detail."""
    uid = "t3-02-p2-more-info-entry"
    _seed(uid, "add_more_info_flow", slots=BASE_SLOTS)

    body = post_turn(client, uid, text="")

    assert body["next_state"] == "add_more_info_flow", "stays in the form until it completes"
    assert _texts(body), "entry must prompt"
    assert "add more details" in _texts(body)[0].lower()
    payloads = all_button_payloads(body)
    assert "/submit_details" in payloads
    assert "/modify_grievance_cancel" in payloads


def test_add_more_info_cancel_returns_to_the_modify_menu(client):
    """
    Cancel sets modify_grievance_new_detail='cancelled' (state_machine.py:1898), which
    routes back to modify_grievance_menu and re-shows the menu.
    """
    uid = "t3-02-p2-more-info-cancel"
    _seed(
        uid,
        "add_more_info_flow",
        slots=BASE_SLOTS,
        active_loop="form_modify_grievance_details",
        requested_slot="modify_grievance_new_detail",
    )

    body = post_turn(client, uid, payload="/modify_grievance_cancel")

    assert body["next_state"] == "modify_grievance_menu"
    assert _texts(body), "the modify menu must be re-shown, not left silent"
    assert "/modify_grievance_add_more_info" in all_button_payloads(body)


def test_add_more_info_submit_returns_to_status_check_and_reshows_the_step(client):
    """
    The completion path (state_machine.py:1916-1932): not cancelled => status_check_form,
    re-showing the story step via action_ask_story_step.

    story_route is set here because that is what the real status-check flow sets before
    ever reaching this branch — and without it this same path goes silent (see
    test_..._is_silent_when_story_route_is_unset below).
    """
    uid = "t3-02-p2-more-info-submit"
    _seed(
        uid,
        "add_more_info_flow",
        slots={
            **BASE_SLOTS,
            "modify_grievance_new_detail": "the dust is worse now",
            "story_route": "route_status_check_grievance_id",
        },
        active_loop="form_modify_grievance_details",
        requested_slot="modify_grievance_new_detail",
    )

    body = post_turn(client, uid, payload="/submit_details")

    assert body["next_state"] == "status_check_form"
    assert _texts(body), "completing the form must not produce a silent turn"


def test_add_more_info_submit_is_silent_when_story_route_is_unset(client):
    """
    ⚠️ CHARACTERIZES A BUG — pinned deliberately, NOT fixed (spec: record, don't fix).

    On the same completion path, if `story_route` is unset the turn returns **zero
    messages**: state_machine.py:1920 invokes action_ask_story_step, whose entire body is
    guarded by `if story_route in [route_status_check_grievance_id, route_status_check_phone]`
    (action_ask_commons.py:29) and otherwise dispatches nothing and returns []. The user
    submits their extra detail and the chatbot says nothing.

    This is D-08's class again — dead air — but one level down, *inside* a recognized
    branch, so T3-02 p1's terminal `else` cannot catch it: `status_check_form` IS a known
    state. Reachability in production is unproven (the real status-check flow sets
    story_route before this branch is reachable), which is exactly why it is logged rather
    than fixed here. See PROGRESS.md -> Deviations.

    If a future change makes this path speak, this test SHOULD fail — that is the signal
    to delete it and record the fix, not to relax it.
    """
    uid = "t3-02-p2-more-info-submit-no-route"
    _seed(
        uid,
        "add_more_info_flow",
        slots={**BASE_SLOTS, "modify_grievance_new_detail": "the dust is worse now"},
        active_loop="form_modify_grievance_details",
        requested_slot="modify_grievance_new_detail",
    )

    body = post_turn(client, uid, payload="/submit_details")

    assert body["next_state"] == "status_check_form"
    assert _texts(body) == [], (
        "current behaviour is a silent turn; if this now speaks, the bug was fixed — "
        "record it and drop this characterization"
    )


# ── add_missing_info_flow (state_machine.py:2145-2197) ────────────────────────────────


def test_add_missing_info_with_nothing_missing_completes_to_the_menu(client):
    """
    When form_modify_contact has nothing left to collect it completes on entry, and the
    `else` at :2175 utters form_modify_contact/utterance_all_contact_complete and returns
    to modify_grievance_menu.
    """
    uid = "t3-02-p2-missing-info-complete"
    _seed(uid, "add_missing_info_flow", slots=BASE_SLOTS, active_loop="form_modify_contact")

    body = post_turn(client, uid, text="")

    assert body["next_state"] == "modify_grievance_menu"
    joined = " ".join(_texts(body)).lower()
    assert "already complete" in joined, f"expected the all-complete utterance; got {joined!r}"
    assert "/modify_grievance_add_more_info" in all_button_payloads(body)


# ── add_missing_info_otp_flow (state_machine.py:2042-2143) ────────────────────────────


def test_add_missing_info_otp_entry_asks_for_the_phone(client):
    """Entry runs the OTP form, which asks for the contact phone and offers /skip."""
    uid = "t3-02-p2-otp-entry"
    _seed(uid, "add_missing_info_otp_flow", slots=BASE_SLOTS)

    body = post_turn(client, uid, text="")

    assert body["next_state"] == "add_missing_info_otp_flow", "stays until the OTP form completes"
    assert _texts(body)
    assert "phone" in _texts(body)[0].lower()
    assert "/skip" in all_button_payloads(body)


def test_add_missing_info_otp_skip_falls_through_to_the_contact_form(client):
    """
    Skipping the phone completes the OTP form, so :2077-2091 hydrates form_modify_contact
    and hands off to add_missing_info_flow. With nothing left to collect, that form also
    completes in the SAME turn (the :2092 branch, which exists to avoid a silent turn
    after OTP), so the observable end state is modify_grievance_menu — NOT
    add_missing_info_flow, despite :2086 setting it.

    Pinning that pass-through is the point: it is the single most surprising transition in
    these 202 lines, and the one a handler-table refactor is most likely to get wrong.
    """
    uid = "t3-02-p2-otp-skip"
    _seed(
        uid,
        "add_missing_info_otp_flow",
        slots=BASE_SLOTS,
        active_loop="form_otp",
        requested_slot="complainant_phone",
    )

    body = post_turn(client, uid, payload="/skip")

    assert body["next_state"] == "modify_grievance_menu"
    joined = " ".join(_texts(body)).lower()
    assert "already complete" in joined
