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
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client


logger = logging.getLogger(__name__)


# Action to prepopulate location based on QR code
class ActionPrepopulateLocation(Action):
    def name(self) -> Text:
        return "action_prepopulate_location"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        qr_code = tracker.get_slot("qr_code")  # Assume this is pre-set
        location_mapping = {
            "QR001": {"district": "Kathmandu", "municipality": "KMC"},
            "QR002": {"district": "Bhaktapur", "municipality": "Bhaktapur"},
        }
        prepopulated = location_mapping.get(qr_code, {})

        if prepopulated:
            dispatcher.utter_message(response="utter_prepopulate_location_success", 
                                      district=prepopulated.get("district"), 
                                      municipality=prepopulated.get("municipality"))
        else:
            dispatcher.utter_message(response="utter_prepopulate_location_failure")

        return [
            SlotSet("district", prepopulated.get("district")),
            SlotSet("municipality", prepopulated.get("municipality")),
        ]

class ActionAskLocation(Action):
    def name(self) -> str:
        return "action_ask_location"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
            response="utter_ask_location",
            buttons=[
                {"title": "Yes", "payload": "/start_location_process"},
                {"title": "Skip", "payload": "/ask_contact_details"},
                {"title": "Exit", "payload": "/goodbye"}
            ]
        )
        return []
    
######### Municipality

class ActionConfirmMunicipality(Action):
    def name(self) -> str:
        return "action_confirm_municipality"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # province = tracker.get_slot("province")
        # district = tracker.get_slot("district")
        municipality = tracker.get_slot("municipality")
        # ward = tracker.get_slot("ward")
        # village = tracker.get_slot("village")
        # address = tracker.get_slot("address")

        confirmation_message = (
            f"""Thank you for providing your location details:
            \n - Municipality: {municipality or 'Skipped'}"
            \n Is this correct?"""
        )
        
        dispatcher.utter_message(text=confirmation_message)
        
        return []

class ActionResetMunicipalitySlots(Action):
    def name(self) -> str:
        return "action_reset_municipality_slots"

    def run(self, dispatcher, tracker, domain):
        """Resets all location-related slots before the form starts."""
        return [
            # SlotSet("province", None),
            # SlotSet("district", None),
            SlotSet("municipality", None),
            # SlotSet("ward", None),
            # SlotSet("village", None),
            # SlotSet("address", None),
        ]
        


class ValidateMunicipalityForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_municipality_form"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        # municipality = tracker.get_slot("municipality")
        # print(f"🔍 DEBUG: municipality slot before validation: {municipality}")
        
        municipality = tracker.latest_message.get("text", "").strip().lower()

        if not municipality or municipality.startswith("/"):
            dispatcher.utter_message(text="Please enter a valid municipality name.")
            print(f"🚨 DEBUG: Invalid municipality detected, resetting slot")
            return [SlotSet("municipality", None), SlotSet("requested_slot", "municipality")]

        print(f"✅ DEBUG: municipality slot set to: {municipality}")
        return [SlotSet("municipality", municipality)]


    ########### Address and Village
    
class ActionConfirmAddress(Action):
    def name(self) -> str:
        return "action_confirm_address"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict):
        # province = tracker.get_slot("province")
        # district = tracker.get_slot("district")
        # municipality = tracker.get_slot("municipality")
        # ward = tracker.get_slot("ward")
        village = tracker.get_slot("village")
        address = tracker.get_slot("address")

        confirmation_message = (
            f"Thank you for providing your location details:\n"
            # f"- Province: {province or 'Skipped'}\n"
            # f"- District: {district or 'Skipped'}\n"
            # f"- Municipality: {municipality or 'Skipped'}\n"
            # f"- Ward: {ward or 'Skipped'}\n"
            f"- Village: {village or 'Skipped'}\n"
            f"- Address: {address or 'Skipped'}\n\n"
            "Is this correct?"
        )
        
        dispatcher.utter_message(text=confirmation_message,
                                 buttons=[
                                         {"title": "Yes", "payload": "/submit_address"},
                                         {"title": "Modify", "payload": "/modify_address"},
                                         {"title": "Exit", "payload": "/exit_grievance_process"}
                                     ])
        
        return []

class ActionResetAddressSlots(Action):
    def name(self) -> str:
        return "action_reset_address_slots"

    def run(self, dispatcher, tracker, domain):
        """Resets all location-related slots before the form starts."""
        return [
            # # SlotSet("province", None),
            # # SlotSet("district", None),
            # SlotSet("municipality", None),
            # # SlotSet("ward", None),
            SlotSet("village", None),
            SlotSet("address", None),
        ]
        
