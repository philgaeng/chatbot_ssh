"""
T3-02 p1 — `run_flow_turn` must never return zero messages for an unrecognized state.

The 22-arm `if/elif state == ...` chain in `state_machine.py` had no terminal `else`.
An unrecognized state fell off the end, kept `next_state = state`, and returned an
empty message list: the user sends a message and the chatbot says nothing, forever,
with nothing in the logs. That is D-08, and these tests pin the fix.

Reachability is not hypothetical: a session persisted under a state name this version
no longer serves (a rename, or the `form_dust` / `submit_grievance` branches T3-02 p1
deletes) lands here across a deploy. The terminal `else` is what makes that deletion
safe rather than a silent dead-air trap.

Driven over HTTP (`post_turn` -> `/message`) per the spec, matching the existing
suite's shape. `test_introduce_after_done.py` is the precedent for seeding a state
directly.
"""

import logging

import pytest

from backend.orchestrator.session_store import create_session, save_session

from tests.orchestrator.flow_helpers import all_button_payloads, post_turn


def _seed_session(user_id: str, state: str, *, language_code: str | None = "en") -> None:
    session = create_session(user_id)
    session["state"] = state
    if language_code is None:
        session["slots"].pop("language_code", None)
    else:
        session["slots"]["language_code"] = language_code
    save_session(session)


def _texts(body: dict) -> list[str]:
    return [m.get("text") for m in body.get("messages", []) if m.get("text")]


def test_unknown_state_returns_a_message(client):
    """The core dead-air guard. Pre-fix: zero messages."""
    user_id = "t3-02-unknown-state-message"
    _seed_session(user_id, "nonexistent_state")

    body = post_turn(client, user_id, text="hello?")

    assert _texts(body), (
        "an unrecognized state returned zero messages — this is the dead-air bug "
        "(D-08): the user speaks and the chatbot says nothing"
    )


def test_unknown_state_logs_an_error(client, caplog):
    """The state name must reach the logs, or the bug is invisible in production."""
    user_id = "t3-02-unknown-state-log"
    _seed_session(user_id, "a_state_that_does_not_exist")

    with caplog.at_level(logging.ERROR, logger="backend.orchestrator.state_machine"):
        post_turn(client, user_id, text="hello?")

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, "an unrecognized state must be logged at error"
    assert any("a_state_that_does_not_exist" in r.getMessage() for r in errors), (
        "the offending state name must appear in the log line, otherwise the "
        f"operator cannot tell which state broke; got: {[r.getMessage() for r in errors]}"
    )


def test_unknown_state_recovers_to_main_menu(client):
    """
    Recovery, not just a message. Leaving `next_state` on the bad state would soft-lock
    the session: every subsequent turn re-enters the fallback and the user can only
    escape via /introduce.
    """
    user_id = "t3-02-unknown-state-recovers"
    _seed_session(user_id, "nonexistent_state")

    body = post_turn(client, user_id, text="hello?")

    assert body["next_state"] == "main_menu"
    assert all_button_payloads(body), "recovery should re-show the main menu options"


def test_unknown_state_without_language_recovers_to_intro(client):
    """
    No language yet => intro, mirroring `_handle_attachment_ids_sync`'s own answer to
    this question (state_machine.py:671-684). Showing a menu in a language the user
    never chose would be the wrong recovery.
    """
    user_id = "t3-02-unknown-state-no-language"
    _seed_session(user_id, "nonexistent_state", language_code=None)

    body = post_turn(client, user_id, text="hello?")

    assert body["next_state"] == "intro"
    assert _texts(body), "expected a bilingual fallback message before language choice"


def test_unknown_state_recovery_is_bilingual(client):
    """NE sessions get NE copy — the fallback must not silently drop to English."""
    user_id = "t3-02-unknown-state-nepali"
    _seed_session(user_id, "nonexistent_state", language_code="ne")

    body = post_turn(client, user_id, text="नमस्ते")

    joined = " ".join(_texts(body))
    assert "माफ गर्नुहोस्" in joined, (
        f"expected Nepali fallback copy for a ne session; got: {joined!r}"
    )


@pytest.mark.parametrize("deleted_state", ["form_dust", "submit_grievance"])
def test_deleted_states_land_in_the_terminal_else(client, deleted_state):
    """
    Ties the deletion to the guard: pins the post-deletion contract for the two branches
    T3-02 p1 removed after proving nothing assigns them.

    Note what this does NOT assert. Pre-fix these branches were not dead air — seeded
    directly they executed (`submit_grievance` ran the submit action and advanced to
    `grievance_review`). They are dead because nothing *assigns* those states, not
    because the bodies were inert. So this test goes red pre-fix on the recovery
    assertion, not the message one. Post-deletion the states are unrecognized, and the
    terminal `else` is what keeps a session stranded there across a deploy from going
    dark.
    """
    user_id = f"t3-02-deleted-state-{deleted_state}"
    _seed_session(user_id, deleted_state)

    body = post_turn(client, user_id, text="hello?")

    assert _texts(body), f"a session stranded in the deleted {deleted_state!r} state went dark"
    assert body["next_state"] == "main_menu", (
        f"{deleted_state!r} should now be unrecognized and recover via the terminal else"
    )


def test_known_state_does_not_hit_the_fallback(client, caplog):
    """
    CONTROL — proves this suite is not simply failing/passing on everything. A real
    state must be served by its own branch and log no error. This test passes both
    pre-fix and post-fix; if it ever fails, the fallback is swallowing live traffic.
    """
    user_id = "t3-02-known-state-control"
    _seed_session(user_id, "main_menu")

    with caplog.at_level(logging.ERROR, logger="backend.orchestrator.state_machine"):
        body = post_turn(client, user_id, text="hello?")

    assert body["next_state"] != "intro", "main_menu must not be treated as unrecognized"
    unknown_state_errors = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and "unrecognized state" in r.getMessage()
    ]
    assert not unknown_state_errors, (
        f"a known state hit the terminal else: {[r.getMessage() for r in unknown_state_errors]}"
    )
