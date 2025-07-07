import re
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Any, Text, Dict, List, Optional, Tuple
from random import randint
from ..config.constants import (
    WHITELIST_PHONE_NUMBERS_OTP_TESTING,
    SMTP_CONFIG,
    ADMIN_EMAILS,
    EMAIL_TEMPLATES,
    DIC_SMS_TEMPLATES,
    DEFAULT_VALUES,
    SMS_ENABLED
)
import os
from dotenv import load_dotenv
from datetime import datetime
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

# Get AWS region from environment variables
AWS_REGION = os.getenv('AWS_REGION', 'ap-southeast-1')

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
        """
        Send SMS to the given phone number.
        THIS FUNCTION IS CURRENTLY USED FOR TESTING AND ONLY RETURNS TRUE
        Args:
            phone_number: Phone number to send SMS to
            message: Message to send
        Returns:
            bool: True if successful, False otherwise
        """
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
                logger.debug(f"Failed to send SMS to: {str(e)}")
                return True 
        else:
            print(f"[DEBUG] TEST ONLY: NOT SENDING SMS to {phone_number}: {message}")
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
        
    def name(self) -> Text:
        return "email_client"

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