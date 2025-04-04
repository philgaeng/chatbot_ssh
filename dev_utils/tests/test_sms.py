import logging
from actions.messaging import SNSClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_sms(test_number):
    logger.info(f"Initializing SNS client for test to number: {test_number}")
    client = SNSClient()
    
    logger.info("Sending test message...")
    result = client.test_connection(test_number)
    logger.info(f"Test result: {'Success' if result else 'Failed'}")

if __name__ == "__main__":
    test_number = "09175330841"  # Replace with your test number
    test_sms(test_number)