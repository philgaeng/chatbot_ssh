import os
import uuid
import psycopg2
import logging
from datetime import datetime
import pytz
from typing import Dict, List, Optional, Any, Sequence, TypeVar, Generic
from psycopg2.extras import DictCursor
import json
import sys
import time
import traceback
from contextlib import contextmanager
# Import database configuration from constants.py (single source of truth)
from backend.config.constants import DB_CONFIG
from backend.logger.logger import TaskLogger
from backend.config.constants import DEFAULT_VALUES, TASK_STATUS, GRIEVANCE_STATUS_DICT, GRIEVANCE_CLASSIFICATION_STATUS_DICT, TRANSCRIPTION_PROCESSING_STATUS_DICT
import hashlib
DEFAULT_TIMEZONE = DEFAULT_VALUES['DEFAULT_TIMEZONE']

# --- Error classes ---
class DatabaseError(Exception):
    """Base exception for database operations"""
    pass

class DatabaseConnectionError(DatabaseError):
    """Exception for database connection issues"""
    pass

class DatabaseQueryError(DatabaseError):
    """Exception for database query issues"""
    pass

class BaseDatabaseManager:
    """Base class for database operations with proper logging and error handling"""
    def __init__(self, logger_name: str = 'db_manager', timezone: Optional[pytz.BaseTzInfo] = pytz.timezone(DEFAULT_TIMEZONE)):
        self.logger = TaskLogger(service_name=logger_name).logger
        self.logger.setLevel(logging.DEBUG)
        self.nepal_tz = timezone
        self.db_params = DB_CONFIG.copy()
        self.logger.info(f"Database parameters: {self.db_params}")
        self.logger.info(f"Database manager initialized successfully")
        self.encryption_key = os.getenv('DB_ENCRYPTION_KEY')
        if not self.encryption_key:
            self.logger.warning("DB_ENCRYPTION_KEY not set - encryption will be disabled")
        else:
            self.logger.info("Encryption enabled for sensitive fields")
        self.DEFAULT_USER = DEFAULT_VALUES['DEFAULT_USER']
        self.ENCRYPTED_FIELDS = {}
        self.HASHED_FIELDS = {}
        self.DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES['DEFAULT_LANGUAGE_CODE']
        self.TASK_STATUS = TASK_STATUS

    def _validate_db_params(self):
        """Validate database connection parameters"""
        required_params = ['host', 'database', 'user', 'password', 'port']
        missing_params = [param for param in required_params if not self.db_params.get(param)]
        if missing_params:
            raise DatabaseConnectionError(f"Missing required database parameters: {', '.join(missing_params)}")

    @contextmanager
    def get_connection(self):
        """Get PostgreSQL connection with context management and logging"""
        conn = None
        start_time = datetime.now()
        try:
            self.logger.info(f"Connecting to database: {self.db_params['database']}")
            conn = psycopg2.connect(**self.db_params, cursor_factory=DictCursor)
            yield conn
        except Exception as e:
            self.logger.error(f"Database connection error: {str(e)}")
            raise DatabaseConnectionError(f"Failed to connect to database: {str(e)}")
        finally:
            if conn:
                duration = (datetime.now() - start_time).total_seconds()
                self.logger.info(f"Database connection closed. Duration: {duration:.2f}s")
                conn.close()

    @contextmanager
    def transaction(self):
        """Transaction context manager with logging"""
        with self.get_connection() as conn:
            try:
                self.logger.info("Starting database transaction")
                yield conn
                conn.commit()
                self.logger.info("Transaction committed successfully")
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Transaction rolled back: {str(e)}")
                raise DatabaseQueryError(f"Transaction failed: {str(e)}")

    @staticmethod
    def setup_logger(name: str, log_file: str) -> logging.Logger:
        """Setup a logger with file and console handlers"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    




    def execute_query(self, query: str, params: tuple = (), operation: str = "query") -> List[Dict]:
        """Execute a query with logging"""
        start_time = datetime.now()
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Executing {operation}: {query[:100]}...")
                    cur.execute(query, params or ())
                    results = [dict(row) for row in cur.fetchall()]
                    duration = (datetime.now() - start_time).total_seconds()
                    self.logger.info(f"{operation} completed in {duration:.2f}s. Rows: {len(results)}")
                    return results
        except Exception as e:
            self.logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"Query execution failed: {str(e)}")

    def execute_update(self, query: str, params: tuple = (), operation: str = "update") -> int:
        """Execute an update query with logging"""
        start_time = datetime.now()
        try:
            with self.transaction() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Executing {operation}: {query[:100]}...")
                    cur.execute(query, params or ())
                    affected_rows = cur.rowcount
                    duration = (datetime.now() - start_time).total_seconds()
                    self.logger.info(f"{operation} completed in {duration:.2f}s. Affected rows: {affected_rows}")
                    return affected_rows
        except Exception as e:
            self.logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"Update execution failed: {str(e)}")

    def execute_insert(self, query: str, params: tuple = (), operation: str = "insert") -> Any:
        """Execute an insert query with logging"""
        start_time = datetime.now()
        try:
            with self.transaction() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Executing {operation}: {query[:100]}...")
                    cur.execute(query, params or ())
                    result = cur.fetchone()
                    duration = (datetime.now() - start_time).total_seconds()
                    self.logger.info(f"{operation} completed in {duration:.2f}s")
                    return result
        except Exception as e:
            self.logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"Insert execution failed: {str(e)}")

    def _encrypt_field(self, value: str) -> Optional[str]:
        """Encrypt a field value using pgcrypto"""
        if not value or not self.encryption_key:
            return value
        try:
            query = "SELECT encode(pgp_sym_encrypt(%s, %s), 'hex') AS encrypted"
            result = self.execute_query(query, (value, self.encryption_key), "encrypt_field")
            return result[0]['encrypted'] if result else value
        except Exception as e:
            self.logger.error(f"Error encrypting field: {str(e)}")
            return value
    
    def _decrypt_field(self, encrypted_value: str) -> Optional[str]:
        """Decrypt a field value using pgcrypto"""
        if not encrypted_value or not self.encryption_key:
            return encrypted_value
        try:
            # Decode the hex string to bytea in SQL using decode(..., 'hex')
            query = "SELECT pgp_sym_decrypt(decode(%s, 'hex'), %s) AS decrypted"
            result = self.execute_query(query, (encrypted_value, self.encryption_key), "decrypt_field")
            return result[0]['decrypted'] if result else encrypted_value
        except Exception as e:
            self.logger.error(f"Error decrypting field: {str(e)}")
            return encrypted_value
    
    def _encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in complainant data"""
        encrypted_data = data.copy()
        for field in self.ENCRYPTED_FIELDS:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self._encrypt_field(encrypted_data[field])
                if field == 'complainant_phone':
                    self.logger.debug(f"encrypted phone number {data[field]} at encrypt_complainant_data: {encrypted_data[field]}")
        return encrypted_data
    
    def _decrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in complainant data"""
        decrypted_data = data.copy()
        for field in self.ENCRYPTED_FIELDS:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self._decrypt_field(decrypted_data[field])
        return decrypted_data

    def _hash_value(self, value: str) -> str:
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def _hash_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Hash sensitive fields in complainant data"""
        hashed_data = {}
        for field in self.HASHED_FIELDS:
            if field in data.keys():
                hashed_key = field + '_hash'
                hashed_data[hashed_key] = self._hash_value(data[field])
                if field == 'complainant_phone':
                    self.logger.debug(f"phone number {data[field]} hashed to {hashed_data[hashed_key]} at hash_sensitive_data")
        return hashed_data

    def get_grievance_or_complainant_source(self, id: str) -> str:
        """Get the source of a grievance or user based on the ID"""
        if id.endswith('-B'):
            return 'bot'
        elif id.endswith('-A'):
            return 'accessible'
        else:
            return 'bot'

    def get_complainant_and_grievance_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get the complainant fields from the data"""
        complainant_fields =  {k: v for k,v in data.items() if 'complainant_' in k}
        grievance_fields = {k: v for k,v in data.items() if 'complainant_' not in k}
        complainant_fields['source']=data.get('source', 'bot')
        grievance_fields['complainant_id']=data.get('complainant_id') 
        return {'complainant_fields':complainant_fields, 'grievance_fields':grievance_fields}

    
    def generate_id(self, type: str='grievance_id', province: str='KO', district: str='JH',  office: str=None, suffix: str='bot'):
        """Generate a unique ID based on type, province, and district"""
        import uuid
        from datetime import datetime

        # Define type mappings
        type_prefixes = {
            'grievance_id': 'GR',
            'complainant_id': 'CM',
            'recording_id': 'REC',
            'transcription_id': 'TR',
            'translation_id': 'TL'
        }
        if office:
            office_suffix = office.upper().replace('_', '')[:3]
        else:
            office_suffix = province.upper()[:2] + district.upper()[:2]


        try:
            prefix = type_prefixes.get(type)
            date_str = datetime.now().strftime('%Y%m%d')

            random_suffix = str(uuid.uuid4())[:4].upper()
            suffix = suffix.upper()[0] if suffix else ''
            
            return f"{prefix}-{date_str}-{office_suffix}-{random_suffix}-{suffix}"

        except Exception as e:
            self.logger.error(f"Error generating ID: {str(e)}")
            # Fallback to a simpler ID format if UUID generation fails
            timestamp = int(time.time() * 1000)
            return f"{prefix}{timestamp}{f'_{suffix}' if suffix else ''}"

    def check_entry_exists_for_entity_key(self, entity_key: str, entity_id: str) -> bool:
        """Check if an entity exists in the database based on entity_key and entity_id
        
        Args:
            entity_key: Type of entity (e.g., 'grievance_id', 'complainant_id', etc.)
            entity_id: ID of the entity to check
            
        Returns:
            bool: True if entity exists, False otherwise
        """
        try:
            if entity_key == 'grievance_id':
                result = self.execute_query(
                    "SELECT grievance_id FROM grievances WHERE grievance_id = %s", 
                    (entity_id,), 
                    "check_grievance_exists"
                )
                
            elif entity_key == 'complainant_id':
                result = self.execute_query(
                    "SELECT id FROM complainants WHERE id = %s", 
                    (entity_id,), 
                    "check_complainant_exists"
                )
                
            elif entity_key == 'recording_id':
                result = self.execute_query(
                    "SELECT recording_id FROM grievance_voice_recordings WHERE recording_id = %s", 
                    (entity_id,), 
                    "check_recording_exists"
                )
                
            elif entity_key == 'transcription_id':
                result = self.execute_query(
                    "SELECT transcription_id FROM grievance_transcriptions WHERE transcription_id = %s", 
                    (entity_id,), 
                    "check_transcription_exists"
                )
                
            elif entity_key == 'translation_id':
                result = self.execute_query(
                    "SELECT translation_id FROM grievance_translations WHERE translation_id = %s", 
                    (entity_id,), 
                    "check_translation_exists"
                )
                
            else:
                self.logger.error(f"Unknown entity key: {entity_key}")
                return False
                
            return len(result) > 0
            
        except Exception as e:
            self.logger.error(f"Error checking entity existence: {str(e)}")
            return False


class TableDbManager(BaseDatabaseManager):
    """Handles schema creation and migration"""
    
    # List of all tables in the correct order (dependencies first)
    ALL_TABLES = [
        'grievance_statuses',
        'processing_statuses',
        'task_statuses',
        'field_names',
        'complainants',
        'office_user',
        'tasks',
        'grievances',
        'task_entities',
        'grievance_status_history',
        'grievance_history',
        'file_attachments',
        'grievance_voice_recordings',
        'grievance_transcriptions',
        'grievance_translations'
    ]

    def __init__(self, **kwargs):
        super().__init__(logger_name='db_manager', **kwargs)
        self.migrations_logger = self.setup_logger('db_migrations', 'logs/db_migrations.log')

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the correct order"""
        return self.ALL_TABLES

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table_name,))
                return cur.fetchone()[0]
        except Exception as e:
            self.migrations_logger.error(f"Error checking if table {table_name} exists: {str(e)}")
            return False

    def recreate_all_tables(self) -> bool:
        """Recreate all tables in the correct order"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                # Drop tables in reverse order of dependency
                self.migrations_logger.info("Dropping tables in reverse order...")
                for table in reversed(self.ALL_TABLES):
                    cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                
                # Create tables and indexes
                self._create_tables(cur)
                self._create_indexes(cur)
                conn.commit()
                self.migrations_logger.info("All tables and indexes recreated successfully")
                return True
        except Exception as e:
            self.migrations_logger.error(f"Error recreating all tables: {str(e)}")
            return False

    def init_db(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
            # Check if database is already initialized
            cur.execute("SELECT to_regclass('grievances')")
            if cur.fetchone()[0] is not None:
                self.migrations_logger.info("Database already initialized")
                return True
            self._create_tables(cur)
            self._create_indexes(cur)
            conn.commit()
            self.migrations_logger.info("Database initialization completed")
            return True
        except Exception as e:
            self.migrations_logger.error(f"Database initialization error: {str(e)}")
            return False

    def recreate_db(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
            # Drop tables in reverse order of dependency
                self.migrations_logger.info("Dropping tables in reverse order...")
                cur.execute("DROP TABLE IF EXISTS grievance_transcriptions CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_translations CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_voice_recordings CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_status_history CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_history CASCADE")
                cur.execute("DROP TABLE IF EXISTS file_attachments CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievances CASCADE")
                cur.execute("DROP TABLE IF EXISTS office_user CASCADE")
                cur.execute("DROP TABLE IF EXISTS complainants CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_statuses CASCADE")
                cur.execute("DROP TABLE IF EXISTS task_statuses CASCADE")
                self._create_tables(cur)
                self._create_indexes(cur)
                conn.commit()
                self.migrations_logger.info("All tables and indexes recreated successfully")
            return True
        except Exception as e:
            self.migrations_logger.error(f"Error recreating database: {str(e)}")
            return False

    def _create_tables(self, cur):
        # Status tables
        self.migrations_logger.info("Creating/recreating grievance_statuses table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_statuses (
                status_code TEXT PRIMARY KEY,
                status_name_en TEXT NOT NULL,
                status_name_ne TEXT NOT NULL,
                description_en TEXT,
                description_ne TEXT,
                is_active BOOLEAN DEFAULT true,
                sort_order INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
         # Initialize default statuses if table is empty
        cur.execute("SELECT COUNT(*) FROM grievance_statuses")
        if cur.fetchone()[0] == 0:
            self.migrations_logger.info("Initializing default grievance statuses...")
            statuses = [(v['code'], v['name_en'], v['name_ne'], v['description_en'], v['description_ne'], 0) for v in GRIEVANCE_STATUS_DICT.values()]
            cur.executemany("INSERT INTO grievance_statuses (status_code, status_name_en, status_name_ne, description_en, description_ne, sort_order) VALUES (%s, %s, %s, %s, %s, %s)", statuses)
            
        
        # Processing statuses table
        self.migrations_logger.info("Creating/recreating processing_statuses table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processing_statuses (
                status_code TEXT PRIMARY KEY,
                status_name TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default processing statuses if not present
        cur.execute("SELECT COUNT(*) FROM processing_statuses")
        if cur.fetchone()[0] == 0:
            self.migrations_logger.info("Initializing default processing statuses...")
            statuses = [(v['code'], v['name'], v['description']) for v in TRANSCRIPTION_PROCESSING_STATUS_DICT.values()]
            cur.executemany("INSERT INTO processing_statuses (status_code, status_name, description) VALUES (%s, %s, %s)", statuses)
        
        
        # Task statuses table
        self.migrations_logger.info("Creating/recreating task_statuses table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_statuses (
                task_status_code TEXT PRIMARY KEY,
                task_status_name TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
      
        
        # Insert default statuses if not present
        cur.execute("SELECT COUNT(*) FROM task_statuses")
        if cur.fetchone()[0] == 0:
            self.migrations_logger.info("Initializing default task statuses...")
            statuses = [
                (TASK_STATUS['SUCCESS'], 'Successful task', 'Task completed successfully'),
                (TASK_STATUS['FAILED'], 'Failed task', 'Task failed'),
                (TASK_STATUS['STARTED'], 'Started', 'Task is started'),
                (TASK_STATUS['RETRYING'], 'Retrying', 'Task is retrying'),
                (TASK_STATUS['ERROR'], 'Error', 'Task has an error'),
                (TASK_STATUS['IN_PROGRESS'], 'In progress', 'Task is in progress')
            ]
            cur.executemany(
                "INSERT INTO task_statuses (task_status_code, task_status_name, description) VALUES (%s, %s, %s)",
                statuses
            )

        # Field types table
        self.migrations_logger.info("Creating/recreating field_names table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS field_names (
                field_name TEXT PRIMARY KEY,
                description TEXT
            )
        """)
        
        # Insert default field types if not present
        cur.execute("SELECT COUNT(*) FROM field_names")
        if cur.fetchone()[0] == 0:
            self.migrations_logger.info("Initializing default field types...")
            cur.execute("""
                INSERT INTO field_names (field_name, description) VALUES
                    ('grievance_description', 'Grievance details'),
                    ('complainant_full_name', 'User full name'),
                    ('complainant_phone', 'User contact phone'),
                    ('complainant_email', 'User contact email'),
                    ('complainant_municipality', 'User municipality'),
                    ('complainant_village', 'User village'),
                    ('complainant_address', 'User address'),
                    ('complainant_province', 'User province'),
                    ('complainant_district', 'User district'),
                    ('complainant_ward', 'User ward'),
                    ('grievance_summary', 'Grievance summary'),
                    ('grievance_categories', 'Grievance categories'),
                    ('grievance_location', 'Grievance location'),
                    ('grievance_claimed_amount', 'Grievance claimed amount')
            """)

        # Users table
        self.migrations_logger.info("Creating/recreating office_user table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS office_user (
                id TEXT PRIMARY KEY,
                us_unique_id TEXT UNIQUE,
                user_name TEXT,
                user_phone TEXT,
                user_email TEXT,
                user_office_id TEXT,
                user_login TEXT,
                user_password TEXT,
                user_role TEXT,
                user_status TEXT,
                user_created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                user_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                user_last_login TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Complainant table
        self.migrations_logger.info("Creating/recreating complainant table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS complainants (
                complainant_id TEXT PRIMARY KEY,
                complainant_unique_id TEXT UNIQUE,
                complainant_full_name TEXT,
                complainant_phone TEXT,
                complainant_email TEXT,
                complainant_province TEXT,
                complainant_district TEXT,
                complainant_municipality TEXT,
                complainant_ward TEXT,
                complainant_village TEXT,
                complainant_address TEXT,
                complainant_phone_hash TEXT,
                complainant_email_hash TEXT,
                complainant_full_name_hash TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tasks table
        self.migrations_logger.info("Creating/recreating tasks table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,  -- This will store Celery's task ID
                task_name TEXT NOT NULL,
                task_status_code TEXT REFERENCES task_statuses(task_status_code),
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT,
                result JSONB,  -- Store task results as JSONB
                retry_count INTEGER DEFAULT 0,
                retry_history JSONB DEFAULT '[]'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Main grievances table with language_code field
        self.migrations_logger.info("Creating/recreating grievances table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievances (
                grievance_id TEXT PRIMARY KEY,
                complainant_id TEXT REFERENCES complainants(complainant_id),
                grievance_categories TEXT,
                grievance_summary TEXT,
                grievance_description TEXT,
                grievance_claimed_amount DECIMAL,
                grievance_location TEXT,
                language_code TEXT DEFAULT 'ne',
                classification_status TEXT DEFAULT 'pending',
                grievance_creation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                grievance_modification_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                is_temporary BOOLEAN DEFAULT TRUE,
                source TEXT DEFAULT 'bot'
            )
        """)

        # Status history table (after grievances table is created)
        self.migrations_logger.info("Creating/recreating grievance_status_history table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_status_history (
                id SERIAL PRIMARY KEY,
                grievance_id TEXT NOT NULL,
                status_code TEXT NOT NULL REFERENCES grievance_statuses(status_code),
                assigned_to TEXT,
                notes TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
            )
        """)
                
        # For backward compatibility - legacy history table
        self.migrations_logger.info("Creating/recreating grievance_history table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_history (
                id SERIAL PRIMARY KEY,
                grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id),
                previous_status TEXT,
                new_status TEXT,
                next_step TEXT,
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # File attachments table
        self.migrations_logger.info("Creating/recreating file_attachments table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS file_attachments (
                id SERIAL PRIMARY KEY,
                file_id UUID NOT NULL,
                grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id),
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Voice recording tables with language_code fields
        self.migrations_logger.info("Creating/recreating grievance_voice_recordings table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_voice_recordings (
                recording_id UUID PRIMARY KEY,
                complainant_id TEXT REFERENCES complainants(complainant_id),
                grievance_id TEXT REFERENCES grievances(grievance_id),
                task_id TEXT,
                file_path TEXT NOT NULL,
                field_name TEXT NOT NULL,
                duration_seconds INTEGER,
                file_size INTEGER,
                processing_status TEXT DEFAULT 'pending' REFERENCES processing_statuses(status_code),
                language_code TEXT,
                language_code_detect TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.migrations_logger.info("Creating/recreating grievance_transcriptions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_transcriptions (
                transcription_id SERIAL PRIMARY KEY,  -- Use SERIAL for auto-increment
                recording_id UUID REFERENCES grievance_voice_recordings(recording_id),
                grievance_id TEXT REFERENCES grievances(grievance_id),
                field_name TEXT NOT NULL,
                automated_transcript TEXT,
                verified_transcript TEXT,
                verification_status TEXT DEFAULT 'pending' REFERENCES processing_statuses(status_code),
                confidence_score FLOAT,
                verification_notes TEXT,
                verified_by TEXT,
                verified_at TIMESTAMP WITH TIME ZONE,
                language_code TEXT,
                language_code_detect TEXT,
                task_id TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Translations table
        self.migrations_logger.info("Creating/recreating grievance_translations table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_translations (
                translation_id SERIAL PRIMARY KEY,  -- Use SERIAL for auto-increment
                grievance_id TEXT REFERENCES grievances(grievance_id),
                task_id TEXT,
                grievance_description_en TEXT,
                grievance_summary_en TEXT,
                grievance_categories_en TEXT,
                source_language TEXT NOT NULL DEFAULT 'ne',
                translation_method TEXT NOT NULL,
                confidence_score FLOAT,
                verified_by TEXT,
                verified_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(grievance_id, translation_method)
            )
        """)

        # Task entities junction table
        self.migrations_logger.info("Creating/recreating task_entities table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_entities (
                task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
                entity_key TEXT NOT NULL CHECK (entity_key IN ('grievance_id', 'complainant_id', 'transcription_id', 'translation_id', 'recording_id', 'task_id', 'ticket_id')),
                entity_id TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, entity_key, entity_id)
            )
        """)
        
        # Create indexes for entity relationships
        self.migrations_logger.info("Creating task entity indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_entities_entity ON task_entities(entity_key, entity_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(task_status_code);
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
            CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed_at);
        """)



    def _create_indexes(self, cur):
        # Task statuses indexes
        self.migrations_logger.info("Creating/recreating task statuses indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_status_active ON task_statuses(is_active);
        """)


        # Users table indexes
        self.migrations_logger.info("Creating/recreating user indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_complainant_phone ON complainants(complainant_phone);
            CREATE INDEX IF NOT EXISTS idx_complainant_email ON complainants(complainant_email);
            CREATE INDEX IF NOT EXISTS idx_complainant_unique_id ON complainants(complainant_unique_id);
        """)

        # Grievances table indexes
        self.migrations_logger.info("Creating/recreating grievances indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_complainant ON grievances(complainant_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_creation_date ON grievances(grievance_creation_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_modification_date ON grievances(grievance_modification_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_source ON grievances(source);
            CREATE INDEX IF NOT EXISTS idx_grievance_temporary ON grievances(is_temporary);
            CREATE INDEX IF NOT EXISTS idx_grievance_language ON grievances(language_code);
        """)

        # Status tables indexes
        self.migrations_logger.info("Creating/recreating status indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_active ON grievance_statuses(is_active);
            CREATE INDEX IF NOT EXISTS idx_status_order ON grievance_statuses(sort_order);
            CREATE INDEX IF NOT EXISTS idx_status_history_grievance ON grievance_status_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_status_history_status ON grievance_status_history(status_code);
            CREATE INDEX IF NOT EXISTS idx_status_history_created ON grievance_status_history(created_at);
            CREATE INDEX IF NOT EXISTS idx_status_history_assigned ON grievance_status_history(assigned_to);
        """)

        # Legacy history table
        self.migrations_logger.info("Creating/recreating history indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_history_id ON grievance_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_new_status ON grievance_history(new_status);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_created ON grievance_history(created_at);
        """)

        # File attachments indexes
        self.migrations_logger.info("Creating/recreating file attachment indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id ON file_attachments(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_file_id ON file_attachments(file_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_upload_timestamp ON file_attachments(upload_timestamp);
        """)

        # Voice recordings indexes
        self.migrations_logger.info("Creating/recreating voice recording indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_grievance_id ON grievance_voice_recordings(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_status ON grievance_voice_recordings(processing_status);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_type ON grievance_voice_recordings(field_name);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_created ON grievance_voice_recordings(created_at);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_language ON grievance_voice_recordings(language_code);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_detected_language ON grievance_voice_recordings(language_code_detect);
        """)

        # Transcriptions indexes
        self.migrations_logger.info("Creating/recreating transcription indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_transcriptions_recording_id ON grievance_transcriptions(recording_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_grievance_id ON grievance_transcriptions(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON grievance_transcriptions(verification_status);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_created ON grievance_transcriptions(created_at);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_language ON grievance_transcriptions(language_code);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_detected_language ON grievance_transcriptions(language_code_detect);
        """)
        
        # Translations indexes
        self.migrations_logger.info("Creating/recreating translation indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_translations_verified ON grievance_translations(verified_at);
            CREATE INDEX IF NOT EXISTS idx_translations_method ON grievance_translations(translation_method);
            CREATE INDEX IF NOT EXISTS idx_translations_source_language ON grievance_translations(source_language);
            CREATE INDEX IF NOT EXISTS idx_translations_created ON grievance_translations(created_at);
        """)
        
    def get_field_names(self) -> List[str]:
        """Get all field names from the field_names table"""
        try:
            query = "SELECT field_name FROM field_names"
            return self.execute_query(query, operation="get_field_names")
        except Exception as e:
            self.logger.error(f"Error getting field names: {str(e)}")
            return []

class TaskDbManager(BaseDatabaseManager):
    """Manager for task-related database operations"""
    
    VALID_ENTITY_KEYS = { 'grievance_id', 'complainant_id', 'recording_id', 'transcription_id', 'translation_id'}
    
    def is_valid_entity_key(self, entity_key: str) -> bool:
        """Check if the entity key is valid"""
        result = entity_key in self.VALID_ENTITY_KEYS
        if not result:
            self.logger.error(f"Invalid entity key: {entity_key}")
        return result
    
    def create_task(self, task_id: str, task_name: str, entity_key: str, entity_id: str) -> Optional[str]:
        """Create a new task record with entity relationship
        
        Args:
            task_id: Celery's generated task ID
            task_name: Name of the task
            entity_key: Key of the entity (grievance_id, complainant_id, etc.) as reference in the task_entities table
            entity_id: ID of the entity
            
        Returns:
            The task ID if successful, None otherwise
        """
        if not self.is_valid_entity_key(entity_key):
            return None
            
        # Check if the referenced entity exists before creating the task
        if not self.check_entry_exists_for_entity_key(entity_key, entity_id):
            self.logger.warning(f"Cannot create task: {entity_key}={entity_id} does not exist in database")
            return None
            
        try:
            with self.transaction() as conn:
                cur = conn.cursor()
                # Create task
                task_query = """
                    INSERT INTO tasks (
                        task_id, task_name, task_status_code
                    ) VALUES (%s, %s, 'PENDING')
                    RETURNING task_id
                """
                cur.execute(task_query, (task_id, task_name))
                task_result = cur.fetchone()
                
                if not task_result:
                    return None
                    
                # Create entity relationship
                entity_query = """
                    INSERT INTO task_entities (
                        task_id, entity_key, entity_id
                    ) VALUES (%s, %s, %s)
                """
                cur.execute(entity_query, (task_id, entity_key, entity_id)) 
                
                self.logger.info(f"Successfully created new task {task_id}")
                return task_id
                
        except DatabaseError as e:
            self.logger.error(f"Failed to create task: {str(e)}")
            return None

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task by ID with its entity relationships"""
        query = """
            SELECT t.*, ts.task_status_name,
                   json_agg(json_build_object(
                       'entity_key', te.entity_key,
                       'entity_id', te.entity_id
                   )) as entities
            FROM tasks t
            JOIN task_statuses ts ON t.task_status_code = ts.task_status_code
            LEFT JOIN task_entities te ON t.task_id = te.task_id
            WHERE t.task_id = %s
            GROUP BY t.task_id, ts.task_status_name
        """
        try:
            results = self.execute_query(query, (task_id,), "get_task")
            return results[0] if results else None
        except DatabaseError as e:
            self.logger.error(f"Failed to get task: {str(e)}")
            return None

    def get_tasks_by_entity_key(self, entity_key: str, entity_id: str) -> List[Dict]:
        """Get all tasks for a specific entity"""
        if not self.is_valid_entity_key(entity_key):
            return []
            
        query = """
            SELECT t.*, ts.status_name,
                   json_agg(json_build_object(
                       'entity_key', te.entity_key,
                       'entity_id', te.entity_id
                   )) as entities
            FROM tasks t
            JOIN task_statuses ts ON t.task_status_code = ts.task_status_code
            JOIN task_entities te ON t.task_id = te.task_id
            WHERE te.entity_key = %s AND te.entity_id = %s
            GROUP BY t.task_id, ts.task_status_name
            ORDER BY t.created_at DESC
        """
        try:
            return self.execute_query(query, (entity_key, entity_id), "get_tasks_by_entity")   
        except DatabaseError as e:
            self.logger.error(f"Failed to get tasks: {str(e)}")
            return []

    def get_pending_tasks(self, entity_key: str = "") -> List[Dict]:
        """Get all pending tasks, optionally filtered by entity type"""
        query = """
            SELECT t.*, ts.status_name,
                   json_agg(json_build_object(
                       'entity_key', te.entity_key,
                       'entity_id', te.entity_id
                   )) as entities
            FROM tasks t
            JOIN task_statuses ts ON t.task_status_code = ts.task_status_code
            LEFT JOIN task_entities te ON t.task_id = te.task_id
            WHERE t.task_status_code = {task_status_code}
            {entity_key_filter}
            GROUP BY t.task_id, ts.task_status_name
            ORDER BY t.created_at ASC
        """
        
        try:
            if entity_key:
                if not self.is_valid_entity_key(entity_key):
                    return []
                query = query.format(entity_key_filter="AND te.entity_key = %s")
                return self.execute_query(query, (self.TASK_STATUS['PENDING'], entity_key), "get_pending_tasks")
            else:
                query = query.format(entity_key_filter="")
                return self.execute_query(query, operation="get_pending_tasks")
        except DatabaseError as e:
            self.logger.error(f"Failed to get pending tasks: {str(e)}")
            return []

    def update_task(self, task_id: str, update_data: dict) -> bool:
        """
        Generic method to update any field(s) in tasks.
        Args:
            task_id: The ID of the task to update
            update_data: Dictionary of field names and new values to update
        Returns:
            bool: True if update was successful, False otherwise
        """
        if not update_data:
            self.logger.warning("No fields to update provided for task")
            return False

        set_clauses = []
        values = []
        for field, value in update_data.items():
            if field in ['task_name',
                'status_code',
                'started_at',
                'completed_at',
                'error_message',
                'retry_count',
                'created_at',
                'updated_at']:
                set_clauses.append(f"{field} = %s")
                # Only JSON-serialize fields that should be JSON
                if field in ['result', 'metadata'] and isinstance(value, dict):  # Add any other fields that should be JSON
                    values.append(json.dumps(value))
                else:
                    values.append(value)
        values.append(task_id)

        query = f"""
            UPDATE tasks
            SET {', '.join(set_clauses)},
                updated_at = CURRENT_TIMESTAMP,
                completed_at = CASE WHEN status_code IN ('SUCCESS', 'FAILED') THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE task_id = %s
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, values)
                if cur.rowcount == 0:
                    self.logger.warning(f"No task found with id {task_id}")
                    return False
                conn.commit()
                self.logger.info(f"Successfully updated task {task_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error updating task {task_id}: {str(e)}")
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get basic task status information without joins
        
        Args:
            task_id: The ID of the task to retrieve
            
        Returns:
            Dict containing task_id, status_code, retry_count, retry_history, error_message
            or None if task not found
        """
        query = """
            SELECT 
                task_id,
                task_status_code,
                retry_count,
                retry_history,
                error_message
            FROM tasks 
            WHERE task_id = %s
        """
        try:
            results = self.execute_query(query, (task_id,), "get_task_status")
            return results[0] if results else None
        except DatabaseError as e:
            self.logger.error(f"Failed to get task status: {str(e)}")
            return None

class FileDbManager(BaseDatabaseManager):
    """Handles file attachment CRUD and lookup logic"""
    def store_file_attachment(self, file_data: Dict) -> bool:
        query = """
            INSERT INTO file_attachments (
                file_id, grievance_id, file_name,
                file_path, file_type, file_size
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            self.execute_update(query, (
                file_data['file_id'],
                file_data['grievance_id'],
                file_data['file_name'],
                file_data['file_path'],
                file_data['file_type'],
                file_data['file_size']
            ), "store_file_attachment")
            return True
        except Exception as e:
            self.logger.error(f"Error storing file attachment: {str(e)}")
            return False
            
    def get_grievance_files(self, grievance_id: str) -> List[Dict]:
        query = """
            SELECT file_id, file_name, file_type, file_size, upload_timestamp
            FROM file_attachments
            WHERE grievance_id = %s
            ORDER BY upload_timestamp DESC
        """
        try:
            return self.execute_query(query, (grievance_id,), "get_grievance_files")
        except Exception as e:
            self.logger.error(f"Error retrieving grievance files: {str(e)}")
            return []
            
    def get_file_by_id(self, file_id: str) -> Optional[Dict]:
        query = """
            SELECT file_id, grievance_id, file_name, file_path, 
                   file_type, file_size, upload_timestamp
            FROM file_attachments
            WHERE file_id = %s
        """
        try:
            results = self.execute_query(query, (file_id,), "get_file_by_id")
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving file by ID: {str(e)}")
            return None

    def is_file_saved(self, file_id: str) -> bool:
        """Check if a file exists in the database
        
        Args:
            file_id (str): The ID of the file to check
            
        Returns:
            bool: True if the file exists in the database, False otherwise
        """
        query = """
            SELECT 1
            FROM file_attachments
            WHERE file_id = %s
        """
        try:
            results = self.execute_query(query, (file_id,), "is_file_saved")
            return bool(results)
        except Exception as e:
            self.logger.error(f"Error checking if file exists: {str(e)}")
            return False

class GSheetDbManager(BaseDatabaseManager):
    
    def get_grievances_for_gsheet(self, status: Optional[str] = None, 
                                 start_date: Optional[str] = None, 
                                 end_date: Optional[str] = None) -> List[Dict]:
        """Get grievances for Google Sheets monitoring with optional filters"""
        query = """
        
            SELECT 
                g.grievance_id,
                g.complainant_id,
                c.complainant_full_name,
                c.complainant_phone,
                c.complainant_municipality,
                c.complainant_village,
                c.complainant_address,
                g.grievance_description,
                g.grievance_summary,
                g.grievance_categories,
                g.grievance_creation_date,
                g.classification_status as status
            FROM grievances g
            LEFT JOIN complainants c ON g.complainant_id = c.id
            WHERE 1=1
            AND g.grievance_description IS NOT NULL
        """
        params = []

        if status:
            query += " AND status = %s"
            params.append(status)
        if start_date:
            query += " AND grievance_creation_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND grievance_creation_date <= %s"
            params.append(end_date)

        query += " ORDER BY grievance_creation_date DESC"

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    
                    grievances = []
                    for row in rows:
                        grievance = dict(zip(columns, row))
                        if grievance.get('grievance_creation_date'):
                            grievance['grievance_creation_date'] = grievance['grievance_creation_date'].isoformat()
                        grievances.append(grievance)
                    
                    return grievances
        except Exception as e:
            self.logger.error(f"Error fetching grievances for GSheet: {str(e)}")
            raise DatabaseQueryError(f"Failed to fetch grievances: {str(e)}")

# --- End moved classes --- 