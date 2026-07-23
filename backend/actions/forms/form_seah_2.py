from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction, BaseFormValidationAction
from backend.actions.forms.seah_shared import SeahSharedFormMixin


class ValidateFormSeah2(SeahSharedFormMixin, BaseFormValidationAction):
    # Victim form: skip allowed (default SKIP_VALUE); accept detail when len > 3 (== >= 4).
    _SEAH_DETAIL_SKIP_ALLOWED = True
    _SEAH_DETAIL_MIN_LENGTH = 4

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
        # Ask follow-up contact channel whenever at least one contact path exists.
        # This now includes anonymous route when phone was collected through OTP.
        phone = tracker.get_slot("complainant_phone")
        email = tracker.get_slot("complainant_email")
        has_phone = phone not in (None, self.SKIP_VALUE, "")
        has_email = email not in (None, self.SKIP_VALUE, "")
        if has_phone or has_email:
            required.append("seah_contact_consent_channel")
        return required

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
        return self.validate_seah_contact_channel_selection(slot_value, tracker)


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
        if description_status == "show_options":
            grievance_description = tracker.get_slot("grievance_description") or ""
            dispatcher.utter_message(
                text=self.get_utterance(2).format(grievance_description=grievance_description),
                buttons=self.get_buttons(2),
            )
        elif description_status == "add_more_details":
            # Keep parity with form_grievance ask flow.
            dispatcher.utter_message(text=self.get_utterance(3), buttons=self.get_buttons(1))
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
        buttons = self.build_seah_contact_channel_buttons(
            buttons=self.get_buttons(1),
            phone_value=tracker.get_slot("complainant_phone"),
            email_value=tracker.get_slot("complainant_email"),
        )
        dispatcher.utter_message(text=self.get_utterance(1), buttons=buttons)
        return []
