import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple
from datetime import datetime

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.base_classes.contact_form_classes import ContactFormValidationAction
from rasa_chatbot.actions.base_classes.base_classes  import BaseAction


  #-----------------------------------------------------------------------------
 ######################## ValidateFormContact Actions ########################
 #-----------------------------------------------------------------------------
    
class ValidateFormContact(ContactFormValidationAction):
    """Form validation action for contact details collection.
    Uses shared complainant location slots and ContactFormValidationAction for validation.
    ContactFormValidationAction provides the following slots:
    - complainant_province
    - complainant_district
    - complainant_municipality_temp
    - complainant_municipality_confirmed
    - complainant_village_temp
    - complainant_village_confirmed
    - complainant_ward
    - complainant_address_temp
    - complainant_address_confirmed

    the following slots are not shared and are specific to the contact form:
    - complainant_consent
    - complainant_full_name
    - complainant_email_temp
    - complainant_email_confirmed

    
    """
    
    def __init__(self):
        super().__init__()
        

    def name(self) -> Text:
        return "validate_form_contact"
    
    async def required_slots(self, 
                       domain_slots: List[Text], 
                       dispatcher: CollectingDispatcher, 
                       tracker: Tracker, 
                       domain: DomainDict) -> List[Text]:
        """
        This function is used to determine the required slots for the contact form.
        Note: Phone collection has been moved to form_otp.
        For status_check flow, use form_otp directly instead of form_contact.
        """
        self._initialize_language_and_helpers(tracker)
        
        required_slots_location = ["complainant_location_consent", 
                      "complainant_province",
                      "complainant_district",
                      "complainant_municipality_temp", 
                      "complainant_municipality_confirmed", 
                      "complainant_village_temp",
                      "complainant_village_confirmed",
                      "complainant_ward",
                      "complainant_address_temp", 
                      "complainant_address_confirmed",
                      "complainant_address"
                      ]
        required_slots_contact = ["complainant_consent", "complainant_full_name", "complainant_email_temp", "complainant_email_confirmed"]
        return required_slots_location + required_slots_contact


#-----------------------------------------------------------------------------
 ######################## ModifyContactInfo Actions ########################
 #-----------------------------------------------------------------------------

class ActionModifyContactInfo(BaseAction):
    def name(self) -> Text:
        return "action_modify_contact_info"

    async def execute_action(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        current_email = tracker.get_slot("complainant_email")
        current_phone = tracker.get_slot("complainant_phone")
        
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        
        if current_email and current_email != self.SKIP_VALUE:
            buttons = [i for i in buttons if "Add Email" or "इमेल परिवर्तन गर्नुहोस्" not in i['title']]
        elif current_email == self.SKIP_VALUE:
            buttons = [i for i in buttons if "Change Email" or "इमेल थप्नुहोस्"not in i['title']]
            
        if current_phone and current_phone != self.SKIP_VALUE:
            buttons = [i for i in buttons if "Add Phone" or "फोन थप्नुहोस्" not in i['title']]
        elif current_phone == self.SKIP_VALUE:
            buttons = [i for i in buttons if "Change Phone" or "फोन परिवर्तन गर्नुहोस्" not in i['title']]
            
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionModifyEmail(BaseAction):
    def name(self) -> Text:
        return "action_modify_email"

    async def execute_action(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return [
            SlotSet("complainant_email", None),
            SlotSet("contact_modification_mode", True),
            ActiveLoop("form_contact")
        ]

class ActionCancelModification(BaseAction):
    def name(self) -> Text:
        return "action_cancel_modification_contact"

    async def execute_action(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return [SlotSet("contact_modification_mode", False)]