from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_chatbot.actions.base_classes.contact_form_classes import ContactFormValidationAction
from rasa_chatbot.actions.base_classes.base_classes import BaseAction



class ValidateFormSkipStatusCheck(ContactFormValidationAction):
    """
    Form validation for status check skip flow.
    Uses shared complainant location slots and LocationValidationMixin for validation.
    """
    
    def __init__(self):
        super().__init__()
    
    def name(self) -> Text:
        return "validate_form_status_check_skip"

    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        """
        Determine required slots based on validation status.
        Uses shared complainant location slots (no prefixes).
        """
        self._initialize_language_and_helpers(tracker)
        
        if tracker.get_slot("valid_province_and_district") == self.SKIP_VALUE:
            return []
        
        # Case: Province and district are invalid - need to re-collect all location data
        if tracker.get_slot("valid_province_and_district") == False:
            self.logger.debug(f"validate_form_status_check_skip: valid_province_and_district: False - re-collect all location data")
            required_slots = [
                "valid_province_and_district",
                "complainant_district",  # Shared slot
                "complainant_municipality_temp",  # Shared slot
                "complainant_municipality_confirmed"  # Shared slot
            ]
            self.logger.debug(f"validate_form_status_check_skip: required_slots: {required_slots}")
            return required_slots
        
        # Default case - just confirm existing location or collect municipality
        required_slots = [
            "valid_province_and_district", 
            "complainant_municipality_temp",  # Shared slot
            "complainant_municipality_confirmed"  # Shared slot
        ]
        self.logger.debug(f"validate_form_status_check_skip: required_slots: {required_slots}")
        return required_slots

    async def extract_valid_province_and_district(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "valid_province_and_district",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_valid_province_and_district(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        """
        Validate if existing province and district are correct.
        If yes, keep them. If no, will re-collect in required_slots.
        """
        if slot_value:
            # User confirmed existing location is correct
            return {"valid_province_and_district": slot_value}
        else:
            # User wants to provide new location
            return {"valid_province_and_district": slot_value}
    
    # Location validation methods (province, district, municipality)
    # are now inherited from LocationValidationMixin with shared slot names


########################## AskActionsFormSkipStatusCheck ######################

class ActionAskValidProvinceAndDistrict(BaseAction):
    """
    Ask user to confirm existing province and district are correct.
    Uses shared complainant_province and complainant_district slots.
    """
    def name(self) -> Text:
        return "action_ask_valid_province_and_district"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        from rasa_chatbot.actions.utils.utterance_mapping_rasa import get_utterance_base, get_buttons_base
        
        # Utterances are in form_status_check section with full action name
        form_section = "form_status_check"
        action_name = "action_ask_form_status_check_skip_valid_province_and_district"
        
        intro_utterance = get_utterance_base(form_section, action_name, 1, self.language_code)
        dispatcher.utter_message(text=intro_utterance)
        
        province = tracker.get_slot("complainant_province")
        district = tracker.get_slot("complainant_district")
        
        if province and district:
            utterance = get_utterance_base(form_section, action_name, 2, self.language_code)
            utterance = utterance.format(province=province, district=district)
            buttons = get_buttons_base(form_section, action_name, 1, self.language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        elif province:
            utterance = get_utterance_base(form_section, action_name, 3, self.language_code)
            utterance = utterance.format(province=province)
            buttons = get_buttons_base(form_section, action_name, 1, self.language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        elif district:
            utterance = get_utterance_base(form_section, action_name, 4, self.language_code)
            utterance = utterance.format(district=district)
            buttons = get_buttons_base(form_section, action_name, 1, self.language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        else:
            # No existing location - need to collect
            return [SlotSet("valid_province_and_district", False)]
        
        return []


# Note: action_ask_complainant_province, action_ask_complainant_district, 
# action_ask_complainant_municipality_temp, action_ask_complainant_municipality_confirmed
# are defined in form_contact.py and reused here (shared slots)




