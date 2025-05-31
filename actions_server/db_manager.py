import os
import uuid
import psycopg2
import psycopg2.extras
import logging
from datetime import datetime
import pytz
from typing import Dict, List, Optional, Any, TypeVar, Generic
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import json
import traceback
from contextlib import contextmanager
import sys
import time

# Load environment variables from .env file
load_dotenv()

# Configure loggingError in db_task operation
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

# Setup loggers
operations_logger = setup_logger('db_operations', 'logs/db_operations.log')
migrations_logger = setup_logger('db_migrations', 'logs/db_migrations.log')
backup_logger = setup_logger('db_backup', 'logs/db_backup.log')

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
    def __init__(self, nepal_tz: Optional[pytz.timezone] = None):
        self.nepal_tz = nepal_tz or pytz.timezone('Asia/Kathmandu')
        self.db_params = {
            'host': os.environ.get('POSTGRES_HOST'),
            'database': os.environ.get('POSTGRES_DB'),
            'user': os.environ.get('POSTGRES_USER'),
            'password': os.environ.get('POSTGRES_PASSWORD'),
            'port': os.environ.get('POSTGRES_PORT')
        }
        self._validate_db_params()

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
            operations_logger.info(f"Connecting to database: {self.db_params['database']}")
            conn = psycopg2.connect(**self.db_params, cursor_factory=DictCursor)
            yield conn
        except Exception as e:
            operations_logger.error(f"Database connection error: {str(e)}")
            raise DatabaseConnectionError(f"Failed to connect to database: {str(e)}")
        finally:
            if conn:
                duration = (datetime.now() - start_time).total_seconds()
                operations_logger.info(f"Database connection closed. Duration: {duration:.2f}s")
                conn.close()

    @contextmanager
    def transaction(self):
        """Transaction context manager with logging"""
        with self.get_connection() as conn:
            try:
                operations_logger.info("Starting database transaction")
                yield conn
                conn.commit()
                operations_logger.info("Transaction committed successfully")
            except Exception as e:
                conn.rollback()
                operations_logger.error(f"Transaction rolled back: {str(e)}")
                raise DatabaseQueryError(f"Transaction failed: {str(e)}")

    def execute_query(self, query: str, params: tuple = None, operation: str = "query") -> List[Dict]:
        """Execute a query with logging"""
        start_time = datetime.now()
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    operations_logger.info(f"Executing {operation}: {query[:100]}...")
                    cur.execute(query, params or ())
                    results = [dict(row) for row in cur.fetchall()]
                    duration = (datetime.now() - start_time).total_seconds()
                    operations_logger.info(f"{operation} completed in {duration:.2f}s. Rows: {len(results)}")
                    return results
        except Exception as e:
            operations_logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"Query execution failed: {str(e)}")

    def execute_update(self, query: str, params: tuple = None, operation: str = "update") -> int:
        """Execute an update query with logging"""
        start_time = datetime.now()
        try:
            with self.transaction() as conn:
                with conn.cursor() as cur:
                    operations_logger.info(f"Executing {operation}: {query[:100]}...")
                    cur.execute(query, params or ())
                    affected_rows = cur.rowcount
                    duration = (datetime.now() - start_time).total_seconds()
                    operations_logger.info(f"{operation} completed in {duration:.2f}s. Affected rows: {affected_rows}")
                    return affected_rows
        except Exception as e:
            operations_logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"Update execution failed: {str(e)}")

    def execute_insert(self, query: str, params: tuple = None, operation: str = "insert") -> Any:
        """Execute an insert query with logging"""
        start_time = datetime.now()
        try:
            with self.transaction() as conn:
                with conn.cursor() as cur:
                    operations_logger.info(f"Executing {operation}: {query[:100]}...")
                    cur.execute(query, params or ())
                    result = cur.fetchone()
                    duration = (datetime.now() - start_time).total_seconds()
                    operations_logger.info(f"{operation} completed in {duration:.2f}s")
                    return result
        except Exception as e:
            operations_logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"Insert execution failed: {str(e)}")
        
    
    def generate_id(self, type: str='grievance_id', province= 'KO', district= 'JH',  suffix=None):
        """Generate a unique ID with format: {prefix}{date}{random_letter}{random_hex}{suffix}"""
        try:
            date = datetime.now().strftime('%Y%m%d')
            prefix = type.upper()[:2]
            province = province.upper()[:2]
            district = district.upper()[:2]
            identifier = province + district + date
            
            # Generate random hex string, ensuring we have enough characters
            random_hex = uuid.uuid4().hex
            if len(random_hex) < 4:
                raise ValueError("Generated UUID hex string is too short")
            random_hex = random_hex[:4].upper()
            # Construct the ID
            id_parts = [prefix, identifier, random_hex]
            if suffix:
                id_parts.append(suffix.upper()[0])
            
            
            return "-".join(id_parts)
        except Exception as e:
            migrations_logger.error(f"Error generating ID: {str(e)}")
            # Fallback to a simpler ID format if UUID generation fails
            timestamp = int(time.time() * 1000)
            return f"{prefix}{timestamp}{f'_{suffix}' if suffix else ''}"


