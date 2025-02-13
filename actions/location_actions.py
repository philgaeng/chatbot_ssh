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
from actions.helpers import LocationValidator  # Add this import
from .constants import QR_PROVINCE, QR_DISTRICT, DISTRICT_LIST, USE_QR_CODE  # Import the constants


logger = logging.getLogger(__name__)



# # Action to prepopulate location based on QR code
# class ActionPrepopulateLocation(Action):
#     def name(self) -> Text:
#         return "action_prepopulate_location"

#     def run(
#         self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
#     ) -> List[Dict[Text, Any]]:
#         if USE_QR_CODE:
#             qr_code = tracker.get_slot("qr_code")  # Assume this is pre-set
#             location_mapping = {
#                 "QR001": {"user_district": "Kathmandu", "user_municipality": "KMC"},
#                 "QR002": {"user_district": "Bhaktapur", "user_municipality": "Bhaktapur"},
#                 }
#             prepopulated = location_mapping.get(qr_code, {})
        
#         else:
#             prepopulated = {
#                 "user_district": QR_DISTRICT,
#                 "user_province": QR_PROVINCE
#             }

#         if prepopulated:
#             dispatcher.utter_message(response="utter_prepopulate_location_success", 
#                                       district=prepopulated.get("user_district"), 
#                                       province=prepopulated.get("user_province"))
#         else:
#             dispatcher.utter_message(response="utter_prepopulate_location_failure")

#         return [
#             SlotSet("user_district", prepopulated.get("user_district")),
#             SlotSet("user_province", prepopulated.get("user_province")),
#         ]

class ActionAskLocation(Action):
    def name(self) -> str:
        return "action_ask_location"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
            text="Do you want to provide the location details for your grievance. This is optional, your grievance can be filed without it.",
            buttons=[
                {"title": "Yes", "payload": "/start_location_process"},
                {"title": "Skip", "payload": "/ask_contact_details"},
                {"title": "Exit", "payload": "/goodbye"}
            ]
        )
        return []
    
######### Municipality

# class ActionConfirmMunicipality(Action):
#     def name(self) -> str:
#         return "action_confirm_municipality"

#     def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
#         # province = tracker.get_slot("user_province")
#         # district = tracker.get_slot("user_district")
#         municipality = tracker.get_slot("user_municipality")
#         # ward = tracker.get_slot("user_ward")
#         # village = tracker.get_slot("user_village")
#         # address = tracker.get_slot("user_address")

#         confirmation_message = (
#             f"""we updated your municipality name to {municipality}
#             \n Is this correct?"""
#         )
        
#         dispatcher.utter_message(text=confirmation_message,
#                                  buttons=[
#                                          {"title": "Yes", "payload": "/Agree"},
#                                          {"title": "Modify", "payload": "/modify_municipality"},
#                                          {"title": "Exit", "payload": "/exit_grievance_process"}
#                                      ])
        
#         return []

# class ActionResetMunicipalitySlots(Action):
#     def name(self) -> str:
#         return "action_reset_municipality_slots"

#     def run(self, dispatcher, tracker, domain):
#         """Resets all location-related slots before the form starts."""
#         return [
#             # SlotSet("user_province", None),
#             # SlotSet("user_district", None),
#             SlotSet("user_municipality", None),
#             # SlotSet("user_ward", None),
#             # SlotSet("user_village", None),
#             # SlotSet("user_address", None),
#         ]
        


