import re
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Any, Text, Dict, List, Optional, Tuple
from random import randint
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction, ActiveLoop
from actions.constants import (
    AWS_REGION,
    WHITELIST_PHONE_NUMBERS_OTP_TESTING,
    SMTP_CONFIG,
    ADMIN_EMAILS,
    EMAIL_TEMPLATES,
    SMS_TEMPLATES,
    DEFAULT_VALUES,
    GRIEVANCE_STATUS,
    SMS_ENABLED
)
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime
import json
import time

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()  # This ensures output to terminal
    ]
)
logger = logging.getLogger(__name__)

# Disable other loggers' debug messages to reduce noise
logging.getLogger('boto3').setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('rasa_sdk').setLevel(logging.INFO)

# Load environment variables
load_dotenv()

class SMSClient:
    def __init__(self):
        try:
            # Initialize SNS (not Pinpoint) client
            self.sns_client = boto3.client('sns', region_name=AWS_REGION)
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

    async def send_sms(self, phone_number: str, message: str):
        if SMS_ENABLED:
            try:
                # Using SNS publish (not Pinpoint send_messages)
                formatted_number = self._format_phone_number(phone_number)
                
                if formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
                    logger.warning(f"Phone number {formatted_number} not in whitelist. SMS not sent.")
                    return False
                    
                logger.info(f"Sending SMS via SNS to whitelisted number: {formatted_number}")
                
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
                logger.info(f"SNS SMS sent successfully: {response['MessageId']}")
                return True
                
            except ClientError as e:
                logger.error(f"Failed to send SMS: {str(e)}")
                return False
        else:
            print(f"[DEBUG] SMS to {phone_number}: {message}")
            return True

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


class CommunicationClient:
    def __init__(self):
        try:
            # Initialize the client with the new service name
            self.client = boto3.client(
                'communication-messages', 
                region_name=AWS_REGION
            )
            logger.info("Successfully initialized Communication Messages client")
        except ClientError as e:
            logger.error(f"Failed to initialize Communication Messages client: {str(e)}")
            raise

    def _format_phone_number(self, phone_number: str) -> str:
        # Your existing phone number formatting logic
        cleaned_number = re.sub(r'[^\d+]', '', phone_number)
        
        if re.match(r'^\+63\d{10}$', cleaned_number):
            return cleaned_number
        
        if cleaned_number.startswith('09'):
            formatted_number = '+63' + cleaned_number[1:]
        elif cleaned_number.startswith('63'):
            formatted_number = '+' + cleaned_number
        elif cleaned_number.startswith('0063'):
            formatted_number = '+' + cleaned_number[2:]
        else:
            raise ValueError(f"Invalid phone number format: {phone_number}")
        
        if not re.match(r'^\+63\d{10}$', formatted_number):
            raise ValueError(f"Invalid phone number format after formatting: {formatted_number}")
            
        return formatted_number


# class PinpointClient:
#     def __init__(self):
#         try:
#             self.pinpoint_client = boto3.client('pinpoint', region_name=AWS_REGION)
#             self.application_id = os.getenv('PINPOINT_APPLICATION_ID')
#             logger.info("Successfully initialized Pinpoint client")
#         except ClientError as e:
#             logger.error(f"Failed to initialize Pinpoint client: {str(e)}")
#             raise

#     def send_otp(self, phone_number: str, otp: str) -> bool:
#         try:
#             formatted_number = self._format_phone_number(phone_number)
            
#             if formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
#                 logger.warning(f"Phone number {formatted_number} not in whitelist. SMS not sent.")
#                 return False

#             # Using the dedicated OTP message endpoint
#             response = self.pinpoint_client.send_otp_message(
#                 ApplicationId=self.application_id,
#                 SendOTPMessageRequestParameters={
#                     'Channel': 'SMS',
#                     'BrandName': 'GrievanceOTP',
#                     'CodeLength': 6,
#                     'ValidityPeriod': 5,  # Minutes
#                     'Language': 'en-US',
#                     'OriginationIdentity': formatted_number,
#                     'AllowedAttempts': 3,
#                     'EntityId': 'grievance-system',
#                     'ReferenceId': str(uuid.uuid4()),  # Unique reference for tracking
#                     'TemplateParameters': {
#                         'OTPCode': otp
#                     }
#                 }
#             )
            
