import boto3
import os
from dotenv import load_dotenv
import logging
import time
from datetime import datetime
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class OTPTester:
    def __init__(self):
        self.client = boto3.client('pinpoint',
            region_name=os.getenv('AWS_REGION'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.application_id = os.getenv('PINPOINT_APPLICATION_ID')

    def test_rapid_requests(self, phone_number: str):
        """Test cooldown period by sending multiple requests quickly"""
        logger.info("\n🔄 Testing rapid OTP requests...")
        
        for i in range(4):  # Try 4 times
            logger.info(f"\nAttempt {i+1}:")
            self.send_otp(phone_number)
            time.sleep(10)  # Wait 10 seconds between attempts

    def test_expiration(self, phone_number: str):
        """Test OTP expiration"""
        logger.info("\n⏲️ Testing OTP expiration...")
        
        # Send OTP
        otp = self.send_otp(phone_number)
        if otp:
            logger.info("Waiting 30 seconds before verification...")
            time.sleep(30)
            
            # Get user input
            user_input = input("Enter the OTP you received: ")
            if user_input == otp:
                logger.info("✅ OTP verified successfully!")
            else:
                logger.error("❌ Invalid OTP entered")

    def send_otp(self, phone_number: str) -> Optional[str]:
        """Send an OTP and return it if successful"""
        try:
            otp = str(randint(100000, 999999))
            
            response = self.client.send_messages(
                ApplicationId=self.application_id,
                MessageRequest={
                    'Addresses': {
                        phone_number: {
                            'ChannelType': 'SMS'
                        }
                    },
                    'MessageConfiguration': {
                        'SMSMessage': {
                            'Body': f'Your verification code is {otp}. Valid for 5 minutes.',
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
                logger.error(f"❌ Failed to send OTP: {message_response.get('StatusMessage')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error sending OTP: {str(e)}")
            return None

def run_tests():
    tester = OTPTester()
    phone_number = input("Enter phone number to test (e.g., +639XXXXXXXXX): ")
    
    while True:
        print("\n🧪 Choose a test to run:")
        print("1. Test rapid requests (cooldown period)")
        print("2. Test OTP expiration")
        print("3. Test both")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == "1":
            tester.test_rapid_requests(phone_number)
        elif choice == "2":
            tester.test_expiration(phone_number)
        elif choice == "3":
            tester.test_rapid_requests(phone_number)
            tester.test_expiration(phone_number)
        elif choice == "4":
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    from random import randint
    run_tests()