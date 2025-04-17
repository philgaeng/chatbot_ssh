import os
import boto3
from dotenv import load_dotenv
import logging
from random import randint
import time
from typing import Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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
                            'MessageType': 'TRANSACTIONAL',
                            'SenderId': 'nepal-chat'  # Using your configured sender ID
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

def test_otp_send():
    """Test basic OTP sending"""
    service = OTPService()
    
    # Get test phone number
    phone_number = input("Enter phone number to test (e.g., +639XXXXXXXXX): ")
    
    # Test single send
    logger.info("\n🔄 Testing OTP send...")
    otp = str(randint(100000, 999999))
    success, error = service.send_otp_message(phone_number, otp)
    
    if success:
        logger.info("✅ OTP sent successfully!")
        logger.info(f"OTP sent: {otp}")
    else:
        logger.error(f"❌ Failed to send OTP: {error}")
    
    # Get verification from user
    received = input("\nDid you receive the OTP? (y/n): ")
    if received.lower() != 'y':
        logger.info("\n🔄 Testing resend...")
        new_otp = str(randint(100000, 999999))
        success, error = service.send_otp_message(phone_number, new_otp)
        if success:
            logger.info("✅ Second OTP sent successfully!")
            logger.info(f"New OTP sent: {new_otp}")
        else:
            logger.error(f"❌ Failed to send second OTP: {error}")

if __name__ == "__main__":
    test_otp_send()