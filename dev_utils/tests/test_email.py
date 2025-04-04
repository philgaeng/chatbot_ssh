import os
import sys
import logging
from dotenv import load_dotenv
from datetime import datetime
import uuid

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def verify_env_variables():
    """Verify all required environment variables are set"""
    from actions.constants import AWS_REGION, SMTP_CONFIG
    
    required_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_REGION',
        'SES_VERIFIED_EMAIL'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            masked_value = value[:4] + '*' * (len(value) - 4) if len(value) > 4 else '****'
            logger.info(f"{var} is set: {masked_value}")
    
    logger.info(f"Using AWS Region: {AWS_REGION}")
    logger.info(f"SMTP Config: {SMTP_CONFIG}")
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def test_email_functions():
    """Test email functionality from messaging.py"""
    try:
        # First verify environment variables
        logger.info("Verifying environment variables...")
        verify_env_variables()
        
        from actions.messaging import EmailClient
        from actions.constants import (
            EMAIL_TEMPLATES, 
            DEFAULT_VALUES, 
            ADMIN_EMAILS,
            GRIEVANCE_STATUS
        )
        
        # Initialize EmailClient
        logger.info("\nInitializing EmailClient...")
        email_client = EmailClient()
        
        # Get test recipient email
        to_email = input("\nEnter test recipient email: ")
        logger.info(f"Using test email: {to_email}")
        
        # Generate a test grievance ID
        grievance_id = f"GR{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        
        # 1. Test Simple Email
        logger.info("\n1. Testing Simple Email...")
        simple_success = email_client.send_email(
            to_emails=[to_email],
            subject="Test Email from Grievance System",
            body=EMAIL_TEMPLATES["SYSTEM_NOTIFICATION_BODY"].format(
                json_data="{ 'test': 'data' }",
                grievance_status=GRIEVANCE_STATUS["SUBMITTED"]
            )
        )
        
        if simple_success:
            logger.info("✅ Simple email test successful!")
        else:
            logger.error("❌ Simple email test failed!")

        input("\nPress Enter to continue with grievance recap email test...")

        # 2. Test Grievance Recap Email
        logger.info("\n2. Testing Grievance Recap Email...")
        
        # Mock grievance data using actual template
        categories = ["Water Supply", "Infrastructure"]
        categories_html = ''.join(f'<li>{category}</li>' for category in categories)
        
        body = EMAIL_TEMPLATES["GRIEVANCE_RECAP_BODY"].format(
            grievance_id=grievance_id,
            user_name="John Doe",
            grievance_details="Detailed description of the water supply issue",
            grievance_summary="Water supply interruption for 3 days",
            categories_html=categories_html,
            municipality="Sample Municipality",
            village="Sample Village",
            address="123 Main Street",
            phone="+639175330841",
            email=to_email
        )
        
        subject = EMAIL_TEMPLATES["GRIEVANCE_RECAP_SUBJECT"].format(
            grievance_id=grievance_id
        )
        
        logger.info("\nGrievance Email Details:")
        logger.info(f"Subject: {subject}")
        logger.info(f"Recipients: User ({to_email}) and Admins {ADMIN_EMAILS}")
        
        # Test sending to both admin and user
        to_emails = ADMIN_EMAILS.copy()
        to_emails.append(to_email)
        
        recap_success = email_client.send_email(
            to_emails=to_emails,
            subject=subject,
            body=body
        )
        
        if recap_success:
            logger.info("✅ Grievance recap email test successful!")
            logger.info(f"Email sent to: {', '.join(to_emails)}")
        else:
            logger.error("❌ Grievance recap email test failed!")

        # 3. Test System Notification Email
        logger.info("\n3. Testing System Notification Email...")
        
        grievance_data = {
            "grievance_id": grievance_id,
            "grievance_status": GRIEVANCE_STATUS["SUBMITTED"],
            "grievance_details": "Detailed description of the water supply issue",
            "grievance_summary": "Water supply interruption for 3 days",
            "categories": categories,
            "municipality": "Sample Municipality",
            "village": "Sample Village",
            "address": "123 Main Street",
            "user_name": "John Doe",
            "phone": "+639175330841",
            "email": to_email,
            "timestamp": datetime.now().isoformat(),
            "submission_type": "new_grievance"
        }
        
        import json
        json_data = json.dumps(grievance_data, indent=2, ensure_ascii=False)
        
        system_body = EMAIL_TEMPLATES["SYSTEM_NOTIFICATION_BODY"].format(
            json_data=json_data,
            grievance_status=GRIEVANCE_STATUS["SUBMITTED"]
        )
        
        system_subject = f"New Grievance Submission - ID: {grievance_id} - Status: {GRIEVANCE_STATUS['SUBMITTED']}"
        
        logger.info(f"Sending system notification to admins: {ADMIN_EMAILS}")
        
        for admin_email in ADMIN_EMAILS:
            system_success = email_client.send_email(
                to_emails=[admin_email],
                subject=system_subject,
                body=system_body
            )
            if system_success:
                logger.info(f"✅ System notification sent to {admin_email}")
            else:
                logger.error(f"❌ Failed to send system notification to {admin_email}")

    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}")
        logger.exception("Detailed error traceback:")
        raise

if __name__ == "__main__":
    test_email_functions()