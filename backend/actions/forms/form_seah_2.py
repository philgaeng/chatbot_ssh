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
        return [
            "seah_project_identification",
            "sensitive_issues_new_detail",
            "seah_contact_consent_channel",
        ]

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
        slots = {"sensitive_issues_new_detail": self.SKIP_VALUE}
        if slot_value not in [self.SKIP_VALUE, None] and len(slot_value.strip()) > 3:
            existing_description = tracker.get_slot("grievance_description")
            base_text = (
                existing_description.strip()
                if isinstance(existing_description, str) and existing_description.strip()
                else ""
            )
            new_text = slot_value.strip()
            slots["sensitive_issues_new_detail"] = slot_value
            slots["grievance_description"] = f"{base_text}\n{new_text}" if base_text else new_text
            slots["grievance_description_status"] = "completed"
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
        dispatcher.utter_message(text=self.get_utterance(1))
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
