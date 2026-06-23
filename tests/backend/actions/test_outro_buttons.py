"""Characterization tests for the extracted outro button helper."""

from backend.actions.services.outro.buttons import post_submit_buttons
from backend.actions.utils.mapping_buttons import (
    BUTTONS_CLOSE_SESSION_ONLY,
    BUTTONS_FILE_ANOTHER_GRIEVANCE,
)


def test_post_submit_buttons_en():
    buttons = post_submit_buttons("en")
    expected = (
        BUTTONS_CLOSE_SESSION_ONLY["en"] + BUTTONS_FILE_ANOTHER_GRIEVANCE["en"]
    )
    assert buttons == expected


def test_post_submit_buttons_ne():
    buttons = post_submit_buttons("ne")
    expected = (
        BUTTONS_CLOSE_SESSION_ONLY["ne"] + BUTTONS_FILE_ANOTHER_GRIEVANCE["ne"]
    )
    assert buttons == expected


def test_post_submit_buttons_unknown_language_falls_back_to_en():
    buttons = post_submit_buttons("xx")
    expected = (
        BUTTONS_CLOSE_SESSION_ONLY["en"] + BUTTONS_FILE_ANOTHER_GRIEVANCE["en"]
    )
    assert buttons == expected


def test_post_submit_buttons_returns_new_list():
    first = post_submit_buttons("en")
    first.append({"title": "x", "payload": "/x"})
    assert post_submit_buttons("en") != first
