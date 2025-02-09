import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple
from random import randint
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client
from .constants import EMAIL_PROVIDERS_NEPAL
from .messaging import PinpointClient
import boto3
import os
import time
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

EMAIL_PROVIDERS_NEPAL_LIST = [domain for provider in EMAIL_PROVIDERS_NEPAL.values() for domain in provider]


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

        
    
class ValidateContactForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_contact_form"
    
    async def extract_user_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")
        
        print("############# Extract user full name ##########")
        print("Requested Slot:", tracker.get_slot("requested_slot"))
        print("User Response:", user_response)

        if intent_name in ["skip", "skip_user_full_name"]:
            print("skipping - slot set to slot_kipped")
            return {"user_full_name": "slot_skipped"}  # Explicitly marking skipped slots
        
        # ✅ Ignore button payloads (they start with "/")
        if user_response.startswith("/"):
            # dispatcher.utter_message(response="utter_ask_contact_form_user_full_name")
            print("payload in slot, reset to None")
            return {"user_full_name": None}  
        
        if tracker.get_slot("requested_slot") != "user_full_name":
            return {}

        return {"user_full_name": user_response if user_response else None}


    # ✅ Extract user contact phone
    async def extract_user_contact_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")
        
        print("############# Extract user contact phone ##########")
        print("Requested Slot:", tracker.get_slot("requested_slot"))
        print("User Response:", user_response)

        
        if intent_name in ['skip', 'skip_contact_phone']:
            dispatcher.utter_message(response="utter_skip_phone_number")
            print("skipping - slot set to slot_kipped")
            return {"user_contact_phone": 'slot_skipped'}
        
        # ✅ Ignore button payloads (they start with "/")
        if user_response.startswith("/"):
            # dispatcher.utter_message(response="utter_ask_contact_form_user_contact_phone")
            print("payload in slot, reset to None")
            return {"user_contact_phone": None}  

        if tracker.get_slot("requested_slot") != "user_contact_phone":
            return {}

        return {"user_contact_phone": user_response}

    # ✅ Extract user contact email
    async def extract_user_contact_email(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        intent_name = tracker.latest_message.get("intent", {}).get("name")

        print("############# Extract user contact email ##########")
        print("Requested Slot:", tracker.get_slot("requested_slot"))
        print("User Response:", user_response)

        # Handle special cases
        if self._email_should_skip_extraction(user_response, intent_name, tracker):
            return self._email_handle_skip_cases(user_response, intent_name, dispatcher)

        # Extract and validate email
        extracted_email = self._email_extract_from_text(user_response)
        if not extracted_email:
            return self._email_handle_invalid_format(dispatcher)
        
        # Validate domain
        if not self._email_is_valid_nepal_domain(extracted_email):
            return self._email_handle_unknown_domain(dispatcher, extracted_email)
        
        return {"user_contact_email": extracted_email}

    def _email_should_skip_extraction(self, user_response: str, intent_name: str, tracker: Tracker) -> bool:
        return (user_response.startswith("/") or 
                intent_name in ['skip', 'skip_contact_email'] or 
                tracker.get_slot("requested_slot") != "user_contact_email")

    def _email_handle_skip_cases(self, user_response: str, intent_name: str, dispatcher: CollectingDispatcher) -> Dict[str, Any]:
        if user_response.startswith("/"):
            print("payload in slot, reset to None")
            return {"user_contact_email": None}
        if intent_name in ['skip', 'skip_contact_email']:
            print("skipping - slot set to slot_kipped")
            dispatcher.utter_message(response="utter_skip_phone_email")
            return {"user_contact_email": 'slot_skipped'}
        return {}

    def _email_extract_from_text(self, text: str) -> Optional[str]:
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_match = re.search(email_pattern, text)
        return email_match.group(0) if email_match else None

    def _email_is_valid_nepal_domain(self, email: str) -> bool:
        email_domain = email.split('@')[1].lower()
        return email_domain in EMAIL_PROVIDERS_NEPAL_LIST or email_domain.endswith('.com.np')

    def _email_handle_invalid_format(self, dispatcher: CollectingDispatcher) -> Dict[str, Any]:
        dispatcher.utter_message(
            text=(
                "⚠️ I couldn't find a valid email address in your message.\n"
                "A valid email should be in the format: **username@domain.com**."
            ),
            buttons=[
                {"title": "Retry", "payload": "/provide_contact_email"},
                {"title": "Skip Email", "payload": "/skip_contact_email"},
            ]
        )
        return {"user_contact_email": None}

    def _email_handle_unknown_domain(self, dispatcher: CollectingDispatcher, email: str) -> Dict[str, Any]:
        email_domain = email.split('@')[1].lower()
        dispatcher.utter_message(
            text=(
                f"⚠️ The email domain '{email_domain}' is not recognized as a common Nepali email provider.\n"
                "Please confirm if this is correct or try again with a different email."
            ),
            buttons=[
                {"title": "Confirm Email", "payload": f"/confirm_email{{{email}}}"},
                {"title": "Try Different Email", "payload": "/provide_contact_email"},
                {"title": "Skip Email", "payload": "/skip_contact_email"},
            ]
        )
        return {"user_contact_email": None}

    # ✅ Validate user full name
    async def validate_user_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        print("################ Validate user full name ###################")

        if not slot_value:
            print("no slot value")
            return {}  

        # Validate Nepal phone number format (starts with 97 or 98 and is 10 digits long)
        if len(slot_value)<3:
            dispatcher.utter_message(
                text=(
                    "The full name you provided is not valid "
                )

            )
            return {}
        print("validated", slot_value)
        return {"user_full_name": slot_value}
    
    
    # ✅ Validate user contact phone
    async def validate_user_contact_phone(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        print("################ Validate user contact phone ###################")

        if not slot_value:
            print("no slot value")
            return {}  

        # Remove non-numeric characters
        cleaned_number = re.sub(r"\D", "", slot_value)

        # Validate Nepal phone number format (starts with 97 or 98 and is 10 digits long)
        
        # specific block for testing phase where we allow numbers from the Philippines
        if re.match(r"^(09|\+?639|00639)\d{9}$", cleaned_number):
            # Format the number to match our whitelist format (+63XXXXXXXXX)
            if cleaned_number.startswith('09'):
                formatted_number = '+63' + cleaned_number[1:]
            elif cleaned_number.startswith('63'):
                formatted_number = '+' + cleaned_number
            elif cleaned_number.startswith('0063'):
                formatted_number = '+' + cleaned_number[2:]
            else:
                formatted_number = cleaned_number

            dispatcher.utter_message(
                text="This phone number from the Philippines will be validated for testing only"
            )
            return {"user_contact_phone": formatted_number}
            
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
            return {}
        print("validated", cleaned_number)
        return {"user_contact_phone": cleaned_number}


    # ✅ Validate user contact email
    async def validate_user_contact_email(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        print("################ Validate user contact email ###################")

        if not slot_value:
            print("no slot value")

            return {}  

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
            return {}
        print("validated", slot_value)
        return {"user_contact_email": slot_value.strip().lower()}

class ActionCheckPhoneValidation(Action):
    def name(self) -> Text:
        return "action_check_phone_validation"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("user_contact_phone")
        
        if phone_number and phone_number != "Skipped":
            return [SlotSet("phone_validation_required", True)]
        else:
            return [SlotSet("phone_validation_required", False)]

class ActionRecommendPhoneValidation(Action):
    def name(self) -> Text:
        return "action_recommend_phone_validation"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text=(
                "Your grievance is filed without a validated number. Providing a valid number "
                "will help in the follow-up of the grievance and we recommend it. However, "
                "you can file the grievance as is."
            ),
            buttons=[
                {"title": "Give Phone Number", "payload": "/provide_phone_number"},
                {"title": "File Grievance as is", "payload": "/file_without_validation"}
            ]
        )
        return []

class PhoneValidationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_phone_validation_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        return ["user_contact_phone"]

    async def validate_user_contact_phone(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if re.match(r'^\+?63\d{10}$', slot_value):
            return {"user_contact_phone": slot_value}
        else:
            dispatcher.utter_message(text="Please enter a valid Philippine phone number.")
            return {"user_contact_phone": None}

class OTPService:
    def __init__(self):
        self.pinpoint_client = boto3.client('pinpoint', 
            region_name=os.getenv('AWS_REGION'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.application_id = os.getenv('PINPOINT_APPLICATION_ID')
        self.aws_retries = 3
        self.retry_delay = 5

    def send_otp_message(self, phone_number: str, otp: str) -> Tuple[bool, Optional[str]]:
        """Attempts to send OTP via AWS Pinpoint"""
        try:
            response = self.pinpoint_client.send_messages(
                ApplicationId=self.application_id,
                MessageRequest={
                    'Addresses': {
                        phone_number: {'ChannelType': 'SMS'}
                    },
                    'MessageConfiguration': {
                        'SMSMessage': {
                            'Body': f'Your verification code is {otp}. Please enter this code to verify your phone number.',
                            'MessageType': 'TRANSACTIONAL'
                        }
                    }
                }
            )
            
            message_response = response['MessageResponse']['Result'][phone_number]
            if message_response['DeliveryStatus'] == 'SUCCESSFUL':
                return True, None
            
            return False, message_response.get('StatusMessage', 'Unknown error')
            
        except Exception as e:
            return False, str(e)


class ActionInitiateOTPVerification(Action):
    def __init__(self):
        self.otp_service = OTPService()

    def name(self) -> Text:
        return "action_initiate_otp_verification"

    def _generate_otp(self) -> str:
        """Generates a 6-digit OTP"""
        return str(randint(100000, 999999))

    def _handle_success(self, dispatcher: CollectingDispatcher, user_resend_count: int) -> List[Dict]:
        """Handles successful OTP send"""
        resend_text = "" if user_resend_count >= 2 else "\n\nType 'resend' if you don't receive the code."
        dispatcher.utter_message(
            text=f"✅ A verification code has been sent to your phone number.\nPlease enter the 6-digit code to verify your number.{resend_text}"
        )
        return [
            SlotSet("otp", self._generate_otp()),
            SlotSet("otp_verified", False),
            SlotSet("resend_count", user_resend_count)
        ]

    def _handle_failure(self, dispatcher: CollectingDispatcher) -> List[Dict]:
        """Handles failed OTP send after retries"""
        dispatcher.utter_message(
            text=(
                "❌ We're having technical difficulties verifying this phone number.\n"
                "You can either:\n"
                "1. Try again with the same number\n"
                "2. Try a different phone number\n"
                "3. Skip phone verification"
            ),
            buttons=[
                {"title": "Try Again", "payload": "/retry_otp"},
                {"title": "Change Number", "payload": "/change_phone_number"},
                {"title": "Skip Verification", "payload": "/skip_otp_verification"}
            ]
        )
        return []

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("user_contact_phone")
        user_resend_count = tracker.get_slot("resend_count") or 0
        
        if not phone_number or phone_number == 'slot_skipped':
            return []

        otp = self._generate_otp()
        
        # Try sending OTP with retries
        for attempt in range(self.otp_service.aws_retries):
            success, error = self.otp_service.send_otp_message(phone_number, otp)
            
            if success:
                return self._handle_success(dispatcher, user_resend_count)
            
            logger.error(f"AWS Attempt {attempt + 1} failed: {error}")
            if attempt < self.otp_service.aws_retries - 1:
                time.sleep(self.otp_service.retry_delay)
        
        return self._handle_failure(dispatcher)


class ActionResendOTP(Action):
    def name(self) -> Text:
        return "action_resend_otp"

    def _handle_max_resends(self, dispatcher: CollectingDispatcher) -> List[Dict]:
        """Handles when max resend attempts reached"""
        dispatcher.utter_message(
            text=(
                "❌ We've tried sending the code 3 times but you haven't received it.\n"
                "This might mean there's an issue with the phone number.\n"
                "You can:\n"
                "1. Try a different phone number\n"
                "2. Skip phone verification"
            ),
            buttons=[
                {"title": "Change Number", "payload": "/change_phone_number"},
                {"title": "Skip Verification", "payload": "/skip_otp_verification"}
            ]
        )
        return []

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        resend_count = tracker.get_slot("resend_count") or 0
        
        if resend_count >= 2:
            return self._handle_max_resends(dispatcher)
        
        # Increment resend count before sending new OTP
        return await ActionInitiateOTPVerification().run(
            dispatcher, 
            tracker, 
            domain
        ) + [SlotSet("resend_count", resend_count + 1)]