#             delivery_status = response['MessageResponse']['Result'][formatted_number]['DeliveryStatus']
#             if delivery_status == 'SUCCESSFUL':
#                 logger.info(f"OTP sent successfully to {formatted_number}")
                
#                 # Update endpoint for better analytics
#                 self._update_endpoint(formatted_number)
#                 return True
#             else:
#                 logger.error(f"Failed to send OTP: {delivery_status}")
#                 return False
                
#         except ClientError as e:
#             logger.error(f"Failed to send OTP: {str(e)}")
#             return False

#     def _update_endpoint(self, phone_number: str):
#         try:
#             self.pinpoint_client.update_endpoint(
#                 ApplicationId=self.application_id,
#                 EndpointId=phone_number,  # Using phone number as endpoint ID
#                 EndpointRequest={
#                     'ChannelType': 'SMS',
#                     'Address': phone_number,
#                     'OptOut': 'NONE',
#                     'Attributes': {
#                         'Platform': ['Grievance_System'],
#                         'User_Type': ['OTP_Verification']
#                     },
#                     'User': {
#                         'UserAttributes': {
#                             'LastOTPRequest': [datetime.now().isoformat()]
#                         }
#                     }
#                 }
#             )
#         except ClientError as e:
#             logger.warning(f"Failed to update endpoint: {str(e)}")

#     def _format_phone_number(self, phone_number: str) -> str:
#         # Your existing phone number formatting logic
#         cleaned_number = re.sub(r'[^\d+]', '', phone_number)
        
#         if re.match(r'^\+63\d{10}$', cleaned_number):
#             return cleaned_number
        
#         if cleaned_number.startswith('09'):
#             formatted_number = '+63' + cleaned_number[1:]
#         elif cleaned_number.startswith('63'):
#             formatted_number = '+' + cleaned_number
#         elif cleaned_number.startswith('0063'):
#             formatted_number = '+' + cleaned_number[2:]
#         else:
#             raise ValueError(f"Invalid phone number format: {phone_number}")
        
#         if not re.match(r'^\+63\d{10}$', formatted_number):
#             raise ValueError(f"Invalid phone number format after formatting: {formatted_number}")
            
#         return formatted_number


# class OTPService:
#     def __init__(self):
#         self.pinpoint_client = boto3.client('pinpoint', 
#             region_name=os.getenv('AWS_REGION'),
#             aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
#             aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
#         )
#         self.application_id = os.getenv('PINPOINT_APPLICATION_ID')
#         self.aws_retries = 3
#         self.retry_delay = 5

#     def send_otp_message(self, phone_number: str, otp: str) -> Tuple[bool, Optional[str]]:
#         """Attempts to send OTP via AWS Pinpoint"""
#         try:
#             response = self.pinpoint_client.send_messages(
#                 ApplicationId=self.application_id,
#                 MessageRequest={
#                     'Addresses': {
#                         phone_number: {'ChannelType': 'SMS'}
#                     },
#                     'MessageConfiguration': {
#                         'SMSMessage': {
#                             'Body': f'Your verification code is {otp}. Please enter this code to verify your phone number.',
#                             'MessageType': 'TRANSACTIONAL'
#                         }
#                     }
#                 }
#             )
            
#             message_response = response['MessageResponse']['Result'][phone_number]
#             if message_response['DeliveryStatus'] == 'SUCCESSFUL':
#                 return True, None
            
#             return False, message_response.get('StatusMessage', 'Unknown error')
            
#         except Exception as e:
#             return False, str(e)

