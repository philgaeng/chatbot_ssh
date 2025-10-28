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
    # Get the project root directory (3 levels up from backend/config/constants.py)
    project_root = Path(__file__).parent.parent.parent
    
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

# Call OpenAI API for classification
LLM_CLASSIFICATION = True

############################
# CORE DEFAULT VALUES
############################

DEFAULT_VALUES = {
    "NOT_PROVIDED": "Not provided",
    "ANONYMOUS": "Anonymous",
    "SKIP_VALUE": "slot_skipped",
    "DEFAULT_PROVINCE": "Koshi",
    "DEFAULT_DISTRICT": "Jhapa",
    "DEFAULT_OFFICE": "Office_1",
    "DEFAULT_LANGUAGE_CODE": "ne",
    "DEFAULT_TIMEZONE": "Asia/Kathmandu",
    "DEFAULT_USER": "test_user",
    "ERROR": "error"
}

# Location Constants
CUT_OFF_FUZZY_MATCH_LOCATION = 75

############################
# DATABASE TABLE METADATA (IMPORTED)
############################

# Import database table metadata from separate module
from .database_tables import (
    TABLE_CREATION_ORDER, TABLE_DEPENDENCIES, FIELD_NAMES, FIELD_DESCRIPTIONS,
    get_seed_data
)

# Note: Database-derived constants are now accessed through database_constants.py
# The database is the authoritative source of truth for lookup tables

############################
# FEATURE FLAGS
############################

SMS_ENABLED = False  # Set to True to enable SMS

############################
# FILE PATHS AND PATHS
############################

# Dynamic file paths based on project root
PROJECT_ROOT = Path(__file__).parent.parent
LOOKUP_FILE_PATH = str(PROJECT_ROOT / "resources/lookup_tables/list_category.txt")
DEFAULT_CSV_PATH = str(PROJECT_ROOT / "resources/grievances_categorization_v1.1.csv")
LOCATION_FOLDER_PATH = str(PROJECT_ROOT / "resources/location_dataset/")

############################
# EMAIL CONFIGURATION
############################

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

############################
# MESSAGING TEMPLATES
############################

