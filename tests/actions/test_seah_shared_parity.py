"""H2-08 parity tests for the shared SEAH slot logic (backend/actions/forms/seah_shared.py).

Guards that de-duplicating the victim (`form_seah_2`) and focal-point (`form_seah_focal_point`)
forms into `SeahSharedFormMixin` preserved behavior exactly — including the two intentional
parameter deltas (skip allowed on the victim form only; length threshold `> 3` vs `>= 8`).
"""
import pytest

from backend.actions.forms.form_seah_2 import ValidateFormSeah2
from backend.actions.forms.form_seah_focal_point import ValidateFormSeahFocalPoint2
from backend.actions.forms.seah_shared import build_seah_multiselect_buttons
from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker
from tests.orchestrator.conftest import run_async


@pytest.fixture
def victim():
    return ValidateFormSeah2()


@pytest.fixture
def focal():
    return ValidateFormSeahFocalPoint2()


def _validate_detail(form, slot_value, *, description=None):
    tracker = SessionTracker(slots={"grievance_description": description}, sender_id="parity")
    return run_async(
        form.validate_sensitive_issues_new_detail(
            slot_value, CollectingDispatcher(), tracker, {}
        )
    )


def test_config_params_encode_the_two_deltas(victim, focal):
    # Victim: skip allowed, len > 3 (encoded as >= 4). Focal: no skip, len >= 8.
    assert (victim._SEAH_DETAIL_SKIP_ALLOWED, victim._SEAH_DETAIL_MIN_LENGTH) == (True, 4)
    assert (focal._SEAH_DETAIL_SKIP_ALLOWED, focal._SEAH_DETAIL_MIN_LENGTH) == (False, 8)


@pytest.mark.parametrize("command", ["restart", "add_more_details", "submit_details"])
def test_shared_command_branches_are_identical(victim, focal, command):
    """restart / add_more_details / submit_details are shared verbatim → identical on both."""
    assert _validate_detail(victim, command) == _validate_detail(focal, command)


def test_victim_length_threshold_is_gt3(victim):
    skip = victim.SKIP_VALUE
    # len 3 → below threshold → skip default (skip allowed).
    assert _validate_detail(victim, "abc") == {"sensitive_issues_new_detail": skip}
    # len 4 → accepted → appended to grievance_description.
    accepted = _validate_detail(victim, "abcd")
    assert accepted["sensitive_issues_new_detail"] is None
    assert accepted["grievance_description"] == "abcd"
    assert accepted["grievance_description_status"] == "show_options"


def test_focal_length_threshold_is_ge8(focal):
    # len 7 → below threshold → None default (no skip → re-ask), no description written.
    assert _validate_detail(focal, "abcdefg") == {"sensitive_issues_new_detail": None}
    # len 8 → accepted.
    accepted = _validate_detail(focal, "abcdefgh")
    assert accepted["sensitive_issues_new_detail"] is None
    assert accepted["grievance_description"] == "abcdefgh"
    assert accepted["grievance_description_status"] == "show_options"


def test_skip_default_differs_between_forms(victim, focal):
    """A too-short/blank entry: victim defaults to SKIP_VALUE, focal to None (must re-ask)."""
    assert _validate_detail(victim, "x")["sensitive_issues_new_detail"] == victim.SKIP_VALUE
    assert _validate_detail(focal, "x")["sensitive_issues_new_detail"] is None


def test_accepted_detail_appends_to_existing_description(victim):
    accepted = _validate_detail(victim, "second line here", description="first line")
    assert accepted["grievance_description"] == "first line\nsecond line here"


def test_seah_project_identification_validate_is_identical(victim, focal):
    """Both forms delegate to the same shared value validator → identical results."""
    for value in ["/not_adb_project", "yes", "no", "some free text"]:
        tracker = SessionTracker(slots={"language_code": "en"}, sender_id="pid")
        v = run_async(
            victim.validate_seah_project_identification(value, CollectingDispatcher(), tracker, {})
        )
        f = run_async(
            focal.validate_seah_project_identification(value, CollectingDispatcher(), tracker, {})
        )
        assert v == f


class _FakeAction:
    """Stands in for a concrete ask action; get_buttons is resolved per-action in production."""

    def get_buttons(self, _index=1):
        return [{"title": "Option A", "payload": "/a"}, {"title": "Option B", "payload": "/b"}]


def test_multiselect_helper_appends_done_and_hides_selected():
    tracker = SessionTracker(slots={"language_code": "en"}, sender_id="ms")
    buttons = build_seah_multiselect_buttons(_FakeAction(), tracker, "risks_selected")
    assert all("title" in b and "payload" in b for b in buttons)
    assert buttons[-1] == {"title": "Done", "payload": "/selection_done"}
    assert [b["title"] for b in buttons[:-1]] == ["Option A", "Option B"]

    # Already-selected options are filtered out.
    tracker2 = SessionTracker(
        slots={"language_code": "en", "risks_selected": ["Option A"]}, sender_id="ms2"
    )
    buttons2 = build_seah_multiselect_buttons(_FakeAction(), tracker2, "risks_selected")
    titles = [b["title"] for b in buttons2]
    assert "Option A" not in titles
    assert "Option B" in titles


def test_multiselect_helper_localizes_done_button():
    tracker = SessionTracker(slots={"language_code": "ne"}, sender_id="ms-ne")
    buttons = build_seah_multiselect_buttons(_FakeAction(), tracker, "risks_selected")
    assert buttons[-1] == {"title": "सम्पन्न", "payload": "/selection_done"}
