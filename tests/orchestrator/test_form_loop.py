import asyncio

from backend.orchestrator.form_loop import run_form_turn
from backend.actions.forms.form_grievance import ValidateFormGrievance
from backend.actions.forms.form_status_check import ValidateFormStatusCheck1
from backend.actions.forms.form_sensitive_issues import ValidateFormSensitiveIssues


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
    from backend.orchestrator.form_loop import get_form

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
    from backend.orchestrator.form_loop import get_form

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
    from backend.orchestrator.form_loop import get_form

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
    from backend.orchestrator.form_loop import get_form

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


def test_seah_focal_point_branch_requires_focal_slots(domain):
    form = ValidateFormSensitiveIssues()
    session = {
        "user_id": "seah-focal",
        "active_loop": "form_sensitive_issues",
        "requested_slot": "seah_focal_full_name",
        "slots": {
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "sensitive_issues_follow_up": "identified",
            "seah_victim_survivor_role": "focal_point",
            "complainant_phone": "9800000000",
            "complainant_email_temp": "focal@example.org",
            "seah_project_identification": "cannot_specify",
            "sensitive_issues_new_detail": "summary",
            "seah_focal_full_name": None,
        },
    }
    user_input = {"text": "John Focal", "intent": {"name": "intent_slot_neutral"}}

    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=user_input, domain=domain)
    )

    assert completed is False
    assert slot_updates.get("seah_focal_full_name") == "John Focal"
    assert slot_updates.get("seah_focal_lookup_status") == "found"
    assert isinstance(messages, list)


def test_seah_focal_lookup_fallback_sets_unverified(domain):
    form = ValidateFormSensitiveIssues()
    session = {
        "user_id": "seah-focal-fallback",
        "active_loop": "form_sensitive_issues",
        "requested_slot": "seah_focal_full_name",
        "slots": {
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "sensitive_issues_follow_up": "identified",
            "seah_victim_survivor_role": "focal_point",
            "complainant_phone": "9800000000",
            "complainant_email_temp": "focal@example.org",
            "seah_project_identification": "cannot_specify",
            "sensitive_issues_new_detail": "summary",
            "seah_focal_lookup_attempts": 1,
            "seah_focal_full_name": None,
        },
    }
    user_input = {"text": "Unknown Person", "intent": {"name": "intent_slot_neutral"}}

    _, slot_updates, _ = _run(
        run_form_turn(form=form, session=session, user_input=user_input, domain=domain)
    )
    assert slot_updates.get("seah_focal_verification_status") == "unverified_focal_point"


def test_seah_focal_otp_failure_allows_unverified_tag(domain):
    form = ValidateFormSensitiveIssues()
    session = {
        "user_id": "seah-focal-otp",
        "active_loop": "form_sensitive_issues",
        "requested_slot": "seah_focal_otp_input",
        "slots": {
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "sensitive_issues_follow_up": "identified",
            "seah_victim_survivor_role": "focal_point",
            "complainant_phone": "9800000000",
            "complainant_email_temp": "focal@example.org",
            "seah_project_identification": "cannot_specify",
            "sensitive_issues_new_detail": "summary",
            "seah_focal_lookup_status": "found",
            "seah_focal_full_name": "John Focal",
            "seah_focal_otp_number": "123456",
            "seah_focal_otp_attempts": 2,
            "seah_focal_otp_input": None,
        },
    }
    user_input = {"text": "000000", "intent": {"name": "intent_slot_neutral"}}

    _, slot_updates, _ = _run(
        run_form_turn(form=form, session=session, user_input=user_input, domain=domain)
    )
    assert slot_updates.get("seah_focal_verification_status") == "unverified_focal_point"


def test_seah_non_focal_required_slots_do_not_include_focal_questions(domain):
    form = ValidateFormSensitiveIssues()
    tracker_slots = {
        "language_code": "en",
        "grievance_sensitive_issue": True,
        "seah_victim_survivor_role": "victim_survivor",
    }
    from backend.orchestrator.adapters import SessionTracker
    tracker = SessionTracker(slots=tracker_slots, sender_id="seah-non-focal")
    dispatcher = None

    required = _run(form.required_slots([], dispatcher, tracker, domain))
    assert "seah_focal_full_name" not in required
    assert "seah_focal_otp_input" not in required
    assert "seah_focal_survivor_risks" not in required


def test_seah_focal_required_slots_include_lookup_then_otp(domain):
    form = ValidateFormSensitiveIssues()
    from backend.orchestrator.adapters import SessionTracker

    tracker_before_lookup = SessionTracker(
        slots={
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "seah_victim_survivor_role": "focal_point",
        },
        sender_id="seah-focal-before",
    )
    required_before = _run(form.required_slots([], None, tracker_before_lookup, domain))
    assert "seah_focal_full_name" in required_before
    assert "seah_focal_otp_input" not in required_before

    tracker_after_lookup = SessionTracker(
        slots={
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "seah_victim_survivor_role": "focal_point",
            "seah_focal_lookup_status": "found",
        },
        sender_id="seah-focal-after",
    )
    required_after = _run(form.required_slots([], None, tracker_after_lookup, domain))
    assert "seah_focal_full_name" in required_after
    assert "seah_focal_otp_input" in required_after


def test_seah_project_not_adb_branch_sets_flag(domain):
    form = ValidateFormSensitiveIssues()
    from backend.orchestrator.adapters import SessionTracker

    tracker = SessionTracker(
        slots={"language_code": "en", "grievance_sensitive_issue": True},
        sender_id="seah-not-adb",
    )
    result = _run(
        form.validate_seah_project_identification(
            "/not_adb_project", None, tracker, domain
        )
    )
    assert result.get("seah_project_identification") == "not_adb_project"
    assert result.get("seah_not_adb_project") is True


def test_seah_incident_summary_handles_missing_grievance_description(domain):
    form = ValidateFormSensitiveIssues()
    from backend.orchestrator.adapters import SessionTracker

    tracker = SessionTracker(
        slots={
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "grievance_description": None,
        },
        sender_id="seah-summary-missing-base",
    )
    result = _run(
        form.validate_sensitive_issues_new_detail(
            "someone followed me and touched me",
            None,
            tracker,
            domain,
        )
    )
    assert result.get("sensitive_issues_new_detail") == "someone followed me and touched me"
    assert result.get("grievance_description") == "someone followed me and touched me"
    assert result.get("grievance_description_status") == "completed"