# Email Templates
EMAIL_TEMPLATES = {
    "GRIEVANCE_SUBJECT_COMPLAINANT": {"en": "Grievance submitted to Department Of Roads - ID: {grievance_id}", "ne": "गुनासो दर्ता गरिएको छ - ID: {grievance_id}"},
    "GRIEVANCE_SUBJECT_ADMIN": {"en": "New Grievance Submission - ID: {grievance_id}", "ne": "नया गुनासो दर्ता - ID: {grievance_id}"},
    "GRIEVANCE_STATUS_UPDATE_SUBJECT": {"en": "Grievance Status Updated - ID: {grievance_id}", "ne": "गुनासो स्थिति अपडेट - ID: {grievance_id}"},
    "GRIEVANCE_RECAP_COMPLAINANT_BODY": {"en":"""
        <h2>Grievance Submission Recap</h2>
        <p><strong>Grievance ID:</strong> {grievance_id}</p>
        <p><strong>Grievance Filed on:</strong> {grievance_timestamp}</p>
        <p><strong>Expected Resolution Date:</strong> {grievance_timeline}</p>
        <p><strong>Submitted by:</strong> {complainant_name}</p>
        
        <h3>Grievance Summary:</h3>
        <p>{grievance_summary}</p>
        
        <h3>Grievance Details:</h3>
        <p>{grievance_description}</p>
        
        <h3>Categories:</h3>
        <ul>
            {categories_html}
        </ul>
        
        <h3>Location:</h3>
        <p>Municipality: {complainant_municipality}</p>
        <p>Village: {complainant_village}</p>
        <p>Address: {complainant_address}</p>
        
        <h3>Contact Information:</h3>
        <p>Phone: {complainant_phone}</p>
        <p>Email: {complainant_email}</p>

        This is an automated notification. Please do not reply to this email.
    """,
     "ne": """
        <h2>गुनासो दर्ता सारांश</h2>
        <p><strong>गुनासो ID:</strong> {grievance_id}</p>
        <p><strong>गुनासो दर्ता गरिएको:</strong> {grievance_timestamp}</p>
        <p><strong>अनुमानित समाधान तिथि:</strong> {grievance_timeline}</p>
        <p><strong>दर्ता गर्ने:</strong> {complainant_name}</p>
        
        <h3>गुनासो सारांश:</h3>
        <p>{grievance_summary}</p>
        
        <h3>गुनासो विवरण:</h3>
        <p>{grievance_description}</p>
        
        <h3>श्रेणी:</h3>
        <ul>
            {categories_html}
        </ul>
        
        <h3>स्थान:</h3>
        <p>महानगरपालिका: {complainant_municipality}</p>
        <p>गाउँपालिका: {complainant_village}</p>
        <p>पत्ता: {complainant_address}</p>
        
        <h3>संपर्क जानकारी:</h3>
        <p>फोन: {complainant_phone}</p>
        <p>इमेल: {complainant_email}</p>

        This is an automated notification. Please do not reply to this email.
    """
    },
    "GRIEVANCE_STATUS_UPDATE_BODY": {"en": """
        <h2>Grievance Status Update Notification</h2>
        <p><strong>Grievance ID:</strong> {grievance_id}</p>
        <p><strong>Complainant ID:</strong> {complainant_id}</p>
        <p><strong>Status Updated to:</strong> {grievance_status}</p>
        <p><strong>Updated on:</strong> {grievance_status_update_date}</p>
        <p><strong>Expected Resolution Date:</strong> {grievance_timeline}</p>
        
        <h3>Complainant Information:</h3>
        <p><strong>Name:</strong> {complainant_full_name}</p>
        <p><strong>Phone:</strong> {complainant_phone}</p>
        <p><strong>Municipality:</strong> {municipality}</p>
        <p><strong>Village:</strong> {village}</p>
        <p><strong>Address:</strong> {address}</p>
        
        <h3>Grievance Details:</h3>
        <p><strong>Summary:</strong> {grievance_summary}</p>
        <p><strong>Description:</strong> {grievance_details}</p>
        <p><strong>Categories:</strong> {grievance_categories}</p>
        
        <p><em>This is an automated notification for office staff. Please do not reply to this email.</em></p>
    """,
    "ne": """
        <h2>गुनासो स्थिति अपडेट सूचना</h2>
        <p><strong>गुनासो ID:</strong> {grievance_id}</p>
        <p><strong>गुनासो दर्ताकर्ता ID:</strong> {complainant_id}</p>
        <p><strong>स्थिति अपडेट:</strong> {grievance_status}</p>
        <p><strong>अपडेट मिति:</strong> {grievance_status_update_date}</p>
        <p><strong>अनुमानित समाधान तिथि:</strong> {grievance_timeline}</p>
        
        <h3>गुनासो दर्ताकर्ता जानकारी:</h3>
        <p><strong>नाम:</strong> {complainant_full_name}</p>
        <p><strong>फोन:</strong> {complainant_phone}</p>
        <p><strong>महानगरपालिका:</strong> {municipality}</p>
        <p><strong>गाउँपालिका:</strong> {village}</p>
        <p><strong>पत्ता:</strong> {address}</p>
        
        <h3>गुनासो विवरण:</h3>
        <p><strong>सारांश:</strong> {grievance_summary}</p>
        <p><strong>विवरण:</strong> {grievance_details}</p>
        <p><strong>श्रेणी:</strong> {grievance_categories}</p>
        
        <p><em>यो कार्यालय कर्मचारीहरूको लागि स्वचालित सूचना हो। कृपया यस इमेलमा जवाफ नदिनुहोस्।</em></p>
    """
    },
    "GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP": {
        "en": """<html>
<body>
<h2>Grievance Follow-Up Request</h2>
<p>The complainant has requested to follow up on their grievance:</p>

<h3>Grievance Details</h3>
<ul>
<li><strong>Grievance ID:</strong> {grievance_id}</li>
<li><strong>Timeline:</strong> {grievance_timeline}</li>
<li><strong>Summary:</strong> {grievance_summary}</li>
<li><strong>Description:</strong> {grievance_description}</li>
<li><strong>Categories:</strong> {grievance_categories}</li>
</ul>

<h3>Complainant Information</h3>
<ul>
<li><strong>Name:</strong> {complainant_name}</li>
<li><strong>Phone:</strong> {complainant_phone}</li>
<li><strong>Email:</strong> {complainant_email}</li>
<li><strong>Municipality:</strong> {complainant_municipality}</li>
<li><strong>Village:</strong> {complainant_village}</li>
<li><strong>Address:</strong> {complainant_address}</li>
</ul>
</body>
</html>""",
        "ne": """<html>
<body>
<h2>गुनासो फलोअप अनुरोध</h2>
<p>उजुरीकर्ताले आफ्नो गुनासोको फलोअप गर्न अनुरोध गर्नुभएको छ:</p>

<h3>गुनासो विवरण</h3>
<ul>
<li><strong>गुनासो आईडी:</strong> {grievance_id}</li>
<li><strong>समयरेखा:</strong> {grievance_timeline}</li>
<li><strong>सारांश:</strong> {grievance_summary}</li>
<li><strong>विवरण:</strong> {grievance_description}</li>
<li><strong>श्रेणीहरू:</strong> {grievance_categories}</li>
</ul>

<h3>उजुरीकर्ता जानकारी</h3>
<ul>
<li><strong>नाम:</strong> {complainant_name}</li>
<li><strong>फोन:</strong> {complainant_phone}</li>
<li><strong>इमेल:</strong> {complainant_email}</li>
<li><strong>नगरपालिका:</strong> {complainant_municipality}</li>
<li><strong>गाउँ:</strong> {complainant_village}</li>
<li><strong>ठेगाना:</strong> {complainant_address}</li>
</ul>
</body>
</html>"""
    },
}

