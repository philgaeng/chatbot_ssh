import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple
from datetime import datetime

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.utils.base_classes import BaseFormValidationAction, BaseAction


logger = logging.getLogger(__name__)


def get_language_code(tracker: Tracker) -> str:
    """Helper function to get the language code from tracker with English as fallback."""
    return tracker.get_slot("language_code") or "en"

#-----------------------------------------------------------------------------
 ######################## AskFormContactSlots Actions ########################
 #-----------------------------------------------------------------------------
 
class ActionAskFormContactUserLocationConsent(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_location_consent"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserMunicipalityTemp(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_municipality_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        province = tracker.get_slot("complainant_province")
        district = tracker.get_slot("complainant_district")
        message = self.get_utterance(1).format(district=district, province=province)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

    
class ActionAskFormContactUserMunicipalityConfirmed(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_municipality_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        validated_municipality = tracker.get_slot('complainant_municipality_temp')
        message = self.get_utterance(1).format(validated_municipality=validated_municipality)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
       
class ActionAskFormContactUserVillage(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_village"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserAddressTemp(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_address_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserAddressConfirmed(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_address_confirmed"
    
    async def execute_action(self,
                  dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: dict
                  ):
        #check if the address and village are correct
        municipality = tracker.get_slot('complainant_municipality')
        village = tracker.get_slot('complainant_village')
        address = tracker.get_slot('complainant_address_temp')
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        message = message.format(municipality=municipality, village=village, address=address)
            
        dispatcher.utter_message(
            text=message,
            buttons=buttons
        )
        return []
    

class ActionAskFormContactUserProvince(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_province"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserDistrict(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_district"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
 

class AskFormContactUserContactConsent(BaseAction):
    def name(self) -> str:
        return "action_ask_form_contact_complainant_consent"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserFullName(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_contact_complainant_full_name"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("sensitive_issues_detected") ==self.SKIP_VALUE:
            message = self.get_utterance(1)
        else:
            message = self.get_utterance(2)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserContactPhone(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_contact_complainant_phone"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    

class ActionAskFormContactPhoneValidationRequired(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_contact_phone_validation_required"

    async def execute_action(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserContactEmailTemp(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_contact_complainant_email_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskFormContactUserContactEmailConfirmed(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_contact_complainant_email_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        domain_name = tracker.get_slot("complainant_email_temp").split('@')[1]
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        message = message.format(domain_name=domain_name)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

  #-----------------------------------------------------------------------------
 ######################## ValidateContactForm Actions ########################
 #-----------------------------------------------------------------------------
    
class ValidateFormContact(BaseFormValidationAction):
    """Form validation action for contact details collection."""
    
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
        This function is used to determine the required slots for the contact form depending on the main story.
        It checks the main story to determine if the user is checking status and only requires the phone number.
        """
        self._initialize_language_and_helpers(tracker)
        main_story = tracker.get_slot("main_story")
        if main_story == "status_update":
            return ["complainant_phone"]
        else:
            required_slots_location = ["complainant_location_consent", 
                          "complainant_province",
                          "complainant_district",
                          "complainant_municipality_temp", 
                          "complainant_municipality_confirmed", 
                          "complainant_village", 
                          "complainant_address_temp", 
                          "complainant_address_confirmed", 
                          "complainant_address"]
            required_slots_contact = ["complainant_consent",  "complainant_phone", "complainant_full_name", "complainant_email_temp", "complainant_email_confirmed"]
            return required_slots_location + required_slots_contact



    
    async def extract_complainant_location_consent(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        result = await self._handle_boolean_slot_extraction(
            "complainant_location_consent",
            tracker,
            dispatcher,
            domain
        )
        return result
    
    async def validate_complainant_location_consent(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate complainant_location_consent value."""
        if slot_value is True:
            result = {"complainant_location_consent": True}
        elif slot_value is False:
            result = {"complainant_location_consent": False,
                    "complainant_municipality_temp":self.SKIP_VALUE,
                    "complainant_municipality":self.SKIP_VALUE,
                    "complainant_municipality_confirmed": False,
                    "complainant_village":self.SKIP_VALUE,
                    "complainant_address_temp":self.SKIP_VALUE,
                    "complainant_address":self.SKIP_VALUE,
                    "complainant_address_confirmed": False}
        self.logger.debug(f"Validate complainant_location_consent: {result}")
        return result
            
    async def extract_complainant_province(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_province",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_complainant_province(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_province": None}
        
        #check if the province is valid
        if not self.helpers.check_province(slot_value):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_province": None}
        
        result = self.helpers.check_province(slot_value).title()
        message = self.get_utterance(3) 
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(
            text=message
        )
        
        return {"complainant_province": result}
        
    async def extract_complainant_district(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(  
            "complainant_district",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_complainant_district(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_district": None}
            
        province = tracker.get_slot("complainant_province").title()
        if not self.helpers.check_district(slot_value, province):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_district": None}
            
        result = self.helpers.check_district(slot_value, province).title()
        message = self.get_utterance(3)
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(
            text=message
        )
        
        return {"complainant_district": result}
        
        
    
    async def extract_complainant_municipality_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_municipality_temp",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_complainant_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        #deal with the slot_skipped case
        if slot_value == self.SKIP_VALUE:
            return {"complainant_municipality_temp": self.SKIP_VALUE,
                    "complainant_municipality": self.SKIP_VALUE,
                    "complainant_municipality_confirmed": False}
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            return {"complainant_municipality_temp": None}
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self.helpers.validate_municipality_input(slot_value, 
                                                                   tracker.get_slot("complainant_province"),
                                                                   tracker.get_slot("complainant_district"))
        
        if validated_municipality:
            return {"complainant_municipality_temp": validated_municipality}
        
        else:
            return {"complainant_municipality_temp": None,
                    "complainant_municipality": None,
                    "complainant_municipality_confirmed": None
                    }
                
                
    async def extract_complainant_municipality_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a municipality to confirm
        if not tracker.get_slot("complainant_municipality_temp"):
            return {}

        return await self._handle_boolean_slot_extraction(
            "complainant_municipality_confirmed",
            tracker,
            dispatcher,
            domain  # When skipped, assume confirmed
        )
    
    async def validate_complainant_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if slot_value == True:
            
        #save the municipality to the slot
            result = {"complainant_municipality_confirmed": True,
                    "complainant_municipality": tracker.get_slot("complainant_municipality_temp")}
            
        elif slot_value == False:
            result = {"complainant_municipality_confirmed": None,
                    "complainant_municipality_temp": None,
                    "complainant_municipality": None
                    }
        else:
            result = {}
        self.logger.debug(f"Validate complainant_municipality_confirmed: {result}")
        return result
    
    async def extract_complainant_village(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_village",
            tracker,
            dispatcher,
            domain# When skipped, assume confirmed
        )
    
    async def validate_complainant_village(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_village": self.SKIP_VALUE}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            result = {"complainant_village": None}
            
        result = {"complainant_village": slot_value}
        self.logger.debug(f"Validate complainant_village: {result}")
        return result
    
        
    
    async def extract_complainant_address_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_address_temp",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_complainant_address_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate complainant_address value."""
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_address_temp": self.SKIP_VALUE}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            result = {"complainant_address_temp": None}
        
        result = {"complainant_address_temp": slot_value}
        self.logger.debug(f"Validate complainant_address_temp: {result}")
        return result

    async def extract_complainant_address_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        return await self._handle_boolean_slot_extraction(
            "complainant_address_confirmed",
            tracker,
            dispatcher,
            domain,
            skip_value=True  # When skipped, assume confirmed
        )

    async def validate_complainant_address_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        # Handle rejection of address confirmation
        if slot_value == False:
            message = self.get_utterance(1)
            dispatcher.utter_message(text="Please enter your correct village and address")
            result = {
                "complainant_village": None,
                "complainant_address": None,
                "complainant_address_temp": None,
                "complainant_address_confirmed": None
            }
        
        # Check if we have a confirmation
        if slot_value == True:
            address = tracker.get_slot("complainant_address_temp")
            result = {
                "complainant_address": address,
                "complainant_address_confirmed": True
            }
        self.logger.debug(f"Validate complainant_address_confirmed: {result['complainant_address_confirmed']}")
        return result
    
    async def extract_complainant_consent(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "complainant_consent",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_complainant_consent(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        
        if slot_value == False:
            result = {"complainant_consent": False,
                    "complainant_full_name": self.SKIP_VALUE,
                    "complainant_phone": self.SKIP_VALUE,
                    "complainant_email_temp": self.SKIP_VALUE,
                    "complainant_email_confirmed": self.SKIP_VALUE
                    }

        if slot_value == True:
            result = {"complainant_consent": True,
                    "complainant_full_name": None,
                    "complainant_phone": None,
                    "complainant_email_temp": None,
                    "complainant_email_confirmed": None
                    }
        self.logger.debug(f"Validate complainant_consent: {result['complainant_consent']}")
        return result
        

    async def extract_complainant_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_full_name",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_complainant_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:

        if self.SKIP_VALUE in slot_value:
            result = {"complainant_full_name": self.SKIP_VALUE}
        
        elif not slot_value or slot_value.startswith('/'):
            result = {"complainant_full_name": None}

        elif len(slot_value)<3:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_full_name": None}
        
        else :
            result = {"complainant_full_name": slot_value}
            
        self.logger.debug(f"Validate complainant_full_name: {result['complainant_full_name']}")
        return result
    
    # ✅ Extract user contact phone
    async def extract_complainant_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        
        return await self._handle_slot_extraction(
            "complainant_phone",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_complainant_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate phone number and set validation requirement."""
        if self.SKIP_VALUE in slot_value:
            result = {
                "complainant_phone": self.SKIP_VALUE
            }
        elif slot_value.startswith("/"):
            result = {"complainant_phone": None}  
        
        # Validate phone number format
        elif not self.helpers.is_valid_phone(slot_value):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_phone": None}
        else:
            if self.helpers.is_philippine_phone(slot_value):
                result = {
                    "complainant_phone": self.helpers.is_philippine_phone(slot_value),
                    "phone_validation_required": True
                }
                dispatcher.utter_message(text="You entered a PH number for validation.")
            else:
                result = {
                "complainant_phone": slot_value,
                "phone_validation_required": True
            }
        self.logger.debug(f"Validate complainant_phone: {result['complainant_phone']}")
        return result

    async def extract_phone_validation_required(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "phone_validation_required",
            tracker,
            dispatcher,
            domain
        )

    async def validate_phone_validation_required(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value and tracker.get_slot("complainant_phone") == self.SKIP_VALUE:
            result = {"phone_validation_required": None,
                    "complainant_phone": None}
        else:
            result = {"phone_validation_required": False}
        self.logger.debug(f"Validate phone_validation_required: {result['phone_validation_required']}")
        return result

    async def extract_complainant_email_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        slot_value = await self._handle_slot_extraction(
            "complainant_email_temp",
            tracker,
            dispatcher,
            domain
        )
        return slot_value
    
    async def validate_complainant_email_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        language = get_language_code(tracker)
        #deal with the slot_skipped case
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_email_temp": self.SKIP_VALUE,
                    "complainant_email_confirmed": False,
                    "complainant_email": self.SKIP_VALUE
                    }
            self.logger.debug(f"Validate complainant_email_temp: {result['complainant_email_temp']}")
            return result
        
        
        extracted_email = self.helpers.email_extract_from_text(slot_value)
        if not extracted_email:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_email_temp": None}
            self.logger.debug(f"Validate complainant_email_temp: {result['complainant_email_temp']}")
            return result
        
        # Use consistent validation methods
        if not self.helpers.email_is_valid_format(extracted_email):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_email_temp": None}

        # Check for Nepali email domain using existing method
        elif not self.helpers.email_is_valid_nepal_domain(extracted_email):
            # Keep the email in slot but deactivate form while waiting for user choice
            result = {"complainant_email_temp": extracted_email,
                    "complainant_email_confirmed": None}
            
        # If all validations pass
        else:
            result = {"complainant_email_temp": extracted_email,
                    "complainant_email_confirmed": True,
                    "complainant_email": extracted_email}
        self.logger.debug(f"Validate complainant_email_temp: {result['complainant_email_temp']}")
        return result
    
    async def extract_complainant_email_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_email_confirmed",
            tracker,
            dispatcher,
            domain
        )
    async def validate_complainant_email_confirmed(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        """Validate the user's confirmation of their email address.
        
        This function handles three possible responses:
        - slot_skipped: User chose to skip providing an email
        - slot_confirmed: User confirmed their non-Nepali email domain is correct
        - slot_edited: User wants to edit their email and try again
        
        Args:
            slot_value: The value received from the user's response
            dispatcher: The dispatcher used to send messages to the user
            tracker: The conversation tracker
            domain: The bot's domain configuration
            
        Returns:
            Dict containing updates to the relevant email slots based on user's choice
        """
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_email_confirmed": self.SKIP_VALUE}
        elif slot_value == "slot_confirmed":
            result = {"complainant_email_confirmed": True}
        elif slot_value == "slot_edited":
            result = {"complainant_email_temp": None,
                    "complainant_email_confirmed": None}
        self.logger.debug(f"Validate complainant_email_confirmed: {result['complainant_email_confirmed']}")
        return result

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