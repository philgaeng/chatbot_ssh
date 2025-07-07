import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple
from datetime import datetime

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from backend.services.database_services.postgres_services import db_manager
from .base_classes import BaseFormValidationAction, BaseAction, SKIP_VALUE
from backend.shared_functions.helpers import ContactLocationValidator
from .utterance_mapping_rasa import get_utterance, get_buttons
from icecream import ic


logger = logging.getLogger(__name__)


def get_language_code(tracker: Tracker) -> str:
    """Helper function to get the language code from tracker with English as fallback."""
    return tracker.get_slot("language_code") or "en"

#-----------------------------------------------------------------------------
 ######################## AskContactFormSlots Actions ########################
 #-----------------------------------------------------------------------------
 
class ActionAskContactFormUserLocationConsent(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_location_consent"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        language_code = tracker.get_slot("language_code") if tracker.get_slot("language_code") else "en"
        message = get_utterance('contact_form', self.name(), 1, language_code)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserMunicipalityTemp(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_municipality_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        province = tracker.get_slot("user_province")
        district = tracker.get_slot("user_district")
        language_code = tracker.get_slot("language_code") if tracker.get_slot("language_code") else "en"
        message = get_utterance('contact_form', self.name(), 1, language_code).format(district=district, province=province)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

    
class ActionAskContactFormUserMunicipalityConfirmed(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_municipality_confirmed"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        validated_municipality = tracker.get_slot('user_municipality_temp')
        language_code = tracker.get_slot("language_code") if tracker.get_slot("language_code") else "en"
        message = get_utterance('contact_form', self.name(), 1, language_code).format(validated_municipality=validated_municipality)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
       
class ActionAskContactFormUserVillage(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_village"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        language_code = tracker.get_slot("language_code") if tracker.get_slot("language_code") else "en"
        message = get_utterance('contact_form', self.name(), 1, language_code)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserAddressTemp(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_address_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        language_code = tracker.get_slot("language_code") if tracker.get_slot("language_code") else "en"
        message = get_utterance('contact_form', self.name(), 1, language_code)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserAddressConfirmed(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_address_confirmed"
    
    async def run(self,
                  dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: dict
                  ):
        #check if the address and village are correct
        municipality = tracker.get_slot('user_municipality')
        village = tracker.get_slot('user_village')
        address = tracker.get_slot('user_address_temp')
        language_code = tracker.get_slot('language_code')
        message = get_utterance('contact_form', self.name(), 1, language_code)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        message = message.format(municipality=municipality, village=village, address=address)
            
        dispatcher.utter_message(
            text=message,
            buttons=buttons
        )
        return []
    

class ActionAskContactFormUserProvince(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_province"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        language_code = tracker.get_slot('language_code') if tracker.get_slot('language_code') else "en"
        message = get_utterance('contact_form', self.name(), 1, language_code)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserDistrict(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_district"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        language_code = tracker.get_slot('language_code') if tracker.get_slot('language_code') else "en"
        message = get_utterance('contact_form', self.name(), 1, language_code)
        buttons = get_buttons('contact_form', self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
 

class AskContactFormUserContactConsent(BaseAction):
    def name(self) -> str:
        return "action_ask_contact_form_user_contact_consent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('contact_form', self.name(), 1, language)
        buttons = get_buttons('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserFullName(BaseAction):
    def name(self) -> Text:
        return "action_ask_contact_form_user_full_name"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        if tracker.get_slot("gender_issues_reported") == SKIP_VALUE:
            message = get_utterance('contact_form', self.name(), 1, language)
        else:
            message = get_utterance('contact_form', self.name(), 2, language)
        buttons = get_buttons('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserContactPhone(BaseAction):
    def name(self) -> Text:
        return "action_ask_contact_form_user_contact_phone"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('contact_form', self.name(), 1, language)
        buttons = get_buttons('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    

class ActionAskContactFormPhoneValidationRequired(BaseAction):
    def name(self) -> Text:
        return "action_ask_contact_form_phone_validation_required"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('contact_form', self.name(), 1, language)
        buttons = get_buttons('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserContactEmailTemp(BaseAction):
    def name(self) -> Text:
        return "action_ask_contact_form_user_contact_email_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('contact_form', self.name(), 1, language)
        buttons = get_buttons('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskContactFormUserContactEmailConfirmed(BaseAction):
    def name(self) -> Text:
        return "action_ask_contact_form_user_contact_email_confirmed"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        domain_name = tracker.get_slot("user_contact_email_temp").split('@')[1]
        language = get_language_code(tracker)
        message = get_utterance('contact_form', self.name(), 1, language).format(domain_name=domain_name)
        buttons = get_buttons('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

  #-----------------------------------------------------------------------------
 ######################## ValidateContactForm Actions ########################
 #-----------------------------------------------------------------------------
    
class ValidateContactForm(BaseFormValidationAction):
    """Form validation action for contact details collection."""
    
    def __init__(self):
        super().__init__()
        self.validator = ContactLocationValidator()
        

    def name(self) -> Text:
        return "validate_contact_form"
    
    async def required_slots(self, 
                       domain_slots: List[Text], 
                       dispatcher: CollectingDispatcher, 
                       tracker: Tracker, 
                       domain: DomainDict) -> List[Text]:
        """
        This function is used to determine the required slots for the contact form depending on the main story.
        It checks the main story to determine if the user is checking status and only requires the phone number.
        """
        main_story = tracker.get_slot("main_story")
        #ic(main_story)
        if main_story == "status_update":
            return ["user_contact_phone"]
        else:
            required_slots_location = ["user_location_consent", 
                          "user_province",
                          "user_district",
                          "user_municipality_temp", 
                          "user_municipality_confirmed", 
                          "user_village", 
                          "user_address_temp", 
                          "user_address_confirmed", 
                          "user_address"]
            required_slots_contact = ["user_contact_consent",  "user_contact_phone", "user_full_name", "user_contact_email_temp", "user_contact_email_confirmed"]
            return required_slots_location + required_slots_contact



    
    async def extract_user_location_consent(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        result = await self._handle_boolean_slot_extraction(
            "user_location_consent",
            tracker,
            dispatcher,
            domain
        )
        return result
    
    async def validate_user_location_consent(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate user_location_consent value."""
        if slot_value is True:
            return {"user_location_consent": True}
        elif slot_value is False:
            return {"user_location_consent": False,
                    "user_municipality_temp": SKIP_VALUE,
                    "user_municipality": SKIP_VALUE,
                    "user_municipality_confirmed": False,
                    "user_village": SKIP_VALUE,
                    "user_address_temp": SKIP_VALUE,
                    "user_address": SKIP_VALUE,
                    "user_address_confirmed": False}
            
    async def extract_user_province(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_province",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_user_province(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        self.validator._initialize_constants(tracker)
        language_code = self.validator.language_code
        if slot_value == SKIP_VALUE:
            dispatcher.utter_message(
                text=get_utterance('contact_form', 'validate_user_province', 1, language_code)
            )
            return {"user_province": None}
        
        #check if the province is valid
        if not self.validator._check_province(slot_value):
            dispatcher.utter_message(
                text=get_utterance('contact_form', 'validate_user_province', 2, language_code).format(slot_value=slot_value)
            )
            return {"user_province": None}
        
        result = self.validator._check_province(slot_value).title()
        dispatcher.utter_message(
            text=get_utterance('contact_form', 'validate_user_province', 3, language_code).format(slot_value=slot_value, result=result)
        )
        
        return {"user_province": result}
        
    async def extract_user_district(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(  
            "user_district",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_user_district(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        self.validator._initialize_constants(tracker)
        language_code = self.validator.language_code
        if slot_value == SKIP_VALUE:
            dispatcher.utter_message(
                text=get_utterance('contact_form', 'validate_user_district', 1, language_code)
            )
            return {"user_district": None}
            
        province = tracker.get_slot("user_province").title()
        if not self.validator._check_district(slot_value, province):
            dispatcher.utter_message(
                text=get_utterance('contact_form', 'validate_user_district', 2, language_code).format(slot_value=slot_value)
            )
            return {"user_district": None}
            
        result = self.validator._check_district(slot_value, province).title()
        dispatcher.utter_message(
            text=get_utterance('contact_form', 'validate_user_district', 3, language_code).format(slot_value=slot_value, result=result)
        )
        
        return {"user_district": result}
        
        
    
    async def extract_user_municipality_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_municipality_temp",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_user_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        self.validator._initialize_constants(tracker)
        language_code = self.validator.language_code
        
        #deal with the slot_skipped case
        if slot_value == SKIP_VALUE:
            return {"user_municipality_temp": SKIP_VALUE,
                    "user_municipality": SKIP_VALUE,
                    "user_municipality_confirmed": False}
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            return {"user_municipality_temp": None}
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self.validator._validate_municipality_input(slot_value, 
                                                                   tracker.get_slot("user_province"),
                                                                   tracker.get_slot("user_district"))
        
        if validated_municipality:
            return {"user_municipality_temp": validated_municipality}
        
        else:
            return {"user_municipality_temp": None,
                    "user_municipality": None,
                    "user_municipality_confirmed": None
                    }
                
                
    async def extract_user_municipality_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a municipality to confirm
        if not tracker.get_slot("user_municipality_temp"):
            return {}

        return await self._handle_boolean_slot_extraction(
            "user_municipality_confirmed",
            tracker,
            dispatcher,
            domain  # When skipped, assume confirmed
        )
    
    async def validate_user_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if slot_value == True:
            
        #save the municipality to the slot
            return {"user_municipality_confirmed": True,
                    "user_municipality": tracker.get_slot("user_municipality_temp")}
            
        elif slot_value == False:
            return {"user_municipality_confirmed": None,
                    "user_municipality_temp": None,
                    "user_municipality": None
                    }
        return {}
    
    async def extract_user_village(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_village",
            tracker,
            dispatcher,
            domain# When skipped, assume confirmed
        )
    
    async def validate_user_village(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        language_code = tracker.get_slot("language_code")
        if slot_value == SKIP_VALUE:
            return {"user_village": SKIP_VALUE}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            
            dispatcher.utter_message(
                text=get_utterance('contact_form', 'validate_user_village', 1, language_code)
            )
            return {"user_village": None}
            
        return {"user_village": slot_value}
    
        
    
    async def extract_user_address_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_address_temp",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_user_address_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate user_address value."""
        language_code = tracker.get_slot("language_code")
        if slot_value == SKIP_VALUE:
            return {"user_address_temp": SKIP_VALUE}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            
            dispatcher.utter_message(
                text=get_utterance('contact_form', 'validate_user_address_temp', 1, language_code)
            )
            return {"user_address_temp": None}
        
        return {"user_address_temp": slot_value}

    async def extract_user_address_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # First check if we have an address to confirm
        if not tracker.get_slot("user_address_temp"):
            return {}

        return await self._handle_boolean_slot_extraction(
            "user_address_confirmed",
            tracker,
            dispatcher,
            domain,
            skip_value=True  # When skipped, assume confirmed
        )

    async def validate_user_address_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        # Handle rejection of address confirmation
        if slot_value == False:
            dispatcher.utter_message(text="Please enter your correct village and address")
            return {
                "user_village": None,
                "user_address": None,
                "user_address_temp": None,
                "user_address_confirmed": None
            }
        
        # Check if we have a confirmation
        if slot_value == True:
            address = tracker.get_slot("user_address_temp")
            return {
                "user_address": address,
                "user_address_confirmed": True
            }
        return {} 
    
    async def extract_user_contact_consent(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "user_contact_consent",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_user_contact_consent(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        
        if slot_value == False:
            return {"user_contact_consent": False,
                    "user_full_name": SKIP_VALUE,
                    "user_contact_phone": SKIP_VALUE,
                    "user_contact_email_temp": SKIP_VALUE,
                    "user_contact_email_confirmed": SKIP_VALUE
                    }

        if slot_value == True:
            return {"user_contact_consent": True,
                    "user_full_name": None,
                    "user_contact_phone": None,
                    "user_contact_email_temp": None,
                    "user_contact_email_confirmed": None
                    }
        

    async def extract_user_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_full_name",
            tracker,
            dispatcher,
            domain
        )
    
    def validate_user_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:

        if SKIP_VALUE in slot_value:
            return {"user_full_name": SKIP_VALUE}
        
        if not slot_value or slot_value.startswith('/'):
            return {"user_full_name": None}

        if len(slot_value)<3:
            language = get_language_code(tracker)
            message = get_utterance('contact_form', 'validate_user_full_name', 1, language)
            dispatcher.utter_message(text=message)
            return {"user_full_name": None}
        
        return {"user_full_name": slot_value}
    
    # ✅ Extract user contact phone
    async def extract_user_contact_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        
        return await self._handle_slot_extraction(
            "user_contact_phone",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_user_contact_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate phone number and set validation requirement."""
        language = get_language_code(tracker)
        if SKIP_VALUE in slot_value:
            return {
                "user_contact_phone": SKIP_VALUE
            }
        if slot_value.startswith("/"):
            return {"user_contact_phone": None}  
        
        # Validate phone number format
        if not self.validator._is_valid_phone(slot_value):
            message = get_utterance('contact_form', 'validate_user_contact_phone', 1, language)
            dispatcher.utter_message(text=message)
            return {"user_contact_phone": None}


        
        if re.match(r'^09\d{9}$', slot_value) or re.match(r'^639\d{8}$', slot_value):
            dispatcher.utter_message(text="You entered a PH number for validation.")
            slot_value = slot_value.replace('09', '+639') if slot_value.startswith('09') else slot_value.replace('639', '+639') if slot_value.startswith('639') else slot_value
        return {
            "user_contact_phone": slot_value,
            "phone_validation_required": True
        }

    async def extract_phone_validation_required(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "phone_validation_required",
            tracker,
            dispatcher,
            domain
        )

    async def validate_phone_validation_required(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value and tracker.get_slot("user_contact_phone") == SKIP_VALUE:
            return {"phone_validation_required": None,
                    "user_contact_phone": None}
        else:
            return {"phone_validation_required": False}

    async def extract_user_contact_email_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        slot_value = await self._handle_slot_extraction(
            "user_contact_email_temp",
            tracker,
            dispatcher,
            domain
        )
        ic(slot_value)
        return slot_value
    
    async def validate_user_contact_email_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        language = get_language_code(tracker)
        #deal with the slot_skipped case
        if slot_value == SKIP_VALUE:
            return {"user_contact_email_temp": SKIP_VALUE,
                    "user_contact_email_confirmed": False,
                    "user_contact_email": SKIP_VALUE
                    }
        
        #deal with the email case
        extracted_email = self.validator._email_extract_from_text(slot_value)
        if not extracted_email:
            message = get_utterance('contact_form', 'validate_user_contact_email_temp', 1, language)
            dispatcher.utter_message(text=message)
            return {"user_contact_email_temp": None}
        
        # Use consistent validation methods
        if not self.validator._email_is_valid_format(extracted_email):
            message = get_utterance('contact_form', 'validate_user_contact_email_temp', 1, language)
            dispatcher.utter_message(text=message)
            return {"user_contact_email_temp": None}

        # Check for Nepali email domain using existing method
        if not self.validator._email_is_valid_nepal_domain(extracted_email):
            # Keep the email in slot but deactivate form while waiting for user choice
            return {"user_contact_email_temp": extracted_email,
                    "user_contact_email_confirmed": None}
            
        # If all validations pass
        return {"user_contact_email_temp": extracted_email,
                "user_contact_email_confirmed": True,
                "user_contact_email": extracted_email}
    
    async def extract_user_contact_email_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_contact_email_confirmed",
            tracker,
            dispatcher,
            domain
        )
    async def validate_user_contact_email_confirmed(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
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
        if slot_value == SKIP_VALUE:
            return {"user_contact_email_confirmed": SKIP_VALUE}
        if slot_value == "slot_confirmed":
            return {"user_contact_email_confirmed": True}
        if slot_value == "slot_edited":
            return {"user_contact_email_temp": None,
                    "user_contact_email_confirmed": None}

#-----------------------------------------------------------------------------
 ######################## ModifyContactInfo Actions ########################
 #-----------------------------------------------------------------------------

class ActionModifyContactInfo(BaseAction):
    def name(self) -> Text:
        return "action_modify_contact_info"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        current_email = tracker.get_slot("user_contact_email")
        current_phone = tracker.get_slot("user_contact_phone")
        language = get_language_code(tracker)
        
        message = get_utterance('contact_form', self.name(), 1, language)
        buttons = get_buttons('contact_form', self.name(), 1, language)
        
        if current_email and current_email != SKIP_VALUE:
            buttons = [i for i in buttons if "Add Email" or "इमेल परिवर्तन गर्नुहोस्" not in i['title']]
        elif current_email == SKIP_VALUE:
            buttons = [i for i in buttons if "Change Email" or "इमेल थप्नुहोस्"not in i['title']]
            
        if current_phone and current_phone != SKIP_VALUE:
            buttons = [i for i in buttons if "Add Phone" or "फोन थप्नुहोस्" not in i['title']]
        elif current_phone == SKIP_VALUE:
            buttons = [i for i in buttons if "Change Phone" or "फोन परिवर्तन गर्नुहोस्" not in i['title']]
            
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionModifyEmail(BaseAction):
    def name(self) -> Text:
        return "action_modify_email"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return [
            SlotSet("user_contact_email", None),
            SlotSet("contact_modification_mode", True),
            ActiveLoop("contact_form")
        ]

class ActionCancelModification(BaseAction):
    def name(self) -> Text:
        return "action_cancel_modification_contact"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('contact_form', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return [SlotSet("contact_modification_mode", False)]