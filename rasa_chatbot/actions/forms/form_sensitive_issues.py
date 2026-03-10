import logging
from typing import Any, Dict, Text, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction

logger = logging.getLogger(__name__)


class ValidateFormSensitiveIssues(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_sensitive_issues"

    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        required_slots = ["sensitive_issues_follow_up", "complainant_phone"]
        # case where the user declares that the content is not sensitive
        if tracker.get_slot("grievance_sensitive_issue") == False:
            return []
        #case where the user provides a phone number, when he skips the form is closed
        if tracker.get_slot("complainant_phone") not in [self.SKIP_VALUE, None]:
            required_slots.append("sensitive_issues_nickname")
        #case where the user wants to add more details
        if tracker.get_slot("sensitive_issues_follow_up") == "more_details":
            required_slots.append("sensitive_issues_new_detail")
        return required_slots
        
    async def extract_sensitive_issues_follow_up(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "sensitive_issues_follow_up",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_sensitive_issues_follow_up(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        # Normalize command-style payloads (e.g. "/exit", "/anonymous_with_phone") to bare names.
        raw = slot_value if isinstance(slot_value, str) else str(slot_value)
        cmd = raw.lstrip("/") if raw else raw

        # Case: user says it's not sensitive after all
        if cmd == "not_sensitive_content" or (isinstance(slot_value, str) and self.SKIP_VALUE in slot_value):
            
            return {"grievance_sensitive_issue": False,
                    "sensitive_issues_category": None,
                    "sensitive_issues_level": None,
                    "sensitive_issues_message": None,
                    "sensitive_issues_confidence": None}
        
        # Preparing the slots for the anonymous filing.
        # Must match contact form's required slots so /exit and /anonymous_with_phone skip contact questions.
        # Align with form_contact.validate_complainant_location_consent(False) + consent slots.
        filling_slots_for_anonymous_filing = {
            "complainant_location_consent": False,
            "complainant_province": self.SKIP_VALUE,
            "complainant_district": self.SKIP_VALUE,
            "complainant_municipality_temp": self.SKIP_VALUE,
            "complainant_municipality": self.SKIP_VALUE,
            "complainant_municipality_confirmed": False,
            "complainant_village": self.SKIP_VALUE,
            "complainant_village_temp": self.SKIP_VALUE,
            "complainant_village_confirmed": False,
            "complainant_ward": self.SKIP_VALUE,
            "complainant_address_temp": self.SKIP_VALUE,
            "complainant_address": self.SKIP_VALUE,
            "complainant_address_confirmed": False,
            "complainant_consent": self.SKIP_VALUE,
            "complainant_full_name": self.SKIP_VALUE,
            "complainant_email_temp": self.SKIP_VALUE,
            "complainant_email_confirmed": self.SKIP_VALUE,
        }
        #case where the user wants to add more details
        if cmd == "add_more_details":
            filling_slots_for_anonymous_filing["sensitive_issues_follow_up"] = "more_details"
            filling_slots_for_anonymous_filing["complainant_consent"] = "anonymous"
            logger.info("form_sensitive_issues: /add_more_details -> slots for anonymous filing + more_details")
            return filling_slots_for_anonymous_filing

        #helper function to update grievance description slots if the content was detected at that step
        def update_grievance_description_slots_sensitive_issues(slots: Dict[Text, Any]):
            if not tracker.get_slot("grievance_description_status"):
                slots["grievance_description_status"] = "completed"
                slots["grievance_new_detail"] = "completed"
            return slots

        filling_slots_for_anonymous_filing = update_grievance_description_slots_sensitive_issues(filling_slots_for_anonymous_filing)

        # /exit = "File anonymously" (no phone) -> same as skip
        if cmd == "exit":
            filling_slots_for_anonymous_filing["sensitive_issues_follow_up"] = "anonymous_no_phone"
            filling_slots_for_anonymous_filing["complainant_consent"] = "anonymous"
            filling_slots_for_anonymous_filing["complainant_phone"] = self.SKIP_VALUE
            filling_slots_for_anonymous_filing["phone_validation_required"] = False
            logger.info(
                "form_sensitive_issues: /exit -> anonymous_no_phone, contact slots pre-filled (%d slots)",
                len(filling_slots_for_anonymous_filing),
            )
            return filling_slots_for_anonymous_filing

        # /anonymous_with_phone = "File anonymously with one phone number" -> ask for complainant_phone next
        if cmd == "anonymous_with_phone":
            filling_slots_for_anonymous_filing["sensitive_issues_follow_up"] = "anonymous_with_phone"
            filling_slots_for_anonymous_filing["complainant_consent"] = "anonymous"
            logger.info(
                "form_sensitive_issues: /anonymous_with_phone -> contact slots pre-filled (%d slots)",
                len(filling_slots_for_anonymous_filing),
            )
            return filling_slots_for_anonymous_filing

        #case where the user skips - we proceed with the anonymous filing without phone
        if slot_value == self.SKIP_VALUE:
            filling_slots_for_anonymous_filing["complainant_phone"] = self.SKIP_VALUE
            filling_slots_for_anonymous_filing["phone_validation_required"] = False
            return filling_slots_for_anonymous_filing

        #case where the user wants to file anonymously with a phone number (legacy payload)
        if cmd == "anonymous":
            filling_slots_for_anonymous_filing["sensitive_issues_follow_up"] = "anonymous_with_phone"
            filling_slots_for_anonymous_filing["complainant_consent"] = "anonymous"
            return filling_slots_for_anonymous_filing
        return {}
        

    async def extract_sensitive_issues_new_detail(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "sensitive_issues_new_detail",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_sensitive_issues_new_detail(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        slots = {"sensitive_issues_new_detail": self.SKIP_VALUE}
        if slot_value not in [self.SKIP_VALUE, None] and len(slot_value.strip())>3:
            slots["sensitive_issues_new_detail"] = slot_value
            slots["grievance_description"] = tracker.get_slot("grievance_description") + "\n" + slot_value
            slots["grievance_description_status"] = "completed"
        return slots

    async def extract_sensitive_issues_nickname(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "sensitive_issues_nickname",
            tracker,
            dispatcher,
            domain
        )
    async def validate_sensitive_issues_nickname(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        if slot_value not in [self.SKIP_VALUE, None] and len(slot_value.strip())>1:
            return {"sensitive_issues_nickname": slot_value}
        else:
            return {"sensitive_issues_nickname": self.SKIP_VALUE}


    async def extract_form_sensitive_issues_complainant_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "complainant_phone",
            tracker,
            dispatcher,
            domain
        )

    async def validate_form_sensitive_issues_complainant_phone(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        """Validate phone number and set validation requirement."""
        if slot_value is None or slot_value == self.SKIP_VALUE or (isinstance(slot_value, (list, str)) and self.SKIP_VALUE in slot_value):
            return {"complainant_phone": self.SKIP_VALUE}
        if isinstance(slot_value, str) and slot_value.strip().startswith("/"):
            return {"complainant_phone": None}
        if not self.helpers.is_valid_phone(slot_value):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            return {"complainant_phone": None}
        if self.helpers.is_philippine_phone(slot_value):
            dispatcher.utter_message(text="You entered a PH number for validation.")
            return {
                "complainant_phone": self.helpers.is_philippine_phone(slot_value),
                "phone_validation_required": True,
            }
        result = {
            "complainant_phone": slot_value,
            "phone_validation_required": True,
        }
        self.logger.debug(f"Validate complainant_phone: {result['complainant_phone']}")
        return result



class ActionAskSensitiveIssuesFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_ask_sensitive_issues_follow_up"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        self.dispatch_sensitive_content_utterances_and_buttons(dispatcher)
        return []

class ActionAskSensitiveIssuesNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_sensitive_issues_new_detail"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []

class ActionAskSensitiveIssuesNickname(BaseAction):
    def name(self) -> Text:
        return "action_ask_sensitive_issues_nickname"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskFormSensitiveIssuesComplainantPhone(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_complainant_phone"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionOutroSensitiveIssues(BaseAction):
    def name(self) -> Text:
        return "action_outro_sensitive_issues"
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []