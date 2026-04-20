from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction, BaseFormValidationAction


class ValidateFormSeah2(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_seah_2"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        if tracker.get_slot("grievance_sensitive_issue") is False:
            return []
        required = [
            "seah_project_identification",
            "sensitive_issues_new_detail",
        ]
        # Anonymous intake should not ask follow-up contact consent/channel.
        if tracker.get_slot("sensitive_issues_follow_up") != "anonymous":
            required.append("seah_contact_consent_channel")
        return required

    async def extract_seah_project_identification(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_project_identification",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_project_identification(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value is None:
            return {"seah_project_identification": None}

        value = slot_value.strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")

        if value == self.SKIP_VALUE:
            value = "cannot_specify"

        if value in ("cannot_specify", "not_adb_project"):
            return {
                "seah_project_identification": value,
                "seah_not_adb_project": value == "not_adb_project",
            }

        if isinstance(value, str) and len(value) >= 2:
            return {"seah_project_identification": value, "seah_not_adb_project": False}

        return {"seah_project_identification": None}

    async def extract_sensitive_issues_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "sensitive_issues_new_detail",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_sensitive_issues_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        expected_values = {"restart", "add_more_details", "submit_details"}
        if isinstance(slot_value, str):
            slot_value = slot_value.strip()
            slot_value = slot_value.lstrip("/")

        if slot_value == "restart":
            return {
                "sensitive_issues_new_detail": None,
                "grievance_description": None,
                "grievance_description_status": "restart",
            }

        if slot_value == "add_more_details":
            return {
                "sensitive_issues_new_detail": None,
                "grievance_description_status": "add_more_details",
            }

        if slot_value == "submit_details":
            return {
                "sensitive_issues_new_detail": "completed",
                "grievance_description": tracker.get_slot("grievance_description"),
                "grievance_description_status": "completed",
            }

        slots = {"sensitive_issues_new_detail": self.SKIP_VALUE}
        if slot_value not in [self.SKIP_VALUE, None] and slot_value not in expected_values and len(slot_value.strip()) > 3:
            existing_description = tracker.get_slot("grievance_description")
            base_text = (
                existing_description.strip()
                if isinstance(existing_description, str) and existing_description.strip()
                else ""
            )
            new_text = slot_value.strip()
            slots["sensitive_issues_new_detail"] = None
            slots["grievance_description"] = f"{base_text}\n{new_text}" if base_text else new_text
            slots["grievance_description_status"] = "show_options"
        return slots

    async def extract_seah_contact_consent_channel(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_contact_consent_channel",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_contact_consent_channel(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        value = (slot_value or "").strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")
        if value in {"phone", "email", "both", "none"}:
            return {"seah_contact_consent_channel": value}
        return {"seah_contact_consent_channel": None}


class ActionAskFormSeah2SeahProjectIdentification(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_2_seah_project_identification"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []


class ActionAskFormSeah2SensitiveIssuesNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_2_sensitive_issues_new_detail"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        description_status = tracker.get_slot("grievance_description_status")
        if description_status in ("show_options", "add_more_details"):
            grievance_description = tracker.get_slot("grievance_description") or ""
            dispatcher.utter_message(
                text=self.get_utterance(2).format(grievance_description=grievance_description),
                buttons=self.get_buttons(2),
            )
        else:
            dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []


class ActionAskFormSeah2SeahContactConsentChannel(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_2_seah_contact_consent_channel"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []
