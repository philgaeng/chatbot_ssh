import re
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Any, Text, Dict, List, Optional
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from actions.constants import WHITELIST_PHONE_NUMBERS_OTP_TESTING

logger = logging.getLogger(__name__)

class SNSClient:
    def __init__(self):
        try:
            # Initialize the SNS client
            self.sns_client = boto3.client('sns', region_name='ap-southeast-1')
            logger.info("Successfully initialized SNS client")
        except ClientError as e:
            logger.error(f"Failed to initialize SNS client: {str(e)}")
            raise

    def test_connection(self, test_phone_number: str) -> bool:
        """
        Test SMS sending functionality with a test message.
        Args:
            test_phone_number: Phone number to send test SMS to
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            test_message = "This is a test message from your chatbot."
            result = self.send_sms(test_phone_number, test_message)
            if result:
                logger.info(f"Test SMS sent successfully to {test_phone_number}")
            else:
                logger.error(f"Failed to send test SMS to {test_phone_number}")
            return result
        except Exception as e:
            logger.error(f"Test SMS failed with error: {str(e)}")
            return False

    def send_sms(self, phone_number: str, message: str) -> bool:
        try:
            # Format phone number to E.164 format
            formatted_number = self._format_phone_number(phone_number)
            
            # Check if number is in whitelist
            if formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
                logger.warning(f"Phone number {formatted_number} not in whitelist. SMS not sent.")
                return False
                
            logger.info(f"Sending SMS to whitelisted number: {formatted_number}")
            
            response = self.sns_client.publish(
                PhoneNumber=formatted_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            logger.info(f"SMS sent successfully: {response['MessageId']}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            return False

    def _format_phone_number(self, phone_number: str) -> str:
        # Remove any non-numeric characters except '+'
        cleaned_number = re.sub(r'[^\d+]', '', phone_number)
        
        # If already in E.164 format (+63XXXXXXXXX), return as is
        if re.match(r'^\+63\d{10}$', cleaned_number):  # Changed from \d{9} to \d{10}
            return cleaned_number
        
        # Handle different formats
        if cleaned_number.startswith('09'):
            formatted_number = '+63' + cleaned_number[1:]
        elif cleaned_number.startswith('63'):
            formatted_number = '+' + cleaned_number
        elif cleaned_number.startswith('0063'):
            formatted_number = '+' + cleaned_number[2:]
        else:
            raise ValueError(f"Invalid phone number format: {phone_number}")
        
        # Final validation
        if not re.match(r'^\+63\d{10}$', formatted_number):  # Changed from \d{9} to \d{10}
            raise ValueError(f"Invalid phone number format - final: {phone_number}, {formatted_number}")
            
        return formatted_number


class ActionInitiateOTPVerification(Action):
    def __init__(self):
        self.sns_client = SNSClient()

    def name(self) -> Text:
        return "action_initiate_otp_verification"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("user_contact_phone")
        
        if not phone_number or phone_number == 'slot_skipped':
            return []

        # Generate OTP
        otp = randint(100000, 999999)
        
        # Prepare message
        message = f"Your verification code is {otp}. Please enter this code to verify your phone number."
        
        # Send OTP via SNS
        if self.sns_client.send_sms(phone_number, message):
            dispatcher.utter_message(
                text=(
                    "✅ A verification code has been sent to your phone number.\n"
                    "Please enter the 6-digit code to verify your number."
                )
            )
            
            return [
                SlotSet("otp", str(otp)),
                SlotSet("otp_verified", False)
            ]
        else:
            dispatcher.utter_message(
                text=(
                    "❌ Sorry, we couldn't send the verification code.\n"
                    "Would you like to continue without phone verification?"
                ),
                buttons=[
                    {"title": "Try Again", "payload": "/retry_otp"},
                    {"title": "Continue Without Verification", "payload": "/skip_otp_verification"}
                ]
            )
            return []


class ActionVerifyOTP(Action):
    def name(self) -> Text:
        return "action_verify_otp"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_otp = tracker.latest_message.get("text", "").strip()
        stored_otp = tracker.get_slot("otp")
        
        if not stored_otp:
            return [FollowupAction("action_initiate_otp_verification")]
        
        if user_otp == stored_otp:
            dispatcher.utter_message(text="✅ Phone number verified successfully!")
            return [
                SlotSet("otp_verified", True),
                FollowupAction("contact_form")
            ]
        else:
            dispatcher.utter_message(
                text=(
                    "❌ Invalid verification code.\n"
                    "Please try again or continue without verification."
                ),
                buttons=[
                    {"title": "Try Again", "payload": "/retry_otp"},
                    {"title": "Continue Without Verification", "payload": "/skip_otp_verification"}
                ]
            )
            return [SlotSet("otp_verified", False)]


class ActionSkipOTPVerification(Action):
    def name(self) -> Text:
        return "action_skip_otp_verification"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="Continuing without phone verification."
        )
        return [
            SlotSet("otp_verified", False),
            FollowupAction("contact_form")
        ]
