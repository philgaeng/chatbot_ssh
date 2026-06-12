"""Unit tests for form routing service."""

from unittest.mock import MagicMock

from backend.actions.services.routing.form_next_action import get_next_action_for_form
from backend.config.constants import DEFAULT_VALUES


def _tracker(*, story_main, form_name, story_route=None, story_step=None, slots=None):
    tracker = MagicMock()
    tracker.active_loop = {"name": form_name}
    tracker.latest_action_name = form_name
    slot_data = {
        "story_main": story_main,
        "story_route": story_route,
        "story_step": story_step,
        "grievance_sensitive_issue": False,
        "seah_victim_survivor_role": None,
    }
    if slots:
        slot_data.update(slots)

    def get_slot(name):
        return slot_data.get(name)

    tracker.get_slot.side_effect = get_slot
    return tracker


def test_new_grievance_grievance_to_contact():
    tracker = _tracker(story_main="new_grievance", form_name="form_grievance")
    assert (
        get_next_action_for_form(tracker, skip_value=DEFAULT_VALUES["SKIP_VALUE"])
        == "form_contact"
    )


def test_status_check_sensitive_to_seah():
    tracker = _tracker(
        story_main="new_grievance",
        form_name="form_grievance",
        slots={"grievance_sensitive_issue": True},
    )
    assert (
        get_next_action_for_form(tracker, skip_value=DEFAULT_VALUES["SKIP_VALUE"])
        == "form_seah_1"
    )