class ValidateLocationForm(FormValidationAction):
    """Form validation action for location details collection."""

    def __init__(self):
        self.location_validator = LocationValidator()

    def name(self) -> Text:
        return "validate_location_form"

    def _is_skip_requested(self, text: str) -> bool:
        """Check if user wants to skip the current field."""
        return text.lower().strip() in ['skip', 'pass', 'next']

    def _is_confirmation_response(self, text: str) -> bool:
        """Check if the input is a confirmation response."""
        return text.lower() in ['yes', 'correct', '/affirm']

    def _is_rejection_response(self, text: str) -> bool:
        """Check if the input is a rejection response."""
        return text.lower() in ['no', 'incorrect', '/deny']

    # def _extract_slot_value(self, tracker: Tracker, slot_name: str) -> Dict[Text, Any]:
    #     """Extract value for a given slot from the latest message."""
    #     print(f"🔍 Extracting slot value for {slot_name} -slotvalue method")
    #     if tracker.get_slot("requested_slot") != slot_name:
    #         return {}
            
    #     value = tracker.latest_message.get("text", "").strip()
    #     intent = tracker.latest_message.get("intent", {}).get("name", "")
    #     print(f"🔍 Extracted value: {value} and intent: {intent} - slotvalue method")
    #     # Handle confirmation responses
    #     if 'affirm' in value:
    #         return {f"{slot_name}_confirmed": True}
    #     elif 'deny' in value:
    #             return {f"{slot_name}_confirmed": False}
        


    def _validate_municipality_input(
        self,
        dispatcher: CollectingDispatcher,
        slot_value: Text
    ) -> Dict[Text, Any]:
        """Validate new municipality input."""
        validation_result = self.location_validator.validate_location(
            slot_value.lower(), 
            qr_province=QR_PROVINCE, 
            qr_district=QR_DISTRICT
        )
        
        if not validation_result:
            dispatcher.utter_message(
                text=f"Please enter a valid municipality name in {QR_DISTRICT}, {QR_PROVINCE}"
            )
            return {"user_municipality": None}
        
        municipality = validation_result["municipality"].title()
        print(f"✅ Municipality validated: {municipality}")
        
        dispatcher.utter_message(
            text=f"I understood your municipality as {municipality}. Is this correct?",
            buttons=[
                {"title": "Yes", "payload": "/affirm"},
                {"title": "No", "payload": "/deny"},
            ]
        )
        
        return {
            "user_municipality": None,
            "user_municipality_temp": municipality
        }

    def _validate_optional_field(
        self,
        slot_value: Text,
        min_length: int,
        field_name: str,
        dispatcher: CollectingDispatcher
    ) -> Dict[Text, Any]:
        """Validate optional fields (village/address)."""
        if slot_value == "Not provided":
            return {field_name: slot_value}
            
        if not slot_value or len(slot_value) < min_length or slot_value.startswith("/"):
            dispatcher.utter_message(
                text=f"Please provide a valid {field_name.replace('user_', '').replace('_temp', '')} (or type 'skip' to skip)."
            )
            return {field_name: None}
        
        return {field_name: slot_value}

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        print("\n=================== Location Form Required Slots ===================")
        
        required_slots = ["user_municipality_temp" == "completed"]
        
        if (tracker.get_slot("user_municipality_temp") == "completed" and 
            tracker.get_slot("provide_additional_location") == True):
            required_slots.extend(["user_address_temp" == "completed"])
            
        print(f"Required slots: {required_slots}")
        return required_slots

    async def extract_user_municipality_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("\n📍 FORM: Extracting municipality")
        
        # Get the latest user message text
        latest_message = tracker.latest_message.get("text", "").strip()
        intent = tracker.latest_message.get("intent", {}).get("name", "")
        print(f"Received value: {latest_message}")
        print(f"Intent: {intent}")
        
        if latest_message == "/start_location_process":
            dispatcher.utter_message(
                text=f"Please enter your municipality name in {QR_DISTRICT}, {QR_PROVINCE}"
            )
            return {}
        
        if tracker.get_slot("provide_additional_location") == False:
            if latest_message == "/affirm":
                return {"user_municipality_temp": "additional_location_confirmed"}
            elif latest_message == "/deny":
                return {"user_municipality_temp": "additional_location_rejected"}
            
            # Just return the extracted value, validation will handle slot setting
        return {"user_municipality_temp": latest_message}

    async def validate_user_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("\n✨ FORM: Validating municipality")
        print(f"Received value: {slot_value}")
        
        # Handle confirmation of additional location
        if tracker.get_slot("user_municipality_temp") == "additional_location_confirmed":
            return {
                "user_municipality_temp": "confirmed",
                "provide_additional_location": True
            }
        
        if tracker.get_slot("user_municipality_temp") == "additional_location_rejected":
            dispatcher.utter_message(
                text=f"Skipping provision of location details",
            )
            return {
                "user_municipality_temp": "comfirmed",
                "provide_additional_location": False
            }

        
        # Check if we have a confirmation
        if tracker.get_slot("user_municipality_temp") == "/affirm":
            municipality = tracker.get_slot("user_municipality")
            dispatcher.utter_message(
                text=f"""Great! I've recorded your municipality as {municipality}./n
                Would you like to provide more detailed location information?""",
                buttons=[
                    {"title": "Yes, add more details", "payload": "/affirm"},
                    {"title": "No, continue", "payload": "/deny"},
                ]
            )
            return {
                "user_municipality_temp": "confirmed",
                "provide_additional_location": False
            }
        
        # ask user to confirm the municipality

        if tracker.get_slot("user_municipality_temp"):
            municipality = tracker.get_slot('user_municipality_temp')
            # Validate new municipality input with the extract and rapidfuzz functions
            validated_municipality = self._validate_municipality_input(dispatcher, slot_value)
            if validated_municipality:
                dispatcher.utter_message(
                    text=f"Is {validated_municipality} your correct municipality?",
                    buttons=[
                        {"title": "Yes", "payload": "/affirm"},
                        {"title": "No", "payload": "/deny"},
                    ]
                )
                return {"user_municipality": tracker.get_slot('user_municipality_temp')}
            
            else:
                dispatcher.utter_message(
                    text=f"Please enter your municipality name in {QR_DISTRICT}, {QR_PROVINCE}"
                )
                return {"user_municipality_temp": None}
            

    async def validate_provide_additional_location(
        self,
        slot_value: bool,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return {"provide_additional_location": slot_value}

    async def extract_user_village(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("\n📍 FORM: Extracting village")
        latest_message = tracker.latest_message.get("text")
        print(f"Received value for village: {latest_message}")
        return {"user_village": latest_message}

    def _extract_user_address( 
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Get the latest user message text
        print("\n📍 FORM: Extracting address")
        latest_message = tracker.latest_message.get("text")
        print(f"Received value for address: {latest_message}")
        return {"user_address_temp": latest_message}
    
    
    
    async def validate_user_address(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Handle rejection of address confirmation
        if tracker.get_slot("user_address_confirmed") is False:
            dispatcher.utter_message(text="Please enter your correct address")
            return {
                "user_village": None,
                "user_address": None,
                "user_address_temp": None,
                "user_address_confirmed": None
            }
        
        # Check if we have a confirmation
        if tracker.get_slot("user_address_confirmed") == True:
            address = tracker.get_slot("user_address_temp")
            return {
                "user_address": address,
                "user_address_temp": None,
                "user_address_confirmed": None
            }

        if not tracker.get_slot("user_address_confirmed"):
            
            result = self._validate_optional_field(slot_value, 2, "user_address_temp", dispatcher)
            # If we have a temp value, we're in confirmation mode
            
            if result.get("user_address_temp") is not None:
                confirmation_message = (
                    f"Thank you for providing your location details:\n"
                    f"- Municipality: {tracker.get_slot('user_municipality')}\n"
                    f"- Village: {tracker.get_slot('user_village')}\n"
                    f"- Address: {address}\n\n"
                    "Is this correct?"
                )
            
                dispatcher.utter_message(
                    text=confirmation_message,
                    buttons=[
                        {"title": "Yes", "payload": "/affirm"},
                        {"title": "No, modify", "payload": "/deny"},
                    ]
                )
            return result
        
    async def validate_user_village(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return self._validate_optional_field(slot_value, 2, "user_village", dispatcher)
