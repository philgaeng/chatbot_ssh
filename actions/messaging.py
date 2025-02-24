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
from datetime import datetime
import json
import time
from rapidfuzz import process
from rasa_sdk.types import DomainDict

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

    def send_sms(self, phone_number: str, message: str):
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



class OTPSMSActions:
    """Base class for OTP and SMS related actions."""
    
    def __init__(self):
        self.sms_client = SMSClient()

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        print("\n=================== OTP Form Required Slots ===================")
        print(f"Current slots: {tracker.slots}")
        
        # Check if we need to initiate OTP verification
        if not tracker.get_slot("otp_number"):
            print("🔄 Initiating OTP verification")
            await self._initiate_otp_verification(dispatcher, tracker)
            return ["otp_input"]
        
        # If verification is complete, no more slots needed
        if tracker.get_slot("otp_verified") in [True, False]:
            print("✅ OTP verification completed - no more slots required")
            return []
            
        print("📝 Requiring OTP input slot")
        return ["otp_input"]

    async def validate_otp_input(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("\n=================== Validating OTP Input ===================")
        print(f"Received value: {slot_value}")
        
        # Handle empty input
        if not slot_value:
            return self._handle_empty_input(dispatcher)

        # Handle resend request
        if slot_value.lower() in ["/resend", "resend"]:
            print("🔄 Resend OTP requested")
            return self._handle_resend_otp(dispatcher, tracker)

        # Handle skip request
        if slot_value.lower() in ["/skip", "skip"]:
            print("⏩ Skip verification requested")
            return self._handle_skip_verification(dispatcher)

        # Validate OTP format
        if not self._is_valid_otp_format(slot_value):
            print(f"❌ Invalid OTP format: {slot_value}")
            return self._handle_invalid_format(dispatcher)

        # Handle test OTP
        if slot_value == "000000":
            print("🔑 Test OTP detected")
            return self._handle_test_otp(dispatcher)

        # Verify OTP match
        expected_otp = tracker.get_slot("otp_number")
        if self._is_matching_otp(slot_value, expected_otp):
            print("✅ OTP matched successfully")
            return self._handle_successful_verification(dispatcher, tracker)
        
        # Handle failed verification
        print("❌ OTP verification failed")
        return self._handle_failed_verification(dispatcher, tracker, slot_value)

    def _is_valid_otp_format(self, slot_value: str) -> bool:
        """Validate OTP format (6 digits)."""
        is_valid = bool(slot_value and slot_value.isdigit() and len(slot_value) == 6)
        print(f"OTP format validation: {is_valid} for value: {slot_value}")
        return is_valid

    def _is_matching_otp(self, input_otp: str, expected_otp: str) -> bool:
        """Verify if the input OTP matches the expected OTP."""
        is_matching = bool(input_otp and expected_otp and input_otp == expected_otp)
        print(f"OTP match validation: {is_matching} (Input: {input_otp}, Expected: {expected_otp})")
        return is_matching

    def _generate_and_send_otp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        is_resend: bool = False
    ) -> Dict[Text, Any]:
        """Generate OTP and send it via SMS."""
        print("\n=================== Generating and Sending OTP ===================")
        
        # Generate OTP
        otp = ''.join([str(randint(0, 9)) for _ in range(6)])
        phone_number = tracker.get_slot("user_contact_phone")
        
        print(f"🔑 Generated OTP: {otp}")
        print(f"📱 Target phone: {phone_number}")
        
        # Prepare message
        message = (
            f"Your {'new ' if is_resend else ''}verification code is {otp}. "
            "Please enter this code to verify your phone number."
        )
        
        # Send SMS
        if self.sms_client.send_sms(phone_number, message):
            print("✅ SMS sent successfully")
            
            # Prepare success message
            if is_resend:
                dispatcher.utter_message(
                    text="✅ A new verification code has been sent to your phone number."
                )
            else:
                dispatcher.utter_message(
                    text="✅ A verification code has been sent to your phone number.\n"
                         "Please enter the 6-digit code to verify your number.\n\n"
                         "Type 'resend' or '000000' if you don't receive the code.\n\n"
                         "Type 'skip' or '999999' if you don't want to verify your phone number."
                )
            
            # Calculate resend count
            current_resend_count = tracker.get_slot("otp_resend_count") or 0
            new_resend_count = current_resend_count + 1 if is_resend else 0
            
            return {
                "otp_number": otp,
                "otp_input": None,
                "otp_resend_count": new_resend_count,
                "otp_verified": None
            }
        else:
            print("❌ Failed to send SMS")
            dispatcher.utter_message(
                text="❌ Sorry, we couldn't send the verification code. Please try again."
            )
            return {"otp_input": None}

    async def _initiate_otp_verification(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker
    ) -> None:
        """Initialize OTP verification by generating and sending OTP."""
        print("\n=================== Initiating OTP Verification ===================")
        return self._generate_and_send_otp(dispatcher, tracker, is_resend=False)

    def _handle_empty_input(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle case when no input is provided."""
        print("🔄 Handling empty input - requesting OTP again")
        dispatcher.utter_message(text="Please enter the 6-digit verification code sent to your phone.")
        return {"otp_input": None}

    def _handle_invalid_format(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle case when input format is invalid."""
        print("🔄 Handling invalid format - requesting valid OTP")
        dispatcher.utter_message(text="Please enter a valid 6-digit code.")
        return {"otp_input": None}

    def _handle_test_otp(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle test OTP case."""
        print("✅ Processing test OTP verification")
        dispatcher.utter_message(text="✅ Phone number verified successfully (Test Mode)")
        return {
            "otp_input": "000000",
            "otp_verified": False
        }

    def _handle_skip_verification(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle case when user wants to skip verification."""
        print("⏩ Processing skip verification request")
        dispatcher.utter_message(
            text="Continuing without phone verification. Your grievance details will not be sent via SMS."
        )
        return {
            "otp_input": "skipped",
            "otp_verified": False
        }

    def _handle_successful_verification(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker
    ) -> Dict[Text, Any]:
        """Handle successful OTP verification."""
        print("✅ Processing successful verification")
        phone_number = tracker.get_slot("user_contact_phone")
        print(f"Phone number being verified: {phone_number}")
        
        dispatcher.utter_message(
            text=f"✅ Phone number verified successfully!\n"
                 f"Your phone number ({phone_number}) has been verified and saved."
        )
        result = {
            "otp_input": tracker.get_slot("otp_number"),
            "otp_verified": True
        }
        print(f"Returning slots: {result}")
        return result

    def _handle_failed_verification(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker,
        slot_value: str
    ) -> Dict[Text, Any]:
        """Handle failed OTP verification."""
        print("⚠️ Processing failed verification")
        resend_count = tracker.get_slot("otp_resend_count") or 0
        print(f"Current resend count: {resend_count}")
        
        if resend_count >= 3:
            print("❌ Maximum attempts reached")
            return self._handle_max_attempts_reached(dispatcher, slot_value)
            
        dispatcher.utter_message(
            text="❌ Invalid code. Please try again or type 'resend' to get a new code."
        )
        result = {
            "otp_input": None,
            "otp_resend_count": resend_count + 1
        }
        print(f"Returning slots: {result}")
        return result

    def _handle_max_attempts_reached(
        self, 
        dispatcher: CollectingDispatcher, 
        slot_value: str
    ) -> Dict[Text, Any]:
        """Handle case when maximum attempts are reached."""
        print("❌ Processing max attempts reached")
        dispatcher.utter_message(
            text="❌ Verification failed. Maximum attempts reached.\n"
                 "You will continue without phone verification.\n"
        )
        result = {
            "otp_input": slot_value,
            "otp_verified": False
        }
        print(f"Returning slots: {result}")
        return result

    def _handle_resend_otp(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker
    ) -> Dict[Text, Any]:
        """Handle OTP resend request."""
        print("\n=================== Processing OTP Resend ===================")
        
        resend_count = tracker.get_slot("otp_resend_count") or 0
        if resend_count >= 3:
            print("❌ Maximum resend attempts reached")
            dispatcher.utter_message(
                text="❌ Maximum resend attempts reached. Please try again later."
            )
            return {
                "otp_input": None,
                "otp_verified": False
            }
            
        return self._generate_and_send_otp(dispatcher, tracker, is_resend=True)





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

        if self.sms_client.send_sms(phone_number, message):
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
            logger.info(f"Attempting to send email to: {to_emails}")
            logger.info(f"Using sender email: {self.sender_email}")
            
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
                        'Html': {
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
            logger.error(f"To: {to_emails}")
            logger.error(f"Subject: {subject}")
            logger.error(f"Body: {body[:100]}...")  # Log first 100 chars of body
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
    def __init__(self):
        self.email_client = EmailClient()

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
            "municipality": tracker.get_slot("user_ municipality") or DEFAULT_VALUES["NOT_PROVIDED"],
            "village": tracker.get_slot("user_village") or DEFAULT_VALUES["NOT_PROVIDED"],
            "address": tracker.get_slot("user_address") or DEFAULT_VALUES["NOT_PROVIDED"],
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
                self.email_client.send_email(
                    to_emails=[admin_email],
                    subject=f"New Grievance Submission - ID: {grievance_data['grievance_id']} - Status: {grievance_data['grievance_status']}",
                    body=body
                )
            return []
        except Exception as e:
            logger.error(f"Failed to send system notification email: {e}")
            return []

# class ActionResendOTP(Action):
#     def __init__(self):
#         self.sms_client = SMSClient()

#     def name(self) -> Text:
#         return "action_resend_otp"

#     async def run(
#         self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         print("\n=================== ActionResendOTP ===================")
        
#         resend_count = tracker.get_slot("otp_resend_count") or 0
#         if resend_count >= 3:
#             dispatcher.utter_message(
#                 text="❌ Maximum resend attempts reached. Please try again later."
#             )
#             return []

#         # Generate new OTP
#         otp = ''.join([str(randint(0, 9)) for _ in range(6)])
#         phone_number = tracker.get_slot("user_contact_phone")
        
#         print(f"Resending OTP: {otp} to phone: {phone_number}")
        
#         message = f"Your new verification code is {otp}. Please enter this code to verify your phone number."
        
#         if self.sms_client.send_sms(phone_number, message):
#             dispatcher.utter_message(
#                 text="✅ A new verification code has been sent to your phone number."
#             )
#             return [
#                 SlotSet("otp_number", otp),
#                 SlotSet("otp_resend_count", resend_count + 1)
#             ]
#         else:
#             dispatcher.utter_message(
#                 text="❌ Sorry, we couldn't send the verification code. Please try again."
#             )
#             return []