EMAIL_TEMPLATES['GRIEVANCE_RECAP_ADMIN_BODY'] = EMAIL_TEMPLATES['GRIEVANCE_RECAP_COMPLAINANT_BODY']

# SMS Templates
DIC_SMS_TEMPLATES = {
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
    },
    "GRIEVANCE_STATUS_UPDATE": {
        'en': """Your grievance (ID: {grievance_id}) status has been updated to: {grievance_status}.
Expected resolution date: {grievance_timeline}.
Thank you for your patience.""",
        'ne': """तपाईंको गुनासो (ID: {grievance_id}) को स्थिति अपडेट भएको छ: {grievance_status}।
अनुमानित समाधान तिथि: {grievance_timeline}।
तपाईंको धैर्यको लागि धन्यवाद।"""
    },
    "GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP": {
        'en': """Thank you for connecting with us. Our officer will follow up on your grievance (ID: {grievance_id}) and contact you shortly on this number: {complainant_phone}.""",
        'ne': """तपाईंको संपर्क गर्ने लागि धन्यवाद। हामीको कर्मचारी तपाईंको गुनासो (ID: {grievance_id}) को फलोअप गर्नेछ र तपाईंको लागि यो नम्बरमा जस्तै सम्पर्क गर्नेछ: {complainant_phone}"""
    }
}

############################
# LOCATION CONFIGURATION
############################

