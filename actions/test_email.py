import os
import sys
import logging
from dotenv import load_dotenv
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_html_email(data: dict) -> str:
    """Create formatted HTML email"""
    html = f"""
        <h2>Grievance Submission Recap</h2>
        <p><strong>Grievance ID:</strong> {data['grievance_id']}</p>
        <p><strong>Submitted by:</strong> {data['user_name']}</p>

        <h3>Grievance Details:</h3>
        <p>{data['grievance_text']}</p>

        <h3>Categories:</h3>
        <ul>
            {''.join(f'<li>{category}</li>' for category in data['categories'])}
        </ul>

        <h3>Location:</h3>
        <p>Municipality: {data['municipality']}</p>
        <p>Village: {data['village']}</p>
        <p>Address: {data['address']}</p>

        <h3>Contact Information:</h3>
        <p>Phone: {data['phone']}</p>
        <p>Email: {data['email']}</p>
    """
    return html

def test_email_functions():
    """Test email functionality from messaging.py"""
    try:
        from actions.messaging import EmailClient
        from actions.constants import EMAIL_TEMPLATES, DEFAULT_VALUES, ADMIN_EMAILS
        
        # Initialize EmailClient
        logger.info("\nInitializing EmailClient...")
        email_client = EmailClient()
        
        # Get test recipient email
        to_email = input("Enter test recipient email: ")
        
        # 1. Test Simple Email
        logger.info("\n1. Testing Simple Email...")
        simple_success = email_client.send_email(
            to_emails=[to_email],
            subject="Simple Test Email",
            body="This is a simple test email from the Grievance System."
        )
        
        if simple_success:
            logger.info("✅ Simple email test successful!")
        else:
            logger.error("❌ Simple email test failed!")

        # 2. Test Grievance Recap Email
        logger.info("\n2. Testing Grievance Recap Email...")
        
        # Mock grievance data
        grievance_data = {
            "grievance_id": "GR-2024-001",
            "user_name": "John Doe",
            "grievance_text": "Water supply interruption for 3 days",
            "categories": ["Water", "Infrastructure", "Urgent"],
            "municipality": "Sample Municipality",
            "village": "Sample Village",
            "address": "123 Main Street",
            "phone": "+639175330841",
            "email": to_email
        }
        
        # Create HTML email body
        html_body = create_html_email(grievance_data)
        
        subject = f"Grievance Submission - {grievance_data['grievance_id']}"
        
        logger.info("\nGrievance Email Preview:\n")
        logger.info(f"Subject: {subject}")
        logger.info("\nBody (HTML):\n")
        logger.info(html_body)
        
        input("\nPress Enter to send the grievance recap email...")
        
        # Test sending to both admin and user
        to_emails = ADMIN_EMAILS.copy()
        to_emails.append(to_email)
        
        recap_success = email_client.send_email(
            to_emails=to_emails,
            subject=subject,
            body=html_body
        )
        
        if recap_success:
            logger.info("✅ Grievance recap email test successful!")
            logger.info(f"Email sent to: {', '.join(to_emails)}")
        else:
            logger.error("❌ Grievance recap email test failed!")

    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    test_email_functions()