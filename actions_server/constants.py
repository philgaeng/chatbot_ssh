import os
import csv
from typing import List
import logging

# Set up logging
logger = logging.getLogger(__name__)


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

# File Paths
LOOKUP_FILE_PATH = "/home/ubuntu/nepal_chatbot/data/lookup_tables/list_category.txt"
DEFAULT_CSV_PATH = "/home/ubuntu/nepal_chatbot/resources/grievances_categorization_v1.csv"
# Location JSON file
LOCATION_FOLDER_PATH = "/home/ubuntu/nepal_chatbot/resources/location_dataset/"
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

EMAIL_PROVIDERS_NEPAL_LIST = [domain for provider in EMAIL_PROVIDERS_NEPAL.values() for domain in provider]


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
    "GRIEVANCE_RECAP_USER_BODY": """
        <h2>Grievance Submission Recap</h2>
        <p><strong>Grievance ID:</strong> {grievance_id}</p>
        <p><strong>Grievance Filed on:</strong> {grievance_timestamp}</p>
        <p><strong>Expected Resolution Date:</strong> {grievance_timeline}</p>
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
    "GRIEVANCE_RECAP_ADMIN_BODY": """
        New grievance submission received.
        Status: {grievance_status}

        Complete Grievance Data:
        {json_data}

        This is an automated notification. Please do not reply to this email.
    """
}

# SMS Templates
DIC_SMS_TEMPLATES ={
    "OTP_MESSAGE": {
        'en': "Your verification code is {otp}. Please enter this code to verify your phone number.",
        'ne': "तपाईंको सत्यापन कोड {otp} हो। कृपया यो कोड फ्रिज गर्नुहोस् तपाईंको फोन नम्बरको सत्यापन गर्ने लागि।",
    },
    "GRIEVANCE_RECAP": {
        'en': """Thank you for submitting your grievance (ID: {grievance_id}).
We have received your complaint and will process it accordingly.
You will receive updates about your grievance through this number.""",
        'ne': """तपाईंको गुनासो दर्ता गर्ने लागि धन्यवाद (ID: {grievance_id})।
        हामीले तपाईंको गुनासो ग्रहण गरेको छ र तपाईंको गुनासोको अनुसार सुनिश्चित गर्नेछौं।
        तपाईंलाई तपाईंको गुनासोको अपडेट यो नम्बरमा प्राप्त हुनेछ।"""
    }
}

# Default values
DEFAULT_VALUES = {
    "NOT_PROVIDED": "Not provided",
    "ANONYMOUS": "Anonymous"
}

# Location Words
DIC_LOCATION_WORDS = { "province" : {
    "en" : ["province"],
    "ne" : ["प्रदेश"]
    },
    "district" : {
        "en" : ["district"],
        "ne" : ["जिल्ला"]
    },
    "municipality" : {
        "en" : ["municipality", "rural municipality", "metropolitan"],
        "ne" : ["महानगरपालिका", "गाउँपालिका", "नगरपालिका"]
    }
}

DIC_LOCATION_MAPPING = {
    "प्रदेश न. १": {
        "new_nepali": "कोशी",
        "english": "Koshi"
    },
    "प्रदेश न. २": {
        "new_nepali": "मधेश",
        "english": "Madhesh"
    },
    "प्रदेश न. ३": {
        "new_nepali": "बागमती",
        "english": "Bagmati"
    },
    "प्रदेश न. ४": {
        "new_nepali": "गण्डकी",
        "english": "Gandaki"
    },
    "प्रदेश न. ५": {
        "new_nepali": "लुम्बिनी",
        "english": "Lumbini"
    },
    "प्रदेश न. ६": {
        "new_nepali": "कर्णाली",
        "english": "Karnali"
    },
    "प्रदेश न. ७": {
        "new_nepali": "सुदूरपश्चिम",
        "english": "Sudurpashchim"
    }
}

# File upload settings
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# File Paths
LOOKUP_FILE_PATH = "/home/ubuntu/nepal_chatbot/data/lookup_tables/list_category.txt"
DEFAULT_CSV_PATH = "/home/ubuntu/nepal_chatbot/resources/grievances_categorization_v1.csv"

def load_categories_from_lookup():
    """Loads categories from the lookup table file (list_category.txt)."""
    try:
        with open(LOOKUP_FILE_PATH, "r", encoding="utf-8") as file:
            category_list = [line.strip() for line in file if line.strip()]  # Remove empty lines
        return category_list
    except FileNotFoundError:
        logger.error(f"⚠ Lookup file not found: {LOOKUP_FILE_PATH}")
        return []
    except Exception as e:
        logger.error(f"⚠ Error loading categories from lookup table: {e}")
        return []  # Return empty list on failure

def load_classification_data(csv_path=DEFAULT_CSV_PATH):
    """
    Loads grievance classification data from a CSV file, updates the lookup table,
    and returns a unique sorted list of categories.
    """
    categories = []

    try:
        with open(csv_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Normalize case and format as "Classification - Grievance Name"
                category = f"{row['Classification'].title()} - {row['Generic Grievance Name'].title()}"
                categories.append(category)

        # Remove duplicates and sort
        unique_categories = sorted(set(categories))

        # Update lookup table
        update_lookup_table(unique_categories)

        return unique_categories

    except FileNotFoundError:
        logger.error(f"⚠ Classification CSV file not found: {csv_path}")
        return []
    except Exception as e:
        logger.error(f"⚠ Error loading classification data: {e}")
        return []

def update_lookup_table(categories):
    """Writes the latest category list to the lookup table file (list_category.txt)."""
    try:
        with open(LOOKUP_FILE_PATH, "w", encoding="utf-8") as file:
            for category in categories:
                file.write(f"{category}\n")
        logger.info("✅ Lookup table successfully updated.")
    except Exception as e:
        logger.error(f"⚠ Error updating lookup table: {e}")
        
# Load classification data and categories as constants
CLASSIFICATION_DATA = load_classification_data()
LIST_OF_CATEGORIES = [cat.strip("-").strip() for cat in load_categories_from_lookup()]