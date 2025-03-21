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
from .base_form import BaseFormValidationAction
from icecream import ic
from .utterance_mapping import get_utterance, get_buttons

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
        input_text: Text,
        qr_province: Text,
        qr_district: Text
    ) -> Dict[Text, Any]:
        """Validate new municipality input."""
        validation_result = self.location_validator._validate_location(
            input_text.lower(), 
            qr_province, 
            qr_district
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
        
        required_slots = ["user_location_consent", 
                          "user_province",
                          "user_district",
                          "user_municipality_temp", 
                          "user_municipality_confirmed", 
                          "user_village", 
                          "user_address_temp", 
                          "user_address_confirmed", 
                          "user_address"]
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
            return {"user_location_consent": False,
                    "user_municipality_temp": "slot_skipped",
                    "user_municipality": "slot_skipped",
                    "user_municipality_confirmed": False,
                    "user_village": "slot_skipped",
                    "user_address_temp": "slot_skipped",
                    "user_address": "slot_skipped",
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
        language_code = tracker.get_slot("language_code")
        if slot_value == "slot_skipped":
            messages = {'en' : "Please provide a valid province name, this is required to file your grievance",
                        'ne' : "कृपया एक वैध प्रदेशको नाम प्रदान गर्नुहोस्, यो आपको ग्रेवियंसको फाइल गर्नको लागि आवश्यक छ"}
            dispatcher.utter_message(
                text=messages[language_code]
            )
            return {"user_province": None}
        
        #check if the province is valid
        if not self.location_validator._check_province(slot_value):
            messages = {'en' : "We cannot match your entry {slot_value} to a valid province. Please try again",
                        'ne' : "आपको प्रविष्टि {slot_value} एक वैध प्रदेशको मिल्न सकिन्छ। कृपया पुनरावर्तन गर्नुहोस्"}
            dispatcher.utter_message(
                text=messages[language_code].format(slot_value=slot_value)
            )
            return {"user_province": None}
        
        result = self.location_validator._check_province(slot_value).title()
        messages = {'en' : "We have matched your entry {slot_value} to {result}.",
                    'ne' : "आपको प्रविष्टि {slot_value} एक वैध प्रदेशको मिल्न सकिन्छ। कृपया पुनरावर्तन गर्नुहोस्"}
        dispatcher.utter_message(
            text=messages[language_code].format(slot_value=slot_value, result=result)
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
        language_code = tracker.get_slot("language_code")
        if slot_value == "slot_skipped":
            messages = {'en' : "Please provide a valid district name, this is required to file your grievance",
                        'ne' : "कृपया एक वैध जिल्लाको नाम प्रदान गर्नुहोस्, यो आपको ग्रेवियंसको फाइल गर्नको लागि आवश्यक छ"}
            dispatcher.utter_message(
                text=messages[language_code]
            )
            return {"user_district": None}
            
        #check if the district is valid
        province = tracker.get_slot("user_province").lower()
        ic(province)
        if not self.location_validator._check_district(slot_value, province):
            messages = {'en' : "We cannot match your entry {slot_value} to a valid district. Please try again",
                        'ne' : "आपको प्रविष्टि {slot_value} एक वैध जिल्लाको मिल्न सकिन्छ। कृपया पुनरावर्तन गर्नुहोस्"}
            dispatcher.utter_message(
                text=messages[language_code].format(slot_value=slot_value)
            )
            return {"user_district": None}
            
        result = self.location_validator._check_district(slot_value, province).title()
        messages = {'en' : "We have matched your entry {slot_value} to {result}.",
                    'ne' : "आपको प्रविष्टि {slot_value} एक वैध जिल्लाको मिल्न सकिन्छ। कृपया पुनरावर्तन गर्नुहोस्"}
        dispatcher.utter_message(
            text=messages[language_code].format(slot_value=slot_value, result=result)
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
        print("######## FORM: Validating municipality_temp ######")
        print(f"Received value: {slot_value}")
        
        #deal with the slot_skipped case
        if slot_value == "slot_skipped":
            return {"user_municipality_temp": "slot_skipped",
                    "user_municipality": "slot_skipped",
                    "user_municipality_confirmed": False}
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            return {"user_municipality_temp": None}
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self._validate_municipality_input(slot_value, 
                                                                   tracker.get_slot("user_province"),
                                                                   tracker.get_slot("user_district"))
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
            domain  # When skipped, assume confirmed
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
            domain# When skipped, assume confirmed
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
        province = tracker.get_slot("user_province")
        district = tracker.get_slot("user_district")
        dispatcher.utter_message(
                text=f"Please enter a valid municipality name in {district}, {province} (at least 3 characters) or Skip to skip",
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
    

class ActionAskLocationFormUserProvince(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_province"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = get_utterance('location_form', self.name(), 1, 'en')
        buttons = get_buttons('location_form', self.name(), 1, 'en')
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskLocationFormUserDistrict(Action):
    def name(self) -> str:
        return "action_ask_location_form_user_district"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = get_utterance('location_form', self.name(), 1, 'en')
        buttons = get_buttons('location_form', self.name(), 1, 'en')
        dispatcher.utter_message(text=message, buttons=buttons)
        return []