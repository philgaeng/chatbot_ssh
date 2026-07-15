"""
T3-02 p2 — characterization tests for `status_check_form`, the 303-line branch p3 splits.

CHARACTERIZATION, not specification: these record what the code does **today**, bugs
included, so p3 can be shown to preserve behaviour. Where the behaviour looks wrong the
test pins the wrong behaviour and says so; the bug is logged in PROGRESS.md -> Deviations
rather than fixed (T3-02's spec: "you would be changing behavior under a test net you just
wrote").

Why this branch: 303 lines at nesting depth 9, and today it is touched only at *entry*
level by `test_form_loop.py` / `test_modify_grievance_flow.py` — nothing exercises its
interior. It is 22% of `run_flow_turn` and where the complexity actually lives.

The shape these tests pin (`state_machine.py:1582-1884`), which is also p3's natural seam:

    if not active_loop:          # 1589-1671 — route on intent (3 arms)
        status_check_request_follow_up  -> OTP form, or the follow-up action + `done`
        status_check_modify_grievance   -> modify menu, `modify_grievance_menu`
        else                            -> re-show the choices, stay put
    else:                        # 1672-1884 — a status-check form is running
        pick the form from active_loop, run a turn, handle completion

Every assertion below was written from a probe of the real code, not from reading it.
"""

import pytest

from backend.orchestrator.session_store import create_session, save_session

from tests.orchestrator.flow_helpers import all_button_payloads, post_turn

BASE_SLOTS = {
    "story_main": "status_check",
    "language_code": "en",
    "status_check_grievance_id_selected": "GR-TEST-1234-A",
    "story_route": "route_status_check_grievance_id",
}


def _seed(user_id: str, *, slots: dict, active_loop=None, requested_slot=None) -> None:
    session = create_session(user_id)
    session["state"] = "status_check_form"
    session["active_loop"] = active_loop
    session["requested_slot"] = requested_slot
    session["slots"].update(slots)
    save_session(session)


def _texts(body: dict) -> list[str]:
    return [m.get("text") for m in body.get("messages", []) if m.get("text")]


# ── arm A: no active_loop => route on intent (state_machine.py:1589-1671) ─────────────


def test_request_follow_up_without_a_phone_completes_to_done(client):
    """
    `status_check_request_follow_up` with no phone on the grievance:
    `follow_up_needs_otp_verification` is False, so :1626 runs the follow-up action and
    the flow ends at `done`.

    NOTE what this does NOT cover: the OTP arm (:1600-1616), which needs a grievance that
    has a phone. Both `otp_status=verified` and the unverified phone-route case land here
    instead, because the *absence of a phone* short-circuits the check before OTP is
    considered. Recorded so p3 does not mistake this for full coverage of the branch.
    """
    uid = "t3-02-p2-scf-follow-up"
    _seed(uid, slots={**BASE_SLOTS, "otp_status": "verified"})

    body = post_turn(client, uid, payload="/status_check_request_follow_up")

    assert body["next_state"] == "done"
    joined = " ".join(_texts(body)).lower()
    assert "received your request for follow up" in joined


def test_modify_grievance_opens_the_modify_menu(client):
    """`status_check_modify_grievance` (:1641) => modify_grievance_menu, menu shown."""
    uid = "t3-02-p2-scf-modify"
    _seed(uid, slots=BASE_SLOTS)

    body = post_turn(client, uid, payload="/status_check_modify_grievance")

    assert body["next_state"] == "modify_grievance_menu"
    payloads = all_button_payloads(body)
    assert "/modify_grievance_add_pictures" in payloads
    assert "/modify_grievance_add_more_info" in payloads
    assert "/modify_grievance_add_missing_info" in payloads


def test_unrecognized_input_reshows_the_choices_and_stays(client):
    """
    The `else` at :1655 — the in-file "re-show choices so we never return empty messages"
    convention (:1629). Free text neither routes nor is swallowed: the step is re-shown and
    the state holds.

    This is the convention the sprint keeps citing as the file's own answer to dead air.
    It is worth pinning precisely because two *other* paths fail to honour it (D-51, D-52).
    """
    uid = "t3-02-p2-scf-unknown"
    _seed(uid, slots=BASE_SLOTS)

    body = post_turn(client, uid, text="hello there")

    assert body["next_state"] == "status_check_form", "unrecognized input must not move state"
    assert _texts(body), "the choices must be re-shown — this is the never-empty convention"
    assert all_button_payloads(body), "re-shown choices come with their buttons"


# ── arm B: an active_loop is running => pick the form and run a turn (:1672-1884) ─────


def test_active_loop_form_otp_runs_the_otp_form_and_holds_state(client):
    """active_loop=form_otp (:1676) => the OTP form asks for the phone; state holds."""
    uid = "t3-02-p2-scf-otp-loop"
    _seed(uid, slots=BASE_SLOTS, active_loop="form_otp")

    body = post_turn(client, uid, text="")

    assert body["next_state"] == "status_check_form"
    assert _texts(body)
    assert "phone" in _texts(body)[0].lower()
    assert "/skip" in all_button_payloads(body)


def test_unknown_active_loop_falls_back_to_status_form_1_silently(client):
    """
    ⚠️ CHARACTERIZES A BUG — pinned deliberately, NOT fixed (D-52).

    The form-selection chain at :1674-1683 ends in a bare `else: form = _get_status_form_1()`.
    An unrecognized active_loop therefore silently runs status form 1, which on an
    already-filled session dispatches **nothing** — the turn returns zero messages and the
    session keeps its bogus active_loop, so every subsequent turn does the same.

    Third instance of D-08's dead-air class this sprint (with D-51), and again invisible to
    T3-02 p1's terminal `else`: the *state* is recognized, only the *loop* is not. The
    fallback is silent where it should be loud — an unknown active_loop is a bug, and the
    file's own convention two hundred lines up (:1629) says never return empty messages.

    If a future change makes this speak or log, this test SHOULD fail — delete it and
    record the fix rather than relaxing it.
    """
    uid = "t3-02-p2-scf-bogus-loop"
    _seed(uid, slots=BASE_SLOTS, active_loop="totally_unknown_loop")

    body = post_turn(client, uid, text="")

    assert body["next_state"] == "status_check_form"
    assert _texts(body) == [], (
        "current behaviour is a silent turn on an unknown active_loop; if this now speaks "
        "or logs, the bug was fixed — record it and drop this characterization"
    )
