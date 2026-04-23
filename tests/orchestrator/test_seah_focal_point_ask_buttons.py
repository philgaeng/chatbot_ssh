import asyncio

from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker
from backend.orchestrator.action_registry import invoke_action


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_focal_point_2_survivor_risks_ask_includes_buttons(domain):
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots={"language_code": "en"},
        sender_id="focal-risk-test",
    )
    _run(
        invoke_action(
            "action_ask_form_seah_focal_point_2_seah_focal_survivor_risks",
            dispatcher,
            tracker,
            domain,
        )
    )
    assert dispatcher.messages
    last = dispatcher.messages[-1]
    assert "text" in last
    assert "additional risks" in last["text"].lower()
    assert last.get("buttons"), "Risk question should include quick-reply buttons"
    assert len(last["buttons"]) >= 2
    assert any((b.get("payload") or "").lstrip("/") == "selection_done" for b in last["buttons"])


def test_focal_point_2_survivor_risks_hides_selected_option(domain):
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots={
            "language_code": "en",
            "seah_focal_survivor_risks_selected": [
                "Retaliation, intimidation, or threat to job security"
            ],
        },
        sender_id="focal-risk-selected-test",
    )
    _run(
        invoke_action(
            "action_ask_form_seah_focal_point_2_seah_focal_survivor_risks",
            dispatcher,
            tracker,
            domain,
        )
    )
    last = dispatcher.messages[-1]
    titles = [b.get("title") for b in last.get("buttons", [])]
    assert "Retaliation, intimidation, or threat to job security" not in titles
