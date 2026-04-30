"""
Form for modifying an existing grievance (Spec 13: Add more info flow).

Uses status_check_grievance_id_selected to load the grievance and append narrative.
"""

from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction


class ValidateFormModifyGrievanceDetails(BaseFormValidationAction):
    """Form to add more details to an existing grievance (status-check modification flow)."""

    def name(self) -> Text:
        return "validate_form_modify_grievance_details"

    def _get_follow_up_question(self, tracker: Tracker) -> Optional[Text]:
        """Load follow_up_question from grievance (classification step). Returns None if none."""
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        if not grievance_id:
            return None
        grievance = self.db_manager.get_grievance_by_id(grievance_id)
        if not grievance:
            return None
        fq = grievance.get("follow_up_question")
        if not fq or fq in ("", "N/A", "None"):
            return None
        if isinstance(fq, list):
            fq = next((q for q in fq if q and str(q).strip()), None)
        if isinstance(fq, str) and fq.strip():
            return fq.strip()
        return None

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        # Cancelled or completed
        if tracker.get_slot("modify_grievance_new_detail") == "completed":
            return []
        if tracker.get_slot("modify_grievance_new_detail") == "cancelled":
            return []
        # Ask classification follow-up question first (if any and not yet answered)
        if tracker.get_slot("modify_follow_up_answered"):
            pass  # fall through to modify_grievance_new_detail
        else:
            fq = self._get_follow_up_question(tracker)
            if fq:
                return ["modify_follow_up_answer"]
        return ["modify_grievance_new_detail"]

    async def extract_modify_follow_up_answer(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "modify_follow_up_answer",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_modify_follow_up_answer(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Accept answer to follow-up question or /skip."""
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "skip" in raw.lower():
            return {"modify_follow_up_answered": True, "modify_follow_up_answer": None}
        if not raw:
            return {}
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        grievance = self.db_manager.get_grievance_by_id(grievance_id) if grievance_id else None
        if grievance_id and grievance:
            current = grievance.get("grievance_description") or grievance.get("grievance_summary") or ""
            fq = self._get_follow_up_question(tracker)
            prefix = f"[Follow-up answer: {raw}]" if fq else raw
            updated = (current + "\n\n" + prefix).strip() if current else prefix
            try:
                self.db_manager.create_or_update_grievance({
                    "grievance_id": grievance_id,
                    "complainant_id": grievance.get("complainant_id"),
                    "grievance_description": updated,
                    "source": "bot",
                })
            except Exception as e:
                self.logger.error(f"Failed to append follow-up answer for {grievance_id}: {e}")
        return {
            "modify_follow_up_answered": True,
            "modify_follow_up_answer": raw,
            "modify_grievance_description_temp": None,
            "modify_grievance_status": "show_options",
        }

    async def extract_modify_grievance_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "modify_grievance_new_detail",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_modify_grievance_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate: text (append), /submit_details (save and done), /cancel (exit without saving)."""
        raw = (slot_value or "").strip()
        cmd = raw.lstrip("/").strip() if raw.startswith("/") else raw if raw in ("submit_details", "cancel", "modify_grievance_cancel") else None

        # Cancel: exit modification flow
        if cmd in ("modify_grievance_cancel", "cancel"):
            return {"modify_grievance_new_detail": "cancelled"}

        # Save and continue: persist current description and complete
        if cmd == "submit_details":
            grievance_id = tracker.get_slot("status_check_grievance_id_selected")
            grievance = self.db_manager.get_grievance_by_id(grievance_id) if grievance_id else None
            if grievance_id and grievance:
                current_db = grievance.get("grievance_description") or grievance.get("grievance_summary") or ""
                # Use temp if we appended this session, else current DB value
                to_save = tracker.get_slot("modify_grievance_description_temp") or current_db
                try:
                    self.db_manager.create_or_update_grievance({
                        "grievance_id": grievance_id,
                        "complainant_id": grievance.get("complainant_id"),
                        "grievance_description": to_save,
                        "source": "bot",
                    })
                except Exception as e:
                    self.logger.error(f"Failed to update grievance {grievance_id}: {e}")
            return {"modify_grievance_new_detail": "completed", "modify_grievance_description_temp": None}

        # Free text: append to description
        if raw and raw not in ("submit_details", "cancel", "modify_grievance_cancel"):
            grievance_id = tracker.get_slot("status_check_grievance_id_selected")
            if not grievance_id:
                return {}
            grievance = self.db_manager.get_grievance_by_id(grievance_id)
            if not grievance:
                return {}
            current = tracker.get_slot("modify_grievance_description_temp") or grievance.get("grievance_description") or grievance.get("grievance_summary") or ""
            updated = (current + "\n" + raw).strip() if current else raw
            # Persist to DB
            if grievance_id and grievance:
                try:
                    self.db_manager.create_or_update_grievance({
                        "grievance_id": grievance_id,
                        "complainant_id": grievance.get("complainant_id"),
                        "grievance_description": updated,
                        "source": "bot",
                    })
                except Exception as e:
                    self.logger.error(f"Failed to append grievance {grievance_id}: {e}")
            return {
                "modify_grievance_new_detail": None,
                "modify_grievance_description_temp": updated,
                "modify_grievance_status": "show_options",
            }
        return {}


class ActionAskModifyFollowUpAnswer(BaseAction):
    """Ask user to answer the classification follow-up question (Spec 13 Flow A)."""

    def name(self) -> Text:
        return "action_ask_modify_follow_up_answer"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        grievance = self.db_manager.get_grievance_by_id(grievance_id) if grievance_id else None
        follow_up = grievance.get("follow_up_question") if grievance else None
        if isinstance(follow_up, list):
            follow_up = next((q for q in follow_up if q and str(q).strip()), follow_up[0] if follow_up else "")
        question = (follow_up or "").strip() if isinstance(follow_up, str) else ""
        if not question or question in ("", "N/A"):
            question = "Please add more details to your grievance."
        utterance = self.get_utterance(1).format(question=question)
        dispatcher.utter_message(text=utterance, buttons=self.get_buttons(1))
        return []


class ActionAskModifyGrievanceNewDetail(BaseAction):
    """Ask user to add more details to their grievance; show summary and buttons."""

    def name(self) -> Text:
        return "action_ask_modify_grievance_new_detail"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        status = tracker.get_slot("modify_grievance_status")

        # Show grievance summary first (only on initial ask, not after each append)
        if not status or status != "show_options":
            grievance = self.collect_grievance_data_from_id(grievance_id, tracker, domain)
            if grievance:
                grievance_text = self.prepare_grievance_text_for_display(
                    grievance, display_only_short=False
                )
                dispatcher.utter_message(text=grievance_text)

        if status == "show_options":
            utterance = self.get_utterance(2)  # "Your text has been added. Add more or save."
        else:
            utterance = self.get_utterance(1)  # "Add more details to your grievance"
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []
