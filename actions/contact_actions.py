# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import re
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

class AskContactConsent(Action):
    def name(self) -> str:
        return "action_ask_contact_consent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = (
            "Would you like to provide your contact information? Here are your options:\n\n"
            "1️⃣ **Yes**: Share your contact details for follow-up and updates about your grievance.\n"
            "2️⃣ **Anonymous with phone number**: Stay anonymous but provide a phone number to receive your grievance ID.\n"
            "3️⃣ **No contact information**: File your grievance without providing contact details. "
            "Note that we won't be able to follow up or share your grievance ID."
        )
        dispatcher.utter_message(
            text=message,
            buttons=[
                {"title": "Yes", "payload": "/provide_contact_yes"},
                {"title": "Anonymous with phone", "payload": "/anonymous_with_phone"},
                {"title": "No contact info", "payload": "/no_contact_provided"},
            ]
        )
        return []


# Action to send OTP
class ActionSendOtp(Action):
    def name(self) -> Text:
        return "action_send_otp"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("user_contact_phone")
        otp = randint(100000, 999999)

        # Save OTP for verification
        dispatcher.utter_message(response="utter_send_otp", phone_number=phone_number)

        # Send OTP via SMS (Twilio Example)
        try:
            client = Client("account_sid", "auth_token")
            client.messages.create(
                body=f"Your OTP is {otp}",
                from_="your_twilio_number",
                to=phone_number,
            )
        except Exception as e:
            dispatcher.utter_message(response="utter_send_otp_failure", error=str(e))

        return [SlotSet("otp", otp)]


class ActionVerifyOtp(Action):
    def name(self) -> Text:
        return "action_verify_otp"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        user_otp = tracker.latest_message.get("text")
        expected_otp = tracker.get_slot("otp")

        if user_otp == str(expected_otp):
            dispatcher.utter_message(response="utter_otp_verified_success")
            return [SlotSet("otp_verified", True)]
        else:
            dispatcher.utter_message(response="utter_otp_verified_failure")
            return [SlotSet("otp_verified", False)]
        
    
class ValidateContactForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_contact_form"
    
    async def extract_user_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")

        if intent_name in ["skip", "skip_user_full_name"]:
            return {"user_full_name": "slot_skipped"}  # Explicitly marking skipped slots

        return {"user_full_name": user_response if user_response else None}


    # ✅ Extract user contact phone
    async def extract_user_contact_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")

        print("############# Extract user contact phone ##########")
        print("Requested Slot:", tracker.get_slot("requested_slot"))
        print("User Response:", user_response)

        if tracker.get_slot("requested_slot") != "user_contact_phone":
            return {}

        # ✅ Ignore button payloads (they start with "/")
        if user_response.startswith("/"):
            dispatcher.utter_message(response="utter_ask_contact_form_user_contact_phone")
            return {"user_contact_phone": None}  

        if intent_name in ['skip', 'skip_contact_phone']:
            dispatcher.utter_message(response="utter_skip_phone_number")
            return {"user_contact_phone": 'slot_skipped'}

        return {"user_contact_phone": user_response}

    # ✅ Extract user contact email
    async def extract_user_contact_email(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")

        print("############# Extract user contact email ##########")
        print("Requested Slot:", tracker.get_slot("requested_slot"))
        print("User Response:", user_response)

        if tracker.get_slot("requested_slot") != "user_contact_email":
            return {}

        if user_response.startswith("/"):
            dispatcher.utter_message(response="utter_ask_contact_form_user_contact_email")
            return {"user_contact_email": None}  

        if intent_name in ['skip', 'skip_contact_email']:
            dispatcher.utter_message(response="utter_skip_phone_email")
            return {"user_contact_email": 'slot_skipped'}

        return {"user_contact_email": user_response}

        # ✅ Validate user contact phone
    async def validate_user_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        print("################ Validate user contact phone ###################")

        if not slot_value:
            return {"user_full_name": None}  

        # Validate Nepal phone number format (starts with 97 or 98 and is 10 digits long)
        if len(slot_value)<3:
            dispatcher.utter_message(
                text=(
                    "The full name you provided is not valid "
                )

            )
            return {"user_contact_phone": None}

        return {"user_contact_phone": slot_value}
    
    # ✅ Validate user contact phone
    async def validate_user_contact_phone(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        print("################ Validate user contact phone ###################")

        if not slot_value:
            return {"user_contact_phone": None}  

        # Remove non-numeric characters
        cleaned_number = re.sub(r"\D", "", slot_value)

        # Validate Nepal phone number format (starts with 97 or 98 and is 10 digits long)
        if not re.match(r"^(98|97)\d{8}$", cleaned_number):
            dispatcher.utter_message(
                text=(
                    "The phone number you provided is invalid. "
                    "Nepal mobile numbers must start with 98 or 97 and be exactly 10 digits long."
                ), 
                buttons=[
                    {"title": "Retry", "payload": "/provide_contact_phone"},
                    {"title": "Skip", "payload": "/skip_contact_phone"}
                ]
            )
            return {"user_contact_phone": None}

        return {"user_contact_phone": cleaned_number}

    # ✅ Validate user contact email
    async def validate_user_contact_email(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        print("################ Validate user contact email ###################")

        if not slot_value:
            return {"user_contact_email": None}  

        # Standard email validation pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, slot_value):
            dispatcher.utter_message(
                text=(
                    "⚠️ The email address you provided is invalid.\n"
                    "A valid email should be in the format: **username@domain.com**."
                ),
                buttons=[
                    {"title": "Retry", "payload": "/provide_contact_email"},
                    {"title": "Skip Email", "payload": "/skip_contact_email"},
                ]
            )
            return {"user_contact_email": None}

        return {"user_contact_email": slot_value.strip().lower()}