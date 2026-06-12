"""Post-submit confirmation messages (chat + SMS body)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from backend.actions.services.messaging import grievance_data as messaging_grievance_data
from backend.actions.utils.utterance_mapping_rasa import get_utterance_base


def check_grievance_high_priority(grievance_categories: Any) -> bool:
    import json

    from backend.actions.utils.ticketing_dispatch import categories_high_priority

    try:
        if isinstance(grievance_categories, str):
            try:
                grievance_categories = json.loads(grievance_categories)
            except (json.JSONDecodeError, TypeError):
                grievance_categories = [grievance_categories]
        return categories_high_priority(grievance_categories)
    except Exception:
        return False


def create_confirmation_message(
    grievance_data: Dict[str, Any],
    *,
    language_code: str,
    not_provided: str,
    db_manager: Any,
) -> str:
    allowed_keys = [
        "grievance_id",
        "grievance_timestamp",
        "grievance_description",
        "complainant_email",
        "complainant_phone",
        "grievance_outro",
        "grievance_timeline",
    ]
    message_keys = [
        k
        for k in allowed_keys
        if grievance_data.get(k) and grievance_data.get(k) != not_provided
    ]
    all_message_elements = {
        "grievance_id": {
            "en": "Your grievance has been filed successfully.\n**Grievance ID: {grievance_id} **",
            "ne": "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।\n**गुनासो ID:** {grievance_id}",
        },
        "grievance_timestamp": {
            "en": "Grievance filed on: {grievance_timestamp}",
            "ne": "गुनासो दर्ता गरिएको: {grievance_timestamp}",
        },
        "grievance_description": {
            "en": "**Details: {grievance_description}**",
            "ne": "**विवरण: {grievance_description}**",
        },
        "complainant_email": {
            "en": "\nA confirmation email will be sent to {complainant_email}",
            "ne": "\nतपाईंको इमेलमा सुनिश्चित गर्ने ईमेल भेटिन्छ। {complainant_email}",
        },
        "complainant_phone": {
            "en": "**A confirmation SMS will be sent to your phone: {complainant_phone}**",
            "ne": "**तपाईंको फोनमा सुनिश्चित गर्ने संदेश भेटिन्छ। {complainant_phone}**",
        },
        "grievance_outro": {
            "en": "Our team will review it shortly and contact you if more information is needed.",
            "ne": "हाम्रो टीमले त्यो गुनासोको लागि कल गर्दैछु र तपाईंलाई यदि अधिक जानकारी आवश्यक हुन्छ भने सम्पर्क गर्नेछ।",
        },
        "grievance_timeline": {
            "en": "The standard resolution time for a grievance is 15 days. Expected resolution date: {grievance_timeline}",
            "ne": "गुनासोको मानक समयावधि 15 दिन हुन्छ। अपेक्षित समाधान तिथि: {grievance_timeline}",
        },
    }
    message_elements = [all_message_elements[k][language_code] for k in message_keys]
    files_info = messaging_grievance_data.get_attached_files_info(
        grievance_data["grievance_id"], db_manager
    )
    message = "\n".join(message_elements).format(
        grievance_id=grievance_data["grievance_id"],
        grievance_timestamp=grievance_data["grievance_timestamp"],
        grievance_description=grievance_data["grievance_description"],
        complainant_email=grievance_data["complainant_email"],
        complainant_phone=grievance_data["complainant_phone"],
        grievance_timeline=grievance_data["grievance_timeline"],
    )
    if files_info["has_files"]:
        message = message + files_info["files_info"]
    return message


def emit_chat_filed_confirmation(
    dispatcher: CollectingDispatcher,
    grievance_data: Dict[str, Any],
    *,
    language_code: str,
    tracker: Optional[Tracker] = None,
) -> None:
    lang = language_code or "en"
    gid = grievance_data.get("grievance_id") or ""
    filed_line = get_utterance_base(
        "action_submit_grievance", "action_submit_grievance", 6, lang
    ).format(grievance_id=gid)
    from backend.actions.forms.form_dust import is_dust_intake

    dust = tracker is not None and is_dust_intake(tracker)
    dispatcher.utter_message(text=filed_line)
    if not dust:
        on_record = get_utterance_base(
            "action_submit_grievance", "action_submit_grievance", 5, lang
        )
        dispatcher.utter_message(text=on_record)
    dispatcher.utter_message(
        json_message={"data": {"event_type": "grievance_filed", "grievance_id": gid}}
    )
