import boto3
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_pinpoint_connection():
    """Test basic connection to Pinpoint"""
    try:
        client = boto3.client('pinpoint',
            region_name=os.getenv('AWS_REGION'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        # Try to list applications
        response = client.get_apps()
        logger.info("✅ Successfully connected to Pinpoint")
        return True
    except Exception as e:
        logger.error(f"❌ Connection failed: {str(e)}")
        return False

def test_send_sms(phone_number: str):
    """Test sending a test SMS"""
    try:
        client = boto3.client('pinpoint',
            region_name=os.getenv('AWS_REGION'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        application_id = os.getenv('PINPOINT_APPLICATION_ID')
        
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
                        'Body': 'This is a test message from your Grievance System',
                        'MessageType': 'TRANSACTIONAL'
                    }
                }
            }
        )
        
        message_response = response['MessageResponse']['Result'][phone_number]
        if message_response['DeliveryStatus'] == 'SUCCESSFUL':
            logger.info(f"✅ Test SMS sent successfully to {phone_number}")
            logger.info(f"Message ID: {message_response['MessageId']}")
            return True
        else:
            logger.error(f"❌ Failed to send SMS: {message_response['StatusMessage']}")
            return False
            
    except Exception as e:
        logger.error(f"❌ SMS sending failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Test connection first
    if test_pinpoint_connection():
        # If connection successful, test SMS
        test_phone = input("Enter phone number to test (e.g., +639XXXXXXXXX): ")
        test_send_sms(test_phone)
    else:
        logger.error("Skipping SMS test due to connection failure")