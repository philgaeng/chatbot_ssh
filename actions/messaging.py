import re
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Any, Text, Dict, List, Optional
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from actions.constants import (
    AWS_REGION,
    WHITELIST_PHONE_NUMBERS_OTP_TESTING,
    SMTP_CONFIG,
    ADMIN_EMAILS,
    EMAIL_TEMPLATES,
    SMS_TEMPLATES,
    DEFAULT_VALUES,
    GRIEVANCE_STATUS
)
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SNSClient:
    def __init__(self):
        try:
            # Initialize the SNS client
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

    def send_otp(self, phone_number: str, otp: str) -> bool:
        try:
            # Format phone number to E.164 format
            formatted_number = self._format_phone_number(phone_number)
            
            # Check if number is in whitelist during testing
            if formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
                logger.warning(f"Phone number {formatted_number} not in whitelist. SMS not sent.")
                return False

            message = f"Your verification code is {otp}. Please enter this code to verify your phone number."
            
            response = self.client.send_message(
                Content={
                    'MessageType': 'TRANSACTIONAL',
                    'Language': 'en',  # or your preferred language
                    'OriginationIdentity': {
                        'MessageType': 'TEXT',
                        'SenderId': 'YourSenderID'  # Configure this in AWS Console
                    },
                    'Body': message
                },
                DestinationIdentity={
                    'ChannelType': 'SMS',
                    'EndpointAddress': formatted_number
                },
                Configuration={
                    'ChannelType': 'SMS',
                    'MessageType': 'TRANSACTIONAL'
                }
            )
            
            # Check delivery status
            if response['MessageId']:
                logger.info(f"OTP sent successfully to {formatted_number}")
                return True
            else:
                logger.error("Failed to send OTP: No MessageId returned")
                return False
                
        except ClientError as e:
            logger.error(f"Failed to send OTP: {str(e)}")
            return False

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


class PinpointClient:
    def __init__(self):
        try:
            self.pinpoint_client = boto3.client('pinpoint', region_name=AWS_REGION)
            self.application_id = os.getenv('PINPOINT_APPLICATION_ID')
            logger.info("Successfully initialized Pinpoint client")
        except ClientError as e:
            logger.error(f"Failed to initialize Pinpoint client: {str(e)}")
            raise

    def send_otp(self, phone_number: str, otp: str) -> bool:
        try:
            formatted_number = self._format_phone_number(phone_number)
            
            if formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
                logger.warning(f"Phone number {formatted_number} not in whitelist. SMS not sent.")
                return False

            # Using the dedicated OTP message endpoint
            response = self.pinpoint_client.send_otp_message(
                ApplicationId=self.application_id,
                SendOTPMessageRequestParameters={
                    'Channel': 'SMS',
                    'BrandName': 'GrievanceOTP',
                    'CodeLength': 6,
                    'ValidityPeriod': 5,  # Minutes
                    'Language': 'en-US',
                    'OriginationIdentity': formatted_number,
                    'AllowedAttempts': 3,
                    'EntityId': 'grievance-system',
                    'ReferenceId': str(uuid.uuid4()),  # Unique reference for tracking
                    'TemplateParameters': {
                        'OTPCode': otp
                    }
                }
            )
            
            delivery_status = response['MessageResponse']['Result'][formatted_number]['DeliveryStatus']
            if delivery_status == 'SUCCESSFUL':
                logger.info(f"OTP sent successfully to {formatted_number}")
                
                # Update endpoint for better analytics
                self._update_endpoint(formatted_number)
                return True
            else:
                logger.error(f"Failed to send OTP: {delivery_status}")
                return False
                
        except ClientError as e:
            logger.error(f"Failed to send OTP: {str(e)}")
            return False

    def _update_endpoint(self, phone_number: str):
        try:
            self.pinpoint_client.update_endpoint(
                ApplicationId=self.application_id,
                EndpointId=phone_number,  # Using phone number as endpoint ID
                EndpointRequest={
                    'ChannelType': 'SMS',
                    'Address': phone_number,
                    'OptOut': 'NONE',
                    'Attributes': {
                        'Platform': ['Grievance_System'],
                        'User_Type': ['OTP_Verification']
                    },
                    'User': {
                        'UserAttributes': {
                            'LastOTPRequest': [datetime.now().isoformat()]
                        }
                    }
                }
            )
        except ClientError as e:
            logger.warning(f"Failed to update endpoint: {str(e)}")

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


