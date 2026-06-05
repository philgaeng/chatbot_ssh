from typing import Any, Text, Dict, List, Optional

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_sdk.types import DomainDict
from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction
from backend.actions.forms.intake_submit import complete_grievance_details_intake
from backend.actions.grievance_intake import (
    classification,
    sensitive,
    voice_record,
)


############################ STEP 0 - GENERIC ACTIONS ############################

class ActionSubmitGrievanceAsIs(BaseAction):
    def name(self) -> Text:
        return "action_submit_grievance_as_is"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance_description = tracker.get_slot("grievance_description")
        if grievance_description:
            dispatcher.utter_message(response="utter_grievance_submitted_as_is", grievance_description=grievance_description)
        else:
            dispatcher.utter_message(response="utter_grievance_submitted_no_details_as_is")

        return [FollowupAction("action_submit_grievance")]


class ActionStartGrievanceProcess(BaseAction):

    def name(self) -> Text:
        return "action_start_grievance_process"

    async def execute_action(self, dispatcher, tracker, domain):
        BaseFormValidationAction.message_display_list_cat = True
        set_id_data = {
            'complainant_province': tracker.get_slot("complainant_province") or self.province,
            'complainant_district': tracker.get_slot("complainant_district") or self.district,
            'complainant_office': tracker.get_slot("complainant_office") or None,
            'source': 'bot'
        }
        complainant_id = self.db_manager.generate_complainant_id(set_id_data)
        grievance_id = self.db_manager.generate_grievance_id(set_id_data)
        self.logger.info(f"Created temporary grievance with ID: {grievance_id} and complainant ID: {complainant_id}")

        dispatcher.utter_message(
            json_message={
                "data": {
                    "grievance_id": grievance_id,
                    "complainant_id": complainant_id,
                    "event_type": "grievance_id_set",
                }
            }
        )

        return [
                SlotSet("grievance_id", grievance_id),
                SlotSet("complainant_id", complainant_id),
                SlotSet("story_main", "new_grievance"),
                SlotSet("grievance_sensitive_issue", False)]


############################ STEP 1 - GRIEVANCE FORM DETAILS ############################

