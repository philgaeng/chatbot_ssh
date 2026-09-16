# SPDX-License-Identifier: Apache-2.0

import os
import csv
from typing import Any, Dict, List, Tuple
import logging
from pathlib import Path
from dotenv import load_dotenv

import psycopg2
from psycopg2.extras import RealDictCursor

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
LOOKUP_FILE_PATH = str(PROJECT_ROOT / "dev-resources" / "lookup_tables" / "list_category.txt")
DEFAULT_CSV_PATH = str(PROJECT_ROOT / "dev-resources" / "grievances_categorization_v1.1.csv")
# Prefix for location_dataset_* files and location_dataset/ JSON (see ContactLocationValidator)
LOCATION_FOLDER_PATH = str(PROJECT_ROOT / "dev-resources" / "location_dataset")

############################
# EMAIL CONFIGURATION
############################

# Email domains accepted without "confirm non-Nepali domain" step.
# Includes global providers commonly used in Nepal (Gmail, Yahoo, Outlook, etc.)
# and Nepal-specific providers (.com.np). Used by contact form validation.
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

# Email Configuration (legacy dict — prefer backend.config.smtp_config.resolve_smtp_config)
SMTP_CONFIG = {
    "SERVER": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "PORT": int(os.getenv("SMTP_PORT", "587")),
    "USERNAME": os.getenv("SMTP_USERNAME", ""),
    "PASSWORD": os.getenv("SMTP_PASSWORD", ""),
    "FROM": os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME", ""),
    "FROM_DISPLAY": os.getenv("SMTP_FROM_DISPLAY", "GRM Ticketing"),
}

# Admin notification emails — recipients of the grievance recap mail.
#
# From the environment, not a literal. These are real personal addresses, and this
# repository is public: a hardcoded recipient list is both a config value that cannot be
# changed per deployment and a set of addresses published to anyone who clones. Set
# ADMIN_EMAILS to a comma-separated list, or ADMIN_EMAIL for a single one; empty means
# nobody is mailed, which is the right default for a fresh clone.
ADMIN_EMAILS: List[str] = [
    addr.strip()
    for addr in (os.getenv("ADMIN_EMAILS") or os.getenv("ADMIN_EMAIL", "")).split(",")
    if addr.strip()
]

# ── GRM portal base URL ──────────────────────────────────────────────────────
# Used to put a LINK into an admin notification instead of the record (F-19). Empty is a
# safe default and the right one for a fresh clone: the notification then names the
# grievance id and says to open the portal, rather than carrying a fabricated hostname.
# ⚠ Never fall back to embedding the narrative because the link is missing.
GRM_PORTAL_BASE_URL: str = (os.getenv("GRM_PORTAL_BASE_URL") or "").strip()

# ── OTP lifetime ─────────────────────────────────────────────────────────────
# Owner's decision, 2026-08-27 (D-62). Until then the OTP had NO expiry at all: the code
# was six digits in a conversation slot compared with `==`, so its validity was bounded by
# the session's lifetime rather than by a clock — which is not what anyone assumes when
# they read "one-time password".
#
# ⚠ Ten minutes is a trade, not a security parameter to tighten by reflex. The people it
# costs are complainants on a slow rural connection who wait for an SMS and then type six
# digits; shortening it makes the resend path the normal path for exactly the users least
# able to use it. Raise it before lowering it, and measure the resend rate first.
#
# Env-overridable so a deployment can adjust without a code change; the default is what a
# fresh clone gets.
OTP_VALIDITY_SECONDS: int = int(os.getenv("OTP_VALIDITY_SECONDS", "600"))

############################
# MESSAGING TEMPLATES
############################

# Email Templates
EMAIL_TEMPLATES = {
    "GRIEVANCE_SUBJECT_COMPLAINANT": {"en": "Grievance submitted to Department Of Roads - ID: {grievance_id}", "ne": "गुनासो दर्ता गरिएको छ - ID: {grievance_id}"},
    "GRIEVANCE_SUBJECT_ADMIN": {"en": "New Grievance Submission - ID: {grievance_id}", "ne": "नया गुनासो दर्ता - ID: {grievance_id}"},
    "GRIEVANCE_STATUS_UPDATE_SUBJECT": {"en": "Grievance Status Updated - ID: {grievance_id}", "ne": "गुनासो स्थिति अपडेट - ID: {grievance_id}"},
    "GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP_SUBJECT": {"en": "Grievance Follow-Up Request - ID: {grievance_id}", "ne": "गुनासो फलोअप अनुरोध - ID: {grievance_id}"},
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
}

