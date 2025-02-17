
import os
from typing import List


# Location Constants
QR_PROVINCE = "KOSHI"
QR_DISTRICT = "Jhapa"
DISTRICT_LIST = ['Jhapa', 'Morang', 'Sunsari']
USE_QR_CODE = True
CUT_OFF_FUZZY_MATCH_LOCATION = 75

# You can add other constants here, organized by category
# For example:
SMS_ENABLED = False  # Set to True to enable SMS    
# API Constants
# API_KEY = "your-api-key"
# BASE_URL = "https://api.example.com"

# File Paths
LOOKUP_FILE_PATH = "/home/ubuntu/nepal_chatbot/data/lookup_tables/list_category.txt"
DEFAULT_CSV_PATH = "/home/ubuntu/nepal_chatbot/resources/grievances_categorization_v1.csv"
# File to store the last grievance ID
COUNTER_FILE = "/home/ubuntu/nepal_chatbot/data/grievance_counter.txt"
# Location JSON file
LOCATION_JSON_PATH = "/home/ubuntu/nepal_chatbot/resources/nepal_location.json"
# List of email providers
EMAIL_PROVIDERS_NEPAL = {
    "Gmail": ["gmail.com"],
    "Outlook": ["outlook.com", "hotmail.com", "live.com"],
    "Yahoo": ["yahoo.com", "yahoo.in"],
    "iCloud": ["icloud.com", "me.com", "mac.com"],
    "Zoho Mail": ["zoho.com", "zoho.in"],
    "ProtonMail": ["protonmail.com"],
    "Cloudlaya": ["cloudlaya.com.np"],
    "Marpa Infotech": ["marpainfotech.com.np"],
    "Prabhu Host": ["prabhuhost.com.np"],
    "Web House Nepal": ["webhousenepal.com.np"],
    "Email Sewa": ["emailsewa.com.np"],
    "Himalayan Host": ["himalayanhost.com.np"],
    "Nepal Link": ["nepallink.com.np"],
    "Mercantile Mail": ["mail.com.np"],
    "WorldLink Email": ["worldlink.com.np"],
    "ADB_testing": ["adb.org"], 
    "project": ["project.com.ph"]
}

# AWS SNS Configuration
AWS_REGION = "ap-southeast-1"
WHITELIST_PHONE_NUMBERS_OTP_TESTING = [
    "+639175330841", 
    "+639154345604"
    # Add other whitelisted numbers
]

# Email Configuration
SMTP_CONFIG = {
    "SERVER": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "PORT": int(os.getenv("SMTP_PORT", "587")),
    "USERNAME": os.getenv("SMTP_USERNAME", "your-email@domain.com"),
    "PASSWORD": os.getenv("SMTP_PASSWORD", "your-app-password"),
}

# Admin notification emails
ADMIN_EMAILS: List[str] = [
    "philgaeng@gmail.com",
    'philgaeng@project.com.ph'
    # Add other admin emails
]

# Grievance status
GRIEVANCE_STATUS = {
    "SUBMITTED": "submitted",
    "UNDER_EVALUATION": "under_evaluation",
    "ESCALATED": "escalated",
    "RESOLVED": "resolved",
    "DENIED": "denied"
}

# Email Templates
EMAIL_TEMPLATES = {
    "GRIEVANCE_RECAP_SUBJECT": "Grievance Submission Recap - ID: {grievance_id}",
    "GRIEVANCE_RECAP_BODY": """
        <h2>Grievance Submission Recap</h2>
        <p><strong>Grievance ID:</strong> {grievance_id}</p>
        <p><strong>Submitted by:</strong> {user_name}</p>
        
        <h3>Grievance Summary:</h3>
        <p>{grievance_summary}</p>
        
        <h3>Grievance Details:</h3>
        <p>{grievance_details}</p>
        
        <h3>Categories:</h3>
        <ul>
            {categories_html}
        </ul>
        
        <h3>Location:</h3>
        <p>Municipality: {municipality}</p>
        <p>Village: {village}</p>
        <p>Address: {address}</p>
        
        <h3>Contact Information:</h3>
        <p>Phone: {phone}</p>
        <p>Email: {email}</p>
    """,
    "SYSTEM_NOTIFICATION_BODY": """
        New grievance submission received.
        Status: {grievance_status}

        Complete Grievance Data:
        {json_data}

        This is an automated notification. Please do not reply to this email.
    """
}

# SMS Templates
SMS_TEMPLATES = {
    "OTP_MESSAGE": "Your verification code is {otp}. Please enter this code to verify your phone number.",
    "GRIEVANCE_RECAP": """Thank you for submitting your grievance (ID: {grievance_id}).
We have received your complaint and will process it accordingly.
You will receive updates about your grievance through this number."""
}

# Default values
DEFAULT_VALUES = {
    "NOT_PROVIDED": "Not provided",
    "ANONYMOUS": "Anonymous"
}