class ValidateFormGrievance(BaseFormValidationAction):

    def name(self) -> Text:
        return "validate_form_grievance"

    # Thin delegates — form_loop stubs _trigger_async_classification on the form instance.
    async def _trigger_async_classification(self, tracker, dispatcher, grievance_description=None):
        return await classification.trigger_async_classification(
            self, tracker, dispatcher, grievance_description=grievance_description
        )

    async def _get_sensitive_issue_slots_on_submit(self, full_description, session_id, grievance_id, dispatcher):
        return await sensitive.get_sensitive_issue_slots_on_submit(
            self, full_description, session_id, grievance_id, dispatcher
        )

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        detail_status = tracker.get_slot("grievance_new_detail")
        if detail_status in ("completed", "voice_record"):
            return []

        return ["grievance_new_detail"]

    def _update_grievance_text(self, current_text: str, new_text: str) -> str:
        if new_text.startswith('/'):
            new_text = ""
        updated = current_text + "\n" + new_text if current_text else new_text
        return updated.strip()

    async def extract_grievance_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        self.logger.debug(f"Extracting grievance_new_detail : {tracker.latest_message.get('text')}")
        return await self._handle_slot_extraction(
            "grievance_new_detail",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_grievance_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        try:
            expected_values = ["restart", "add_more_details", "submit_details", "voice_record"]
            normalized_slot_value = slot_value.strip() if isinstance(slot_value, str) else slot_value

            self.logger.debug(f"Validating grievance_new_detail: {slot_value}")

            if normalized_slot_value == "voice_record":
                return await voice_record.finalize_voice_record(
                    self, tracker, dispatcher, require_voice_attachment=False
                )

            if isinstance(normalized_slot_value, str) and not normalized_slot_value:
                current_description = tracker.get_slot("grievance_description")
                grievance_id = tracker.get_slot("grievance_id")
                if voice_record.has_voice_attachment(self.db_manager, grievance_id):
                    return await voice_record.finalize_voice_record(self, tracker, dispatcher)
                return {
                    "grievance_new_detail": None,
                    "grievance_description_status": "add_more_details" if current_description else None,
                }

            if normalized_slot_value == "restart":
                return {
                    "grievance_new_detail": None,
                    "grievance_description": None,
                    "grievance_description_status": "restart",
                }

            if normalized_slot_value == "add_more_details":
                return {
                    "grievance_new_detail": None,
                    "grievance_description_status": "add_more_details",
                }

            if normalized_slot_value == "submit_details":
                self.logger.debug(
                    f"Submitting details for grievance {tracker.get_slot('grievance_description')}"
                )
                grievance_description = tracker.get_slot("grievance_description")
                grievance_id = tracker.get_slot("grievance_id")
                if not (grievance_description or "").strip():
                    if voice_record.has_voice_attachment(self.db_manager, grievance_id):
                        grievance_description = ""
                    else:
                        return {
                            "grievance_new_detail": None,
                            "grievance_description_status": "add_more_details",
                        }
                self.logger.info(
                    "submit_details_received grievance_id=%s complainant_id=%s has_description=%s description_len=%s llm_classification=%s",
                    tracker.get_slot("grievance_id"),
                    tracker.get_slot("complainant_id"),
                    bool(grievance_description),
                    len(grievance_description or ""),
                    self.LLM_CLASSIFICATION,
                )
                return await complete_grievance_details_intake(
                    self,
                    tracker,
                    dispatcher,
                    domain,
                    grievance_description,
                )

            if normalized_slot_value and normalized_slot_value not in expected_values:
                updated_temp = self._update_grievance_text(
                    tracker.get_slot("grievance_description"),
                    normalized_slot_value,
                )
                sensitive.persist_grievance_description_for_detection(
                    self, tracker, updated_temp
                )
                session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
                sensitive.trigger_detect_sensitive_content_task(
                    self.logger,
                    updated_temp,
                    self.language_code,
                    grievance_id=tracker.get_slot("grievance_id"),
                    session_id=session_id,
                    complainant_id=tracker.get_slot("complainant_id"),
                )
                return {
                    "grievance_new_detail": None,
                    "grievance_description": updated_temp,
                    "grievance_description_status": "show_options",
                    "grievance_sensitive_issue": False,
                }
            return {}
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_new_detail: {e}")
            raise Exception(f"Error in validate_grievance_new_detail: {e}") from e


class ActionAskGrievanceNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_new_detail"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        if tracker.get_slot("grievance_new_detail") in ("completed", "voice_record"):
            return []

        slot_grievance_description_status = tracker.get_slot("grievance_description_status")

        if not slot_grievance_description_status:
            utterance = self.get_utterance(5) or self.get_utterance(1)
            dispatcher.utter_message(text=utterance)
            dispatcher.utter_message(
                json_message={
                    "data": {
                        "event_type": "enable_voice_note",
                        "max_seconds": 90,
                    }
                }
            )

        if slot_grievance_description_status == "restart":
            utterance = self.get_utterance(2)
            dispatcher.utter_message(text=utterance)
            dispatcher.utter_message(
                json_message={
                    "data": {
                        "event_type": "enable_voice_note",
                        "max_seconds": 90,
                    }
                }
            )

        if slot_grievance_description_status == "add_more_details":
            utterance = self.get_utterance(3)
            dispatcher.utter_message(text=utterance)
            dispatcher.utter_message(
                json_message={
                    "data": {
                        "event_type": "enable_voice_note",
                        "max_seconds": 90,
                    }
                }
            )

        if slot_grievance_description_status == "show_options":
            dispatcher.utter_message(
                json_message={"data": {"event_type": "disable_voice_note"}}
            )
            slot_grievance_description = tracker.get_slot("grievance_description")
            utterance = self.get_utterance(4).format(grievance_description=slot_grievance_description)
            buttons = self.get_buttons(4)
            dispatcher.utter_message(text=utterance, buttons=buttons)

        return []
