import re
import boto3
from botocore.exceptions import ClientError
from typing import Any, Text, Dict, List, Optional, Tuple
from random import randint
from backend.config.constants import (
    WHITELIST_PHONE_NUMBERS_OTP_TESTING,
    SMTP_CONFIG,
    ADMIN_EMAILS,
    EMAIL_TEMPLATES,
    DIC_SMS_TEMPLATES,
    DEFAULT_VALUES,
    SMS_ENABLED,
    AWS_REGION
)
from backend.logger.logger import TaskLogger
import os


class Messaging:
    """
    Main messaging class that provides functions called by Rasa Actions.
    Uses separate service classes for SMS and Email functionality.
    """
    
    def __init__(self):
        try:
            self.sms_client = SMSClient()
            self.email_client = EmailClient()
            self.task_logger = TaskLogger(service_name='messaging_service')
            self.logger = self.task_logger.logger
            self.log_event = self.task_logger.log_event
            self.logger.info("Successfully initialized Messaging repository")
        except Exception as e:
            # Create a basic logger for error reporting if the main one failed
            try:
                
                self.logger.error(f"Failed to initialize Messaging repository: {str(e)}")
            except:
                pass  # If even the error logger fails, just raise the original exception
            raise

    def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Send SMS to the given phone number.
        Args:
            phone_number: Phone number to send SMS to
            message: Message to send
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.sms_client.send_sms(phone_number, message)
        except Exception as e:
            self.logger.error(f"Failed to send SMS: {str(e)}")
            return False

    def send_email(self, to_emails: List[str], subject: str, body: str) -> bool:
        """
        Send email to the given email addresses.
        Args:
            to_emails: List of email addresses to send to
            subject: Email subject
            body: Email body (HTML)
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.email_client.send_email(to_emails, subject, body)
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False

    def test_sms_connection(self, test_phone_number: str) -> bool:
        """
        Test SMS sending functionality.
        Args:
            test_phone_number: Phone number to send test SMS to
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.sms_client.test_connection(test_phone_number)
        except Exception as e:
            self.logger.error(f"Failed to test SMS connection: {str(e)}")
            return False

    def format_phone_number(self, phone_number: str) -> str:
        """
        Format phone number to E.164 format.
        Args:
            phone_number: Phone number to format
        Returns:
            str: Formatted phone number
        """
        try:
            return self.sms_client._format_phone_number(phone_number)
        except Exception as e:
            self.logger.error(f"Failed to format phone number: {str(e)}")
            raise

class SMSClient:
    def __init__(self):
        self.task_logger = TaskLogger(service_name='messaging_service')
        self.logger = self.task_logger.logger
        self.log_event = self.task_logger.log_event
        try:
            # Initialize SNS (not Pinpoint) client
            self.sns_client = boto3.client('sns', region_name=AWS_REGION)
            self.logger.info("Successfully initialized SNS client")
        except ClientError as e:
            self.logger.error(f"Failed to initialize SNS client: {str(e)}")
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
            
            self.logger.info(f"Test SMS sent successfully to {test_phone_number}")
            return result
        except Exception as e:
            self.logger.error(f"Test SMS to {test_phone_number} failed with error: {str(e)}")
            return False

    def send_sms(self, phone_number: str, message: str):
        """
        Send SMS to the given phone number.
        THIS FUNCTION IS CURRENTLY USED FOR TESTING AND ONLY RETURNS TRUE
        Args:
            phone_number: Phone number to send SMS to
            message: Message to send
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if SMS_ENABLED:
                formatted_number = self._format_phone_number(phone_number)
                if formatted_number not in WHITELIST_PHONE_NUMBERS_OTP_TESTING:
                    self.logger.warning(f"Phone number {formatted_number} not in whitelist. SMS not sent.")
                    return False
                    
                self.logger.info(f"Sending SMS via SNS to whitelisted number: {formatted_number}")
                
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
                self.logger.info(f"SNS SMS sent successfully: {response['MessageId']}")
                return True
        except ClientError as e:
            self.logger.error(f"Failed to send SMS to: {str(e)}")
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

class EmailClient:
    def __init__(self):
        self.task_logger = TaskLogger(service_name='messaging_service')
        self.logger = self.task_logger.logger
        self.log_event = self.task_logger.log_event
        try:
            self.ses_client = boto3.client('ses',
                region_name=AWS_REGION,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            self.sender_email = os.getenv('SES_VERIFIED_EMAIL')
            self.logger.info(f"SES Configuration:")
            self.logger.info(f"Region: {AWS_REGION}")
            self.logger.info(f"Sender Email: {self.sender_email}")  # Check if this is None
            
            if not self.sender_email:
                raise ValueError("SES_VERIFIED_EMAIL not set in .env file")
                
            self.logger.info("Successfully initialized SES client")
        except Exception as e:
            self.logger.error(f"Failed to initialize SES client: {str(e)}")
            raise
        
    def name(self) -> Text:
        return "email_client"

    def send_email(self, to_emails: List[str], subject: str, body: str) -> bool:
        try:
            self.logger.info(f"Attempting to send email to: {to_emails}")
            self.logger.info(f"Using sender email: {self.sender_email}")
            
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
            
            self.logger.info(f"Email sent successfully! MessageId: {response['MessageId']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            self.logger.error(f"To: {to_emails}")
            self.logger.error(f"Subject: {subject}")
            self.logger.error(f"Body: {body[:100]}...")  # Log first 100 chars of body
            return False


messaging = Messaging()