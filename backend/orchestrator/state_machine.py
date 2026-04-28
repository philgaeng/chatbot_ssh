"""
State machine: drives all flows from flow.yaml.

New grievance: intro -> main_menu -> form_grievance -> contact_form -> otp_form
    -> submit_grievance -> grievance_review -> done.
Status check: intro -> main_menu -> status_check_form (form_status_check_1 ->
    form_otp | form_status_check_2 | form_status_check_skip) -> done.
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple


def _silence_third_party_loggers() -> None:
    """Ensure botocore/boto3 don't flood logs when backend/messaging load on first request."""
    for name in ("botocore", "boto3", "urllib3", "s3transfer"):
        logging.getLogger(name).setLevel(logging.WARNING)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker
from backend.orchestrator.action_registry import invoke_action, events_to_slot_updates
from backend.orchestrator.form_loop import run_form_turn
from backend.orchestrator.session_store import DEFAULT_SLOTS

_log_sm = logging.getLogger(__name__)


async def _append_seah_outro_after_submit_if_applicable(
    dispatcher: CollectingDispatcher,
    session: Dict[str, Any],
    latest_message: Dict[str, Any],
    domain: Dict[str, Any],
    slot_updates: Dict[str, Any],
) -> None:
    """After successful action_submit_seah, append variant outro + referral (spec 08)."""
    slots = session.get("slots", {})
    if slots.get("story_main") != "seah_intake":
        return
    # Phase 2 canonical reference: grievance_id is the only case reference.
    if not slots.get("grievance_id"):
        return
    outro_dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots=dict(slots),
        sender_id=session.get("user_id", "default"),
        latest_message=latest_message,
        active_loop=None,
        requested_slot=None,
    )
    try:
        events = await invoke_action(
            "action_seah_outro",
            outro_dispatcher,
            tracker,
            domain,
        )
        if events:
            ou = events_to_slot_updates(events)
            slot_updates.update(ou)
            session["slots"].update(ou)
        dispatcher.messages.extend(outro_dispatcher.messages)
    except Exception as e:
        _log_sm.warning("action_seah_outro failed after submit: %s", e, exc_info=True)


# Lazy form instances
_FORM = None
_STATUS_FORM_1 = None
_STATUS_FORM_2 = None
_CONTACT_FORM = None
_OTP_FORM = None
_REVIEW_FORM = None
_STATUS_FORM_SKIP = None


def _get_form() -> Any:
    global _FORM
    if _FORM is None:
        from backend.actions.forms.form_grievance import ValidateFormGrievance
        _FORM = ValidateFormGrievance()
    return _FORM


def _get_status_form_1() -> Any:
    global _STATUS_FORM_1
    if _STATUS_FORM_1 is None:
        from backend.actions.forms.form_status_check import ValidateFormStatusCheck1
        _STATUS_FORM_1 = ValidateFormStatusCheck1()
    return _STATUS_FORM_1


def _get_status_form_2() -> Any:
    global _STATUS_FORM_2
    if _STATUS_FORM_2 is None:
        from backend.actions.forms.form_status_check import ValidateFormStatusCheck2
        _STATUS_FORM_2 = ValidateFormStatusCheck2()
    return _STATUS_FORM_2


def _get_contact_form() -> Any:
    global _CONTACT_FORM
    if _CONTACT_FORM is None:
        from backend.actions.forms.form_contact import ValidateFormContact
        _CONTACT_FORM = ValidateFormContact()
    return _CONTACT_FORM


def _get_otp_form() -> Any:
    global _OTP_FORM
    if _OTP_FORM is None:
        from backend.actions.forms.form_otp import ValidateFormOtp
        _OTP_FORM = ValidateFormOtp()
    return _OTP_FORM


def _get_review_form() -> Any:
    global _REVIEW_FORM
    if _REVIEW_FORM is None:
        from backend.actions.forms.form_grievance_complainant_review import ValidateFormGrievanceComplainantReview
        _REVIEW_FORM = ValidateFormGrievanceComplainantReview()
    return _REVIEW_FORM


def _get_status_form_skip() -> Any:
    global _STATUS_FORM_SKIP
    if _STATUS_FORM_SKIP is None:
        from backend.actions.forms.form_status_check_skip import ValidateFormSkipStatusCheck
        _STATUS_FORM_SKIP = ValidateFormSkipStatusCheck()
    return _STATUS_FORM_SKIP


_SEAH_1_FORM = None
_SEAH_2_FORM = None
_SEAH_FOCAL_FORM_1 = None
_SEAH_FOCAL_FORM_2 = None


def _is_seah_enabled() -> bool:
    return os.environ.get("ENABLE_SEAH_DEDICATED_FLOW", "true").strip().lower() in ("1", "true", "yes")


def _get_form_seah_1() -> Any:
    global _SEAH_1_FORM
    if _SEAH_1_FORM is None:
        from backend.actions.forms.form_seah_1 import ValidateFormSeah1
        _SEAH_1_FORM = ValidateFormSeah1()
    return _SEAH_1_FORM


def _get_form_seah_2() -> Any:
    global _SEAH_2_FORM
    if _SEAH_2_FORM is None:
        from backend.actions.forms.form_seah_2 import ValidateFormSeah2
        _SEAH_2_FORM = ValidateFormSeah2()
    return _SEAH_2_FORM


def _get_form_seah_focal_point_1() -> Any:
    global _SEAH_FOCAL_FORM_1
    if _SEAH_FOCAL_FORM_1 is None:
        from backend.actions.forms.form_seah_focal_point import ValidateFormSeahFocalPoint1
        _SEAH_FOCAL_FORM_1 = ValidateFormSeahFocalPoint1()
    return _SEAH_FOCAL_FORM_1


def _get_form_seah_focal_point_2() -> Any:
    global _SEAH_FOCAL_FORM_2
    if _SEAH_FOCAL_FORM_2 is None:
        from backend.actions.forms.form_seah_focal_point import ValidateFormSeahFocalPoint2
        _SEAH_FOCAL_FORM_2 = ValidateFormSeahFocalPoint2()
    return _SEAH_FOCAL_FORM_2


_FORM_MODIFY_GRIEVANCE = None


def _get_form_modify_grievance_details() -> Any:
    global _FORM_MODIFY_GRIEVANCE
    if _FORM_MODIFY_GRIEVANCE is None:
        from backend.actions.forms.form_modify_grievance import ValidateFormModifyGrievanceDetails
        _FORM_MODIFY_GRIEVANCE = ValidateFormModifyGrievanceDetails()
    return _FORM_MODIFY_GRIEVANCE


_FORM_MODIFY_CONTACT = None


def _get_form_modify_contact() -> Any:
    global _FORM_MODIFY_CONTACT
    if _FORM_MODIFY_CONTACT is None:
        from backend.actions.forms.form_modify_contact import ValidateFormModifyContact
        _FORM_MODIFY_CONTACT = ValidateFormModifyContact()
    return _FORM_MODIFY_CONTACT


