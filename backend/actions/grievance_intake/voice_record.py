"""Voice-only grievance detail intake (CB-01)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from backend.actions.grievance_intake.sensitive import get_sensitive_issue_slots_on_submit
from backend.config.classification_status import LLM_SKIPPED

VOICE_DESCRIPTION_PLACEHOLDER = "[Voice note — officer review]"


def has_voice_attachment(db_manager: Any, grievance_id: Optional[str]) -> bool:
    if not grievance_id:
        return False
    try:
        from backend.config.constants import AUDIO_EXTENSIONS

        files = db_manager.get_grievance_files(grievance_id) or []
    except Exception:
        return False
    for f in files:
        if (f.get("file_type") or "").lower() == "audio":
            return True
        name = (f.get("file_name") or "").lower()
        if name.startswith("voice_note_"):
            return True
        ext = name.rsplit(".", 1)[-1] if "." in name else ""
        if ext in AUDIO_EXTENSIONS:
            return True
    return False


async def finalize_voice_record(
    form: Any,
    tracker: Tracker,
    dispatcher: CollectingDispatcher,
    *,
    require_voice_attachment: bool = True,
) -> Dict[Text, Any]:
    """Voice-only intake: persist grievance, skip LLM classification."""
    form._initialize_language_and_helpers(tracker)
    grievance_id = tracker.get_slot("grievance_id")
    if not grievance_id:
        return {
            "grievance_new_detail": None,
            "grievance_description_status": "add_more_details",
        }
    if require_voice_attachment and not has_voice_attachment(form.db_manager, grievance_id):
        return {
            "grievance_new_detail": None,
            "grievance_description_status": "add_more_details",
        }

    description = (tracker.get_slot("grievance_description") or "").strip()
    if not description:
        description = VOICE_DESCRIPTION_PLACEHOLDER

    session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
    sensitive_slots = await get_sensitive_issue_slots_on_submit(
        form,
        description,
        session_id=session_id,
        grievance_id=grievance_id,
        dispatcher=dispatcher,
    )

    grievance_data = {
        "grievance_id": grievance_id,
        "complainant_id": tracker.get_slot("complainant_id"),
        "grievance_description": description,
        "complainant_province": tracker.get_slot("complainant_province"),
        "complainant_district": tracker.get_slot("complainant_district"),
        "complainant_office": tracker.get_slot("complainant_office"),
        "source": "bot",
        "grievance_classification_status": LLM_SKIPPED,
        "grievance_summary": "",
        "grievance_categories": [],
    }
    form.db_manager.create_or_update_complainant(grievance_data)
    form.db_manager.create_or_update_grievance(grievance_data)

    try:
        dispatcher.utter_message(
            json_message={
                "data": {
                    "grievance_id": grievance_id,
                    "event_type": "grievance_saved_in_db",
                }
            }
        )
        dispatcher.utter_message(
            json_message={"data": {"event_type": "disable_voice_note"}}
        )
    except Exception as e:
        form.logger.error(f"Failed to emit voice_record frontend events: {e}")

    form.logger.info(
        "voice_record_finalized grievance_id=%s classification=LLM_skipped",
        grievance_id,
    )
    return {
        "grievance_new_detail": "voice_record",
        "grievance_description": description,
        "grievance_description_status": None,
        "grievance_classification_status": LLM_SKIPPED,
        "grievance_summary": "",
        "grievance_categories": [],
        "grievance_summary_status": form.SKIP_VALUE,
        "grievance_categories_status": form.SKIP_VALUE,
        **sensitive_slots,
    }
