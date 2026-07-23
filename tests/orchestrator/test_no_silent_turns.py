"""
The dead-air class, closed at the boundary that actually owns it.

`run_flow_turn` must never return zero messages. The user speaks; the chatbot answers.
That is the whole invariant, and until now it was a *convention* — stated in a comment at
`state_machine.py:1629` ("re-show choices so we never return empty messages"), honoured at
some sites, enforced at none. So it failed at each site separately and was found at each
site separately:

    D-08  unrecognized STATE falls off the 22-arm chain      -> fixed by T3-02 p1's terminal else
    D-51  add_more_info_flow completes; action_ask_story_step
          no-ops because story_route is unset                 -> state RECOGNIZED, p1's else blind
    D-52  unrecognized active_loop silently runs status form 1;
          nothing clears the loop, so the session wedges       -> state RECOGNIZED, p1's else blind
    D-59  main_menu + /seah_intake with the SEAH flag off:
          `next_state = "main_menu"` and nothing dispatched    -> found by measuring, not reading

p1's terminal `else` catches only the first: in the other three the *state* is recognized,
so the else never runs — and p4's handler table is blind for the same reason (the dict
lookup succeeds; the default never fires). Four instances, four different guard sites, one
invariant. So the guard belongs where the invariant is stated: at the turn boundary.

**This suite exists to make the class extinct rather than the instances.** A future silent
path fails here without anyone having to notice it.

Method note: the four instances were found by *measuring* — instrumenting all three of
`run_flow_turn`'s returns and running the whole suite — not by reading. That census also
established the precondition for a postcondition at all: across 208 tests, exactly three
turns returned zero messages and **all three were bugs**. `attachment_ids_sync` and the
`/introduce` restart never do. There is no legitimately-silent turn to protect.
"""

import logging

import pytest

from backend.orchestrator.session_store import create_session, save_session

from tests.orchestrator.flow_helpers import all_button_payloads, post_turn

# `story_route` is the hinge, and the two bugs need OPPOSITE values of it — which is worth
# stating plainly, because getting it wrong makes these tests pass pre-fix for the wrong
# reason (it did, on the first attempt, and only red-verification caught it):
#
#   D-51 needs it UNSET — action_ask_story_step's body is guarded on it, so unset => no-op.
#   D-52 needs it SET   — form_status_check_1 *collects* it, so unset => the form prompts
#                         for it and the turn is not silent at all.
#
# Both are realistic: every real session that reaches status_check_form has answered it.
BASE_SLOTS = {
    "story_main": "status_check",
    "language_code": "en",
    "status_check_grievance_id_selected": "GR-TEST-1234-A",
}
# D-52's shape: the route already answered.
STATUS_CHECK_SLOTS = {**BASE_SLOTS, "story_route": "route_status_check_grievance_id"}


def _seed(user_id: str, state: str, *, slots: dict, active_loop=None, requested_slot=None) -> None:
    session = create_session(user_id)
    session["state"] = state
    session["active_loop"] = active_loop
    session["requested_slot"] = requested_slot
    session["slots"].update(slots)
    save_session(session)


def _texts(body: dict) -> list[str]:
    return [m.get("text") for m in body.get("messages", []) if m.get("text")]


def _silent_turn_errors(caplog) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.ERROR and "zero-message turn" in r.getMessage()
    ]


# ── D-51: add_more_info_flow completes with story_route unset ─────────────────────────


def test_add_more_info_submit_is_not_silent_without_story_route(client):
    """
    D-51, fixed. Was: 0 messages — the user submits the detail they typed and the chatbot
    says nothing. `action_ask_story_step`'s whole body is guarded on `story_route`
    (`action_ask_commons.py:29`) and otherwise dispatches nothing.

    Verified red pre-fix: this returned `[]`.
    """
    uid = "t3-02-fix-more-info-no-route"
    _seed(
        uid,
        "add_more_info_flow",
        slots={**BASE_SLOTS, "modify_grievance_new_detail": "the dust is worse now"},  # no story_route: D-51's trigger
        active_loop="form_modify_grievance_details",
        requested_slot="modify_grievance_new_detail",
    )

    body = post_turn(client, uid, payload="/submit_details")

    assert _texts(body), "the user submitted their detail and got silence"
    assert all_button_payloads(body), "a fallback must leave the user something to click"


def test_add_more_info_submit_logs_the_silent_turn(client, caplog):
    """The net must be loud: a silent turn is a bug, and an operator has to be able to find it."""
    uid = "t3-02-fix-more-info-log"
    _seed(
        uid,
        "add_more_info_flow",
        slots={**BASE_SLOTS, "modify_grievance_new_detail": "x"},  # no story_route: D-51's trigger
        active_loop="form_modify_grievance_details",
        requested_slot="modify_grievance_new_detail",
    )

    with caplog.at_level(logging.ERROR, logger="backend.orchestrator.state_machine"):
        post_turn(client, uid, payload="/submit_details")

    errors = _silent_turn_errors(caplog)
    assert errors, "a zero-message turn must be logged at error"
    assert any("add_more_info_flow" in e for e in errors), (
        f"the log must name the state that went silent, or it is unactionable; got {errors}"
    )


