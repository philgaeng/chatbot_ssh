# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import re
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client



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

    async def extract_user_full_name(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        if tracker.latest_message.get("intent", {}).get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_full_name")
            return {"user_full_name": None}
        return {"user_full_name": tracker.latest_message.get("text")}

    async def extract_user_honorific_prefix(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        if tracker.latest_message.get("intent", {}).get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_honorific_prefix")
            return {"user_honorific_prefix": None}
        return {"user_honorific_prefix": tracker.latest_message.get("text")}

    async def extract_user_contact_phone(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        phone_number = tracker.latest_message.get("text")
        if tracker.latest_message.get("intent", {}).get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_phone_number")
            return {"user_contact_phone": None}

        # Validate Nepal phone number format
        if not re.match(r"^(98|97)\d{8}$", phone_number):
            dispatcher.utter_message(
                text=(
                    "The phone number you provided is invalid. "
                    "Nepal mobile numbers must start with 98 or 97 and be exactly 10 digits long. "
                    "Please provide a valid number."
                )
            )
            return {"user_contact_phone": None}

        return {"user_contact_phone": phone_number}

    async def extract_user_contact_email(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        email = tracker.latest_message.get("text")
        if tracker.latest_message.get("intent", {}).get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_email_address")
            return {"user_contact_email": None}

        # Validate email format
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            dispatcher.utter_message(
                text=(
                    "The email address you provided is invalid. "
                    "A valid email should be in the format: username@domain.com. "
                    "Please provide a valid email address."
                )
            )
            return {"user_contact_email": None}

        return {"user_contact_email": email}

    async def validate(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        try:
            # Collect the slot values
            user_full_name = tracker.get_slot("user_full_name")
            user_contact_phone = tracker.get_slot("user_contact_phone")
            user_contact_email = tracker.get_slot("user_contact_email")
            user_honorific_prefix = tracker.get_slot("user_honorific_prefix")

            # Construct the confirmation message
            confirmation_message = (
                "Thank you for providing your contact details:\n"
                f"- Full Name: {user_full_name or 'Not provided'}\n"
                f"- Honorific Prefix: {user_honorific_prefix or 'Not provided'}\n"
                f"- Phone Number: {user_contact_phone or 'Not provided'}\n"
                f"- Email Address: {user_contact_email or 'Not provided'}\n\n"
                "Is this correct?"
            )

            dispatcher.utter_message(text=confirmation_message)
            return []
        
        except Exception as e:
            dispatcher.utter_message(text="An error occurred while processing your contact details.")
            logger.error(f"Error in validate_contact_form: {e}")
            return []



