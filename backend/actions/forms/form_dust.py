"""CB-09: road dust fast-path intake (preset category, map + photos)."""

from __future__ import annotations

from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction
from backend.actions.forms.form_grievance import ValidateFormGrievance
from backend.actions.forms.intake_submit import complete_dust_intake_submit


DUST_CATEGORY = "Air Pollution"
DUST_DEFAULT_DESCRIPTION = (
    "Road dust complaint filed via the dust fast path (location and photos to follow)."
)


class ActionStartDustGrievanceProcess(BaseAction):
    """Start dust fast path: IDs, preset category, default description."""

    def name(self) -> Text:
        return "action_start_dust_grievance_process"

    async def execute_action(self, dispatcher, tracker, domain):
        BaseFormValidationAction.message_display_list_cat = True
        set_id_data = {
            "complainant_province": tracker.get_slot("complainant_province") or self.province,
            "complainant_district": tracker.get_slot("complainant_district") or self.district,
            "complainant_office": tracker.get_slot("complainant_office") or None,
            "source": "bot",
        }
        complainant_id = self.db_manager.generate_complainant_id(set_id_data)
        grievance_id = self.db_manager.generate_grievance_id(set_id_data)
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
            SlotSet("story_main", "dust_grievance"),
            SlotSet("grievance_sensitive_issue", False),
            SlotSet("grievance_categories", [DUST_CATEGORY]),
            SlotSet("grievance_description", DUST_DEFAULT_DESCRIPTION),
            SlotSet("intake_fast_path", "dust"),
        ]


class ValidateFormDust(ValidateFormGrievance):
    """Collect optional dust note or File as is; then continue to location flow."""

    def name(self) -> Text:
        return "validate_form_dust"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        if tracker.get_slot("dust_new_detail") == "completed":
            return []
        return ["dust_new_detail"]

    def _update_description(self, current_text: str, new_text: str) -> str:
        if new_text.startswith("/"):
            new_text = ""
        updated = current_text + "\n" + new_text if current_text else new_text
        return updated.strip()

    async def extract_dust_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "dust_new_detail",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_dust_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        try:
            expected = {"restart", "add_more_details", "submit_details"}
            normalized = slot_value.strip() if isinstance(slot_value, str) else slot_value
            self.logger.debug(f"Validating dust_new_detail: {slot_value}")

            if isinstance(normalized, str) and not normalized:
                description = tracker.get_slot("grievance_description") or DUST_DEFAULT_DESCRIPTION
                slots = await complete_dust_intake_submit(
                    self,
                    tracker,
                    dispatcher,
                    domain,
                    description,
                    preset_categories=[DUST_CATEGORY],
                )
                return {"dust_new_detail": "completed", **slots}

            if normalized == "restart":
                return {
                    "dust_new_detail": None,
                    "grievance_description": DUST_DEFAULT_DESCRIPTION,
                    "dust_description_status": "restart",
                }

            if normalized == "add_more_details":
                return {
                    "dust_new_detail": None,
                    "dust_description_status": "add_more_details",
                }

            if normalized == "submit_details":
                description = (tracker.get_slot("grievance_description") or "").strip()
                if not description:
                    description = DUST_DEFAULT_DESCRIPTION
                self.logger.info(
                    "dust_submit_details grievance_id=%s description_len=%s",
                    tracker.get_slot("grievance_id"),
                    len(description),
                )
                slots = await complete_dust_intake_submit(
                    self,
                    tracker,
                    dispatcher,
                    domain,
                    description,
                    preset_categories=[DUST_CATEGORY],
                )
                return {
                    "dust_new_detail": "completed",
                    **slots,
                }

            if normalized and normalized not in expected:
                updated = self._update_description(
                    tracker.get_slot("grievance_description") or DUST_DEFAULT_DESCRIPTION,
                    normalized,
                )
                return {
                    "dust_new_detail": None,
                    "grievance_description": updated,
                    "dust_description_status": "show_options",
                }

            return {}
        except Exception as e:
            self.logger.error(f"Error in validate_dust_new_detail: {e}")
            raise Exception(f"Error in validate_dust_new_detail: {e}") from e


class ActionAskDustNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_dust_new_detail"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        if tracker.get_slot("dust_new_detail") == "completed":
            return []

        status = tracker.get_slot("dust_description_status")

        if not status:
            utterance = self.get_utterance(1)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            dispatcher.utter_message(
                json_message={"data": {"event_type": "disable_voice_note"}}
            )

        if status == "restart":
            dispatcher.utter_message(text=self.get_utterance(2))

        if status == "add_more_details":
            dispatcher.utter_message(text=self.get_utterance(3))

        if status == "show_options":
            description = tracker.get_slot("grievance_description") or DUST_DEFAULT_DESCRIPTION
            utterance = self.get_utterance(4).format(grievance_description=description)
            buttons = self.get_buttons(4)
            dispatcher.utter_message(text=utterance, buttons=buttons)

        return []
