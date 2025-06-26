import os
import csv
from typing import List
import logging
from pathlib import Path
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)

# Auto-detect and load environment variables
# (This must happen BEFORE any os.getenv calls)
def load_environment():
    """Load environment variables from env.local (development) or .env (production/remote)"""
    # Get the project root directory (2 levels up from actions_server)
    project_root = Path(__file__).parent.parent
    
    # Try to load from env.local first (development)
    env_local = project_root / "env.local"
    env_file = project_root / ".env"
    
    if env_local.exists():
        logger.info(f"Loading environment from {env_local} (development)")
        load_dotenv(env_local)
        return "env.local"
    elif env_file.exists():
        logger.info(f"Loading environment from {env_file} (production/remote)")
        load_dotenv(env_file)
        return ".env"
    else:
        logger.warning("No environment file found, using system environment variables")
        return "system"

# Load environment variables BEFORE any config is set
ENV_SOURCE = load_environment()

# Location Constants
QR_PROVINCE = "Koshi"
QR_DISTRICT = "Jhapa"
DEFAULT_PROVINCE = "Koshi"
DEFAULT_DISTRICT = "Jhapa"
DISTRICT_LIST = ['Jhapa', 'Morang', 'Sunsari']
USE_QR_CODE = True
CUT_OFF_FUZZY_MATCH_LOCATION = 75

# You can add other constants here, organized by category
# For example:
SMS_ENABLED = False  # Set to True to enable SMS    
# API Constants

# Dynamic file paths based on project root
PROJECT_ROOT = Path(__file__).parent.parent
LOOKUP_FILE_PATH = str(PROJECT_ROOT / "data/lookup_tables/list_category.txt")
DEFAULT_CSV_PATH = str(PROJECT_ROOT / "resources/grievances_categorization_v1.csv")
LOCATION_FOLDER_PATH = str(PROJECT_ROOT / "resources/location_dataset/")

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
    "ANONYMOUS": "Anonymous",
    "SKIP_VALUE": "slot_skipped"
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

# File type categories
FILE_TYPES = {
    'IMAGE': {
        'extensions': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'heic', 'heif'},
        'mime_types': {'image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/webp', 'image/heic', 'image/heif'},
        'max_size_mb': 5
    },
    'VIDEO': {
        'extensions': {'mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm', 'm4v'},
        'mime_types': {'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska', 'video/x-ms-wmv', 'video/x-flv', 'video/webm'},
        'max_size_mb': 50
    },
    'AUDIO': {
        'extensions': {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'wma', 'flac', 'webm'},
        'mime_types': {'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/x-m4a', 'audio/aac', 'audio/x-ms-wma', 'audio/flac', 'audio/webm'},
        'max_size_mb': 10
    },
    'DOCUMENT': {
        'extensions': {
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
            'txt', 'rtf', 'csv', 'odt', 'ods', 'odp'
        },
        'mime_types': {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'application/rtf',
            'text/csv',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.oasis.opendocument.spreadsheet',
            'application/vnd.oasis.opendocument.presentation'
        },
        'max_size_mb': 2
    },
    'ARCHIVE': {
        'extensions': {'zip', 'rar', '7z', 'tar', 'gz'},
        'mime_types': {'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed', 'application/x-tar', 'application/gzip'},
        'max_size_mb': 20
    }
}

# Get all allowed extensions
ALLOWED_EXTENSIONS = {ext for type_info in FILE_TYPES.values() for ext in type_info['extensions']}
AUDIO_EXTENSIONS = {ext for k, v in FILE_TYPES.items() for ext in v['extensions'] if k == 'AUDIO'}

# Get all allowed mime types
ALLOWED_MIME_TYPES = {mime for type_info in FILE_TYPES.values() for mime in type_info['mime_types']}

# Get max file size for each type
FILE_TYPE_MAX_SIZES = {file_type: info['max_size_mb'] * 1024 * 1024 for file_type, info in FILE_TYPES.items()}

# Default max file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# Enhanced field configuration with categories and metadata
FIELD_CONFIG = {
        'user_full_name': {'alias': 'full_name', 'required': True, 'category': 'user'},
        'user_contact_phone': {'alias': 'contact_phone', 'required': True, 'category': 'user'},
        'user_contact_email': {'alias': 'contact_email', 'required': False, 'category': 'user'},
        'user_province': {'alias': 'province', 'required': True, 'category': 'user'},
        'user_district': {'alias': 'district', 'required': True, 'category': 'user'},
        'user_municipality': {'alias': 'municipality', 'required': True, 'category': 'user'},
        'user_ward': {'alias': 'ward', 'required': False, 'category': 'user'},
        'user_village': {'alias': 'village', 'required': False, 'category': 'user'},
        'user_address': {'alias': 'address', 'required': False, 'category': 'user'},
        'grievance_details': {'alias': 'grievance', 'required': True, 'category': 'grievance'},
        'grievance_details_en': {'alias': 'grievance_en', 'required': False, 'category': 'grievance'},
        'grievance_summary': {'alias': 'summary', 'required': False, 'category': 'grievance'},
        'grievance_categories': {'alias': 'categories', 'required': True, 'category': 'grievance'},
    }

FIELD_MAPPING = {k:v['alias'] for k,v in FIELD_CONFIG.items()}
# Derived constants for backward compatibility and easy access
VALID_FIELD_NAMES = list(FIELD_MAPPING.keys())
USER_FIELDS = [k for k, v in FIELD_CONFIG.items() if v['category'] == 'user']
GRIEVANCE_FIELDS = [k for k, v in FIELD_CONFIG.items() if v['category'] == 'grievance']
REQUIRED_FIELDS = [k for k, v in FIELD_CONFIG.items() if v['required']]
FIELD_CATEGORIES_MAPPING = {k:v['category'] for k, v in FIELD_CONFIG.items()}

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

# Get Redis configuration from environment variables
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
REDIS_DB = os.getenv('REDIS_DB', '0')

# Database configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'database': os.getenv('POSTGRES_DB', 'grievance_db'),
    'user': os.getenv('POSTGRES_USER', 'nepal_grievance_admin'),
    'password': os.getenv('POSTGRES_PASSWORD', 'K9!mP2$vL5nX8&qR4jW7'),
    'port': os.getenv('POSTGRES_PORT', '5432')
}

# Log configuration source
logger.info(f"Configuration loaded from: {ENV_SOURCE}")
logger.info(f"Database host: {DB_CONFIG['host']}")
logger.info(f"Database name: {DB_CONFIG['database']}")
logger.info(f"Redis host: {REDIS_HOST}")

# RASA WebSocket configuration
RASA_WS_HOST = os.getenv('RASA_WS_HOST', 'localhost')
RASA_WS_PORT = int(os.getenv('RASA_WS_PORT', 5005))
RASA_WS_PROTOCOL = os.getenv('RASA_WS_PROTOCOL', 'ws')
RASA_WS_PATH = os.getenv('RASA_WS_PATH', '/socket.io/')
RASA_WS_URL = f"{RASA_WS_PROTOCOL}://{RASA_WS_HOST}:{RASA_WS_PORT}"
RASA_WS_TRANSPORTS = os.getenv('RASA_WS_TRANSPORTS', ['websocket'])