# ── D-52: unrecognized active_loop ────────────────────────────────────────────────────


def test_unknown_active_loop_is_not_silent(client):
    """D-52, fixed. Was: 0 messages, and the bogus loop was never cleared."""
    uid = "t3-02-fix-bogus-loop"
    _seed(uid, "status_check_form", slots=STATUS_CHECK_SLOTS, active_loop="totally_unknown_loop")

    body = post_turn(client, uid, text="")

    assert _texts(body)
    assert all_button_payloads(body)


def test_unknown_active_loop_does_not_wedge_the_session(client):
    """
    The half of D-52 that a message alone would not fix. The bogus `active_loop` used to
    survive the turn, so **every** later turn re-entered the same silent path — the session
    was stuck until `/introduce`. Recovery clears the loop, so the next turn is served
    normally.
    """
    uid = "t3-02-fix-bogus-loop-wedge"
    _seed(uid, "status_check_form", slots=STATUS_CHECK_SLOTS, active_loop="totally_unknown_loop")

    post_turn(client, uid, text="")
    second = post_turn(client, uid, text="hello again")

    assert _texts(second), "the session is still wedged — the bogus active_loop survived"


def test_unknown_active_loop_names_the_loop_in_the_log(client, caplog):
    """
    The state alone is not enough here: `status_check_form` is a *valid* state, so an
    operator seeing only the state would look in the wrong place. The offending loop is
    the actionable detail.
    """
    uid = "t3-02-fix-bogus-loop-log"
    _seed(uid, "status_check_form", slots=STATUS_CHECK_SLOTS, active_loop="totally_unknown_loop")

    with caplog.at_level(logging.ERROR, logger="backend.orchestrator.state_machine"):
        post_turn(client, uid, text="")

    errors = _silent_turn_errors(caplog)
    assert errors
    assert any("totally_unknown_loop" in e for e in errors), (
        f"the log must name the unrecognized active_loop; got {errors}"
    )


# ── D-59: SEAH flag off, found by measurement ─────────────────────────────────────────


def test_seah_intake_with_flag_off_is_not_silent(client, monkeypatch):
    """
    D-59 — a fourth instance, in shipped code, found by *measuring* zero-message turns
    across the suite rather than by reading.

    `main_menu` + `/seah_intake` with `ENABLE_SEAH_DEDICATED_FLOW=false` hits
    `state_machine.py:1379`, which sets `next_state = "main_menu"` and dispatches nothing:
    the user clicks the SEAH option and the chatbot goes quiet. `test_orchestrator_api.py`
    has covered this path since it was written and stayed green — it asserts `next_state`
    and never looks at the messages. Its sibling two functions below *does* assert texts.

    Verified red pre-fix: `[]`.
    """
    monkeypatch.setenv("ENABLE_SEAH_DEDICATED_FLOW", "false")
    uid = "t3-02-fix-seah-flag-off"

    post_turn(client, uid, text="")
    post_turn(client, uid, payload="/set_english")
    body = post_turn(client, uid, payload="/seah_intake")

    assert body["next_state"] == "main_menu", "unchanged: the flag-off arm still stays on the menu"
    assert _texts(body), "the user clicked SEAH with the flag off and got silence"
    assert all_button_payloads(body), "and had nothing to click next"


# ── the guard's own guards ────────────────────────────────────────────────────────────


def test_normal_turns_do_not_trip_the_postcondition(client, caplog):
    """
    CONTROL, and the one that matters most. The postcondition must be invisible on every
    healthy path — if it fires on a legitimate turn it is worse than the bug it replaces.

    Non-vacuous by construction: it drives four different live paths (intro, language
    select, main menu, status-check entry) and asserts each produced messages *and* that
    nothing was logged.
    """
    uid = "t3-02-fix-control"

    with caplog.at_level(logging.ERROR, logger="backend.orchestrator.state_machine"):
        first = post_turn(client, uid, text="")
        second = post_turn(client, uid, payload="/set_english")
        third = post_turn(client, uid, payload="/start_status_check")

    for label, body in (("intro", first), ("set_english", second), ("status_check", third)):
        assert _texts(body), f"{label} produced no messages — unrelated regression"

    assert not _silent_turn_errors(caplog), (
        f"the postcondition fired on a healthy turn: {_silent_turn_errors(caplog)}"
    )


def test_postcondition_preserves_a_healthy_turns_state(client, caplog):
    """
    The net must not route. On a healthy turn `next_state` is whatever the branch decided;
    the postcondition must not touch it.
    """
    uid = "t3-02-fix-control-state"

    post_turn(client, uid, text="")
    body = post_turn(client, uid, payload="/set_english")

    assert body["next_state"] == "main_menu", "a healthy turn's next_state was altered"
