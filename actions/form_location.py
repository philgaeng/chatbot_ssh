# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import logging
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client
from .helpers import LocationValidator #add this import
from .constants import QR_PROVINCE, QR_DISTRICT, DISTRICT_LIST, USE_QR_CODE  # Import the constants
from .base_form import BaseFormValidationAction

logger = logging.getLogger(__name__)



    

class ValidateLocationForm(BaseFormValidationAction):
    """Form validation action for location details collection."""

    def __init__(self):
        """Initialize the form validation action."""
        print("ValidateLocationForm.__init__ called")
        super().__init__()
        print("super().__init__() completed")
        print(f"self.lang_helper exists: {hasattr(self, 'lang_helper')}")
        self.location_validator = LocationValidator()
        print("ValidateLocationForm.__init__ completed")

    def name(self) -> Text:
        return "validate_location_form"

    def _validate_municipality_input(
        self,
        input_text: Text
    ) -> Dict[Text, Any]:
        """Validate new municipality input."""
        validation_result = self.location_validator.validate_location(
            input_text.lower(), 
            qr_province=QR_PROVINCE, 
            qr_district=QR_DISTRICT
        )
        
        municipality = validation_result.get("municipality")
        
        if not municipality:
            return None
        
        municipality = municipality.title()
        print(f"✅ Municipality validated: {municipality}")
        
        return municipality

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        print("\n=================== Location Form Required Slots ===================")
        

        # required_slots = domain_slots if domain_slots else ["user_location_consent"]
        # print(f"user_location_consent: {tracker.get_slot('user_location_consent')}")
        # if tracker.get_slot("user_location_consent") == False:
        #     required_slots = [] 

        # if tracker.get_slot("user_location_consent") == True:
        #     required_slots = ["user_municipality_temp", "user_municipality_confirmed", "user_village", "user_address_temp", "user_address_confirmed", "user_address"]
        #     #expend required slots as the slots get filled
        required_slots = ["user_location_consent", "user_municipality_temp", "user_municipality_confirmed", "user_village", "user_address_temp", "user_address_confirmed", "user_address"]
        print(f"Input slots: {domain_slots} \n Updated slots: {required_slots}")
        print(f"requested slot: {tracker.get_slot('requested_slot')}")
        
        return required_slots
    
    async def extract_user_location_consent(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("######## FORM: Extracting user_location_consent ######")
        result = await self._handle_boolean_slot_extraction(
            "user_location_consent",
            tracker,
            dispatcher,
            domain
        )
        print(f"Extraction result: {result}")
        return result
    
    async def validate_user_location_consent(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate user_location_consent value."""
        print("######## FORM: Validating user_location_consent ########")
        print(f"Validating value: {slot_value}")
        
        if slot_value is True:
            return {"user_location_consent": True}
        elif slot_value is False:
            return {"user_location_consent": False}
        return {"user_location_consent": None}
    
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
        print("######## FORM: Validating municipality_temp ######")
        print(f"Received value: {slot_value}")
        
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            return {"user_municipality_temp": None}
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self._validate_municipality_input(slot_value)
        print(f"Validated municipality: {validated_municipality}")
        
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
            domain,
            skip_value=True  # When skipped, assume confirmed
        )
    
    async def validate_user_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating municipality confirmed slot ######")
        
        print(f"Received value for municipality confirmed: {slot_value}")
        if slot_value == True:
            print("## user_municipality_confirmed: True ######")
            print(f"Received value for municipality: {slot_value}")
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
            domain,
            skip_value=True  # When skipped, assume confirmed
        )
    
    async def validate_user_village(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating village ######")
        
        if slot_value == "slot_skipped":

            return {"user_village": "slot_skipped"}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            dispatcher.utter_message(
                text="Please provide a valid village name (at least 3 characters) or type 'skip' to skip"
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
        if slot_value == "slot_skipped":
            return {"user_address_temp": "slot_skipped"}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            dispatcher.utter_message(
                text="Please provide a valid address (at least 3 characters)"
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
        print("######## FORM: Validating address confirmed slot ######")
        print(f"Received value for address confirmed: {slot_value}")
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
            print(f"Address set to: {address}")
            return {
                "user_address": address,
                "user_address_confirmed": True
            }
        return {} 
    
    
class ActionAskLocationFormUserLocationConsent(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_location_consent"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
            text="Do you want to provide the location details for your grievance. This is optional, your grievance can be filed without it.",
            buttons=[
                {"title": "Yes", "payload": "/affirm"},
                {"title": "No", "payload": "/deny"},
            ]
        )
        return []
    
class ActionAskLocationFormUserMunicipalityTemp(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_municipality_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
                text=f"Please enter a valid municipality name in {QR_DISTRICT}, {QR_PROVINCE} (at least 3 characters) or Skip to skip",
                buttons=[
                    {"title": "Skip", "payload": "/skip"}
                ]   
            )
        return []

    
class ActionAskLocationFormUserMunicipalityConfirmed(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_municipality_confirmed"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        validated_municipality = tracker.get_slot('user_municipality_temp')
        dispatcher.utter_message(
            text=f"Is {validated_municipality} your correct municipality?",
                buttons=[
                    {"title": "Yes", "payload": "/affirm"},
                    {"title": "No", "payload": "/deny"},
                ]
            )
        return []
       
class ActionAskLocationFormUserVillage(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_village"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
                text="Please provide your village name or Skip to skip",
                buttons=[
                    {"title": "Skip", "payload": "/skip"}
                ]
            )
        return []
    
class ActionAskLocationFormUserAddressTemp(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_address_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
                text="Please provide your address or Skip to skip",
                buttons=[
                    {"title": "Skip", "payload": "/skip"}
                ]
            )
        return []
    
class ActionAskLocationFormUserAddressConfirmed(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_address_confirmed"
    
    async def run(self,
                  dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: dict
                  ):
                #check if the address and village are correct
        confirmation_message = f"""Thank you for providing your location details:
            - Municipality: {tracker.get_slot('user_municipality')}
            - Village: {tracker.get_slot('user_village')}
            - Address: {tracker.get_slot('user_address_temp')}
            Is this correct?"""
            
        dispatcher.utter_message(
            text= confirmation_message,
            buttons=[
                {"title": "Yes", "payload": "/affirm"},
                {"title": "No", "payload": "/deny"},
            ]
        )
        return []
    