# Payload -> intent mapping (from 04_flow_logic.md and extended status-check flow)
PAYLOAD_TO_INTENT = {
    "set_english": "set_english",
    "set_nepali": "set_nepali",
    "new_grievance": "new_grievance",
    "seah_intake": "start_seah_intake",
    "check_status": "start_status_check",
    "start_status_check": "start_status_check",
    "route_status_check_phone": "route_status_check_phone",
    "route_status_check_grievance_id": "route_status_check_grievance_id",
    "status_check_request_follow_up": "status_check_request_follow_up",
    "status_check_modify_grievance": "status_check_modify_grievance",
    "modify_grievance_add_pictures": "modify_grievance_add_pictures",
    "modify_grievance_add_more_info": "modify_grievance_add_more_info",
    "modify_grievance_add_missing_info": "modify_grievance_add_missing_info",
    "modify_missing_done": "modify_missing_done",
    "modify_grievance_cancel": "modify_grievance_cancel",
    "submit_details": "submit_details",
    "add_more_details": "add_more_details",
    "restart": "restart",
    "skip": "skip",
    "identified": "identified",
    "anonymous": "anonymous",
    "victim_survivor": "victim_survivor",
    "not_victim_survivor": "not_victim_survivor",
    "focal_point": "focal_point",
    "yes": "affirm",
    "no": "deny",
    "not_adb_project": "not_adb_project",
    "cannot_specify": "cannot_specify",
    "phone": "phone",
    "email": "email",
    "both": "both",
    "none": "none",
    "affirm_skip": "affirm",
    "deny_skip": "deny",
    "not_sensitive_content": "not_sensitive_content",
    "anonymous": "anonymous",
    "anonymous_with_phone": "anonymous_with_phone",
    "exit": "exit",
}


def derive_intent(text: str, payload: Optional[str]) -> str:
    """Derive intent from payload or text."""
    if payload:
        raw = payload.strip("/").strip() if payload.startswith("/") else payload
        return PAYLOAD_TO_INTENT.get(raw, "intent_slot_neutral")
    if text and text.strip().startswith("/"):
        raw = text.strip().lstrip("/").strip()
        return PAYLOAD_TO_INTENT.get(raw, raw or "intent_slot_neutral")
    return "intent_slot_neutral"


def build_latest_message(text: str, payload: Optional[str], intent: str) -> Dict[str, Any]:
    """
    Build latest_message dict for tracker.

    Rasa-style extract/validate logic relies on latest_message['text'] containing
    either the raw user text or the command payload (e.g. \"/submit_details\").
    When the client sends both (e.g. button label as text and /slot_confirmed as payload),
    prefer the payload so the form sees the slash-command and not the label (which can
    be misclassified e.g. as skip).
    """
    if payload and payload.strip().startswith("/"):
        msg_text = payload.strip()
    else:
        msg_text = text or (payload or "")
    return {"text": msg_text, "intent": {"name": intent}}