# ── Admin notification bodies (F-19, 2026-09-03) ─────────────────────────────
# ⚠ THESE MUST NEVER REFERENCE A PII FIELD. Until 2026-09-03 there was no admin body at
# all: `GRIEVANCE_RECAP_ADMIN_BODY` was ASSIGNED from `GRIEVANCE_RECAP_COMPLAINANT_BODY`,
# so the admin list was mailed the complainant's own receipt — narrative, name, phone,
# address and email — on every submission. Nobody decided that; a template written for
# the one reader who already knows the whole story was reused, and the audience changed
# without the content changing.
#
# The rule now, and `test_admin_email_boundary.py` enforces it by parsing these strings:
# an admin body may reference ONLY the placeholders in `ADMIN_SAFE_FIELDS`
# (backend/actions/services/messaging/recap_email.py). Adding {grievance_description} or
# any complainant_* field here fails the build. The admin reads the case IN the platform,
# behind authentication and with an audit trail, instead of holding a copy in a mailbox
# with neither.
#
# English only, both language keys. Admin-facing copy is English by convention, and
# machine-translating an internal notification is the wrong way to fill a language slot
# (same reasoning as the OTP-expired message).
_ADMIN_RECAP_BODY = """<html>
<body>
<h2>New grievance filed</h2>
<p>A grievance has been submitted through the chatbot.</p>
<ul>
<li><strong>Grievance ID:</strong> {grievance_id}</li>
<li><strong>Filed on:</strong> {grievance_timestamp}</li>
<li><strong>Expected resolution date:</strong> {grievance_timeline}</li>
<li><strong>Categories:</strong> {grievance_categories}</li>
<li><strong>Location:</strong> {grievance_location}</li>
</ul>
<h3>Summary</h3>
<p>{grievance_summary}</p>
<p><em>Names, phone numbers and addresses are replaced with placeholders in this
summary. The full record is not sent by email.</em></p>
{portal_link_html}
<p>This is an automated notification. Please do not reply to this email.</p>
</body>
</html>"""

_ADMIN_FOLLOW_UP_BODY = """<html>
<body>
<h2>Grievance follow-up request</h2>
<p>The complainant has asked to follow up on their grievance.</p>
<ul>
<li><strong>Grievance ID:</strong> {grievance_id}</li>
<li><strong>Expected resolution date:</strong> {grievance_timeline}</li>
<li><strong>Categories:</strong> {grievance_categories}</li>
</ul>
<h3>Summary</h3>
<p>{grievance_summary}</p>
<p><em>Names, phone numbers and addresses are replaced with placeholders in this
summary. Open the case in the platform for the complainant's contact details.</em></p>
{portal_link_html}
<p>This is an automated notification. Please do not reply to this email.</p>
</body>
</html>"""

EMAIL_TEMPLATES['GRIEVANCE_RECAP_ADMIN_BODY'] = {"en": _ADMIN_RECAP_BODY, "ne": _ADMIN_RECAP_BODY}
EMAIL_TEMPLATES['GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP'] = {
    "en": _ADMIN_FOLLOW_UP_BODY,
    "ne": _ADMIN_FOLLOW_UP_BODY,
}

# ⚠ F-22, 2026-09-03. The third of three email paths that each carried the whole record. This one
# went to `office_emails`, which `get_office_emails_for_grievance` resolves from the grievance's
# MUNICIPALITY — the PD office plus whichever office covers that location — and NOT from the case's
# assigned cast. So a status update on a sensitive case mailed a survivor's narrative, name, phone
# and address to a location-derived list, and unlike the other two that list grows with deployment.
_OFFICE_STATUS_UPDATE_BODY = """<html>
<body>
<h2>Grievance status updated</h2>
<ul>
<li><strong>Grievance ID:</strong> {grievance_id}</li>
<li><strong>New status:</strong> {grievance_status}</li>
<li><strong>Updated on:</strong> {grievance_status_update_date}</li>
<li><strong>Expected resolution date:</strong> {grievance_timeline}</li>
<li><strong>Categories:</strong> {grievance_categories}</li>
</ul>
<h3>Summary</h3>
<p>{grievance_summary}</p>
<p><em>Names, phone numbers and addresses are replaced with placeholders in this
summary. The complainant's contact details are in the platform, not in this email.</em></p>
{portal_link_html}
<p>This is an automated notification. Please do not reply to this email.</p>
</body>
</html>"""