# class ValidateAddressForm(FormValidationAction):
#     def name(self) -> str:
#         return "validate_address_form"

#     async def validate_village(self, slot_name: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
#     ) -> Dict[Text, Any]:
#         """Handles slot validation, allowing skipping and ensuring valid input."""
        
#         print("#####validate_village ##############")
#         # requested_slot = tracker.get_slot("requested_slot")  # Get the slot currently being requested

#         # if not requested_slot:
#         #     return {}

#         user_response = tracker.latest_message.get("text", "").strip().lower()
#         print("user_response", user_response)
#         print("slot_name" ,slot_name)
#         intent_name = tracker.latest_message.get("intent", {}).get("name")
        
#         # ✅ Ignore payloads from buttons (they start with "/")
#         if user_response and user_response.startswith("/"):
#             print("""village - Ignore payloads from buttons (they start with "/")""")
#             dispatcher.utter_message(response= "utter_ask_municipality_form_municipality")
#             return {"village": None}  # Ask again

#         # If the user wants to skip, acknowledge and move to the next slot
#         if intent_name == "skip":
#             dispatcher.utter_message(text=f"Skipping 'village.")
#             return {"village": None}

#         # If the response is "yes" or "no", repeat only the current question
#         if user_response in ["yes", "no"]:
#             dispatcher.utter_message(text=f"I need more details for 'village'. Please provide a valid answer.")
#             return {"village": None}
#         dispatcher.utter_message(response="utter_ask_address_form_address")
#         return {"village": user_response, "address": None,
#                         "last_message_saved": user_response  # Save the message for comparison
#     } # Store the valid response
    
#     async def validate_address(
#     self, 
#     slot_name: str,
#     dispatcher: CollectingDispatcher, 
#     tracker: Tracker, 
#     domain: Dict
#     )    -> Dict[Text, Any]:
#         """Handles slot validation, allowing skipping and ensuring valid input."""
#         print("#####validate_adress##############")
#         # requested_slot = tracker.get_slot("requested_slot")  # Get the slot currently being requested

#         # if not requested_slot:
#         #     return {}

#         user_response = tracker.latest_message.get("text", "").strip().lower()
#         intent_name = tracker.latest_message.get("intent", {}).get("name")
#         village = tracker.get_slot("village")

#         print("user_response", user_response)
#         print("village", village)
#         print("slot_name", slot_name)
        
#         # ✅ Ignore payloads from buttons (they start with "/")
#         if user_response and user_response.startswith("/") or user_response == village:
#             print("""adress - Ignore payloads from buttons (they start with "/")""")
#             dispatcher.utter_message(response= "utter_ask_municipality_form_address")
#             return {"address": None, "last_message_saved": None}  # Ask again

#         # If the user wants to skip, acknowledge and move to the next slot
#         if intent_name == "skip":
#             dispatcher.utter_message(text=f"Skipping 'address'.")
#             return {"address": None}

#         # If the response is "yes" or "no", repeat only the current question
#         if user_response in ["yes", "no"]:
#             dispatcher.utter_message(text=f"I need more details for 'address'. Please provide a valid answer.")
#             return {"address": None}

#         return {"address": user_response,
#                         "last_message_saved": user_response  # Save the message for comparison
#     } # Store the valid response
        


class ValidateAddressForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_address_form"

    # ✅ Extract village slot correctly
    async def extract_village(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")

        # Ignore nlu_fallback
        if intent_name == "nlu_fallback":
            dispatcher.utter_message(text="I couldn't understand that. Please provide the name of the village.")
            return {"village": None}

        # Only extract input when village is the requested slot
        if tracker.get_slot("requested_slot") == "village":
            return {"village": user_response}

        return {}

    # ✅ Extract address slot correctly
    async def extract_address(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")

        # Ignore nlu_fallback
        if intent_name == "nlu_fallback":
            dispatcher.utter_message(text="I couldn't understand that. Please provide the address.")
            return {"address": None}

        # Only extract input when address is the requested slot
        if tracker.get_slot("requested_slot") == "address":
            return {"address": user_response}

        return {}

    # ✅ Validate village
    async def validate_village(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        if not slot_value or len(slot_value) < 2:
            dispatcher.utter_message(text="Please provide a valid village name.")
            return {"village": None}
        return {"village": slot_value}

    # ✅ Validate address
    async def validate_address(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        if not slot_value or len(slot_value) < 5:
            dispatcher.utter_message(text="Please provide a more detailed address.")
            return {"address": None}
        return {"address": slot_value}