class ActionInitiateOTPVerification(Action):
    def __init__(self):
        self.sms_client = SMSClient()

    def name(self) -> Text:
        return "action_initiate_otp_verification"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        print("\n=================== ActionInitiateOTPVerification ===================")
        
        otp = ''.join([str(randint(0, 9)) for _ in range(6)])
        phone_number = tracker.get_slot("user_contact_phone")
        
        print(f"Generated OTP: {otp} for phone: {phone_number}")
        
        message = f"Your verification code is {otp}. Please enter this code to verify your phone number."
        
        if await self.sms_client.send_sms(phone_number, message):
            print(f"Setting otp_number slot to: {otp}")
            dispatcher.utter_message(
                text="✅ A verification code has been sent to your phone number.\n"
                     "Please enter the 6-digit code to verify your number.\n\n"
                     "Type 'resend' if you don't receive the code."
            )
            return [
                ActiveLoop(None),
                SlotSet("otp_number", otp),
                SlotSet("otp_verified", False),
                SlotSet("otp_resend_count", 0),
                ActiveLoop("otp_verification_form")
            ]
        else:
            dispatcher.utter_message(
                text="❌ Sorry, we couldn't send the verification code. Please try again."
            )
            return []

class ActionActivateOTPForm(Action):
    def name(self) -> Text:
        return "action_activate_otp_form"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        return [
            SlotSet("requested_slot", "otp_input"),  # Explicitly set the requested slot
            ActiveLoop("otp_verification_form")
        ]

class OTPVerificationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_otp_verification_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        print("\n=================== OTP Form Required Slots ===================")
        print("Required slots: ['otp_input']")
        logger.debug("Required slots: ['otp_input']")
        return ["otp_input"]

    async def validate_otp_input(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("\n=================== Validating OTP Input ===================")
        print(f"Received value: {slot_value}")
        print(f"""Expected OTP: {tracker.get_slot("otp_number")}""")
        print(f"Active loop: {tracker.active_loop}")
        print(f"Current slots: {tracker.slots}")
        logger.debug(f"Received value: {slot_value}")
        logger.debug(f"""Expected OTP: {tracker.get_slot("otp_number")}""")
        logger.debug(f"Active loop: {tracker.active_loop}")
        logger.debug(f"Current slots: {tracker.slots}")

        # Skip validation for test OTP
        if self._is_test_otp(slot_value):
            print("Test OTP detected - bypassing validation")
            logger.debug("Test OTP detected - bypassing validation")
            return self._handle_test_otp(slot_value)

        # Validate OTP format
        if not self._is_valid_otp_format(slot_value):
            print(f"Invalid OTP format: {slot_value}")
            logger.debug(f"Invalid OTP format: {slot_value}")
            dispatcher.utter_message(text="Please enter a valid 6-digit code.")
            return {"otp_input": None}

        # Validate OTP match
        expected_otp = tracker.get_slot("otp_number")
        if self._is_matching_otp(slot_value, expected_otp):
            print("OTP matched successfully")
            logger.debug("OTP matched successfully")
            return self._handle_successful_verification(slot_value)
        else:
            print("OTP mismatch")
            logger.debug("OTP mismatch")
            return self._handle_failed_verification(tracker, dispatcher)

    def _is_test_otp(self, slot_value: str) -> bool:
        """Check if the OTP is the test bypass code."""
        return slot_value == "000000"

    def _is_valid_otp_format(self, slot_value: str) -> bool:
        """Validate OTP format (6 digits)."""
        return bool(slot_value and slot_value.isdigit() and len(slot_value) == 6)

    def _is_matching_otp(self, slot_value: str, expected_otp: str) -> bool:
        """Check if provided OTP matches expected OTP."""
        return bool(expected_otp and slot_value == expected_otp)

    def _handle_test_otp(self, slot_value: str) -> Dict[str, Any]:
        """Handle test OTP case."""
        return {
            "otp_input": slot_value,
            "otp_verified": True,
            "requested_slot": None
        }

    def _handle_successful_verification(self, slot_value: str) -> Dict[str, Any]:
        """Handle successful OTP verification."""
        print("Handling successful verification")
        logger.debug("Handling successful verification")
        return {
            "otp_input": slot_value,
            "otp_verified": True,
            "requested_slot": None
        }

    def _handle_failed_verification(
        self, tracker: Tracker, dispatcher: CollectingDispatcher
    ) -> Dict[str, Any]:
        """Handle failed OTP verification."""
        resend_count = tracker.get_slot("otp_resend_count") or 0
        print(f"Handling failed verification. Resend count: {resend_count}")
        logger.debug(f"Handling failed verification. Resend count: {resend_count}")

        if resend_count >= 3:
            print("Max resend attempts reached")
            logger.debug("Max resend attempts reached")
            dispatcher.utter_message(
                text="You've made too many incorrect attempts. Please try again later."
            )
            return {"otp_input": None, "requested_slot": None}

        dispatcher.utter_message(
            text="❌ Invalid code. Please try again or type 'resend' to get a new code."
        )
        return {"otp_input": None}

class ActionVerifyOTP(Action):
    def name(self) -> Text:
        return "action_verify_otp"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        print("\n=================== ActionVerifyOTP ===================")
        logger.debug("Starting OTP Verification Action")
        
        print(f"Active loop: {tracker.active_loop}")
        print(f"Current slots: {tracker.slots}")
        logger.debug(f"Active loop: {tracker.active_loop}")
        logger.debug(f"Current slots: {tracker.slots}")

        # Get relevant slots
        input_otp = tracker.get_slot("otp_input")
        expected_otp = tracker.get_slot("otp_number")
        phone_number = tracker.get_slot("user_contact_phone")

        print(f"Input OTP: {input_otp}")
        print(f"Expected OTP: {expected_otp}")
        print(f"Phone number: {phone_number}")
        logger.debug(f"Input OTP: {input_otp}")
        logger.debug(f"Expected OTP: {expected_otp}")
        logger.debug(f"Phone number: {phone_number}")

        # Handle test OTP case
        if self._is_test_otp(input_otp):
            print("Test OTP detected - automatic verification")
            logger.debug("Test OTP detected - automatic verification")
            return self._handle_test_verification(dispatcher)

        # Verify OTP match
        if self._is_valid_verification(input_otp, expected_otp):
            print("OTP verification successful")
            logger.debug("OTP verification successful")
            return self._handle_successful_verification(dispatcher, phone_number)
        else:
            print("OTP verification failed")
            logger.debug("OTP verification failed")
            return self._handle_failed_verification(dispatcher, tracker)

    def _is_test_otp(self, input_otp: str) -> bool:
        """Check if the input is the test bypass code."""
        return input_otp == "000000"

    def _is_valid_verification(self, input_otp: str, expected_otp: str) -> bool:
        """Verify if the input OTP matches the expected OTP."""
        return bool(input_otp and expected_otp and input_otp == expected_otp)

    def _handle_test_verification(
        self, dispatcher: CollectingDispatcher
    ) -> List[Dict[Text, Any]]:
        """Handle verification for test OTP."""
        print("Processing test verification")
        logger.debug("Processing test verification")
        dispatcher.utter_message(text="✅ Phone number verified successfully (Test Mode)")
        return [
            SlotSet("otp_verified", True),
            ActiveLoop(None),
            SlotSet("requested_slot", None)
        ]

    def _handle_successful_verification(
        self, dispatcher: CollectingDispatcher, phone_number: str
    ) -> List[Dict[Text, Any]]:
        """Handle successful OTP verification."""
        print("Processing successful verification")
        logger.debug("Processing successful verification")
        
        success_message = (
            "✅ Phone number verified successfully!\n"
            f"Your phone number ({phone_number}) has been verified and saved."
        )
        dispatcher.utter_message(text=success_message)
        
        return [
            SlotSet("otp_verified", True),
            ActiveLoop(None),
            SlotSet("requested_slot", None)
        ]

    def _handle_failed_verification(
        self, dispatcher: CollectingDispatcher, tracker: Tracker
    ) -> List[Dict[Text, Any]]:
        """Handle failed OTP verification."""
        print("Processing failed verification")
        logger.debug("Processing failed verification")
        
        resend_count = tracker.get_slot("otp_resend_count") or 0
        print(f"Current resend count: {resend_count}")
        logger.debug(f"Current resend count: {resend_count}")

        if resend_count >= 3:
            print("Max resend attempts reached")
            logger.debug("Max resend attempts reached")
            dispatcher.utter_message(
                text=(
                    "❌ Verification failed. Maximum attempts reached.\n"
                    "Please try again later or contact support."
                )
            )
            return [
                SlotSet("otp_verified", False),
                ActiveLoop(None),
                SlotSet("requested_slot", None)
            ]

        dispatcher.utter_message(
            text=(
                "❌ Verification failed. Please try again.\n"
                "Type 'resend' to get a new code."
            )
        )
        
        return [
            SlotSet("otp_verified", False),
            SlotSet("otp_resend_count", resend_count + 1)
        ]


class ActionSkipOTPVerification(Action):
    def name(self) -> Text:
        return "action_skip_otp_verification"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="Continuing without phone verification. Your grievance details will not be sent via SMS."
        )
        return [SlotSet("otp_verified", False)]

class ActionSendGrievanceSMS(Action):
    def __init__(self):
        self.sms_client = SMSClient()

    def name(self) -> Text:
        return "action_send_grievance_sms"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        if not tracker.get_slot("otp_verified"):
            return []

        phone_number = tracker.get_slot("user_contact_phone")
        grievance_id = tracker.get_slot("grievance_id")  # Assuming you have this
        # Get other relevant grievance details from slots

        message = (
            f"Thank you for submitting your grievance (ID: {grievance_id}).\n"
            "We have received your complaint and will process it accordingly.\n"
            "You will receive updates about your grievance through this number."
        )

        if await self.sms_client.send_sms(phone_number, message):
            dispatcher.utter_message(
                text="✅ Your grievance details have been sent to your phone number."
            )
        else:
            dispatcher.utter_message(
                text="❌ Sorry, we couldn't send the grievance details to your phone number."
            )

        return []

class EmailClient:
    def __init__(self):
        try:
            self.ses_client = boto3.client('ses',
                region_name=os.getenv('AWS_REGION'),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            self.sender_email = os.getenv('SES_VERIFIED_EMAIL')
            logger.info(f"SES Configuration:")
            logger.info(f"Region: {os.getenv('AWS_REGION')}")
            logger.info(f"Sender Email: {self.sender_email}")  # Check if this is None
            
            if not self.sender_email:
                raise ValueError("SES_VERIFIED_EMAIL not set in .env file")
                
            logger.info("Successfully initialized SES client")
        except Exception as e:
            logger.error(f"Failed to initialize SES client: {str(e)}")
            raise

    def send_email(self, to_emails: List[str], subject: str, body: str) -> bool:
        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={
                    'ToAddresses': to_emails
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {  # Changed from Text to Html
                            'Data': body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            
            logger.info(f"Email sent successfully! MessageId: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

class ActionSendGrievanceRecapEmail(Action):
    def __init__(self):
        self.email_client = EmailClient()

    def name(self) -> Text:
        return "action_send_grievance_recap_email"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_email = tracker.get_slot("user_contact_email")
        to_emails = ADMIN_EMAILS.copy()
        
        if user_email and user_email != "slot_skipped":
            to_emails.append(user_email)

        # Get grievance details
        grievance_id = tracker.get_slot("grievance_id")
        grievance_details = tracker.get_slot("grievance_details")
        grievance_summary = tracker.get_slot("grievance_summary")
        categories = tracker.get_slot("list_of_cat_for_summary")
        municipality = tracker.get_slot("municipality") or DEFAULT_VALUES["NOT_PROVIDED"]
        village = tracker.get_slot("village") or DEFAULT_VALUES["NOT_PROVIDED"]
        address = tracker.get_slot("address") or DEFAULT_VALUES["NOT_PROVIDED"]
        user_name = tracker.get_slot("user_full_name") or DEFAULT_VALUES["ANONYMOUS"]
        phone = tracker.get_slot("user_contact_phone") or DEFAULT_VALUES["NOT_PROVIDED"]
        email = user_email or DEFAULT_VALUES["NOT_PROVIDED"]

        categories_html = ''.join(f'<li>{category}</li>' for category in (categories or []))

        # Create email body using template
        body = EMAIL_TEMPLATES["GRIEVANCE_RECAP_BODY"].format(
            grievance_id=grievance_id,
            user_name=user_name,
            grievance_details=grievance_details,
            grievance_summary=grievance_summary,
            categories_html=categories_html,
            municipality=municipality,
            village=village,
            address=address,
            phone=phone,
            email=email
        )

        subject = EMAIL_TEMPLATES["GRIEVANCE_RECAP_SUBJECT"].format(
            grievance_id=grievance_id
        )

        if self.email_client.send_email(to_emails, subject, body):
            if user_email and user_email != "slot_skipped":
                dispatcher.utter_message(
                    text="✅ A recap of your grievance has been sent to your email."
                )
        else:
            dispatcher.utter_message(
                text="❌ There was an issue sending the recap email. Please contact support if needed."
            )

        return []

class ActionSendSystemNotificationEmail(Action):
    def name(self) -> Text:
        return "action_send_system_notification_email"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        # Get all relevant slots
        grievance_data = {
            "grievance_id": tracker.get_slot("grievance_id"),
            "grievance_status": GRIEVANCE_STATUS["SUBMITTED"],  # Explicitly set status for new submissions
            "grievance_details": tracker.get_slot("grievance_details"),
            "grievance_summary": tracker.get_slot("grievance_summary"),
            "categories": tracker.get_slot("list_of_cat_for_summary"),
            "municipality": tracker.get_slot("municipality") or DEFAULT_VALUES["NOT_PROVIDED"],
            "village": tracker.get_slot("village") or DEFAULT_VALUES["NOT_PROVIDED"],
            "address": tracker.get_slot("address") or DEFAULT_VALUES["NOT_PROVIDED"],
            "user_name": tracker.get_slot("user_full_name") or DEFAULT_VALUES["ANONYMOUS"],
            "phone": tracker.get_slot("user_contact_phone") or DEFAULT_VALUES["NOT_PROVIDED"],
            "email": tracker.get_slot("user_contact_email") or DEFAULT_VALUES["NOT_PROVIDED"],
            "timestamp": datetime.now().isoformat(),
            "submission_type": "new_grievance"  # Adding a type identifier
        }

        # Convert to JSON string with proper formatting
        json_data = json.dumps(grievance_data, indent=2, ensure_ascii=False)

        # Create email body using system notification template
        body = EMAIL_TEMPLATES["SYSTEM_NOTIFICATION_BODY"].format(
            json_data=json_data,
            grievance_status=GRIEVANCE_STATUS["SUBMITTED"]  # Also include in email template
        )

        try:
            for admin_email in ADMIN_EMAILS:
                await self.email_client.send_email(
                    to_email=admin_email,
                    subject=f"New Grievance Submission - ID: {grievance_data['grievance_id']} - Status: {grievance_data['grievance_status']}",
                    body=body
                )
            return []
        except Exception as e:
            logger.error(f"Failed to send system notification email: {e}")
            return []

class ActionResendOTP(Action):
    def __init__(self):
        self.sms_client = SMSClient()

    def name(self) -> Text:
        return "action_resend_otp"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        print("\n=================== ActionResendOTP ===================")
        
        resend_count = tracker.get_slot("otp_resend_count") or 0
        if resend_count >= 3:
            dispatcher.utter_message(
                text="❌ Maximum resend attempts reached. Please try again later."
            )
            return []

        # Generate new OTP
        otp = ''.join([str(randint(0, 9)) for _ in range(6)])
        phone_number = tracker.get_slot("user_contact_phone")
        
        print(f"Resending OTP: {otp} to phone: {phone_number}")
        
        message = f"Your new verification code is {otp}. Please enter this code to verify your phone number."
        
        if await self.sms_client.send_sms(phone_number, message):
            dispatcher.utter_message(
                text="✅ A new verification code has been sent to your phone number."
            )
            return [
                SlotSet("otp_number", otp),
                SlotSet("otp_resend_count", resend_count + 1)
            ]
        else:
            dispatcher.utter_message(
                text="❌ Sorry, we couldn't send the verification code. Please try again."
            )
            return []