EMAIL_TEMPLATES['GRIEVANCE_STATUS_UPDATE_BODY'] = {
    "en": _OFFICE_STATUS_UPDATE_BODY,
    "ne": _OFFICE_STATUS_UPDATE_BODY,
}
# `build_admin_email` resolves the subject as f"{body_name}_SUBJECT". This one was authored as
# GRIEVANCE_STATUS_UPDATE_SUBJECT — without the _BODY — because its old call site formatted both
# by hand. Aliased rather than renamed: the old name is referenced elsewhere.
EMAIL_TEMPLATES['GRIEVANCE_STATUS_UPDATE_BODY_SUBJECT'] = EMAIL_TEMPLATES['GRIEVANCE_STATUS_UPDATE_SUBJECT']
# prepare_recap_email resolves subject via f"{body_name}_SUBJECT"
EMAIL_TEMPLATES['GRIEVANCE_RECAP_ADMIN_BODY_SUBJECT'] = EMAIL_TEMPLATES['GRIEVANCE_SUBJECT_ADMIN']
EMAIL_TEMPLATES['GRIEVANCE_RECAP_COMPLAINANT_BODY_SUBJECT'] = EMAIL_TEMPLATES['GRIEVANCE_SUBJECT_COMPLAINANT']

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

# Image compression policy (chatbot complainant uploads — locked 2026-06-05)
IMAGE_COMPRESS_MAX_LONG_EDGE = 1280
IMAGE_COMPRESS_JPEG_QUALITY = 80
IMAGE_COMPRESS_SKIP_MAX_LONG_EDGE = 1280
IMAGE_COMPRESS_SKIP_MAX_BYTES = 500_000

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
# SMS TEST WHITELIST
############################

# Gates the DOIT gateway when SMS_WHITELIST_ONLY=true. **Nepal mobile format only** (97…/98…) —
# anything else is ignored with a warning (messaging._normalized_whitelist).
#
# ⚠ Emptied 2026-08-24 with the removal of the AWS SNS path. It held two real Philippine mobile
# numbers, committed to a public repository: real personal data of real people, and the reason
# SMS_WHITELIST_ONLY=true crashed the DOIT send path. Empty means "send to nobody", which is the
# safe reading of a whitelist.
WHITELIST_PHONE_NUMBERS_OTP_TESTING: list[str] = []

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
    # Every value comes from the environment, which compose interpolates from env.local
    # with ${VAR:?}. The fallbacks are the identity the deployed volumes actually hold.
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'database': os.getenv('POSTGRES_DB', 'app_db'),
    'user': os.getenv('POSTGRES_USER', 'user'),
    # No fallback, deliberately. A default password here is read by nothing when the
    # environment is set and leaks a live credential into git when it is not.
    'password': os.getenv('POSTGRES_PASSWORD', ''),
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
# Backend HTTP base URL (FastAPI). Celery posts task status to FLASK_URL + "/task-status".
# Legacy name FLASK_URL — in Docker set e.g. FLASK_URL=http://backend:5001 so workers reach the API service.

BACKEND_HTTP_URL = os.getenv("BACKEND_HTTP_URL") or os.getenv("FLASK_URL", "http://localhost:5001")
FLASK_URL = BACKEND_HTTP_URL


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

