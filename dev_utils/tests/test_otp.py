import boto3
import os
from dotenv import load_dotenv
import logging
from random import randint

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_send_otp(phone_number: str):
    """Test sending an OTP"""
    try:
        client = boto3.client('pinpoint',
            region_name=os.getenv('AWS_REGION'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        application_id = os.getenv('PINPOINT_APPLICATION_ID')
        otp = str(randint(100000, 999999))
        
        response = client.send_messages(
            ApplicationId=application_id,
            MessageRequest={
                'Addresses': {
                    phone_number: {
                        'ChannelType': 'SMS'
                    }
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
            logger.info(f"✅ OTP sent successfully to {phone_number}")
            logger.info(f"Message ID: {message_response['MessageId']}")
            return otp
        else:
            logger.error(f"❌ Failed to send OTP: {message_response['StatusMessage']}")
            return None
            
    except Exception as e:
        logger.error(f"❌ OTP sending failed: {str(e)}")
        return None

def verify_otp(sent_otp: str, user_input: str) -> bool:
    """Verify the OTP entered by user"""
    return sent_otp == user_input

if __name__ == "__main__":
    test_phone = input("Enter phone number to test (e.g., +639XXXXXXXXX): ")
    
    # Send OTP
    sent_otp = test_send_otp(test_phone)
    if sent_otp:
        # Get user input for verification
        user_otp = input("Enter the OTP you received: ")
        
        # Verify OTP
        if verify_otp(sent_otp, user_otp):
            logger.info("✅ OTP verified successfully!")
        else:
            logger.error("❌ Invalid OTP entered")