# Location Words
DIC_LOCATION_WORDS = {
    "province": {
        "en": ["province"],
        "ne": ["प्रदेश"]
    },
    "district": {
        "en": ["district"],
        "ne": ["जिल्ला"]
    },
    "municipality": {
        "en": ["municipality", "rural municipality", "metropolitan"],
        "ne": ["महानगरपालिका", "गाउँपालिका", "नगरपालिका"]
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

############################
# FILE HANDLING CONFIGURATION
############################

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

############################
# FIELD CONFIGURATION
############################

# Enhanced field configuration with categories and metadata
FIELD_CONFIG = {
    'complainant_full_name': {'alias': 'full_name', 'required': True, 'category': 'user'},
    'complainant_phone': {'alias': 'contact_phone', 'required': True, 'category': 'user'},
    'complainant_email': {'alias': 'contact_email', 'required': False, 'category': 'user'},
    'complainant_province': {'alias': 'province', 'required': True, 'category': 'user'},
    'complainant_district': {'alias': 'district', 'required': True, 'category': 'user'},
    'complainant_municipality': {'alias': 'municipality', 'required': True, 'category': 'user'},
    'complainant_ward': {'alias': 'ward', 'required': False, 'category': 'user'},
    'complainant_village': {'alias': 'village', 'required': False, 'category': 'user'},
    'complainant_address': {'alias': 'address', 'required': False, 'category': 'user'},
    'grievance_description': {'alias': 'grievance', 'required': True, 'category': 'grievance'},
    'grievance_description_en': {'alias': 'grievance_en', 'required': False, 'category': 'grievance'},
    'grievance_summary': {'alias': 'summary', 'required': False, 'category': 'grievance'},
    'grievance_categories': {'alias': 'categories', 'required': True, 'category': 'grievance'},
}

FIELD_MAPPING = {k: v['alias'] for k, v in FIELD_CONFIG.items()}

# Derived constants for backward compatibility and easy access
VALID_FIELD_NAMES = list(FIELD_MAPPING.keys())
USER_FIELDS = [k for k, v in FIELD_CONFIG.items() if v['category'] == 'user']
GRIEVANCE_FIELDS = [k for k, v in FIELD_CONFIG.items() if v['category'] == 'grievance']
REQUIRED_FIELDS = [k for k, v in FIELD_CONFIG.items() if v['required']]
FIELD_CATEGORIES_MAPPING = {k: v['category'] for k, v in FIELD_CONFIG.items()}

############################
# AWS CONFIGURATION
############################

# AWS SNS Configuration
AWS_REGION = "ap-southeast-1"
WHITELIST_PHONE_NUMBERS_OTP_TESTING = [
    "+639175330841", 
    "+639154345604"
    # Add other whitelisted numbers
]

############################
# DATABASE CONFIGURATION
############################

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

############################
# RASA CONFIGURATION
############################

# RASA WebSocket configuration
RASA_HOST = os.getenv('RASA_HOST', 'localhost')
RASA_PORT = int(os.getenv('RASA_PORT', 5005))
RASA_WS_PROTOCOL = os.getenv('RASA_WS_PROTOCOL', 'ws')
RASA_WS_PATH = os.getenv('RASA_WS_PATH', '/socket.io/')
RASA_WS_URL = f"{RASA_WS_PROTOCOL}://{RASA_HOST}:{RASA_PORT}"
RASA_WS_TRANSPORTS = os.getenv('RASA_WS_TRANSPORTS', ['websocket'])
RASA_API_PROTOCOL = os.getenv('RASA_API_PROTOCOL', 'http')
RASA_API_URL = f"{RASA_API_PROTOCOL}://{RASA_HOST}:{RASA_PORT}"

############################
# FLASK CONFIGURATION

FLASK_URL = os.getenv('FLASK_URL', 'http://localhost:5001')


############################
# DATA LOADING FUNCTIONS
############################

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
    Loads grievance classification data from a CSV file and returns a JSON structure
    where keys are category names and values contain all grievance data.
    """
    classification_data = {}

    try:
        with open(csv_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Create category key as "Classification - Grievance Name"
                category_key = f"{row['classification'].replace('-', ' ').title()} - {row['generic_grievance_name'].replace('-', ' ').title()}"
                
                # Create the data structure for this category
                classification_data[category_key] = {
                    'generic_grievance_name': row['generic_grievance_name'],
                    'generic_grievance_name_ne': row['generic_grievance_name_ne'],
                    'short_description': row['short_description'],
                    'short_description_ne': row['short_description_ne'],
                    'classification': row['classification'],
                    'classification_ne': row['classification_ne'],
                    'description': row['description'],
                    'description_ne': row['description_ne'],
                    'follow_up_question_description': row['follow_up_question_description'],
                    'follow_up_question_description_ne': row['follow_up_question_description_ne'],
                    'follow_up_question_quantification': row['follow_up_question_quantification'],
                    'follow_up_question_quantification_ne': row['follow_up_question_quantification_ne'],
                    'high_priority': row['high_priority'].lower() == 'true' if row.get('high_priority') else False
                }

        # Update lookup table with category names
        unique_categories = sorted(classification_data.keys())
        update_lookup_table(unique_categories)

        return classification_data, unique_categories

    except FileNotFoundError:
        logger.error(f"⚠ Classification CSV file not found: {csv_path}")
        return {}
    except Exception as e:
        logger.error(f"⚠ Error loading classification data: {e}")
        return {}

def update_lookup_table(categories):
    """Writes the latest category list to the lookup table file (list_category.txt)."""
    try:
        with open(LOOKUP_FILE_PATH, "w", encoding="utf-8") as file:
            for category in categories:
                file.write(f"{category}\n")
        logger.info("✅ Lookup table successfully updated.")
    except Exception as e:
        logger.error(f"⚠ Error updating lookup table: {e}")

############################
# LOAD CLASSIFICATION DATA
############################

# Load classification data and categories as constants
CLASSIFICATION_DATA, LIST_OF_CATEGORIES = load_classification_data()


############################
# LOGGING AND INITIALIZATION
############################

# Log configuration source
logger.info(f"Configuration loaded from: {ENV_SOURCE}")
logger.info(f"Database host: {DB_CONFIG['host']}")
logger.info(f"Database name: {DB_CONFIG['database']}")
logger.info(f"Redis host: {REDIS_HOST}")