class ActionInitiateOTPVerification(Action):
    def __init__(self):
        self.otp_manager = OTPManager()

    def name(self) -> Text:
        return "action_initiate_otp_verification"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("user_contact_phone")
        otp = self.otp_manager.generate_otp()
        message = self.otp_manager.create_otp_message(otp)

        # Debug prints for testing
        print("\n" + "="*50)
        print(f"🔐 Generated OTP for {phone_number}: {otp}")
        print(f"📱 SMS Message: {message}")
        print("="*50 + "\n")

        try:
            # Your SMS sending logic here (commented out for testing)
            # self.sns_client.send_sms(phone_number, message)
            
            logger.info(f"OTP generated for testing: {otp}")
            
            dispatcher.utter_message(
                text=(
                    f"A verification code has been sent to {phone_number}.\n"
                    "Please choose an option:"
                ),
                buttons=[
                    {"title": "Enter Code", "payload": "/enter_otp"},
                    {"title": "Resend Code", "payload": "/resend_otp"},
                    {"title": "Skip Verification", "payload": "/skip_otp_verification"}
                ]
            )
            return await self.otp_manager.store_otp(tracker, otp)
        except Exception as e:
            logger.error(f"Failed to send OTP: {e}")
            dispatcher.utter_message(
                text="Sorry, we couldn't send the verification code.",
                buttons=[
                    {"title": "Try Again", "payload": "/retry_otp"},
                    {"title": "Skip Verification", "payload": "/skip_otp_verification"}
                ]
            )
            return []

class ActionActivateOTPForm(Action):
    def name(self) -> Text:
        return "action_activate_otp_form"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="Please enter the verification code:\nType 000000 if you haven't received the code."
        )
        return [ActiveLoop("otp_verification_form")]

class ValidateOTPForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_otp_verification_form"

    async def validate_otp_input(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if slot_value == "000000":
            return {"otp_input": slot_value, "requested_slot": None}
        
        if len(slot_value) != 6 or not slot_value.isdigit():
            dispatcher.utter_message(text="Please enter a valid 6-digit code.")
            return {"otp_input": None}
        
        return {"otp_input": slot_value}

class ActionVerifyOTP(Action):
    def __init__(self):
        self.otp_manager = OTPManager()

    def name(self) -> Text:
        return "action_verify_otp"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_otp = tracker.get_slot("otp_input")
        
        if user_otp == "000000":
            dispatcher.utter_message(
                text="Would you like to try again?",
                buttons=[
                    {"title": "Resend Code", "payload": "/resend_otp"},
                    {"title": "Skip Verification", "payload": "/skip_otp_verification"}
                ]
            )
            return [SlotSet("otp_input", None)]
        
        if self.otp_manager.verify_otp(tracker, user_otp):
            dispatcher.utter_message(text="✅ Phone number verified successfully!")
            return [
                SlotSet("otp_verified", True),
                FollowupAction("action_send_grievance_sms")
            ]
        else:
            dispatcher.utter_message(
                text="❌ Invalid verification code.",
                buttons=[
                    {"title": "Try Again", "payload": "/enter_otp"},
                    {"title": "Resend Code", "payload": "/resend_otp"},
                    {"title": "Skip Verification", "payload": "/skip_otp_verification"}
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
            text="Continuing without phone verification. Your grievance details will not be sent via SMS."
        )
        return [SlotSet("otp_verified", False)]

class ActionSendGrievanceSMS(Action):
    def __init__(self):
        self.sns_client = SNSClient()

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

        if self.sns_client.send_sms(phone_number, message):
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
            "email": tracker.get_slot("user_email") or DEFAULT_VALUES["NOT_PROVIDED"],
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
            await send_email(
                to_email=SYSTEM_NOTIFICATION_EMAIL,
                subject=f"New Grievance Submission - ID: {grievance_data['grievance_id']} - Status: {grievance_data['grievance_status']}",
                body=body
            )
            return []
        except Exception as e:
            logger.error(f"Failed to send system notification email: {e}")
            return []