def _classification_row_to_entry(row: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Build category_key and payload dict from DB row or CSV row."""
    classification_data = {
        "generic_grievance_name": row.get("generic_grievance_name") or "",
        "generic_grievance_name_ne": row.get("generic_grievance_name_ne") or "",
        "short_description": row.get("short_description") or "",
        "short_description_ne": row.get("short_description_ne") or "",
        "classification": row.get("classification") or "",
        "classification_ne": row.get("classification_ne") or "",
        "description": row.get("description") or "",
        "description_ne": row.get("description_ne") or "",
        "follow_up_question_description": row.get("follow_up_question_description") or "",
        "follow_up_question_description_ne": row.get("follow_up_question_description_ne") or "",
        "follow_up_question_quantification": row.get("follow_up_question_quantification") or "",
        "follow_up_question_quantification_ne": row.get("follow_up_question_quantification_ne") or "",
        "high_priority": bool(row.get("high_priority")),
    }
    ck = row.get("category_key")
    if not ck:
        ck = (
            f"{classification_data['classification'].replace('-', ' ').title()} - "
            f"{classification_data['generic_grievance_name'].replace('-', ' ').title()}"
        )
    return ck, classification_data


def _load_classification_from_database() -> Tuple[Dict[str, Any], List[str]]:
    """Load taxonomy from grievance_classification_taxonomy when seeded."""
    classification_data: Dict[str, Any] = {}
    try:
        with psycopg2.connect(
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
        ) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT category_key, generic_grievance_name, generic_grievance_name_ne,
                           short_description, short_description_ne, classification, classification_ne,
                           description, description_ne, follow_up_question_description,
                           follow_up_question_description_ne, follow_up_question_quantification,
                           follow_up_question_quantification_ne, high_priority
                    FROM grievance_classification_taxonomy
                    """
                )
                rows = cur.fetchall()
        if not rows:
            return {}, []
        for row in rows:
            rd = dict(row)
            hp = rd.get("high_priority")
            if isinstance(hp, str):
                rd["high_priority"] = hp.lower() == "true"
            else:
                rd["high_priority"] = bool(hp)
            key, payload = _classification_row_to_entry(rd)
            classification_data[key] = payload
        unique_categories = sorted(classification_data.keys())
        logger.info("Loaded grievance classification from database (%s categories)", len(unique_categories))
        return classification_data, unique_categories
    except Exception as e:
        logger.debug("Classification DB load skipped or failed: %s", e)
        return {}, []


def load_classification_data(csv_path=DEFAULT_CSV_PATH):
    """
    Load grievance classification: Postgres (grievance_classification_taxonomy) when seeded,
    else CSV under dev-resources. Returns (dict keyed by category display name, sorted keys).
    """
    db_data, db_cats = _load_classification_from_database()
    if db_data:
        return db_data, db_cats

    classification_data: Dict[str, Any] = {}

    try:
        with open(csv_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                category_key = (
                    f"{row['classification'].replace('-', ' ').title()} - "
                    f"{row['generic_grievance_name'].replace('-', ' ').title()}"
                )
                classification_data[category_key] = {
                    "generic_grievance_name": row["generic_grievance_name"],
                    "generic_grievance_name_ne": row["generic_grievance_name_ne"],
                    "short_description": row["short_description"],
                    "short_description_ne": row["short_description_ne"],
                    "classification": row["classification"],
                    "classification_ne": row["classification_ne"],
                    "description": row["description"],
                    "description_ne": row["description_ne"],
                    "follow_up_question_description": row["follow_up_question_description"],
                    "follow_up_question_description_ne": row["follow_up_question_description_ne"],
                    "follow_up_question_quantification": row["follow_up_question_quantification"],
                    "follow_up_question_quantification_ne": row["follow_up_question_quantification_ne"],
                    "high_priority": row["high_priority"].lower() == "true" if row.get("high_priority") else False,
                }

        unique_categories = sorted(classification_data.keys())
        if ENV_SOURCE == "env.local" or os.getenv("WRITE_LOOKUP_FROM_CLASSIFICATION", "").lower() in (
            "1",
            "true",
            "yes",
        ):
            update_lookup_table(unique_categories)

        return classification_data, unique_categories

    except FileNotFoundError:
        logger.error("⚠ Classification CSV file not found: %s", csv_path)
        return {}, []
    except Exception as e:
        logger.error("⚠ Error loading classification data: %s", e)
        return {}, []

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
# LOAD CLASSIFICATION DATA (lazy; prefer DB after seed — see dev-scripts/seed_reference_data.py)
############################

_CLASSIFICATION_CACHE: Tuple[Dict[str, Any], List[str]] | None = None


def __getattr__(name: str) -> Any:
    if name not in ("CLASSIFICATION_DATA", "LIST_OF_CATEGORIES"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    global _CLASSIFICATION_CACHE
    if _CLASSIFICATION_CACHE is None:
        _CLASSIFICATION_CACHE = load_classification_data()
    return _CLASSIFICATION_CACHE[0] if name == "CLASSIFICATION_DATA" else _CLASSIFICATION_CACHE[1]


############################
# LOGGING AND INITIALIZATION
############################

# Log configuration source
logger.info(f"Configuration loaded from: {ENV_SOURCE}")
logger.info(f"Database host: {DB_CONFIG['host']}")
logger.info(f"Database name: {DB_CONFIG['database']}")
logger.info(f"Redis host: {REDIS_HOST}")