class TableDbManager(BaseDatabaseManager):
    """Handles schema creation and migration"""
    
    # List of all tables in the correct order (dependencies first)
    ALL_TABLES = [
        'grievance_statuses',
        'processing_statuses',
        'task_statuses',
        'field_types',
        'users',
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
            migrations_logger.error(f"Error checking if table {table_name} exists: {str(e)}")
            return False

    def recreate_all_tables(self) -> bool:
        """Recreate all tables in the correct order"""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                # Drop tables in reverse order of dependency
                migrations_logger.info("Dropping tables in reverse order...")
                for table in reversed(self.ALL_TABLES):
                    cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                
                # Create tables and indexes
                self._create_tables(cur)
                self._create_indexes(cur)
                conn.commit()
                migrations_logger.info("All tables and indexes recreated successfully")
                return True
        except Exception as e:
            migrations_logger.error(f"Error recreating all tables: {str(e)}")
            return False

    def init_db(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
            # Check if database is already initialized
            cur.execute("SELECT to_regclass('grievances')")
            if cur.fetchone()[0] is not None:
                migrations_logger.info("Database already initialized")
                return True
            self._create_tables(cur)
            self._create_indexes(cur)
            conn.commit()
            migrations_logger.info("Database initialization completed")
            return True
        except Exception as e:
            migrations_logger.error(f"Database initialization error: {str(e)}")
            return False

    def recreate_db(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
            # Drop tables in reverse order of dependency
                migrations_logger.info("Dropping tables in reverse order...")
                cur.execute("DROP TABLE IF EXISTS grievance_transcriptions CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_translations CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_voice_recordings CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_status_history CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_history CASCADE")
                cur.execute("DROP TABLE IF EXISTS file_attachments CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievances CASCADE")
                cur.execute("DROP TABLE IF EXISTS users CASCADE")
                cur.execute("DROP TABLE IF EXISTS grievance_statuses CASCADE")
                cur.execute("DROP TABLE IF EXISTS task_executions CASCADE")
                cur.execute("DROP TABLE IF EXISTS task_statuses CASCADE")
                self._create_tables(cur)
                self._create_indexes(cur)
                conn.commit()
                migrations_logger.info("All tables and indexes recreated successfully")
            return True
        except Exception as e:
            migrations_logger.error(f"Error recreating database: {str(e)}")
            return False

    def _create_tables(self, cur):
        # Status tables
        migrations_logger.info("Creating/recreating grievance_statuses table...")
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
            migrations_logger.info("Initializing default grievance statuses...")
            cur.execute("""
                INSERT INTO grievance_statuses (status_code, status_name_en, status_name_ne, description_en, description_ne, sort_order) VALUES
                ('TEMP', 'Temporary', 'अस्थायी', 'Initial temporary status for new grievances', 'नयाँ गुनासोहरूको लागि प्रारम्भिक अस्थायी स्थिति', 0),
                ('PENDING', 'Pending', 'प्रतीक्षामा', 'Grievance is pending review', 'गुनासो समीक्षाको लागि प्रतीक्षामा छ', 1),
                ('IN_REVIEW', 'In Review', 'समीक्षामा', 'Grievance is being reviewed', 'गुनासो समीक्षा भइरहेको छ', 2),
                ('IN_PROGRESS', 'In Progress', 'प्रगतिमा', 'Grievance is being addressed', 'गुनासो समाधान भइरहेको छ', 3),
                ('RESOLVED', 'Resolved', 'समाधान भएको', 'Grievance has been resolved', 'गुनासो समाधान भएको छ', 4),
                ('CLOSED', 'Closed', 'बन्द भएको', 'Grievance case is closed', 'गुनासो केस बन्द भएको छ', 5),
                ('REJECTED', 'Rejected', 'अस्वीकृत', 'Grievance has been rejected', 'गुनासो अस्वीकृत भएको छ', 6)
            """)
            
        
        # Processing statuses table
        migrations_logger.info("Creating/recreating processing_statuses table...")
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
            migrations_logger.info("Initializing default processing statuses...")
            cur.execute("""
                INSERT INTO processing_statuses (status_code, status_name, description) VALUES
                ('PENDING', 'Pending', 'Processing is pending'),
                ('PROCESSING', 'Processing', 'Processing is in progress'),
                ('COMPLETED', 'Completed', 'Processing is completed'),
                ('FAILED', 'Failed', 'Processing failed'),
                ('FOR VERIFICATION', 'For Verification', 'Processing is for verification by dedicated team'),
                ('VERIFICATION IN PROGRESS', 'Verification In Progress', 'Verification is in progress by dedicated team'),
                ('VERIFIED', 'Verified', 'Processing is verified by dedicated team'),
                ('VERIFIED AND AMENDED', 'Verified and Amended', 'Results have been verified and amended by dedicated team')
            """)
        
        
        # Task statuses table
        migrations_logger.info("Creating/recreating task_statuses table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_statuses (
                status_code TEXT PRIMARY KEY,
                status_name TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
      
        
        # Insert default statuses if not present
        cur.execute("SELECT COUNT(*) FROM task_statuses")
        if cur.fetchone()[0] == 0:
            migrations_logger.info("Initializing default task statuses...")
            cur.execute("""
                INSERT INTO task_statuses (status_code, status_name, description) VALUES
                ('TEST', 'Test Status', 'For testing'),
                ('SUCCESS', 'Successful task', 'Task completed successfully'),
                ('FAILED', 'Failed task', 'Task failed'),
                ('PENDING', 'Pending task', 'Task is pending'),
                ('QUEUED', 'Queued task', 'Task is queued'),
                ('RUNNING', 'Running task', 'Task is currently running'),
                ('CANCELLED', 'Cancelled task', 'Task was cancelled')
            """)

        # Field types table
        migrations_logger.info("Creating/recreating field_types table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS field_types (
                field_type TEXT PRIMARY KEY,
                description TEXT
            )
        """)
        
        # Insert default field types if not present
        cur.execute("SELECT COUNT(*) FROM field_types")
        if cur.fetchone()[0] == 0:
            migrations_logger.info("Initializing default field types...")
            cur.execute("""
                INSERT INTO field_types (field_type, description) VALUES
                    ('grievance_details', 'Grievance details'),
                    ('user_full_name', 'User full name'),
                    ('user_contact_phone', 'User contact phone'),
                    ('user_contact_email', 'User contact email'),
                    ('user_municipality', 'User municipality'),
                    ('user_village', 'User village'),
                    ('user_address', 'User address'),
                    ('user_province', 'User province'),
                    ('user_district', 'User district'),
                    ('user_ward', 'User ward'),
                    ('grievance_summary', 'Grievance summary'),
                    ('grievance_categories', 'Grievance categories'),
                    ('grievance_location', 'Grievance location'),
                    ('grievance_claimed_amount', 'Grievance claimed amount')
            """)
        
        # Users table
        migrations_logger.info("Creating/recreating users table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                user_unique_id TEXT UNIQUE,
                user_full_name TEXT,
                user_contact_phone TEXT,
                user_contact_email TEXT,
                user_province TEXT,
                user_district TEXT,
                user_municipality TEXT,
                user_ward TEXT,
                user_village TEXT,
                user_address TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tasks table
        migrations_logger.info("Creating/recreating tasks table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,  -- This will store Celery's task ID
                task_name TEXT NOT NULL,
                status_code TEXT REFERENCES task_statuses(status_code),
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
        migrations_logger.info("Creating/recreating grievances table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievances (
                grievance_id TEXT PRIMARY KEY,
                user_id TEXT REFERENCES users(id),
                grievance_categories TEXT,
                grievance_summary TEXT,
                grievance_details TEXT,
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
        migrations_logger.info("Creating/recreating grievance_status_history table...")
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
        migrations_logger.info("Creating/recreating grievance_history table...")
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
        migrations_logger.info("Creating/recreating file_attachments table...")
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
        migrations_logger.info("Creating/recreating grievance_voice_recordings table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_voice_recordings (
                recording_id UUID PRIMARY KEY,
                grievance_id TEXT REFERENCES grievances(grievance_id),
                file_path TEXT NOT NULL,
                recording_type TEXT NOT NULL REFERENCES field_types(field_type),
                duration_seconds INTEGER,
                file_size_bytes INTEGER,
                processing_status TEXT DEFAULT 'pending' REFERENCES processing_statuses(status_code),
                language_code TEXT,
                language_code_detect TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        migrations_logger.info("Creating/recreating grievance_transcriptions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_transcriptions (
                transcription_id UUID PRIMARY KEY,
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
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Translations table
        migrations_logger.info("Creating/recreating grievance_translations table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_translations (
                translation_id UUID PRIMARY KEY,
                grievance_id TEXT REFERENCES grievances(grievance_id),
                grievance_details_en TEXT,
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
        migrations_logger.info("Creating/recreating task_entities table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_entities (
                task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
                entity_type TEXT NOT NULL CHECK (entity_type IN ('grievance', 'user', 'report', 'file', 'recording')),
                entity_id TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, entity_type, entity_id),
                CONSTRAINT fk_entity_grievance 
                    FOREIGN KEY (entity_id) 
                    REFERENCES grievances(grievance_id) 
                    ON DELETE CASCADE
            )
        """)
        
        # Create indexes for entity relationships
        migrations_logger.info("Creating task entity indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_entities_entity ON task_entities(entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status_code);
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
            CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed_at);
        """)



    def _create_indexes(self, cur):
        # Task statuses indexes
        migrations_logger.info("Creating/recreating task statuses indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_status_active ON task_statuses(is_active);
        """)

        # Task executions indexes
        migrations_logger.info("Creating/recreating task executions indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_executions_task_id ON task_executions(task_id);
            CREATE INDEX IF NOT EXISTS idx_task_executions_celery_task_id ON task_executions(celery_task_id);
            CREATE INDEX IF NOT EXISTS idx_task_executions_grievance_id ON task_executions(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_task_executions_status ON task_executions(status_code);
            CREATE INDEX IF NOT EXISTS idx_task_executions_started ON task_executions(started_at);
            CREATE INDEX IF NOT EXISTS idx_task_executions_completed ON task_executions(completed_at);
        """)

        # Users table indexes
        migrations_logger.info("Creating/recreating user indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_phone ON users(user_contact_phone);
            CREATE INDEX IF NOT EXISTS idx_user_email ON users(user_contact_email);
            CREATE INDEX IF NOT EXISTS idx_user_unique_id ON users(user_unique_id);
        """)

        # Grievances table indexes
        migrations_logger.info("Creating/recreating grievances indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_user ON grievances(user_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_creation_date ON grievances(grievance_creation_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_modification_date ON grievances(grievance_modification_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_source ON grievances(source);
            CREATE INDEX IF NOT EXISTS idx_grievance_temporary ON grievances(is_temporary);
            CREATE INDEX IF NOT EXISTS idx_grievance_language ON grievances(language_code);
        """)

        # Status tables indexes
        migrations_logger.info("Creating/recreating status indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_active ON grievance_statuses(is_active);
            CREATE INDEX IF NOT EXISTS idx_status_order ON grievance_statuses(sort_order);
            CREATE INDEX IF NOT EXISTS idx_status_history_grievance ON grievance_status_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_status_history_status ON grievance_status_history(status_code);
            CREATE INDEX IF NOT EXISTS idx_status_history_created ON grievance_status_history(created_at);
            CREATE INDEX IF NOT EXISTS idx_status_history_assigned ON grievance_status_history(assigned_to);
        """)

        # Legacy history table
        migrations_logger.info("Creating/recreating history indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_history_id ON grievance_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_new_status ON grievance_history(new_status);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_created ON grievance_history(created_at);
        """)

        # File attachments indexes
        migrations_logger.info("Creating/recreating file attachment indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id ON file_attachments(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_file_id ON file_attachments(file_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_upload_timestamp ON file_attachments(upload_timestamp);
        """)

        # Voice recordings indexes
        migrations_logger.info("Creating/recreating voice recording indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_grievance_id ON grievance_voice_recordings(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_status ON grievance_voice_recordings(processing_status);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_type ON grievance_voice_recordings(recording_type);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_created ON grievance_voice_recordings(created_at);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_language ON grievance_voice_recordings(language_code);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_detected_language ON grievance_voice_recordings(language_code_detect);
        """)

        # Transcriptions indexes
        migrations_logger.info("Creating/recreating transcription indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_transcriptions_recording_id ON grievance_transcriptions(recording_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_grievance_id ON grievance_transcriptions(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON grievance_transcriptions(verification_status);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_created ON grievance_transcriptions(created_at);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_language ON grievance_transcriptions(language_code);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_detected_language ON grievance_transcriptions(language_code_detect);
        """)
        
        # Translations indexes
        migrations_logger.info("Creating/recreating translation indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_translations_verified ON grievance_translations(verified_at);
            CREATE INDEX IF NOT EXISTS idx_translations_method ON grievance_translations(translation_method);
            CREATE INDEX IF NOT EXISTS idx_translations_source_language ON grievance_translations(source_language);
            CREATE INDEX IF NOT EXISTS idx_translations_created ON grievance_translations(created_at);
        """)

class TaskDbManager(BaseDatabaseManager):
    """Manager for task-related database operations"""
    
    VALID_ENTITY_TYPES = {'grievance', 'user', 'report', 'file', 'recording'}
    
    def create_task(self, task_id: str, task_name: str, entity_type: str, entity_id: str) -> Optional[str]:
        """Create a new task record with entity relationship
        
        Args:
            task_id: Celery's generated task ID
            task_name: Name of the task
            entity_type: Type of entity (grievance, user, etc.)
            entity_id: ID of the entity
            
        Returns:
            The task ID if successful, None otherwise
        """
        if entity_type not in self.VALID_ENTITY_TYPES:
            operations_logger.error(f"Invalid entity type: {entity_type}")
            return None
            
        try:
            with self.transaction() as conn:
                cur = conn.cursor()
                # Create task
                task_query = """
                    INSERT INTO tasks (
                        task_id, task_name, status_code
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
                        task_id, entity_type, entity_id
                    ) VALUES (%s, %s, %s)
                """
                cur.execute(entity_query, (task_id, entity_type, entity_id))
                
                return task_id
                
        except DatabaseError as e:
            operations_logger.error(f"Failed to create task: {str(e)}")
            return None

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task by ID with its entity relationships"""
        query = """
            SELECT t.*, ts.status_name,
                   json_agg(json_build_object(
                       'entity_type', te.entity_type,
                       'entity_id', te.entity_id
                   )) as entities
            FROM tasks t
            JOIN task_statuses ts ON t.status_code = ts.status_code
            LEFT JOIN task_entities te ON t.task_id = te.task_id
            WHERE t.task_id = %s
            GROUP BY t.task_id, ts.status_name
        """
        try:
            results = self.execute_query(query, (task_id,), "get_task")
            return results[0] if results else None
        except DatabaseError as e:
            operations_logger.error(f"Failed to get task: {str(e)}")
            return None

    def get_tasks_by_entity(self, entity_type: str, entity_id: str) -> List[Dict]:
        """Get all tasks for a specific entity"""
        if entity_type not in self.VALID_ENTITY_TYPES:
            operations_logger.error(f"Invalid entity type: {entity_type}")
            return []
            
        query = """
            SELECT t.*, ts.status_name,
                   json_agg(json_build_object(
                       'entity_type', te.entity_type,
                       'entity_id', te.entity_id
                   )) as entities
            FROM tasks t
            JOIN task_statuses ts ON t.status_code = ts.status_code
            JOIN task_entities te ON t.task_id = te.task_id
            WHERE te.entity_type = %s AND te.entity_id = %s
            GROUP BY t.task_id, ts.status_name
            ORDER BY t.created_at DESC
        """
        try:
            return self.execute_query(query, (entity_type, entity_id), "get_tasks_by_entity")
        except DatabaseError as e:
            operations_logger.error(f"Failed to get tasks: {str(e)}")
            return []

    def get_pending_tasks(self, entity_type: str = None) -> List[Dict]:
        """Get all pending tasks, optionally filtered by entity type"""
        query = """
            SELECT t.*, ts.status_name,
                   json_agg(json_build_object(
                       'entity_type', te.entity_type,
                       'entity_id', te.entity_id
                   )) as entities
            FROM tasks t
            JOIN task_statuses ts ON t.status_code = ts.status_code
            LEFT JOIN task_entities te ON t.task_id = te.task_id
            WHERE t.status_code = 'PENDING'
            {entity_type_filter}
            GROUP BY t.task_id, ts.status_name
            ORDER BY t.created_at ASC
        """
        
        try:
            if entity_type:
                if entity_type not in self.VALID_ENTITY_TYPES:
                    operations_logger.error(f"Invalid entity type: {entity_type}")
                    return []
                query = query.format(entity_type_filter="AND te.entity_type = %s")
                return self.execute_query(query, (entity_type,), "get_pending_tasks")
            else:
                query = query.format(entity_type_filter="")
                return self.execute_query(query, operation="get_pending_tasks")
        except DatabaseError as e:
            operations_logger.error(f"Failed to get pending tasks: {str(e)}")
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
            operations_logger.warning("No fields to update provided for task")
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
                    operations_logger.warning(f"No task found with id {task_id}")
                    return False
                conn.commit()
                operations_logger.info(f"Successfully updated task {task_id}")
                return True
        except Exception as e:
            operations_logger.error(f"Error updating task {task_id}: {str(e)}")
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
                status_code,
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
            operations_logger.error(f"Failed to get task status: {str(e)}")
            return None

class GrievanceDbManager(BaseDatabaseManager):
    """Handles grievance CRUD and business logic"""
    
    # Whitelist of fields that can be updated
    ALLOWED_UPDATE_FIELDS = {
        'user_id',
        'grievance_categories',
        'grievance_summary',
        'grievance_details',
        'grievance_claimed_amount',
        'grievance_location',
        'is_temporary',
        'source',
        'language_code',
        'classification_status'
    }

    def create_grievance(self, data: Dict[str, Any] = None) -> Optional[str]:
        """Create a new grievance record"""
        try:
            if not data:
                data = dict()
            
            # Use provided grievance_id or generate new one
            grievance_id = data.get('grievance_id') or self.generate_id(type='grievance_id', suffix=data.get('source', 'bot'))
            operations_logger.info(f"create_grievance: Creating grievance with ID: {grievance_id}")
            
            # Ensure we have a user_id
            user_id = data.get('user_id')
            if not user_id:
                user_id = db_manager.user.create_or_update_user()  # a user_id is required to create a grievance
            
            insert_query = """
                INSERT INTO grievances (
                    grievance_id, user_id, grievance_categories,
                    grievance_summary, grievance_details, grievance_claimed_amount,
                    grievance_location, language_code, is_temporary, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING grievance_id
            """
            result = self.execute_insert(insert_query, (
                grievance_id,
                user_id,
                data.get('grievance_categories'),
                data.get('grievance_summary'),
                data.get('grievance_details'),
                data.get('grievance_claimed_amount'),
                data.get('grievance_location'),
                data.get('language_code', 'ne'),
                data.get('is_temporary', True),
                data.get('source', 'bot')
            ))
            operations_logger.info(f"create_grievance: Successfully created grievance with ID: {grievance_id}")
            return result['grievance_id'] if result else grievance_id
            
        except Exception as e:
            operations_logger.error(f"Error in create_grievance: {str(e)}")
            return None
    
    def update_grievance(self, grievance_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing grievance record"""
        try:
            operations_logger.info(f"update_grievance: Updating grievance with ID: {grievance_id}")
            
            update_query = """
                    UPDATE grievances 
                    SET grievance_categories = %s,
                        grievance_summary = %s,
                        grievance_details = %s,
                        grievance_claimed_amount = %s,
                        grievance_location = %s,
                        language_code = %s,
                        grievance_modification_date = CURRENT_TIMESTAMP
                    WHERE grievance_id = %s
                    RETURNING grievance_id
                """
            result = self.execute_update(update_query, (
                    data.get('grievance_categories'),
                    data.get('grievance_summary'),
                    data.get('grievance_details'),
                    data.get('grievance_claimed_amount'),
                    data.get('grievance_location'),
                    data.get('language_code', 'ne'),
                    grievance_id
                ))
            operations_logger.info(f"update_grievance: Updated grievance with ID: {grievance_id}, rows affected: {result}")
            return result > 0
            
        except Exception as e:
            operations_logger.error(f"Error in update_grievance: {str(e)}")
            return False

    def create_or_update_grievance(self, data: Dict[str, Any] = None) -> Optional[str]:
        """Legacy method - creates or updates grievance based on whether it exists"""
        try:
            if not data:
                data = dict()
            
            grievance_id = data.get('grievance_id')
            operations_logger.info(f"create_or_update_grievance: Handling grievance with ID: {grievance_id}")
            
            if grievance_id:
                # Check if grievance exists
                if self.get_grievance_by_id(grievance_id):
                    # Grievance exists, update it
                    success = self.update_grievance(grievance_id, data)
                    return grievance_id if success else None
                else:
                    # Grievance doesn't exist, create it with provided ID
                    return self.create_grievance(data)
            else:
                # No grievance_id provided, create new one
                return self.create_grievance(data)
                
        except Exception as e:
            operations_logger.error(f"Error in create_or_update_grievance: {str(e)}")
            return None

    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        query = """
                SELECT g.*, u.user_full_name, u.user_contact_phone, u.user_contact_email,
                       u.user_province, u.user_district, u.user_municipality,
                       u.user_ward, u.user_village, u.user_address
                FROM grievances g
                LEFT JOIN users u ON g.user_id = u.id
                WHERE g.grievance_id = %s
        """
        try:
            results = self.execute_query(query, (grievance_id,), "get_grievance_by_id")
            return results[0] if results else None
        except Exception as e:
            operations_logger.error(f"Error retrieving grievance by ID: {str(e)}")
            return None
            
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
            operations_logger.error(f"Error retrieving grievance files: {str(e)}")
            return []

    def get_grievance_status(self, grievance_id: str, language: str = 'en') -> Optional[Dict]:
        query = """
                WITH latest_status AS (
                    SELECT status_code, assigned_to, notes, created_at
                    FROM grievance_status_history
                    WHERE grievance_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                SELECT 
                    h.status_code,
                    CASE WHEN %s = 'en' THEN s.status_name_en ELSE s.status_name_ne END as status_name,
                    CASE WHEN %s = 'en' THEN s.description_en ELSE s.description_ne END as description,
                    h.assigned_to,
                    h.notes,
                    h.created_at as status_date
                FROM latest_status h
                JOIN grievance_statuses s ON h.status_code = s.status_code
        """
        try:
            results = self.execute_query(query, (grievance_id, language, language), "get_grievance_status")
            return results[0] if results else None
        except Exception as e:
            operations_logger.error(f"Error retrieving grievance status: {str(e)}")
            return None
            
    def update_grievance_status(self, grievance_id: str, status_code: str, created_by: str,
                              assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
        try:
            # Verify status code exists and is active
            status_check_query = """
                SELECT status_code FROM grievance_statuses
                WHERE status_code = %s AND is_active = true
            """
            status_check = self.execute_query(status_check_query, (status_code,), "check_status_code")
            if not status_check:
                operations_logger.error(f"Invalid or inactive status code: {status_code}")
                return False
            # Add status history entry
            insert_query = """
                INSERT INTO grievance_status_history (
                    grievance_id, status_code, assigned_to,
                    notes, created_by
                ) VALUES (%s, %s, %s, %s, %s)
            """
            self.execute_update(insert_query, (
                grievance_id,
                status_code,
                assigned_to,
                notes,
                created_by
            ), "insert_status_history")
            # Update grievance modification date
            update_query = """
                UPDATE grievances SET
                    grievance_modification_date = CURRENT_TIMESTAMP
                WHERE grievance_id = %s
            """
            self.execute_update(update_query, (grievance_id,), "update_modification_date")
            return True
        except Exception as e:
            operations_logger.error(f"Error updating grievance status: {str(e)}")
            return False
            
    def get_grievance_status_history(self, grievance_id: str, language: str = 'en') -> List[Dict]:
        query = """
                SELECT 
                    h.status_code,
                    CASE WHEN %s = 'en' THEN s.status_name_en ELSE s.status_name_ne END as status_name,
                    h.assigned_to,
                    h.notes,
                    h.created_by,
                    h.created_at
                FROM grievance_status_history h
                JOIN grievance_statuses s ON h.status_code = s.status_code
                WHERE h.grievance_id = %s
                ORDER BY h.created_at DESC
        """
        try:
            return self.execute_query(query, (language, grievance_id), "get_grievance_status_history")
        except Exception as e:
            operations_logger.error(f"Error retrieving status history: {str(e)}")
            return []
            
    def get_available_statuses(self, language: str = 'en') -> List[Dict]:
        query = """
                SELECT 
                    status_code,
                    CASE WHEN %s = 'en' THEN status_name_en ELSE status_name_ne END as status_name,
                    CASE WHEN %s = 'en' THEN description_en ELSE description_ne END as description,
                    sort_order
                FROM grievance_statuses
                WHERE is_active = true
                ORDER BY sort_order
        """
        try:
            return self.execute_query(query, (language, language), "get_available_statuses")
        except Exception as e:
            operations_logger.error(f"Error retrieving available statuses: {str(e)}")
            return []
            
    def get_grievance_history(self, grievance_id: str) -> List[Dict]:
        query = """
                SELECT id, grievance_id, previous_status, new_status,
                       next_step, notes, created_at
                FROM grievance_history
                WHERE grievance_id = %s
                ORDER BY created_at DESC
        """
        try:
            return self.execute_query(query, (grievance_id,), "get_grievance_history")
        except Exception as e:
            operations_logger.error(f"Error retrieving grievance history: {str(e)}")
            return []

    def is_valid_grievance_id(self, grievance_id: str) -> bool:
        if not grievance_id or not isinstance(grievance_id, str):
            return False
        if not grievance_id.startswith('GR') or not grievance_id[2:].replace('-', '').isalnum():
            return False
        query = "SELECT COUNT(*) FROM grievances WHERE grievance_id = %s"
        try:
            results = self.execute_query(query, (grievance_id,), "is_valid_grievance_id")
            return results[0]['count'] > 0 if results else False
        except Exception as e:
            operations_logger.error(f"Error validating grievance ID: {str(e)}")
            return False
            
            
class UserDbManager(BaseDatabaseManager):
    """Handles user CRUD and lookup logic"""
    
    # Whitelist of fields that can be updated
    ALLOWED_UPDATE_FIELDS = {
        'user_full_name',
        'user_contact_phone',
        'user_contact_email',
        'user_province',
        'user_district',
        'user_municipality',
        'user_ward',
        'user_village',
        'user_address'
    }

    

    def get_users_by_phone_number(self, phone_number: str) -> List[Dict[str, Any]]:
        query = """
            SELECT id, user_unique_id, user_full_name, user_contact_phone,
                   user_contact_email, user_province, user_district,
                   user_municipality, user_ward, user_village, user_address,
                   created_at
            FROM users
            WHERE user_contact_phone = %s
            ORDER BY created_at DESC
        """
        try:
            return self.execute_query(query, (phone_number,), "get_users_by_phone_number")
        except Exception as e:
            operations_logger.error(f"Error retrieving users by phone number: {str(e)}")
            return []
            
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT id, user_unique_id, user_full_name, user_contact_phone,
                   user_contact_email, user_province, user_district,
                   user_municipality, user_ward, user_village, user_address,
                   created_at
            FROM users
            WHERE id = %s
        """
        try:
            results = self.execute_query(query, (user_id,), "get_user_by_id")
            return results[0] if results else None
        except Exception as e:
            operations_logger.error(f"Error retrieving user by id: {str(e)}")
            return None

    def create_user(self, data: Dict[str, Any] = None) -> Optional[str]:
        """Create a new user record"""
        try:
            if not data:
                data = dict()
            
            # Use provided user_id or generate new one
            user_id = data.get('user_id') or self.generate_id(type='user_id')
            operations_logger.info(f"create_user: Creating user with ID: {user_id}")
            
            insert_query = """
                    INSERT INTO users (
                        id, user_unique_id, user_full_name,
                        user_contact_phone, user_contact_email,
                        user_province, user_district, user_municipality,
                        user_ward, user_village, user_address
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
            result = self.execute_insert(insert_query, (
                user_id,
                user_id,  # Use same ID for user_unique_id
                    data.get('user_full_name'),
                    data.get('user_contact_phone'),
                    data.get('user_contact_email'),
                    data.get('user_province'),
                    data.get('user_district'),
                    data.get('user_municipality'),
                    data.get('user_ward'),
                    data.get('user_village'),
                    data.get('user_address')
                ))
            operations_logger.info(f"create_user: Successfully created user with ID: {user_id}")
            return result['id'] if result else user_id
            
        except Exception as e:
            operations_logger.error(f"Error in create_user: {str(e)}")
            return None
    
    def update_user(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing user record"""
        try:
            operations_logger.info(f"update_user: Updating user with ID: {user_id}")
            
            update_query = """
                    UPDATE users 
                    SET user_full_name = %s,
                        user_contact_phone = %s,
                        user_contact_email = %s,
                        user_province = %s,
                        user_district = %s,
                        user_municipality = %s,
                        user_ward = %s,
                        user_village = %s,
                        user_address = %s
                    WHERE id = %s
                    RETURNING id
                """
            result = self.execute_update(update_query, (
                    data.get('user_full_name'),
                    data.get('user_contact_phone'),
                    data.get('user_contact_email'),
                    data.get('user_province'),
                    data.get('user_district'),
                    data.get('user_municipality'),
                    data.get('user_ward'),
                    data.get('user_village'),
                    data.get('user_address'),
                    user_id
                ))
            operations_logger.info(f"update_user: Updated user with ID: {user_id}, rows affected: {result}")
            return result > 0
            
        except Exception as e:
            operations_logger.error(f"Error in update_user: {str(e)}")
            return False

    def create_or_update_user(self, data: Dict[str, Any] = None) -> Optional[str]:
        """Legacy method - creates a user with provided or generated ID"""
        operations_logger.info("create_or_update_user: Using legacy method, redirecting to create_user")
        if data.get('user_id'):
            if self.get_user_by_id(data.get('user_id')):
                return self.update_user(data.get('user_id'), data)
            else:
                return self.create_user(data)
        else:
            return self.create_user(data)
            
    def get_user_from_grievance_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT u.*
            FROM users u
            JOIN grievances g ON u.id = g.user_id
            WHERE g.grievance_id = %s
        """
        try:
            results = self.execute_query(query, (grievance_id,), "get_user_from_grievance_id")
            return results[0] if results else None
        except Exception as e:
            operations_logger.error(f"Error retrieving user from grievance id: {str(e)}")
            return None
        
    def get_user_id_from_grievance_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT user_id
            FROM grievances
            WHERE grievance_id = %s
        """
        try:
            results = self.execute_query(query, (grievance_id,), "get_user_id_from_grievance_id")
            return results[0] if results else None
        except Exception as e:
            operations_logger.error(f"Error retrieving user from grievance id: {str(e)}")
            return None
        
    #create a function to merge different users with same phone number
    def merge_users_with_same_phone_number(self, user_id: int, target_user_id: int) -> bool:
        query = """
            UPDATE grievances
            SET user_id = %s
            WHERE user_id = %s
        """
        try:
            self.execute_update(query, (target_user_id, user_id), "merge_users_with_same_phone_number")
            return True
        except Exception as e:
            operations_logger.error(f"Error merging users with same phone number: {str(e)}")
            return False
        
    def get_users_by_phone_number(self, phone_number: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT id, user_unique_id, user_full_name, user_contact_phone,
                   user_contact_email, user_province, user_district,
                   user_municipality, user_ward, user_village, user_address,
                   created_at
            FROM users
            WHERE user_contact_phone = %s
            ORDER BY created_at ASC
        """
        try:
            results = self.execute_query(query, (phone_number,), "get_users_by_phone_number")
            return results[0] if results else None
        except Exception as e:
            operations_logger.error(f"Error retrieving users by phone number: {str(e)}")
            return None
        
        
    def check_and_merge_users_by_phone_number(self, phone_number: str) -> bool:
        """
        Check and merge users with same phone number
        Args:
            phone_number: The phone number to check and merge users for
        Returns:
            MERGE_SUCCESS: if check and merge was successful, 
            MERGE_FAIL: if users were found but merge failed
            MANUAL_REVIEW_REQUIRED: if users were found but manual review is required
            NO_USERS_FOUND: if no users with same phone number were found
            ERROR_UNKNOWN_PHONE_NUMBER: if there was an error with the phone number
        """
        try:
            users = self.get_users_by_phone_number(phone_number)
            if len(users) ==0:
                return 'ERROR_UNKNOWN_PHONE_NUMBER'
            elif len(users) == 1:
                return 'NO_USERS_FOUND'
            else:
                list_merged_users = []
                list_merge_failed_users = []
                list_manual_review_users = []
                from rapidfuzz import process
                user_names = [users['user_full_name'] for users in users]
                for i in range(len(user_names)):
                    for j in range(i+1, len(user_names)):
                        match_ratio = process.extractOne(user_names[i], user_names[j])
                        if match_ratio[1] > 90:
                            try:
                                self.merge_users_with_same_phone_number(users[i]['user_unique_id'], users[j]['user_unique_id'])
                                list_merged_users.append(users[i]['user_unique_id'])
                                list_merged_users.append(users[j]['user_unique_id'])
                            except Exception as e:
                                list_merge_failed_users.append(users[i]['user_unique_id'])
                                list_merge_failed_users.append(users[j]['user_unique_id'])
                        if match_ratio[1] >70:
                            list_manual_review_users.append(users[i]['user_unique_id'])
                            list_manual_review_users.append(users[j]['user_unique_id'])
                        else:
                            pass
                
                #prepare the response
                list_merged_users = list(set(list_merged_users))
                list_merge_failed_users = list(set(list_merge_failed_users))
                list_manual_review_users = list(set(list_manual_review_users))
                response = {
                    'merged_users': list_merged_users,
                    'merge_failed_users': list_merge_failed_users,
                    'manual_review_users': list_manual_review_users
                }
                if len(list_merged_users) + len(list_merge_failed_users) + len(list_manual_review_users) > 0:
                    return response
                else:
                    return 'NO_USERS_FOUND'
        except Exception as e:
            operations_logger.error(f"Error checking and merging users by phone number: {str(e)}")
            return 'ERROR_UNKNOWN_PHONE_NUMBER'
                



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
            operations_logger.error(f"Error storing file attachment: {str(e)}")
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
            operations_logger.error(f"Error retrieving grievance files: {str(e)}")
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
            operations_logger.error(f"Error retrieving file by ID: {str(e)}")
            return None

class RecordingDbManager(BaseDatabaseManager):
    """Handles voice recording CRUD and lookup logic"""
    def create_or_update_recording(self, recording_data: Dict) -> Optional[str]:
        """Create or update a voice recording record
        
        Args:
            recording_data: Dictionary containing recording data including:
                - recording_id: ID of the recording (optional for updates)
                - grievance_id: ID of the grievance (required)
                - file_path: Path to the recording file
                - file_name: Name of the recording file
                - recording_type: Type of recording (e.g., 'details', 'contact')
                - file_type: Type of file (e.g., 'webm', 'mp3')
                - file_size_bytes: Size of the file in bytes
                - duration_seconds: Duration of the recording in seconds
                - language_code: Language code (defaults to 'ne')
                - processing_status: Status of processing (defaults to 'pending')
                
        Returns:
            str: The recording_id if successful, None otherwise
        """
        try:
            recording_id = recording_data.get('recording_id')
            grievance_id = recording_data.get('grievance_id')
            
            # Validate required fields
            if not grievance_id:
                operations_logger.error("Missing required field: grievance_id")
                return None
                
            if not recording_data.get('file_path') or not recording_data.get('file_name'):
                operations_logger.error("Missing required fields: file_path and file_name")
                return None
            
            if recording_id:
                # Update existing record
                update_query = """
                    UPDATE grievance_voice_recordings 
                    SET file_path = %s,
                        file_name = %s,
                        recording_type = %s,
                        file_type = %s,
                        file_size_bytes = %s,
                        duration_seconds = %s,
                        language_code = %s,
                        processing_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE recording_id = %s
                    RETURNING recording_id
                """
                result = self.execute_update(update_query, (
                    recording_data['file_path'],
                    recording_data['file_name'],
                    recording_data.get('recording_type'),
                    recording_data.get('file_type'),
                    recording_data.get('file_size_bytes'),
                    recording_data.get('duration_seconds'),
                    recording_data.get('language_code', 'ne'),
                    recording_data.get('processing_status', 'pending'),
                    recording_id
                ))
                return recording_id if result > 0 else None
            else:
                # Create new record
                recording_id = str(uuid.uuid4())  # Generate new UUID
                insert_query = """
                    INSERT INTO grievance_voice_recordings (
                        recording_id, grievance_id, file_path,
                        file_name, recording_type, file_type,
                        file_size_bytes, duration_seconds,
                        processing_status, language_code
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING recording_id
                """
                result = self.execute_insert(insert_query, (
                    recording_id,
                    grievance_id,
                    recording_data['file_path'],
                    recording_data['file_name'],
                    recording_data.get('recording_type'),
                    recording_data.get('file_type'),
                    recording_data.get('file_size_bytes'),
                    recording_data.get('duration_seconds'),
                    recording_data.get('processing_status', 'pending'),
                    recording_data.get('language_code', 'ne')
                ))
                return result['recording_id'] if result else recording_id
            
        except Exception as e:
            operations_logger.error(f"Error in store_recording: {str(e)}")
            return None

    def get_transcription_for_recording_id(self, recording_id: str) -> str:
        query = """
            SELECT grievance_id, language_code, automated_transcript, field_name, recording_type 
            FROM grievance_transcriptions 
            LEFT JOIN grievance_voice_recordings 
            ON grievance_transcriptions.recording_id = grievance_voice_recordings.recording_id 
            WHERE recording_id = %s
        """
        try:
            results = self.execute_query(query, (recording_id,), "get_grievance_transcription_for_recording_id")
            return {
                'grievance_id': results[0].get('grievance_id'),
                'language_code': results[0].get('language_code'),
                'automated_transcript': results[0].get('automated_transcript'),
                'field_name': results[0].get('field_name')
            } if results else None
        except Exception as e:
            operations_logger.error(f"Error retrieving grievance transcription for recording ID: {str(e)}")
            return None

    def create_or_update_transcription(self, data: Dict[str, Any]) -> Optional[str]:
        """Create or update a transcription record
        
        Args:
            data: Dictionary containing transcription data including:
                - recording_id: ID of the recording
                - grievance_id: ID of the grievance
                - field_name: Name of the field being transcribed
                - automated_transcript: The transcription text
                - language_code: Language code (defaults to 'ne')
                
        Returns:
            str: The transcription_id if successful, None otherwise
        """
        try:
            transcription_id = data.get('transcription_id')
            recording_id = data.get('recording_id')
            
            # Validate required fields
            if not recording_id:
                if (data.get('grievance_id') and data.get('field_name')):
                    recording_id = db_manager.recording.get_recording_id_for_grievance_id_and_field_name(data['grievance_id'], data['field_name'])
                else:
                    operations_logger.error("Missing required fields for transcription")
                    return None
            
            if not transcription_id:
                # Check if recording exists
                transcription_id = self.get_transcription_for_recording_id(recording_id)
            
            if transcription_id:
                # Update existing record
                update_query = """
                    UPDATE grievance_transcriptions 
                    SET automated_transcript = %s,
                        language_code = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE recording_id = %s
                    RETURNING transcription_id
                """
                result = self.execute_update(update_query, (
                    data['automated_transcript'],
                    data.get('language_code', 'ne'),
                    recording_id
                ))
                if result > 0:
                    # Update verification status in the new verification_statuses table
                    verification_query = """
                        INSERT INTO grievance_verifications (
                            grievance_id, verification_type, status_code
                        ) VALUES (%s, 'transcription', 'PENDING')
                        ON CONFLICT (grievance_id, verification_type) 
                        DO UPDATE SET 
                            status_code = 'PENDING',
                            updated_at = CURRENT_TIMESTAMP
                    """
                    self.execute_update(verification_query, (data['grievance_id'],))
                    return transcription_id
                return None
            else:
                # Create new record
                insert_query = """
                    INSERT INTO grievance_transcriptions (
                        recording_id, grievance_id,
                        field_name, automated_transcript, language_code
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING transcription_id
                """
                result = self.execute_insert(insert_query, (
                    recording_id,
                    data['grievance_id'],
                    data['field_name'],
                    data['automated_transcript'],
                    data.get('language_code', 'ne')
                ))
                if result:
                    # Update verification status in the new verification_statuses table
                    verification_query = """
                        INSERT INTO grievance_verifications (
                            grievance_id, verification_type, status_code
                        ) VALUES (%s, 'transcription', 'PENDING')
                        ON CONFLICT (grievance_id, verification_type) 
                        DO UPDATE SET 
                            status_code = 'PENDING',
                            updated_at = CURRENT_TIMESTAMP
                    """
                    self.execute_update(verification_query, (data['grievance_id'],))
                    return result['transcription_id']
                return None
                
        except Exception as e:
            operations_logger.error(f"Error in create_or_update_transcription: {str(e)}")
            return None

class TranslationDbManager(BaseDatabaseManager):
    def create_or_update_translation(self, data: Dict[str, Any]) -> Optional[str]:
        """Create or update a translation record
        
        Args:
            data: Dictionary containing translation data including:
                - grievance_id: ID of the grievance (required)
                - grievance_details_en: English translation of details
                - grievance_summary_en: English translation of summary
                - grievance_categories_en: English translation of categories
                - translation_method: Method used for translation
                - confidence_score: Confidence score of translation
                - source_language: Source language code (defaults to 'ne')
                
        Returns:
            str: The grievance_id if successful, None otherwise
        """
        try:
            # Validate required fields
            if not data.get('grievance_id'):
                operations_logger.error("Missing required field: grievance_id")
                return None

            # Validate allowed fields
            allowed_fields = {
                'grievance_id',
                'grievance_details_en',
                'grievance_summary_en',
                'grievance_categories_en',
                'translation_method',
                'confidence_score',
                'source_language'
            }
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                operations_logger.error(f"Attempted to update invalid translation fields: {invalid_fields}")
                return None

            grievance_id = data['grievance_id']
            
            # Check if translation exists
            check_query = """
                SELECT grievance_id FROM grievance_translations 
                WHERE grievance_id = %s
            """
            result = self.execute_query(check_query, (grievance_id,))
            
            if result:
                # Update existing record
                update_query = """
                    UPDATE grievance_translations 
                    SET grievance_details_en = %s,
                        grievance_summary_en = %s,
                        grievance_categories_en = %s,
                        translation_method = %s,
                        confidence_score = %s,
                        source_language = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE grievance_id = %s
                    RETURNING translation_id
                """
                result = self.execute_update(update_query, (
                    data.get('grievance_details_en'),
                    data.get('grievance_summary_en'),
                    data.get('grievance_categories_en'),
                    data.get('translation_method'),
                    data.get('confidence_score'),
                    data.get('source_language', 'ne'),
                    grievance_id
                ))
                if result > 0:
                    # Update verification status in the verification table
                    verification_query = """
                        INSERT INTO grievance_verifications (
                            translation_id, verification_type, status_code
                        ) VALUES (%s, 'translation', 'PENDING')
                        ON CONFLICT (translation_id, verification_type) 
                        DO UPDATE SET 
                            status_code = 'PENDING',
                            updated_at = CURRENT_TIMESTAMP
                    """
                    self.execute_update(verification_query, (result,))
                    return result
                return None
            else:
                # Create new record
                insert_query = """
                    INSERT INTO grievance_translations (
                        grievance_id, grievance_details_en,
                        grievance_summary_en, grievance_categories_en,
                        source_language, translation_method,
                        confidence_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING translation_id
                """
                result = self.execute_insert(insert_query, (
                    grievance_id,
                    data.get('grievance_details_en'),
                    data.get('grievance_summary_en'),
                    data.get('grievance_categories_en'),
                    data.get('source_language', 'ne'),
                    data.get('translation_method'),
                    data.get('confidence_score')
                ))
                if result:
                    # Update verification status in the verification table
                    verification_query = """
                        INSERT INTO grievance_verifications (
                            translation_id, verification_type, status_code
                        ) VALUES (%s, 'translation', 'PENDING')
                        ON CONFLICT (translation_id, verification_type) 
                        DO UPDATE SET 
                            status_code = 'PENDING',
                            updated_at = CURRENT_TIMESTAMP
                    """
                    self.execute_update(verification_query, (result,))
                    return result['translation_id']
                return None
                
        except Exception as e:
            operations_logger.error(f"Error in create_or_update_translation: {str(e)}")
            return None

class DatabaseManagers:
    """Unified access point for all database managers"""
    def __init__(self):
        self.table = TableDbManager()
        self.grievance = GrievanceDbManager()
        self.task = TaskDbManager()
        self.user = UserDbManager()
        self.file = FileDbManager()
        self.recording = RecordingDbManager()
        self.translation = TranslationDbManager()
        self.base = BaseDatabaseManager()

# Individual manager instances (kept for backward compatibility)
file_manager = FileDbManager()
schema_manager = TableDbManager()
grievance_manager = GrievanceDbManager()
task_manager = TaskDbManager()
user_manager = UserDbManager()
recording_manager = RecordingDbManager()
translation_manager = TranslationDbManager()
base_manager = BaseDatabaseManager()
# Unified manager instance
db_manager = DatabaseManagers() 