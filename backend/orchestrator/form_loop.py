"""
Form loop driver: required_slots -> extract -> validate -> apply -> ask or complete.
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_RASA_DIR = os.path.join(_REPO_ROOT, "rasa_chatbot")
if _RASA_DIR not in sys.path:
    sys.path.insert(0, _RASA_DIR)

from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker
from backend.orchestrator.action_registry import invoke_action, events_to_slot_updates


_ASK_ACTIONS_BY_SLOT = {
    # Grievance flow
    "grievance_new_detail": "action_ask_grievance_new_detail",
    # Contact form
    "complainant_location_consent": "action_ask_complainant_location_consent",
    "complainant_province": "action_ask_complainant_province",
    "complainant_district": "action_ask_complainant_district",
    "complainant_municipality_temp": "action_ask_complainant_municipality_temp",
    "complainant_municipality_confirmed": "action_ask_complainant_municipality_confirmed",
    "complainant_village_temp": "action_ask_complainant_village_temp",
    "complainant_village_confirmed": "action_ask_complainant_village_confirmed",
    "complainant_ward": "action_ask_complainant_ward",
    "complainant_address_temp": "action_ask_complainant_address_temp",
    "complainant_address_confirmed": "action_ask_complainant_address_confirmed",
    "complainant_consent": "action_ask_complainant_consent",
    "complainant_full_name": "action_ask_complainant_full_name",
    "complainant_email_temp": "action_ask_complainant_email_temp",
    "complainant_email_confirmed": "action_ask_complainant_email_confirmed",
    # OTP form
    "complainant_phone": "action_ask_complainant_phone",
    "otp_consent": "action_ask_otp_consent",
    "otp_input": "action_ask_otp_input",
    # Status check flow
    "story_route": "action_ask_status_check_method",
    "status_check_grievance_id_selected": "action_ask_status_check_grievance_id_selected",
    "status_check_complainant_full_name": "action_ask_status_check_complainant_full_name",
    "status_check_retrieve_grievances": "action_ask_status_check_retrieve_grievances",
    "valid_province_and_district": "action_ask_form_status_check_skip_valid_province_and_district",
    # Grievance review
    "grievance_classification_consent": "action_ask_form_grievance_complainant_review_grievance_classification_consent",
    "grievance_categories_status": "action_ask_form_grievance_complainant_review_grievance_categories_status",
    "grievance_cat_modify": "action_ask_form_grievance_complainant_review_grievance_cat_modify",
    "grievance_summary_status": "action_ask_form_grievance_complainant_review_grievance_summary_status",
    "grievance_summary_temp": "action_ask_form_grievance_complainant_review_grievance_summary_temp",
    # Modify grievance (add more info)
    "modify_follow_up_answer": "action_ask_modify_follow_up_answer",
    "modify_grievance_new_detail": "action_ask_modify_grievance_new_detail",
    # Sensitive issues form
    "sensitive_issues_follow_up": "action_ask_sensitive_issues_follow_up",
    "sensitive_issues_new_detail": "action_ask_sensitive_issues_new_detail",
    "sensitive_issues_nickname": "action_ask_sensitive_issues_nickname",
}

# Form-specific overrides for shared slots (check active_loop + slot first)
_ASK_ACTIONS_BY_FORM_SLOT = {
    ("form_status_check_skip", "valid_province_and_district"): "action_ask_form_status_check_skip_valid_province_and_district",
    ("form_status_check_skip", "complainant_district"): "action_ask_form_status_check_skip_complainant_district",
    ("form_status_check_skip", "complainant_municipality_temp"): "action_ask_form_status_check_skip_complainant_municipality_temp",
    ("form_status_check_skip", "complainant_municipality_confirmed"): "action_ask_form_status_check_skip_complainant_municipality_confirmed",
    ("form_status_check_1", "complainant_phone"): "action_ask_form_status_check_1_complainant_phone",
    ("form_sensitive_issues", "complainant_phone"): "action_ask_form_sensitive_issues_complainant_phone",
    # form_modify_contact: phone has its own ask action for context-specific wording
    ("form_modify_contact", "complainant_phone"): "action_ask_form_modify_contact_complainant_phone",
    ("form_modify_contact", "complainant_full_name"): "action_ask_modify_missing_field",
    ("form_modify_contact", "complainant_province"): "action_ask_modify_missing_field",
    ("form_modify_contact", "complainant_district"): "action_ask_modify_missing_field",
    ("form_modify_contact", "complainant_municipality_temp"): "action_ask_modify_missing_field",
    ("form_modify_contact", "complainant_village_temp"): "action_ask_modify_missing_field",
    ("form_modify_contact", "complainant_ward"): "action_ask_modify_missing_field",
    ("form_modify_contact", "complainant_address_temp"): "action_ask_modify_missing_field",
    ("form_modify_contact", "complainant_email_temp"): "action_ask_modify_missing_field",
    ("form_modify_grievance_details", "modify_follow_up_answer"): "action_ask_modify_follow_up_answer",
}


def _get_ask_action(active_loop: Optional[str], slot: str) -> Optional[str]:
    """Resolve ask action: (active_loop, slot) first, then slot-only."""
    key = (active_loop, slot) if active_loop else None
    if key and key in _ASK_ACTIONS_BY_FORM_SLOT:
        return _ASK_ACTIONS_BY_FORM_SLOT[key]
    return _ASK_ACTIONS_BY_SLOT.get(slot)


async def run_form_turn(
    form: Any,
    session: Dict[str, Any],
    user_input: Optional[Dict[str, Any]],
    domain: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], bool]:
    """Run one turn of a Rasa-style validation form.

    Args:
        form: BaseFormValidationAction instance (grievance or status-check forms)
        session: Session dict with slots, requested_slot, active_loop
        user_input: {"text": str, "intent": {"name": str}} or None for first ask
        domain: Domain dict with slots

    Returns:
        (messages, slot_updates, completed)
    """
    # Stub _trigger_async_classification only when Celery classification is disabled
    # Set ENABLE_CELERY_CLASSIFICATION=1 to use real Celery task (requires Redis + workers)
    if not os.environ.get("ENABLE_CELERY_CLASSIFICATION", "").strip() in ("1", "true", "yes"):
        async def _stub_async_classification(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {}

        if hasattr(form, "_trigger_async_classification"):
            form._trigger_async_classification = _stub_async_classification

    slots = session.get("slots", {})
    domain_slots = list(domain.get("slots", {}).keys())
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots=slots,
        sender_id=session.get("user_id", "default"),
        latest_message=user_input or {},
        active_loop=session.get("active_loop"),
        requested_slot=session.get("requested_slot"),
    )

    required = await form.required_slots(domain_slots, dispatcher, tracker, domain)
    if not required:
        return (dispatcher.messages, {}, True)

    next_slot = _first_empty(required, slots)
    if next_slot is None:
        return (dispatcher.messages, {}, True)

    slot_updates: Dict[str, Any] = {}
    tracker._requested_slot = next_slot
    slots["requested_slot"] = next_slot

    # Run extraction when we have user input: text (including slash-commands from button
    # payloads) or intent (some clients send payload as intent.name with empty text).
    has_input = user_input and (
        user_input.get("text")
        or (user_input.get("intent") or {}).get("name")
    )
    if has_input:
        active_loop = session.get("active_loop")
        extract_name = f"extract_{next_slot}"
        validate_name = f"validate_{next_slot}"
        # Form-specific method names (e.g. form_sensitive_issues has extract_form_sensitive_issues_complainant_phone)
        if active_loop:
            extract_name_form = f"extract_{active_loop}_{next_slot}".replace(" ", "_")
            validate_name_form = f"validate_{active_loop}_{next_slot}".replace(" ", "_")
            if hasattr(form, extract_name_form):
                extract_name = extract_name_form
            if hasattr(form, validate_name_form):
                validate_name = validate_name_form

        raw: Dict[str, Any] = {}
        if hasattr(form, extract_name):
            extract_fn = getattr(form, extract_name)
            raw = await extract_fn(dispatcher, tracker, domain)  # type: ignore[arg-type]
        elif hasattr(form, "extract_grievance_new_detail"):
            # Backwards compatibility for grievance form
            raw = await form.extract_grievance_new_detail(  # type: ignore[attr-defined]
                dispatcher, tracker, domain
            )

        slot_value = None
        if raw:
            if next_slot in raw:
                slot_value = raw.get(next_slot)
            elif "grievance_new_detail" in raw:
                slot_value = raw.get("grievance_new_detail")

        if slot_value is not None:
            if hasattr(form, validate_name):
                validate_fn = getattr(form, validate_name)
                slot_updates = await validate_fn(  # type: ignore[misc]
                    slot_value, dispatcher, tracker, domain
                )
            elif hasattr(form, "validate_grievance_new_detail"):
                slot_updates = await form.validate_grievance_new_detail(  # type: ignore[attr-defined]
                    slot_value, dispatcher, tracker, domain
                )

        if slot_updates:
            slots.update(slot_updates)
            tracker._slots.update(slot_updates)

    required_after = await form.required_slots(
        domain_slots, dispatcher, tracker, domain
    )
    # Next slot to ask: first empty in required_after (may differ from next_slot after validation)
    next_slot_to_ask = _first_empty(required_after, slots) if required_after else None
    # Form completes when all required slots are filled (no next slot to ask)
    completed = next_slot_to_ask is None

    if not completed:
        if next_slot_to_ask and not slot_updates.get("skip_validation_needed"):
            ask_dispatcher = CollectingDispatcher()
            ask_tracker = SessionTracker(
                slots=slots,
                sender_id=tracker.sender_id,
                latest_message=tracker.latest_message,
                active_loop=session.get("active_loop"),
                requested_slot=next_slot_to_ask,
            )
            ask_action_name = _get_ask_action(session.get("active_loop"), next_slot_to_ask)
            if ask_action_name:
                try:
                    events = await invoke_action(
                        ask_action_name,
                        ask_dispatcher,
                        ask_tracker,
                        domain,
                    )
                    ask_slot_updates = events_to_slot_updates(events or [])
                    if ask_slot_updates:
                        slots.update(ask_slot_updates)
                        tracker._slots.update(ask_slot_updates)
                        slot_updates.update(ask_slot_updates)
                except Exception:
                    ask_dispatcher.messages.append({
                        "text": "Please provide the requested information.",
                    })
            dispatcher.messages.extend(ask_dispatcher.messages)
            if not dispatcher.messages and next_slot_to_ask:
                dispatcher.messages.append({"text": "Please provide the requested information."})
        slot_updates["requested_slot"] = next_slot_to_ask

    if completed:
        slot_updates["requested_slot"] = None
        slot_updates["active_loop"] = None

    return (dispatcher.messages, slot_updates, completed)


def _first_empty(required: List[str], slots: Dict[str, Any]) -> Optional[str]:
    """First slot in required that is empty/None."""
    for s in required:
        v = slots.get(s)
        if v is None or v == "":
            return s
    return None


# Lazy form instances (loaded on first use)
_FORMS: Dict[str, Any] = {}


def get_form(active_loop: str) -> Any:
    """
    Get form instance by active_loop name. Lazy-loads on first use.

    Supports: form_grievance, form_contact, form_otp, form_status_check_1,
    form_status_check_2, form_status_check_skip, form_grievance_complainant_review.
    """
    if active_loop not in _FORMS:
        if active_loop == "form_grievance":
            from backend.actions.forms.form_grievance import ValidateFormGrievance
            _FORMS[active_loop] = ValidateFormGrievance()
        elif active_loop == "form_contact":
            from backend.actions.forms.form_contact import ValidateFormContact
            _FORMS[active_loop] = ValidateFormContact()
        elif active_loop == "form_otp":
            from backend.actions.forms.form_otp import ValidateFormOtp
            _FORMS[active_loop] = ValidateFormOtp()
        elif active_loop == "form_status_check_1":
            from backend.actions.forms.form_status_check import ValidateFormStatusCheck1
            _FORMS[active_loop] = ValidateFormStatusCheck1()
        elif active_loop == "form_status_check_2":
            from backend.actions.forms.form_status_check import ValidateFormStatusCheck2
            _FORMS[active_loop] = ValidateFormStatusCheck2()
        elif active_loop == "form_status_check_skip":
            from backend.actions.forms.form_status_check_skip import ValidateFormSkipStatusCheck
            _FORMS[active_loop] = ValidateFormSkipStatusCheck()
        elif active_loop == "form_grievance_complainant_review":
            from backend.actions.forms.form_grievance_complainant_review import ValidateFormGrievanceComplainantReview
            _FORMS[active_loop] = ValidateFormGrievanceComplainantReview()
        elif active_loop == "form_sensitive_issues":
            from backend.actions.forms.form_sensitive_issues import ValidateFormSensitiveIssues
            _FORMS[active_loop] = ValidateFormSensitiveIssues()
        elif active_loop == "form_modify_grievance_details":
            from backend.actions.forms.form_modify_grievance import ValidateFormModifyGrievanceDetails
            _FORMS[active_loop] = ValidateFormModifyGrievanceDetails()
        elif active_loop == "form_modify_contact":
            from backend.actions.forms.form_modify_contact import ValidateFormModifyContact
            _FORMS[active_loop] = ValidateFormModifyContact()
        else:
            raise ValueError(f"Unknown form: {active_loop}")
    return _FORMS[active_loop]
