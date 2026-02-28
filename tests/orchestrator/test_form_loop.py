import asyncio

from orchestrator.form_loop import run_form_turn
from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance
from rasa_chatbot.actions.forms.form_status_check import ValidateFormStatusCheck1


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _base_session() -> dict:
    return {
        "user_id": "test-user",
        "state": "form_grievance",
        "active_loop": "form_grievance",
        "requested_slot": "grievance_new_detail",
        "slots": {
            "language_code": "en",
            "complainant_province": "Koshi",
            "complainant_district": "Jhapa",
            "story_main": "new_grievance",
            "grievance_id": "G-TEST-001",
            "complainant_id": "C-TEST-001",
            "grievance_sensitive_issue": False,
            "grievance_description": "My complaint is about delayed services",
            "grievance_new_detail": None,
            "grievance_description_status": "show_options",
        },
    }


def _status_check_session() -> dict:
    return {
        "user_id": "status-user",
        "state": "status_check_form",
        "active_loop": "form_status_check_1",
        "requested_slot": None,
        "slots": {
            "language_code": "en",
            "story_main": "status_check",
            "story_route": None,
            "status_check_grievance_id_selected": None,
            "complainant_phone": None,
        },
    }


def test_submit_details_completes_form(domain):
    form = ValidateFormGrievance()
    session = _base_session()
    user_input = {"text": "/submit_details", "intent": {"name": "submit_details"}}

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=user_input, domain=domain)
    )

    assert completed is True
    assert slot_updates.get("grievance_new_detail") == "completed"
    assert slot_updates.get("requested_slot") is None
    # messages may contain recap or nothing; just ensure list exists
    assert isinstance(messages, list)


def test_free_text_adds_details_and_reasks(domain):
    form = ValidateFormGrievance()
    session = _base_session()
    user_input = {
        "text": "additional detail about my grievance",
        "intent": {"name": "intent_slot_neutral"},
    }

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=user_input, domain=domain)
    )

    assert completed is False
    assert session["slots"]["grievance_description"].startswith(
        "My complaint is about delayed services"
    )
    # We expect at least one ask message after updating description
    assert any("text" in m for m in messages)


def test_status_check_first_turn_asks_for_method(domain):
    form = ValidateFormStatusCheck1()
    session = _status_check_session()

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=None, domain=domain)
    )

    assert completed is False
    # We should now be asking for story_route via action_ask_status_check_method
    assert any("buttons" in m for m in messages)
    assert session["slots"]["requested_slot"] == "story_route"


# Agent 10.E: Verify first ask for form_contact, form_otp, form_status_check_skip,
# form_grievance_complainant_review (no Unknown action errors)
def test_form_contact_first_ask(domain):
    from orchestrator.form_loop import get_form

    form = get_form("form_contact")
    session = {
        "user_id": "test",
        "active_loop": "form_contact",
        "requested_slot": None,
        "slots": {"language_code": "en"},
    }

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=None, domain=domain)
    )

    assert isinstance(messages, list)
    assert completed is False
    assert "requested_slot" in slot_updates


def test_form_otp_first_ask(domain):
    from orchestrator.form_loop import get_form

    form = get_form("form_otp")
    session = {
        "user_id": "test",
        "active_loop": "form_otp",
        "requested_slot": None,
        "slots": {"language_code": "en"},
    }

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=None, domain=domain)
    )

    assert isinstance(messages, list)
    assert completed is False
    assert "requested_slot" in slot_updates


def test_form_status_check_skip_first_ask(domain):
    from orchestrator.form_loop import get_form

    form = get_form("form_status_check_skip")
    session = {
        "user_id": "test",
        "active_loop": "form_status_check_skip",
        "requested_slot": None,
        "slots": {
            "language_code": "en",
            "complainant_province": "Koshi",
            "complainant_district": "Jhapa",
            "valid_province_and_district": None,
        },
    }

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=None, domain=domain)
    )

    assert isinstance(messages, list)
    assert completed is False
    assert "requested_slot" in slot_updates


def test_form_grievance_complainant_review_first_ask(domain):
    from orchestrator.form_loop import get_form

    form = get_form("form_grievance_complainant_review")
    session = {
        "user_id": "test",
        "active_loop": "form_grievance_complainant_review",
        "requested_slot": None,
        "slots": {
            "language_code": "en",
            "grievance_id": "G-TEST-001",
            "complainant_id": "C-TEST-001",
        },
    }

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=None, domain=domain)
    )

    assert isinstance(messages, list)
    assert completed is False
    assert "requested_slot" in slot_updates