async def run_flow_turn(
    session: Dict[str, Any],
    text: str,
    payload: Optional[str],
    domain: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Run one turn of the flow.

    Returns:
        (messages, next_state, expected_input_type)
    """
    _silence_third_party_loggers()  # Keep botocore/boto3 quiet when backend loads lazily
    intent = derive_intent(text, payload)
    latest_message = build_latest_message(text, payload, intent)
    slots = session.get("slots", {})
    state = session.get("state", "intro")

    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots=slots,
        sender_id=session.get("user_id", "default"),
        latest_message=latest_message,
        active_loop=session.get("active_loop"),
        requested_slot=session.get("requested_slot"),
    )

    next_state = state
    slot_updates: Dict[str, Any] = {}
    msg_text = (latest_message.get("text") or "").strip()
    payload_raw = (payload or "").strip()

    # REST webchat sends /introduce on page load. Treat it as a hard reset from
    # any in-flight state so refresh always starts a clean session.
    introduce_restart = msg_text.lower().startswith("/introduce") or payload_raw.lower().startswith("/introduce")
    if introduce_restart and state != "intro":
        session["state"] = "intro"
        session["active_loop"] = None
        session["requested_slot"] = None
        session["slots"] = DEFAULT_SLOTS.copy()
        next_state = "intro"
        intro_tracker = SessionTracker(
            slots=session["slots"],
            sender_id=session.get("user_id", "default"),
            latest_message=latest_message,
            active_loop=None,
            requested_slot=None,
        )
        events = await invoke_action(
            "action_introduce",
            dispatcher,
            intro_tracker,
            domain,
        )
        slot_updates.update(events_to_slot_updates(events))
        session["slots"].update(slot_updates)
        return (dispatcher.messages, next_state, "buttons")

    if state == "intro":
        # First turn: show language selection intro. On subsequent turns, when the
        # user clicks a language button, set the language and go straight to main
        # menu without re-sending the intro message.
        if intent in ("set_english", "set_nepali"):
            action_name = f"action_{intent}"  # action_set_english, action_set_nepali
            lang_dispatcher = CollectingDispatcher()
            events = await invoke_action(
                action_name,
                lang_dispatcher,
                tracker,
                domain,
            )
            slot_updates = events_to_slot_updates(events)
            session["slots"].update(slot_updates)

            # Immediately show the main menu in the selected language so the user
            # doesn't need to click the language button twice.
            main_dispatcher = CollectingDispatcher()
            main_tracker = SessionTracker(
                slots=session["slots"],
                sender_id=session.get("user_id", "default"),
                latest_message=latest_message,
                active_loop=None,
                requested_slot=None,
            )
            await invoke_action(
                "action_main_menu",
                main_dispatcher,
                main_tracker,
                domain,
            )
            dispatcher.messages.extend(main_dispatcher.messages)
            next_state = "main_menu"
        else:
            await invoke_action("action_introduce", dispatcher, tracker, domain)

    elif state == "main_menu":
        await invoke_action("action_main_menu", dispatcher, tracker, domain)
        if intent == "new_grievance":
            ask_dispatcher = CollectingDispatcher()
            events = await invoke_action(
                "action_start_grievance_process",
                ask_dispatcher,
                tracker,
                domain,
            )
            slot_updates = events_to_slot_updates(events)
            dispatcher.messages.extend(ask_dispatcher.messages)
            session["slots"].update(slot_updates)
            session["active_loop"] = "form_grievance"
            session["requested_slot"] = "grievance_new_detail"
            next_state = "form_grievance"
            # First form prompt: run form loop with no user input
            session_copy = dict(session)
            session_copy["slots"] = dict(session["slots"])
            form = _get_form()
            msgs, form_updates, completed = await run_form_turn(
                form, session_copy, None, domain
            )
            dispatcher.messages.extend(msgs)
            slot_updates.update(form_updates)
            if completed:
                next_state = "contact_form"
                session["active_loop"] = "form_contact"
                session["requested_slot"] = None
        elif intent == "start_seah_intake" and _is_seah_enabled():
            slot_updates["story_main"] = "seah_intake"
            slot_updates["grievance_sensitive_issue"] = True
            session["slots"].update(slot_updates)
            session["active_loop"] = "form_seah_1"
            session["requested_slot"] = None
            next_state = "form_seah_1"
            session_copy = dict(session)
            session_copy["slots"] = dict(session["slots"])
            sensitive_form = _get_form_seah_1()
            msgs, form_updates, completed = await run_form_turn(
                sensitive_form, session_copy, None, domain
            )
            dispatcher.messages.extend(msgs)
            slot_updates.update(form_updates)
            if completed:
                next_state = "contact_form"
                session["active_loop"] = "form_contact"
                session["requested_slot"] = None
        elif intent == "start_seah_intake" and not _is_seah_enabled():
            # Feature-flag off: keep legacy behavior and do not enter dedicated SEAH flow.
            next_state = "main_menu"
        elif intent == "start_status_check":
            ask_dispatcher = CollectingDispatcher()
            events = await invoke_action(
                "action_start_status_check",
                ask_dispatcher,
                tracker,
                domain,
            )
            slot_updates = events_to_slot_updates(events)
            dispatcher.messages.extend(ask_dispatcher.messages)
            session["slots"].update(slot_updates)
            session["active_loop"] = "form_status_check_1"
            session["requested_slot"] = None
            next_state = "status_check_form"
            # First form prompt: run form loop with no user input
            session_copy = dict(session)
            session_copy["slots"] = dict(session["slots"])
            form_status_1 = _get_status_form_1()
            msgs, form_updates, completed = await run_form_turn(
                form_status_1, session_copy, None, domain
            )
            dispatcher.messages.extend(msgs)
            slot_updates.update(form_updates)
            if completed:
                next_state = "done"
                session["active_loop"] = None
                session["requested_slot"] = None

    elif state == "form_grievance":
        user_input = latest_message if (text or payload) else None
        form = _get_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            session["slots"].update(slot_updates)
            if session.get("slots", {}).get("grievance_sensitive_issue"):
                next_state = "form_seah_1"
                session["active_loop"] = "form_seah_1"
                session["requested_slot"] = None
                sensitive_form = _get_form_seah_1()
                msgs2, form_updates2, _ = await run_form_turn(
                    sensitive_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)
            else:
                next_state = "contact_form"
                session["active_loop"] = "form_contact"
                session["requested_slot"] = None
                contact_form = _get_contact_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    contact_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)

    elif state == "form_seah_1":
        user_input = latest_message if (text or payload) else None
        form = _get_form_seah_1()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            # Merge this turn's form output so routing sees slots set in the same turn
            # (e.g. seah_victim_survivor_role after the victim/survivor answer).
            merged_slots = {**session.get("slots", {}), **form_updates}
            story_main = merged_slots.get("story_main")
            identity_mode = merged_slots.get("sensitive_issues_follow_up")
            seah_role = merged_slots.get("seah_victim_survivor_role")
            next_state = "contact_form"
            session["active_loop"] = "form_contact"
            session["requested_slot"] = None
            session["slots"].update(slot_updates)
            _log = logging.getLogger("orchestrator.state_machine")
            contact_slots = ["complainant_location_consent", "complainant_province", "complainant_village_temp", "complainant_consent"]
            slot_preview = {k: session["slots"].get(k) for k in contact_slots}
            _log.info("form_seah_1 completed -> contact_form | contact slot preview: %s", slot_preview)
            # Focal-point branch first bootstraps reporter phone/name/location using shared OTP/contact forms.
            if story_main == "seah_intake" and seah_role == "focal_point":
                next_state = "otp_form"
                session["active_loop"] = "form_otp"
                session["requested_slot"] = None
                slot_updates["seah_focal_stage"] = "bootstrap_reporter_otp"
                session["slots"]["seah_focal_stage"] = "bootstrap_reporter_otp"
                otp_form = _get_otp_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    otp_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)
            # In dedicated SEAH intake, identified users should be asked for phone first.
            elif story_main == "seah_intake" and identity_mode == "identified":
                next_state = "otp_form"
                session["active_loop"] = "form_otp"
                session["requested_slot"] = None
                otp_form = _get_otp_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    otp_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)
            # Anonymous SEAH now uses the same OTP hop as identified flow, so phone can
            # still be requested/collected consistently for victim and other routes.
            elif story_main == "seah_intake" and identity_mode == "anonymous":
                next_state = "otp_form"
                session["active_loop"] = "form_otp"
                session["requested_slot"] = None
                otp_form = _get_otp_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    otp_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)
            else:
                contact_form = _get_contact_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    contact_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)

    elif state == "contact_form":
        user_input = latest_message if (text or payload) else None
        form = _get_contact_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            session["slots"].update(slot_updates)
            story_main = session.get("slots", {}).get("story_main")
            complainant_consent = session.get("slots", {}).get("complainant_consent")
            seah_victim_survivor_role = session.get("slots", {}).get("seah_victim_survivor_role")
            seah_focal_stage = session.get("slots", {}).get("seah_focal_stage")

            # Dedicated SEAH intake must always collect SEAH incident details
            # in form_seah_2 / form_seah_focal_point before submission.
            if story_main == "seah_intake":
                if seah_victim_survivor_role == "focal_point" and seah_focal_stage == "bootstrap_reporter_contact":
                    prep_dispatcher = CollectingDispatcher()
                    prep_events = await invoke_action(
                        "action_prepare_seah_focal_complainant_capture",
                        prep_dispatcher,
                        SessionTracker(
                            slots=session["slots"],
                            sender_id=session.get("user_id", "default"),
                            latest_message=latest_message,
                            active_loop=None,
                            requested_slot=None,
                        ),
                        domain,
                    )
                    prep_updates = events_to_slot_updates(prep_events)
                    slot_updates.update(prep_updates)
                    session["slots"].update(prep_updates)
                    next_state = "form_seah_focal_point_1"
                    session["active_loop"] = "form_seah_focal_point_1"
                    slot_updates["seah_focal_stage"] = "focal_point_1"
                    session["slots"]["seah_focal_stage"] = "focal_point_1"
                    seah_form = _get_form_seah_focal_point_1()
                elif seah_victim_survivor_role == "focal_point" and seah_focal_stage == "complainant_contact":
                    next_state = "form_seah_focal_point_2"
                    session["active_loop"] = "form_seah_focal_point_2"
                    slot_updates["seah_focal_stage"] = "focal_point_2"
                    session["slots"]["seah_focal_stage"] = "focal_point_2"
                    seah_form = _get_form_seah_focal_point_2()
                elif seah_victim_survivor_role == "focal_point":
                    next_state = "form_seah_focal_point_2"
                    session["active_loop"] = "form_seah_focal_point_2"
                    slot_updates["seah_focal_stage"] = "focal_point_2"
                    session["slots"]["seah_focal_stage"] = "focal_point_2"
                    seah_form = _get_form_seah_focal_point_2()
                else:
                    next_state = "form_seah_2"
                    session["active_loop"] = "form_seah_2"
                    seah_form = _get_form_seah_2()

                session["requested_slot"] = None
                msgs2, form_updates2, _ = await run_form_turn(
                    seah_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)

            # If the user refused to share any contact information in the grievance flow,
            # skip the OTP form entirely and move directly to grievance submission +
            # review (same path as otp_form completed for new_grievance).
            elif story_main in ("new_grievance", "grievance_submission") and complainant_consent is False:
                session["active_loop"] = None
                session["requested_slot"] = None

                ask_dispatcher = CollectingDispatcher()
                tracker_submit = SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                )
                submit_action = "action_submit_seah" if story_main == "seah_intake" else "action_submit_grievance"
                events = await invoke_action(
                    submit_action,
                    ask_dispatcher,
                    tracker_submit,
                    domain,
                )
                submit_updates = events_to_slot_updates(events)
                slot_updates.update(submit_updates)
                session["slots"].update(submit_updates)
                dispatcher.messages.extend(ask_dispatcher.messages)

                next_state = "grievance_review"
                session["active_loop"] = "form_grievance_complainant_review"
                session["requested_slot"] = None

                retrieve_dispatcher = CollectingDispatcher()
                retrieve_tracker = SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                )
                retrieve_events = await invoke_action(
                    "action_retrieve_classification_results",
                    retrieve_dispatcher,
                    retrieve_tracker,
                    domain,
                )
                if retrieve_events:
                    retrieve_updates = events_to_slot_updates(retrieve_events)
                    session["slots"].update(retrieve_updates)
                    slot_updates.update(retrieve_updates)
                dispatcher.messages.extend(retrieve_dispatcher.messages)

                review_form = _get_review_form()
                msgs_review, form_updates_review, _ = await run_form_turn(
                    review_form, session, None, domain
                )
                dispatcher.messages.extend(msgs_review)
                slot_updates.update(form_updates_review)
            else:
                next_state = "otp_form"
                session["active_loop"] = "form_otp"
                session["requested_slot"] = None
                otp_form = _get_otp_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    otp_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)

    elif state == "form_seah_2":
        user_input = latest_message if (text or payload) else None
        form = _get_form_seah_2()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            session["slots"].update(slot_updates)
            session["active_loop"] = None
            session["requested_slot"] = None
            ask_dispatcher = CollectingDispatcher()
            submit_events = await invoke_action(
                "action_submit_seah",
                ask_dispatcher,
                SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                ),
                domain,
            )
            submit_updates = events_to_slot_updates(submit_events)
            slot_updates.update(submit_updates)
            session["slots"].update(submit_updates)
            dispatcher.messages.extend(ask_dispatcher.messages)
            await _append_seah_outro_after_submit_if_applicable(
                dispatcher, session, latest_message, domain, slot_updates
            )
            next_state = "done"

    elif state == "form_seah_focal_point_1":
        user_input = latest_message if (text or payload) else None
        form = _get_form_seah_focal_point_1()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            session["slots"].update(slot_updates)
            consent_to_report = session.get("slots", {}).get("seah_focal_reporter_consent_to_report")
            if consent_to_report == "no":
                # If the complainant does not consent to report, end SEAH intake early:
                # submit immediately and send the dedicated SEAH outro.
                session["active_loop"] = None
                session["requested_slot"] = None
                ask_dispatcher = CollectingDispatcher()
                submit_events = await invoke_action(
                    "action_submit_seah",
                    ask_dispatcher,
                    SessionTracker(
                        slots=session["slots"],
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                submit_updates = events_to_slot_updates(submit_events)
                slot_updates.update(submit_updates)
                session["slots"].update(submit_updates)
                dispatcher.messages.extend(ask_dispatcher.messages)
                await _append_seah_outro_after_submit_if_applicable(
                    dispatcher, session, latest_message, domain, slot_updates
                )
                next_state = "done"
            else:
                next_state = "otp_form"
                session["active_loop"] = "form_otp"
                session["requested_slot"] = None
                slot_updates["seah_focal_stage"] = "complainant_otp"
                session["slots"]["seah_focal_stage"] = "complainant_otp"
                otp_form = _get_otp_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    otp_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)

    elif state == "form_seah_focal_point_2":
        user_input = latest_message if (text or payload) else None
        form = _get_form_seah_focal_point_2()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            session["slots"].update(slot_updates)
            session["active_loop"] = None
            session["requested_slot"] = None
            ask_dispatcher = CollectingDispatcher()
            submit_events = await invoke_action(
                "action_submit_seah",
                ask_dispatcher,
                SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                ),
                domain,
            )
            submit_updates = events_to_slot_updates(submit_events)
            slot_updates.update(submit_updates)
            session["slots"].update(submit_updates)
            dispatcher.messages.extend(ask_dispatcher.messages)
            await _append_seah_outro_after_submit_if_applicable(
                dispatcher, session, latest_message, domain, slot_updates
            )
            next_state = "done"

    elif state == "otp_form":
        user_input = latest_message if (text or payload) else None
        form = _get_otp_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            story_main = session.get("slots", {}).get("story_main")
            seah_focal_stage = session.get("slots", {}).get("seah_focal_stage")
            if story_main == "status_check":
                next_state = "status_check_form"
                session["active_loop"] = "form_status_check_2"
                session["requested_slot"] = None
            elif story_main == "seah_intake":
                next_state = "contact_form"
                session["active_loop"] = "form_contact"
                session["requested_slot"] = None
                if seah_focal_stage == "bootstrap_reporter_otp":
                    slot_updates["seah_focal_stage"] = "bootstrap_reporter_contact"
                    # Default yes: reporter agrees to share contact for follow-up; user can still skip name/email fields.
                    slot_updates["complainant_consent"] = True
                elif seah_focal_stage == "complainant_otp":
                    slot_updates["seah_focal_stage"] = "complainant_contact"
                    # Consent already captured earlier; collect affected-person location/contact without re-asking.
                    slot_updates["complainant_consent"] = True
                session["slots"].update(slot_updates)
                contact_form = _get_contact_form()
                msgs2, form_updates2, _ = await run_form_turn(
                    contact_form, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)
            else:
                session["slots"].update(slot_updates)
                session["active_loop"] = None
                session["requested_slot"] = None
                ask_dispatcher = CollectingDispatcher()
                tracker_submit = SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                )
                submit_action = "action_submit_seah" if story_main == "seah_intake" else "action_submit_grievance"
                events = await invoke_action(
                    submit_action,
                    ask_dispatcher,
                    tracker_submit,
                    domain,
                )
                slot_updates = events_to_slot_updates(events)
                dispatcher.messages.extend(ask_dispatcher.messages)
                next_state = "grievance_review"
                session["active_loop"] = "form_grievance_complainant_review"
                session["requested_slot"] = None
                session["slots"].update(slot_updates)
                retrieve_dispatcher = CollectingDispatcher()
                retrieve_tracker = SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                )
                retrieve_events = await invoke_action(
                    "action_retrieve_classification_results",
                    retrieve_dispatcher,
                    retrieve_tracker,
                    domain,
                )
                if retrieve_events:
                    retrieve_updates = events_to_slot_updates(retrieve_events)
                    session["slots"].update(retrieve_updates)
                    slot_updates.update(retrieve_updates)
                dispatcher.messages.extend(retrieve_dispatcher.messages)
                review_form = _get_review_form()
                msgs_review, form_updates_review, _ = await run_form_turn(
                    review_form, session, None, domain
                )
                dispatcher.messages.extend(msgs_review)
                slot_updates.update(form_updates_review)

    elif state == "submit_grievance":
        ask_dispatcher = CollectingDispatcher()
        submit_action = "action_submit_seah" if session.get("slots", {}).get("story_main") == "seah_intake" else "action_submit_grievance"
        events = await invoke_action(
            submit_action,
            ask_dispatcher,
            tracker,
            domain,
        )
        slot_updates = events_to_slot_updates(events)
        dispatcher.messages.extend(ask_dispatcher.messages)
        next_state = "grievance_review"
        session["active_loop"] = "form_grievance_complainant_review"
        session["requested_slot"] = None
        session["slots"].update(slot_updates)
        await _append_seah_outro_after_submit_if_applicable(
            dispatcher, session, latest_message, domain, slot_updates
        )
        retrieve_dispatcher = CollectingDispatcher()
        retrieve_tracker = SessionTracker(
            slots=session["slots"],
            sender_id=session.get("user_id", "default"),
            latest_message=latest_message,
            active_loop=None,
            requested_slot=None,
        )
        retrieve_events = await invoke_action(
            "action_retrieve_classification_results",
            retrieve_dispatcher,
            retrieve_tracker,
            domain,
        )
        if retrieve_events:
            retrieve_updates = events_to_slot_updates(retrieve_events)
            session["slots"].update(retrieve_updates)
            slot_updates.update(retrieve_updates)
        dispatcher.messages.extend(retrieve_dispatcher.messages)
        review_form = _get_review_form()
        msgs_review, form_updates_review, _ = await run_form_turn(
            review_form, session, None, domain
        )
        dispatcher.messages.extend(msgs_review)
        slot_updates.update(form_updates_review)

    elif state == "grievance_review":
        user_input = latest_message if (text or payload) else None
        form = _get_review_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            next_state = "done"
            session["active_loop"] = None
            session["requested_slot"] = None
            # Apply form updates so update/outro actions see confirmed slots
            slots_after_review = dict(session.get("slots", {}))
            slots_after_review.update(slot_updates)
            review_tracker = SessionTracker(
                slots=slots_after_review,
                sender_id=session.get("user_id", "default"),
                latest_message=latest_message,
                active_loop=None,
                requested_slot=None,
            )
            outro_dispatcher = CollectingDispatcher()
            await invoke_action(
                "action_update_grievance_categorization",
                outro_dispatcher,
                review_tracker,
                domain,
            )
            await invoke_action(
                "action_grievance_outro",
                outro_dispatcher,
                review_tracker,
                domain,
            )
            dispatcher.messages.extend(outro_dispatcher.messages)

    elif state == "status_check_form":
        user_input = latest_message if (text or payload) else None
        active_loop = session.get("active_loop")

        # Post-form status-check step: user has seen grievance details and is choosing
        # an action (request follow-up, modify, or skip). In this phase we don't run
        # any forms, we just route based on intent.
        if not active_loop:
            slots_after = dict(session.get("slots", {}))
            slots_after.update(slot_updates)

            if intent == "status_check_request_follow_up":
                ask_dispatcher = CollectingDispatcher()
                events = await invoke_action(
                    "action_status_check_request_follow_up",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                slot_updates.update(events_to_slot_updates(events))
                dispatcher.messages.extend(ask_dispatcher.messages)
                next_state = "done"
                session["active_loop"] = None
                session["requested_slot"] = None
            elif intent == "status_check_modify_grievance":
                ask_dispatcher = CollectingDispatcher()
                events = await invoke_action(
                    "action_status_check_modify_grievance",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                slot_updates.update(events_to_slot_updates(events))
                dispatcher.messages.extend(ask_dispatcher.messages)
                next_state = "modify_grievance_menu"
                session["active_loop"] = None
                session["requested_slot"] = None
            else:
                # Unknown or neutral input (e.g. free text): re-show choices so we never return empty messages.
                ask_dispatcher = CollectingDispatcher()
                await invoke_action(
                    "action_ask_story_step",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                dispatcher.messages.extend(ask_dispatcher.messages)
                next_state = "status_check_form"
        else:
            # We are still inside one of the status-check related forms.
            if active_loop == "form_status_check_1":
                form = _get_status_form_1()
            elif active_loop == "form_otp":
                form = _get_otp_form()
            elif active_loop == "form_status_check_2":
                form = _get_status_form_2()
            elif active_loop == "form_status_check_skip":
                form = _get_status_form_skip()
            else:
                form = _get_status_form_1()

            msgs, form_updates, completed = await run_form_turn(
                form, session, user_input, domain
            )
            dispatcher.messages.extend(msgs)
            slot_updates.update(form_updates)

            if completed:
                slots_after = dict(session.get("slots", {}))
                slots_after.update(slot_updates)
                story_route = slots_after.get("story_route")

                if active_loop == "form_status_check_1":
                    if story_route == "route_status_check_phone":
                        session["active_loop"] = "form_otp"
                        session["requested_slot"] = None
                        session["slots"].update(slot_updates)
                        otp_form = _get_otp_form()
                        msgs2, form_updates2, _ = await run_form_turn(
                            otp_form, session, None, domain
                        )
                        dispatcher.messages.extend(msgs2)
                        slot_updates.update(form_updates2)
                    elif story_route == "route_status_check_grievance_id":
                        session["active_loop"] = "form_status_check_2"
                        session["requested_slot"] = None
                        session["slots"].update(slot_updates)
                        status_form_2 = _get_status_form_2()
                        msgs2, form_updates2, completed_2 = await run_form_turn(
                            status_form_2, session, None, domain
                        )
                        dispatcher.messages.extend(msgs2)
                        slot_updates.update(form_updates2)
                        # If form_status_check_2 completed immediately (e.g. grievance ID
                        # already set from 6-char lookup), show grievance details
                        if completed_2 and not msgs2:
                            session["active_loop"] = None
                            session["requested_slot"] = None
                            session["slots"].update(slot_updates)
                            ask_dispatcher = CollectingDispatcher()
                            await invoke_action(
                                "action_ask_story_step",
                                ask_dispatcher,
                                SessionTracker(
                                    slots=session["slots"],
                                    sender_id=session.get("user_id", "default"),
                                    latest_message=latest_message,
                                    active_loop=None,
                                    requested_slot=None,
                                ),
                                domain,
                            )
                            dispatcher.messages.extend(ask_dispatcher.messages)
                            next_state = "status_check_form"
                    elif story_route and "skip" in str(story_route).lower():
                        session["active_loop"] = "form_status_check_skip"
                        session["requested_slot"] = None
                    else:
                        # story_route missing or unknown: re-ask so we never return done with no messages
                        ask_dispatcher = CollectingDispatcher()
                        await invoke_action(
                            "action_ask_status_check_method",
                            ask_dispatcher,
                            SessionTracker(
                                slots=slots_after,
                                sender_id=session.get("user_id", "default"),
                                latest_message=latest_message,
                                active_loop="form_status_check_1",
                                requested_slot="story_route",
                            ),
                            domain,
                        )
                        dispatcher.messages.extend(ask_dispatcher.messages)
                        session["active_loop"] = "form_status_check_1"
                        session["requested_slot"] = "story_route"
                        next_state = "status_check_form"
                elif active_loop == "form_otp":
                    session["active_loop"] = "form_status_check_2"
                    session["requested_slot"] = None
                    session["slots"].update(slot_updates)
                    status_form_2 = _get_status_form_2()
                    msgs2, form_updates2, completed_2 = await run_form_turn(
                        status_form_2, session, None, domain
                    )
                    dispatcher.messages.extend(msgs2)
                    slot_updates.update(form_updates2)
                    # If form_status_check_2 completes immediately after OTP
                    # (e.g., a single grievance is already selected), ensure
                    # we still show grievance details/options in this turn.
                    if completed_2 and not msgs2:
                        session["active_loop"] = None
                        session["requested_slot"] = None
                        session["slots"].update(slot_updates)
                        ask_dispatcher = CollectingDispatcher()
                        await invoke_action(
                            "action_ask_story_step",
                            ask_dispatcher,
                            SessionTracker(
                                slots=session["slots"],
                                sender_id=session.get("user_id", "default"),
                                latest_message=latest_message,
                                active_loop=None,
                                requested_slot=None,
                            ),
                            domain,
                        )
                        dispatcher.messages.extend(ask_dispatcher.messages)
                        next_state = "status_check_form"
                elif active_loop == "form_status_check_2":
                    # After the second status-check form completes, show grievance
                    # details and offer follow-up/modify/skip choices.
                    session["active_loop"] = None
                    session["requested_slot"] = None
                    session["slots"].update(slot_updates)
                    ask_dispatcher = CollectingDispatcher()
                    await invoke_action(
                        "action_ask_story_step",
                        ask_dispatcher,
                        SessionTracker(
                            slots=session["slots"],
                            sender_id=session.get("user_id", "default"),
                            latest_message=latest_message,
                            active_loop=None,
                            requested_slot=None,
                        ),
                        domain,
                    )
                    dispatcher.messages.extend(ask_dispatcher.messages)
                    next_state = "status_check_form"
                elif active_loop == "form_status_check_skip":
                    ask_dispatcher = CollectingDispatcher()
                    await invoke_action(
                        "action_skip_status_check_outro",
                        ask_dispatcher,
                        SessionTracker(
                            slots=slots_after,
                            sender_id=session.get("user_id", "default"),
                            latest_message=latest_message,
                            active_loop=None,
                            requested_slot=None,
                        ),
                        domain,
                    )
                    dispatcher.messages.extend(ask_dispatcher.messages)
                    next_state = "done"
                    session["active_loop"] = None
                    session["requested_slot"] = None
            elif (
                active_loop == "form_status_check_2"
                and not dispatcher.messages
            ):
                # Safety net: if the second status-check form is still in progress
                # and produced no messages (e.g. after the user provides a full
                # name), ensure we at least show the grievance selection buttons.
                slots_after = dict(session.get("slots", {}))
                slots_after.update(slot_updates)
                if (
                    slots_after.get("list_grievance_id")
                    and not slots_after.get("status_check_grievance_id_selected")
                ):
                    ask_dispatcher = CollectingDispatcher()
                    await invoke_action(
                        "action_ask_status_check_grievance_id_selected",
                        ask_dispatcher,
                        SessionTracker(
                            slots=slots_after,
                            sender_id=session.get("user_id", "default"),
                            latest_message=latest_message,
                            active_loop="form_status_check_2",
                            requested_slot="status_check_grievance_id_selected",
                        ),
                        domain,
                    )
                    dispatcher.messages.extend(ask_dispatcher.messages)
                    session["active_loop"] = "form_status_check_2"
                    session["requested_slot"] = "status_check_grievance_id_selected"
                    next_state = "status_check_form"
            elif active_loop not in (
                "form_status_check_1",
                "form_otp",
                "form_status_check_2",
                "form_status_check_skip",
            ):
                # active_loop not in the four known forms: re-prompt so we never return done with no messages
                ask_dispatcher = CollectingDispatcher()
                await invoke_action(
                    "action_ask_status_check_method",
                    ask_dispatcher,
                    SessionTracker(
                        slots=session.get("slots", {}),
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop="form_status_check_1",
                        requested_slot="story_route",
                    ),
                    domain,
                )
                dispatcher.messages.extend(ask_dispatcher.messages)
                session["active_loop"] = "form_status_check_1"
                session["requested_slot"] = "story_route"
                next_state = "status_check_form"

    elif state == "add_more_info_flow":
        user_input = latest_message if (text or payload) else None
        form_modify = _get_form_modify_grievance_details()
        msgs_modify, form_updates_modify, completed_modify = await run_form_turn(
            form_modify, session, user_input, domain
        )
        dispatcher.messages.extend(msgs_modify)
        slot_updates.update(form_updates_modify)
        if completed_modify:
            session["slots"].update(slot_updates)
            session["active_loop"] = None
            session["requested_slot"] = None
            if session.get("slots", {}).get("modify_grievance_new_detail") == "cancelled":
                next_state = "modify_grievance_menu"
                # Re-show the modify menu
                slots_after = dict(session.get("slots", {}))
                ask_dispatcher = CollectingDispatcher()
                await invoke_action(
                    "action_status_check_modify_grievance",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                dispatcher.messages.extend(ask_dispatcher.messages)
            else:
                next_state = "status_check_form"
                slots_after = dict(session.get("slots", {}))
                ask_dispatcher = CollectingDispatcher()
                await invoke_action(
                    "action_ask_story_step",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                dispatcher.messages.extend(ask_dispatcher.messages)

    elif state == "modify_grievance_menu":
        grievance_id = session.get("slots", {}).get("status_check_grievance_id_selected")
        if intent == "modify_grievance_add_pictures" and grievance_id:
            # Tell frontend to open the file upload modal for this grievance (same as "add file" button).
            dispatcher.utter_message(
                json_message={
                    "data": {
                        "event_type": "open_upload_modal",
                        "grievance_id": grievance_id,
                    }
                }
            )
            next_state = "modify_grievance_menu"
        elif intent == "modify_grievance_cancel":
            session["active_loop"] = None
            session["requested_slot"] = None
            slots_after = dict(session.get("slots", {}))
            ask_dispatcher = CollectingDispatcher()
            await invoke_action(
                "action_ask_story_step",
                ask_dispatcher,
                SessionTracker(
                    slots=slots_after,
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                ),
                domain,
            )
            dispatcher.messages.extend(ask_dispatcher.messages)
            next_state = "status_check_form"
        elif intent == "exit":
            # User chose to exit from the modify-grievance menu: show the
            # status-check outro and end the flow.
            session["active_loop"] = None
            session["requested_slot"] = None
            slots_after = dict(session.get("slots", {}))
            ask_dispatcher = CollectingDispatcher()
            await invoke_action(
                "action_skip_status_check_outro",
                ask_dispatcher,
                SessionTracker(
                    slots=slots_after,
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                ),
                domain,
            )
            dispatcher.messages.extend(ask_dispatcher.messages)
            next_state = "done"
        elif intent == "modify_grievance_add_more_info":
            session["active_loop"] = "form_modify_grievance_details"
            session["requested_slot"] = None
            slot_updates["modify_follow_up_answered"] = None
            slot_updates["modify_follow_up_answer"] = None
            next_state = "add_more_info_flow"
            form_modify = _get_form_modify_grievance_details()
            msgs_modify, form_updates_modify, _ = await run_form_turn(
                form_modify, session, None, domain
            )
            dispatcher.messages.extend(msgs_modify)
            slot_updates.update(form_updates_modify)
        elif intent == "modify_grievance_add_missing_info":
            form_modify = _get_form_modify_contact()
            grievance_id = session.get("slots", {}).get("status_check_grievance_id_selected")
            hydrate = events_to_slot_updates(
                form_modify.get_complainant_slot_events_from_grievance(grievance_id)
            )
            session.setdefault("slots", {}).update(hydrate)
            check_tracker = SessionTracker(
                slots=session.get("slots", {}),
                sender_id=session.get("user_id", "default"),
                latest_message=latest_message,
                active_loop=None,
                requested_slot=None,
            )
            _, missing = form_modify.get_missing_contact_fields(check_tracker)
            if missing and missing[0] == "complainant_phone":
                # Phone is first missing: run OTP form to collect and verify
                session["active_loop"] = "form_otp"
                session["requested_slot"] = None
                if session.get("slots", {}).get("story_main") is None:
                    slot_updates["story_main"] = "status_check"
                slot_updates["complainant_consent"] = True
                session["slots"].update(slot_updates)
                next_state = "add_missing_info_otp_flow"
                otp_form = _get_otp_form()
                msgs_otp, form_updates_otp, _ = await run_form_turn(
                    otp_form, session, None, domain
                )
                dispatcher.messages.extend(msgs_otp)
                slot_updates.update(form_updates_otp)
            else:
                session["active_loop"] = "form_modify_contact"
                session["requested_slot"] = None
                next_state = "add_missing_info_flow"
                msgs_modify, form_updates_modify, _ = await run_form_turn(
                    form_modify, session, None, domain
                )
                dispatcher.messages.extend(msgs_modify)
                slot_updates.update(form_updates_modify)
        else:
            next_state = "modify_grievance_menu"

    elif state == "add_missing_info_otp_flow":
        user_input = latest_message if (text or payload) else None
        otp_form = _get_otp_form()
        msgs_otp, form_updates_otp, completed_otp = await run_form_turn(
            otp_form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs_otp)
        slot_updates.update(form_updates_otp)
        if completed_otp:
            # Persist complainant_phone (and complainant_phone_verified) to complainant
            grievance_id = session.get("slots", {}).get("status_check_grievance_id_selected")
            slots_after = dict(session.get("slots", {}))
            slots_after.update(slot_updates)
            complainant_phone = slots_after.get("complainant_phone")
            otp_status = slots_after.get("otp_status")
            skip_val = "slot_skipped"  # SKIP_VALUE from constants
            if (
                grievance_id
                and complainant_phone
                and complainant_phone != skip_val
            ):
                try:
                    from backend.services.database_services.postgres_services import db_manager
                    complainant_id = db_manager.complainant.get_complainant_id_from_grievance_id(
                        grievance_id
                    )
                    if complainant_id:
                        update_data = {"complainant_phone": complainant_phone}
                        if otp_status == "verified":
                            update_data["complainant_phone_verified"] = True
                        db_manager.update_complainant(complainant_id, update_data)
                except Exception as e:
                    logging.getLogger(__name__).error(
                        f"Failed to persist complainant_phone after OTP: {e}"
                    )
            session["slots"].update(slot_updates)
            grievance_id = session.get("slots", {}).get("status_check_grievance_id_selected")
            form_modify = _get_form_modify_contact()
            hydrate = events_to_slot_updates(
                form_modify.get_complainant_slot_events_from_grievance(grievance_id)
            )
            session.setdefault("slots", {}).update(hydrate)
            session["active_loop"] = "form_modify_contact"
            session["requested_slot"] = None
            next_state = "add_missing_info_flow"
            msgs_modify, form_updates_modify, completed_modify = await run_form_turn(
                form_modify, session, None, domain
            )
            dispatcher.messages.extend(msgs_modify)
            slot_updates.update(form_updates_modify)
            if completed_modify:
                # If form_modify_contact already completes in the same turn
                # (e.g., phone was the only missing field), emit the same
                # completion messages as add_missing_info_flow to avoid a
                # "silent" turn after OTP verification.
                session["slots"].update(slot_updates)
                session["active_loop"] = None
                session["requested_slot"] = None
                slots_after = dict(session.get("slots", {}))
                # Flush on any form completion — not only "I'm done" (modify_missing_info_complete).
                # Natural completion (last missing field filled) previously skipped persist entirely.
                form_modify.persist_all_contact_fields_to_complainant(slots_after)
                if session.get("slots", {}).get("modify_missing_info_complete"):
                    next_state = "status_check_form"
                    ask_dispatcher = CollectingDispatcher()
                    await invoke_action(
                        "action_ask_story_step",
                        ask_dispatcher,
                        SessionTracker(
                            slots=slots_after,
                            sender_id=session.get("user_id", "default"),
                            latest_message=latest_message,
                            active_loop=None,
                            requested_slot=None,
                        ),
                        domain,
                    )
                    dispatcher.messages.extend(ask_dispatcher.messages)
                else:
                    lang = session.get("slots", {}).get("language_code") or "en"
                    from backend.actions.utils.utterance_mapping_rasa import get_utterance_base

                    msg = get_utterance_base(
                        "form_modify_contact", "utterance_all_contact_complete", 1, lang
                    )
                    dispatcher.utter_message(text=msg)
                    next_state = "modify_grievance_menu"
                    slots_after = dict(session.get("slots", {}))
                    ask_dispatcher = CollectingDispatcher()
                    await invoke_action(
                        "action_status_check_modify_grievance",
                        ask_dispatcher,
                        SessionTracker(
                            slots=slots_after,
                            sender_id=session.get("user_id", "default"),
                            latest_message=latest_message,
                            active_loop=None,
                            requested_slot=None,
                        ),
                        domain,
                    )
                    dispatcher.messages.extend(ask_dispatcher.messages)

    elif state == "add_missing_info_flow":
        user_input = latest_message if (text or payload) else None
        form_modify = _get_form_modify_contact()
        msgs_modify, form_updates_modify, completed_modify = await run_form_turn(
            form_modify, session, user_input, domain
        )
        dispatcher.messages.extend(msgs_modify)
        slot_updates.update(form_updates_modify)
        if completed_modify:
            session["slots"].update(slot_updates)
            session["active_loop"] = None
            session["requested_slot"] = None
            slots_after = dict(session.get("slots", {}))
            form_modify.persist_all_contact_fields_to_complainant(slots_after)
            if session.get("slots", {}).get("modify_missing_info_complete"):
                next_state = "status_check_form"
                ask_dispatcher = CollectingDispatcher()
                await invoke_action(
                    "action_ask_story_step",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                dispatcher.messages.extend(ask_dispatcher.messages)
            else:
                lang = session.get("slots", {}).get("language_code") or "en"
                from backend.actions.utils.utterance_mapping_rasa import get_utterance_base
                msg = get_utterance_base(
                    "form_modify_contact", "utterance_all_contact_complete", 1, lang
                )
                dispatcher.utter_message(text=msg)
                next_state = "modify_grievance_menu"
                slots_after = dict(session.get("slots", {}))
                ask_dispatcher = CollectingDispatcher()
                await invoke_action(
                    "action_status_check_modify_grievance",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                dispatcher.messages.extend(ask_dispatcher.messages)

    elif state == "done":
        # Allow modify-grievance actions even if the session state was already marked as done
        grievance_id = session.get("slots", {}).get("status_check_grievance_id_selected")
        msg_text = (latest_message.get("text") or "").strip()
        payload_raw = (payload or "").strip()
        introduce_restart = msg_text.lower().startswith(
            "/introduce"
        ) or payload_raw.lower().startswith("/introduce")
        if introduce_restart:
            # REST webchat sends /introduce on every page load; a persisted session can
            # still be "done" from a prior flow, which previously hit `else: pass` and
            # returned no messages (empty chat on refresh).
            session["state"] = "intro"
            session["active_loop"] = None
            session["requested_slot"] = None
            session["slots"] = DEFAULT_SLOTS.copy()
            next_state = "intro"
            intro_tracker = SessionTracker(
                slots=session["slots"],
                sender_id=session.get("user_id", "default"),
                latest_message=latest_message,
                active_loop=None,
                requested_slot=None,
            )
            events = await invoke_action(
                "action_introduce",
                dispatcher,
                intro_tracker,
                domain,
            )
            slot_updates.update(events_to_slot_updates(events))
        elif intent == "modify_grievance_add_pictures" and grievance_id:
            dispatcher.utter_message(
                json_message={
                    "data": {
                        "event_type": "open_upload_modal",
                        "grievance_id": grievance_id,
                    }
                }
            )
            next_state = "modify_grievance_menu"
        elif intent == "modify_grievance_add_more_info":
            session["active_loop"] = "form_modify_grievance_details"
            session["requested_slot"] = None
            slot_updates["modify_follow_up_answered"] = None
            slot_updates["modify_follow_up_answer"] = None
            next_state = "add_more_info_flow"
            form_modify = _get_form_modify_grievance_details()
            msgs_modify, form_updates_modify, _ = await run_form_turn(
                form_modify, session, None, domain
            )
            dispatcher.messages.extend(msgs_modify)
            slot_updates.update(form_updates_modify)
        elif intent == "modify_grievance_add_missing_info":
            form_modify = _get_form_modify_contact()
            grievance_id = session.get("slots", {}).get("status_check_grievance_id_selected")
            hydrate = events_to_slot_updates(
                form_modify.get_complainant_slot_events_from_grievance(grievance_id)
            )
            session.setdefault("slots", {}).update(hydrate)
            check_tracker = SessionTracker(
                slots=session.get("slots", {}),
                sender_id=session.get("user_id", "default"),
                latest_message=latest_message,
                active_loop=None,
                requested_slot=None,
            )
            _, missing = form_modify.get_missing_contact_fields(check_tracker)
            if missing and missing[0] == "complainant_phone":
                session["active_loop"] = "form_otp"
                session["requested_slot"] = None
                if session.get("slots", {}).get("story_main") is None:
                    slot_updates["story_main"] = "status_check"
                slot_updates["complainant_consent"] = True
                session["slots"].update(slot_updates)
                next_state = "add_missing_info_otp_flow"
                otp_form = _get_otp_form()
                msgs_otp, form_updates_otp, _ = await run_form_turn(
                    otp_form, session, None, domain
                )
                dispatcher.messages.extend(msgs_otp)
                slot_updates.update(form_updates_otp)
            else:
                session["active_loop"] = "form_modify_contact"
                session["requested_slot"] = None
                next_state = "add_missing_info_flow"
                msgs_modify, form_updates_modify, _ = await run_form_turn(
                    form_modify, session, None, domain
                )
                dispatcher.messages.extend(msgs_modify)
                slot_updates.update(form_updates_modify)
        elif intent == "modify_grievance_cancel":
            slots_after = dict(session.get("slots", {}))
            ask_dispatcher = CollectingDispatcher()
            await invoke_action(
                "action_ask_story_step",
                ask_dispatcher,
                SessionTracker(
                    slots=slots_after,
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                ),
                domain,
            )
            dispatcher.messages.extend(ask_dispatcher.messages)
            next_state = "status_check_form"
        else:
            pass

    session["slots"].update(slot_updates)
    session["state"] = next_state
    # Persist form_loop metadata so next turn has correct requested_slot.
    # active_loop is managed explicitly by the state machine when transitioning
    # between forms (e.g., status_check_1 -> otp_form -> status_check_2).
    if "requested_slot" in slot_updates:
        session["requested_slot"] = slot_updates["requested_slot"]

    expected = "buttons" if next_state in ("intro", "main_menu") else "text"
    form_states = (
        "form_grievance", "form_seah_1", "form_seah_2", "form_seah_focal_point_1", "form_seah_focal_point_2",
        "contact_form", "otp_form", "grievance_review",
        "status_check_form", "add_more_info_flow", "add_missing_info_flow", "add_missing_info_otp_flow",
    )
    if next_state in form_states and session.get("requested_slot"):
        expected = "text"

    return (dispatcher.messages, next_state, expected)
