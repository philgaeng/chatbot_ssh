import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

############################
# GRM SYSTEM CONFIGURATION
############################

# GRM MySQL Database Configuration
GRM_MYSQL_CONFIG = {
    'host': os.getenv('GRM_MYSQL_HOST', 'localhost'),
    'database': os.getenv('GRM_MYSQL_DB', 'grm_database'),
    'user': os.getenv('GRM_MYSQL_USER', 'grm_user'),
    'password': os.getenv('GRM_MYSQL_PASSWORD', ''),
    'port': int(os.getenv('GRM_MYSQL_PORT', '3306')),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': False,
    'pool_name': 'grm_pool',
    'pool_size': 5,
    'pool_reset_session': True,
    'connect_timeout': 60,
    'read_timeout': 30,
    'write_timeout': 30
}

# GRM System Integration Settings
GRM_INTEGRATION_CONFIG = {
    'enabled': os.getenv('GRM_INTEGRATION_ENABLED', 'false').lower() == 'true',
    'sync_interval_minutes': int(os.getenv('GRM_SYNC_INTERVAL_MINUTES', '5')),
    'auto_sync_grievances': os.getenv('GRM_AUTO_SYNC_GRIEVANCES', 'true').lower() == 'true',
    'sync_status_updates': os.getenv('GRM_SYNC_STATUS_UPDATES', 'true').lower() == 'true',
    'retry_failed_syncs': os.getenv('GRM_RETRY_FAILED_SYNCS', 'true').lower() == 'true',
    'max_retry_attempts': int(os.getenv('GRM_MAX_RETRY_ATTEMPTS', '3')),
    'retry_delay_seconds': int(os.getenv('GRM_RETRY_DELAY_SECONDS', '30'))
}

# GRM Database Schema Mapping
# Map your chatbot fields to GRM system fields
GRM_FIELD_MAPPING = {
    # User/Complainant Information
    'user_full_name': 'complainant_name',
    'user_contact_phone': 'contact_phone',
    'user_contact_email': 'contact_email',
    'user_province': 'province',
    'user_district': 'district',
    'user_municipality': 'municipality',
    'user_ward': 'ward',
    'user_village': 'village',
    'user_address': 'address',
    
    # Grievance Information
    'grievance_id': 'grievance_id',
    'grievance_details': 'grievance_description',
    'grievance_summary': 'grievance_summary',
    'grievance_categories': 'grievance_category',
    'grievance_location': 'location',
    'grievance_claimed_amount': 'claimed_amount',
    
    # System Fields
    'grievance_creation_date': 'submission_date',
    'classification_status': 'processing_status',
    'language_code': 'language'
}

# GRM Status Mapping
# Map your chatbot statuses to GRM system statuses
GRM_STATUS_MAPPING = {
    'pending': 'pending',
    'submitted': 'submitted',
    'under_evaluation': 'under_evaluation',
    'escalated': 'escalated',
    'resolved': 'resolved',
    'denied': 'denied',
    'LLM_generated': 'pending',
    'LLM_failed': 'pending',
    'user_confirmed': 'submitted',
    'officer_confirmed': 'under_evaluation'
}

# GRM Table Names (adjust based on actual GRM schema)
GRM_TABLE_NAMES = {
    'grievances': 'grievances',
    'complainants': 'complainants',
    'grievance_status': 'grievance_status',
    'officers': 'officers',
    'departments': 'departments',
    'categories': 'grievance_categories'
}

# SSH Tunnel Configuration (if needed for remote connection)
SSH_TUNNEL_CONFIG = {
    'enabled': os.getenv('GRM_SSH_TUNNEL_ENABLED', 'false').lower() == 'true',
    'ssh_host': os.getenv('GRM_SSH_HOST', ''),
    'ssh_port': int(os.getenv('GRM_SSH_PORT', '22')),
    'ssh_user': os.getenv('GRM_SSH_USER', ''),
    'ssh_key_path': os.getenv('GRM_SSH_KEY_PATH', ''),
    'ssh_password': os.getenv('GRM_SSH_PASSWORD', ''),
    'local_bind_port': int(os.getenv('GRM_LOCAL_BIND_PORT', '3307')),
    'remote_bind_port': int(os.getenv('GRM_REMOTE_BIND_PORT', '3306'))
}

############################
# CONNECTION TESTING
############################

def test_grm_connection() -> Dict[str, Any]:
    """Test connection to GRM system and return status"""
    try:
        from backend.services.database_services.mysql_services import MySQLDatabaseManager
        
        db_manager = MySQLDatabaseManager()
        
        if db_manager.test_connection():
            db_info = db_manager.get_database_info()
            tables = db_manager.get_all_tables()
            
            return {
                'status': 'success',
                'message': 'GRM connection successful',
                'database_info': db_info,
                'table_count': len(tables),
                'sample_tables': tables[:10] if tables else []
            }
        else:
            return {
                'status': 'error',
                'message': 'GRM connection failed',
                'database_info': {},
                'table_count': 0,
                'sample_tables': []
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'GRM connection test failed: {str(e)}',
            'database_info': {},
            'table_count': 0,
            'sample_tables': []
        }

def get_grm_config_summary() -> Dict[str, Any]:
    """Get a summary of GRM configuration"""
    return {
        'mysql_config': {
            'host': GRM_MYSQL_CONFIG['host'],
            'database': GRM_MYSQL_CONFIG['database'],
            'port': GRM_MYSQL_CONFIG['port'],
            'user': GRM_MYSQL_CONFIG['user']
        },
        'integration_config': GRM_INTEGRATION_CONFIG,
        'ssh_tunnel_enabled': SSH_TUNNEL_CONFIG['enabled'],
        'field_mapping_count': len(GRM_FIELD_MAPPING),
        'status_mapping_count': len(GRM_STATUS_MAPPING)
    }

############################
# ENVIRONMENT VALIDATION
############################

def validate_grm_environment() -> Dict[str, Any]:
    """Validate that all required GRM environment variables are set"""
    required_vars = [
        'GRM_MYSQL_HOST',
        'GRM_MYSQL_DB', 
        'GRM_MYSQL_USER',
        'GRM_MYSQL_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    return {
        'valid': len(missing_vars) == 0,
        'missing_variables': missing_vars,
        'recommendation': 'Set missing environment variables in your .env file' if missing_vars else 'All required variables are set'
    }

if __name__ == "__main__":
    # Print configuration summary
    print("=== GRM Configuration Summary ===")
    summary = get_grm_config_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    print("\n=== Environment Validation ===")
    validation = validate_grm_environment()
    print(f"Valid: {validation['valid']}")
    if not validation['valid']:
        print(f"Missing variables: {validation['missing_variables']}")
        print(f"Recommendation: {validation['recommendation']}")
    
    print("\n=== Connection Test ===")
    connection_test = test_grm_connection()
    print(f"Status: {connection_test['status']}")
    print(f"Message: {connection_test['message']}")
    if connection_test['status'] == 'success':
        print(f"Database: {connection_test['database_info'].get('database_name')}")
        print(f"Tables: {connection_test['table_count']}") 