# Location Constants
QR_PROVINCE = "KOSHI"
QR_DISTRICT = "Jhapa"
DISTRICT_LIST = ['Jhapa', 'Morang', 'Sunsari']

# You can add other constants here, organized by category
# For example:

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
    "WorldLink Email": ["worldlink.com.np"]
}


WHITELIST_PHONE_NUMBERS_OTP_TESTING = ["+639175330841", "+639154345604"]