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

# Load environment variables from .env file
load_dotenv()

# Configure logging
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

class TaskManager(BaseDatabaseManager):
    """Manager for task-related database operations"""
    
    def create_task_status(self, status_code: str, status_name: str, description: str = None) -> bool:
        """Create a new task status"""
        query = """
            INSERT INTO task_statuses (status_code, status_name, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (status_code) DO UPDATE
            SET status_name = EXCLUDED.status_name,
                description = EXCLUDED.description,
                updated_at = CURRENT_TIMESTAMP
        """
        try:
            self.execute_update(query, (status_code, status_name, description), "create_task_status")
            return True
        except DatabaseError as e:
            operations_logger.error(f"Failed to create task status: {str(e)}")
            return False

    def get_task_status(self, status_code: str) -> Optional[Dict]:
        """Get task status by code"""
        query = "SELECT * FROM task_statuses WHERE status_code = %s"
        try:
            results = self.execute_query(query, (status_code,), "get_task_status")
            return results[0] if results else None
        except DatabaseError as e:
            operations_logger.error(f"Failed to get task status: {str(e)}")
            return None

    def create_task_execution(self, task_id: str, grievance_id: str, celery_task_id: str = None) -> Optional[int]:
        """Create a new task execution record"""
        query = """
            INSERT INTO task_executions (task_id, grievance_id, celery_task_id, status_code)
            VALUES (%s, %s, %s, 'PENDING')
            RETURNING id
        """
        try:
            result = self.execute_insert(query, (task_id, grievance_id, celery_task_id), "create_task_execution")
            return result[0] if result else None
        except DatabaseError as e:
            operations_logger.error(f"Failed to create task execution: {str(e)}")
            return None

    def update_task_execution_status(self, execution_id: int, status_code: str, error_message: str = None) -> bool:
        """Update task execution status"""
        query = """
            UPDATE task_executions
            SET status_code = %s,
                error_message = %s,
                completed_at = CASE WHEN %s IN ('COMPLETED', 'FAILED') THEN CURRENT_TIMESTAMP ELSE NULL END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        try:
            self.execute_update(query, (status_code, error_message, status_code, execution_id), "update_task_execution")
            return True
        except DatabaseError as e:
            operations_logger.error(f"Failed to update task execution: {str(e)}")
            return False

    def get_task_execution(self, execution_id: int) -> Optional[Dict]:
        """Get task execution by ID"""
        query = """
            SELECT te.*, ts.status_name
            FROM task_executions te
            JOIN task_statuses ts ON te.status_code = ts.status_code
            WHERE te.id = %s
        """
        try:
            results = self.execute_query(query, (execution_id,), "get_task_execution")
            return results[0] if results else None
        except DatabaseError as e:
            operations_logger.error(f"Failed to get task execution: {str(e)}")
            return None

    def get_task_executions_by_grievance(self, grievance_id: str) -> List[Dict]:
        """Get all task executions for a grievance"""
        query = """
            SELECT te.*, ts.status_name
            FROM task_executions te
            JOIN task_statuses ts ON te.status_code = ts.status_code
            WHERE te.grievance_id = %s
            ORDER BY te.created_at DESC
        """
        try:
            return self.execute_query(query, (grievance_id,), "get_task_executions_by_grievance")
        except DatabaseError as e:
            operations_logger.error(f"Failed to get task executions: {str(e)}")
            return []

    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks"""
        query = """
            SELECT te.*, ts.status_name
            FROM task_executions te
            JOIN task_statuses ts ON te.status_code = ts.status_code
            WHERE te.status_code = 'PENDING'
            ORDER BY te.created_at ASC
        """
        try:
            return self.execute_query(query, operation="get_pending_tasks")
        except DatabaseError as e:
            operations_logger.error(f"Failed to get pending tasks: {str(e)}")
            return []

# Create singleton instances
db_manager = BaseDatabaseManager()
task_manager = TaskManager()

class DatabaseManager:
    """PostgreSQL database manager class"""
    def __init__(self, nepal_tz: Optional[pytz.timezone] = None, default_value: str = 'NOT_PROVIDED'):
        # Common attributes
        self.nepal_tz = nepal_tz or pytz.timezone('Asia/Kathmandu')
        self.default_value = default_value
        
        # Database connection parameters
        self.db_params = {
            'host': os.environ.get('POSTGRES_HOST'),
            'database': os.environ.get('POSTGRES_DB'),
            'user': os.environ.get('POSTGRES_USER'),
            'password': os.environ.get('POSTGRES_PASSWORD'),
            'port': os.environ.get('POSTGRES_PORT')
        }

    def get_connection(self):
        """Get PostgreSQL connection"""
        try:
            logger.info(f"Connecting to PostgreSQL database with params: host={self.db_params['host']}, database={self.db_params['database']}, port={self.db_params['port']}")
            return psycopg2.connect(
                **self.db_params,
                cursor_factory=DictCursor
            )
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def generate_grievance_id(self, source: str = 'bot') -> str:
        """Generate a unique grievance ID using Nepal time and UUID.
        
        Args:
            source (str): Source of the grievance - 'accessibility' or 'bot'
            
        Returns:
            str: A unique grievance ID in the format GR{YYYYMMDD}{UUID[:6]}_{A|B}
        """
        suffix = '_A' if source == 'accessibility' else '_B'
        return f"GR{datetime.now(self.nepal_tz).strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}{suffix}"

    def init_db(self):
        """Initialize the database tables and indexes"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cur = conn.cursor()
            
            # Check if database is already initialized
            cur.execute("SELECT to_regclass('grievances')")
            if cur.fetchone()[0] is not None:
                logger.info("Database already initialized")
                return True
            
            # Create tables
            self._create_tables(cur)
            
            # Create indexes
            self._create_indexes(cur)
            
            conn.commit()
            logger.info("Database initialization completed")
            return True
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            if conn:
                conn.rollback()
            return False
        finally:
            if 'cur' in locals() and cur:
                cur.close()
            if 'conn' in locals() and conn:
                conn.close()

    def recreate_db(self):
        """Drop and recreate all database tables with updated schema"""
        try:
            conn = self.get_connection()
            if not conn:
                logger.error("Failed to connect to database")
                return False
            
            cur = conn.cursor()
            
            # Drop tables in reverse order of dependency
            logger.info("Dropping tables in reverse order...")
            
            # Drop tables with foreign key dependencies first
            cur.execute("DROP TABLE IF EXISTS grievance_transcriptions CASCADE")
            cur.execute("DROP TABLE IF EXISTS grievance_translations CASCADE")
            cur.execute("DROP TABLE IF EXISTS grievance_voice_recordings CASCADE")
            cur.execute("DROP TABLE IF EXISTS grievance_status_history CASCADE")
            cur.execute("DROP TABLE IF EXISTS grievance_history CASCADE")
            cur.execute("DROP TABLE IF EXISTS file_attachments CASCADE")
            cur.execute("DROP TABLE IF EXISTS grievances CASCADE")
            cur.execute("DROP TABLE IF EXISTS users CASCADE")
            cur.execute("DROP TABLE IF EXISTS grievance_statuses CASCADE")
            
            # Create tables with updated schema
            self._create_tables(cur)
            
            # Create indexes
            self._create_indexes(cur)
            
            conn.commit()
            logger.info("All tables and indexes recreated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error recreating database: {str(e)}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if 'cur' in locals() and cur:
                cur.close()
            if 'conn' in locals() and conn:
                conn.close()

    def _create_tables(self, cur):
        """Create PostgreSQL tables"""
        # Status tables
        logger.info("Creating/recreating grievance_statuses table...")
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

        # Task statuses table
        logger.info("Creating/recreating task_statuses table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_statuses (
                status_code TEXT PRIMARY KEY,
                status_name TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Task executions table
        logger.info("Creating/recreating task_executions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_executions (
                id SERIAL PRIMARY KEY,
                task_id TEXT NOT NULL,
                celery_task_id TEXT,
                grievance_id TEXT REFERENCES grievances(grievance_id),
                status_code TEXT REFERENCES task_statuses(status_code),
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Users table
        logger.info("Creating/recreating users table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
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

        # Main grievances table with language_code field
        logger.info("Creating/recreating grievances table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievances (
                grievance_id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
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
        logger.info("Creating/recreating grievance_status_history table...")
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
        logger.info("Creating/recreating grievance_history table...")
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
        logger.info("Creating/recreating file_attachments table...")
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
        logger.info("Creating/recreating grievance_voice_recordings table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_voice_recordings (
                recording_id UUID PRIMARY KEY,
                grievance_id TEXT REFERENCES grievances(grievance_id),
                file_path TEXT NOT NULL,
                recording_type TEXT NOT NULL CHECK (recording_type IN ('details', 'contact', 'location')),
                duration_seconds INTEGER,
                file_size_bytes INTEGER,
                processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'transcribing', 'transcribed', 'failed')),
                language_code TEXT,
                language_code_detect TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.info("Creating/recreating grievance_transcriptions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_transcriptions (
                transcription_id UUID PRIMARY KEY,
                recording_id UUID REFERENCES grievance_voice_recordings(recording_id),
                grievance_id TEXT REFERENCES grievances(grievance_id),
                automated_transcript TEXT,
                verified_transcript TEXT,
                verification_status TEXT DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected')),
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
        logger.info("Creating/recreating grievance_translations table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_translations (
                grievance_id TEXT PRIMARY KEY REFERENCES grievances(grievance_id),
                grievance_details_en TEXT,
                grievance_summary_en TEXT,
                grievance_categories_en TEXT,
                source_language TEXT NOT NULL DEFAULT 'ne',
                translation_method TEXT NOT NULL,
                confidence_scores JSONB DEFAULT '{"details": null, "summary": null, "categories": null}'::jsonb,
                verified_by TEXT,
                verified_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize default statuses if table is empty
        cur.execute("SELECT COUNT(*) FROM grievance_statuses")
        if cur.fetchone()[0] == 0:
            logger.info("Initializing default grievance statuses...")
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

    def _create_indexes(self, cur):
        """Create PostgreSQL indexes"""
        # Task statuses indexes
        logger.info("Creating/recreating task statuses indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_status_active ON task_statuses(is_active);
        """)

        # Task executions indexes
        logger.info("Creating/recreating task executions indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_executions_task_id ON task_executions(task_id);
            CREATE INDEX IF NOT EXISTS idx_task_executions_celery_task_id ON task_executions(celery_task_id);
            CREATE INDEX IF NOT EXISTS idx_task_executions_grievance_id ON task_executions(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_task_executions_status ON task_executions(status_code);
            CREATE INDEX IF NOT EXISTS idx_task_executions_started ON task_executions(started_at);
            CREATE INDEX IF NOT EXISTS idx_task_executions_completed ON task_executions(completed_at);
        """)

        # Users table indexes
        logger.info("Creating/recreating user indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_phone ON users(user_contact_phone);
            CREATE INDEX IF NOT EXISTS idx_user_email ON users(user_contact_email);
            CREATE INDEX IF NOT EXISTS idx_user_unique_id ON users(user_unique_id);
        """)

        # Grievances table indexes
        logger.info("Creating/recreating grievances indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_user ON grievances(user_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_creation_date ON grievances(grievance_creation_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_modification_date ON grievances(grievance_modification_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_source ON grievances(source);
            CREATE INDEX IF NOT EXISTS idx_grievance_temporary ON grievances(is_temporary);
            CREATE INDEX IF NOT EXISTS idx_grievance_language ON grievances(language_code);
        """)

        # Status tables indexes
        logger.info("Creating/recreating status indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_active ON grievance_statuses(is_active);
            CREATE INDEX IF NOT EXISTS idx_status_order ON grievance_statuses(sort_order);
            CREATE INDEX IF NOT EXISTS idx_status_history_grievance ON grievance_status_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_status_history_status ON grievance_status_history(status_code);
            CREATE INDEX IF NOT EXISTS idx_status_history_created ON grievance_status_history(created_at);
            CREATE INDEX IF NOT EXISTS idx_status_history_assigned ON grievance_status_history(assigned_to);
        """)

        # Legacy history table
        logger.info("Creating/recreating history indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_history_id ON grievance_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_new_status ON grievance_history(new_status);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_created ON grievance_history(created_at);
        """)

        # File attachments indexes
        logger.info("Creating/recreating file attachment indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id ON file_attachments(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_file_id ON file_attachments(file_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_upload_timestamp ON file_attachments(upload_timestamp);
        """)

        # Voice recordings indexes
        logger.info("Creating/recreating voice recording indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_grievance_id ON grievance_voice_recordings(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_status ON grievance_voice_recordings(processing_status);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_type ON grievance_voice_recordings(recording_type);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_created ON grievance_voice_recordings(created_at);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_language ON grievance_voice_recordings(language_code);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_detected_language ON grievance_voice_recordings(language_code_detect);
        """)

        # Transcriptions indexes
        logger.info("Creating/recreating transcription indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_transcriptions_recording_id ON grievance_transcriptions(recording_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_grievance_id ON grievance_transcriptions(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON grievance_transcriptions(verification_status);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_created ON grievance_transcriptions(created_at);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_language ON grievance_transcriptions(language_code);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_detected_language ON grievance_transcriptions(language_code_detect);
        """)
        
        # Translations indexes
        logger.info("Creating/recreating translation indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_translations_verified ON grievance_translations(verified_at);
            CREATE INDEX IF NOT EXISTS idx_translations_method ON grievance_translations(translation_method);
            CREATE INDEX IF NOT EXISTS idx_translations_source_language ON grievance_translations(source_language);
            CREATE INDEX IF NOT EXISTS idx_translations_created ON grievance_translations(created_at);
        """)

    def create_grievance(self, source: str = 'bot', language_code: str = 'ne') -> Optional[str]:
        """Create a minimal grievance record with temporary status
        
        Args:
            source: Source of the grievance (bot, accessibility, etc.)
            language_code: Language code (default: 'ne' for Nepali)
            
        Returns:
            Grievance ID if successful, None if failed
        """
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if not conn:
                return None
            
            cur = conn.cursor()
            
            # Generate unique ID for the grievance
            grievance_id = self.generate_grievance_id(source)
            
            # Get the current date
            nepal_today = datetime.now(self.nepal_tz).strftime('%Y-%m-%d %H:%M:%S') if self.nepal_tz else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Insert into grievances table
            cur.execute("""
                INSERT INTO grievances (
                    grievance_id, grievance_creation_date, grievance_modification_date, is_temporary, source, language_code
                ) VALUES (%s, %s, %s, TRUE, %s, %s)
                RETURNING grievance_id
            """, (grievance_id, nepal_today, nepal_today, source, language_code))
            
            result = cur.fetchone()
            
            if not result:
                raise ValueError("Failed to create grievance record")
            
            # Commit the transaction to ensure the grievance exists in the database
            conn.commit()
            
            # Now set the initial status in a separate transaction
            success = self.update_grievance_status(grievance_id, 'TEMP', 'system')
            if not success:
                logger.warning(f"Failed to set initial status for grievance {grievance_id}, but grievance was created")
            
            return grievance_id
            
        except Exception as e:
            logger.error(f"Error creating grievance: {str(e)}")
            if conn:
                conn.rollback()
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def update_grievance_db(self, grievance_data: Dict) -> Optional[str]:
        """Update an existing grievance with complete data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            grievance_id = grievance_data.get('grievance_id')
            if not grievance_id:
                logger.error("No grievance_id provided for update")
                return None
            
            user_full_name = grievance_data.get('user_full_name', self.default_value)
            user_phone = grievance_data.get('user_contact_phone', self.default_value)
            
            # Check if user exists based on phone and name (if name is provided)
            if user_full_name != self.default_value:
                cursor.execute("""
                    SELECT id FROM users 
                    WHERE user_contact_phone = %s AND user_full_name = %s
                """, (user_phone, user_full_name))
            else:
                cursor.execute("""
                    SELECT id FROM users 
                    WHERE user_contact_phone = %s
                """, (user_phone,))
            
            user_result = cursor.fetchone()
            
            if user_result is None:
                # User doesn't exist, insert new user
                cursor.execute("""
                    INSERT INTO users (
                        user_unique_id, user_full_name, user_contact_phone,
                        user_contact_email, user_province, user_district,
                        user_municipality, user_ward, user_village, user_address
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    grievance_data.get('user_unique_id'),
                    user_full_name,
                    user_phone,
                    grievance_data.get('user_contact_email', self.default_value),
                    grievance_data.get('user_province', self.default_value),
                    grievance_data.get('user_district', self.default_value),
                    grievance_data.get('user_municipality', self.default_value),
                    grievance_data.get('user_ward', self.default_value),
                    grievance_data.get('user_village', self.default_value),
                    grievance_data.get('user_address', self.default_value)
                ))
                user_id = cursor.fetchone()[0]
            else:
                # User exists, update user
                cursor.execute("""
                    UPDATE users SET
                        user_unique_id = %s,
                        user_full_name = %s,
                        user_contact_email = %s,
                        user_province = %s,
                        user_district = %s,
                        user_municipality = %s,
                        user_ward = %s,
                        user_village = %s,
                        user_address = %s
                    WHERE id = %s
                    RETURNING id
                """, (
                    grievance_data.get('user_unique_id'),
                    user_full_name,
                    grievance_data.get('user_contact_email', self.default_value),
                    grievance_data.get('user_province', self.default_value),
                    grievance_data.get('user_district', self.default_value),
                    grievance_data.get('user_municipality', self.default_value),
                    grievance_data.get('user_ward', self.default_value),
                    grievance_data.get('user_village', self.default_value),
                    grievance_data.get('user_address', self.default_value),
                    user_result[0]
                ))
                user_id = cursor.fetchone()[0]

            # Handle grievance_claimed_amount
            claimed_amount = grievance_data.get('grievance_claimed_amount', '0')
            if claimed_amount == 'Not provided':
                claimed_amount = '0'

            # Update grievance
            cursor.execute("""
                UPDATE grievances SET
                    user_id = %s,
                    grievance_categories = %s,
                    grievance_summary = %s,
                    grievance_details = %s,
                    grievance_claimed_amount = %s,
                    grievance_location = %s,
                    is_temporary = %s,
                    grievance_modification_date = CURRENT_TIMESTAMP,
                    source = %s
                WHERE grievance_id = %s
            """, (
                user_id,
                grievance_data.get('grievance_categories', 'PENDING'),
                grievance_data.get('grievance_summary', 'PENDING'),
                grievance_data.get('grievance_details', 'PENDING'),
                claimed_amount,
                grievance_data.get('grievance_location', self.default_value),
                grievance_data.get('is_temporary', False),
                grievance_data.get('source', 'bot'),
                str(grievance_id)
            ))
            
            # Update status if provided
            status_code = grievance_data.get('grievance_status')
            if status_code:
                cursor.execute("""
                    INSERT INTO grievance_status_history (
                        grievance_id, status_code, notes, created_by
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    str(grievance_id),
                    status_code,
                    'Grievance updated with complete data',
                    'system'
                ))
            
            conn.commit()
            return grievance_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating grievance: {e}")
            logger.error(f"Values being updated - grievance_id: {grievance_id}")
            logger.error(f"Grievance data values: {grievance_data}")
            return None
            
        finally:
            conn.close()

    def store_file_attachment(self, file_data: Dict) -> bool:
        """Store file attachment metadata"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO file_attachments (
                    file_id, grievance_id, file_name,
                    file_path, file_type, file_size
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                file_data['file_id'],
                file_data['grievance_id'],
                file_data['file_name'],
                file_data['file_path'],
                file_data['file_type'],
                file_data['file_size']
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing file attachment: {e}")
            return False
            
        finally:
            conn.close()

    def get_grievance_files(self, grievance_id: str) -> List[Dict]:
        """Get all files for a grievance"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT file_id, file_name, file_type, file_size, upload_timestamp
                FROM file_attachments
                WHERE grievance_id = %s
                ORDER BY upload_timestamp DESC
            """, (grievance_id,))
            
            files = cursor.fetchall()
            return [dict(file) for file in files]
            
        except Exception as e:
            logger.error(f"Error retrieving grievance files: {e}")
            return []
            
        finally:
            conn.close()

    def get_file_by_id(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT file_id, grievance_id, file_name, file_path, 
                       file_type, file_size, upload_timestamp
                FROM file_attachments
                WHERE file_id = %s
            """, (file_id,))
            
            file = cursor.fetchone()
            return dict(file) if file else None
            
        except Exception as e:
            logger.error(f"Error retrieving file by ID: {e}")
            return None
            
        finally:
            conn.close()

    def get_users_by_phone_number(self, phone_number: str) -> List[Dict[str, Any]]:
        """Get all users with a given phone number.
        
        Args:
            phone_number (str): The phone number to search for
            
        Returns:
            List[Dict[str, Any]]: List of user records matching the phone number
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT id, user_unique_id, user_full_name, user_contact_phone,
                       user_contact_email, user_province, user_district,
                       user_municipality, user_ward, user_village, user_address,
                       created_at
                FROM users
                WHERE user_contact_phone = %s
                ORDER BY created_at DESC
            """, (phone_number,))
            
            users = cursor.fetchall()
            return [dict(user) for user in users]
            
        except Exception as e:
            logger.error(f"Error retrieving users by phone number: {e}")
            return []
            
        finally:
            cursor.close()
            conn.close()

    def is_valid_grievance_id(self, grievance_id: str) -> bool:
        """Check if a grievance ID is valid.
        
        Args:
            grievance_id (str): The grievance ID to validate
            
        Returns:
            bool: True if the grievance ID is valid, False otherwise
        """
        if not grievance_id or not isinstance(grievance_id, str):
            return False
        
        # Check if the ID starts with GR and contains only alphanumeric characters
        if not grievance_id.startswith('GR') or not grievance_id[2:].replace('-', '').isalnum():
            return False
        
        # Check if the grievance exists in the database
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM grievances 
                WHERE grievance_id = %s
            """, (grievance_id,))
            
            count = cursor.fetchone()[0]
            return count > 0
            
        except Exception as e:
            logger.error(f"Error validating grievance ID: {e}")
            return False
            
        finally:
            conn.close()

    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance details by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT g.*, u.user_full_name, u.user_contact_phone, u.user_contact_email,
                       u.user_province, u.user_district, u.user_municipality,
                       u.user_ward, u.user_village, u.user_address
                FROM grievances g
                LEFT JOIN users u ON g.user_id = u.id
                WHERE g.grievance_id = %s
            """, (grievance_id,))
            
            grievance = cursor.fetchone()
            return dict(grievance) if grievance else None
            
        except Exception as e:
            logger.error(f"Error retrieving grievance by ID: {e}")
            return None
            
        finally:
            conn.close()

    def store_voice_recording(self, recording_data: Dict) -> Optional[str]:
        """Store voice recording metadata in the database
        
        Args:
            recording_data: Dictionary containing recording metadata with fields:
                - recording_id: UUID for the recording
                - grievance_id: Associated grievance ID
                - file_path: Path to the audio file
                - recording_type: Type of recording (details, contact, location)
                - duration_seconds: Duration of recording in seconds (optional)
                - file_size_bytes: Size of the file in bytes
                - processing_status: Status of the recording (pending, transcribing, transcribed, failed)
                - language_code: Language code of the interface (default: 'ne' for Nepali)
                
        Returns:
            Recording ID if successful, None otherwise
        """
        try:
            conn = self.get_connection()
            if not conn:
                return None
            
            cur = conn.cursor()
            
            # Extract required fields
            recording_id = recording_data.get('recording_id')
            if not recording_id:
                recording_id = str(uuid.uuid4())
            
            grievance_id = recording_data.get('grievance_id')
            if not grievance_id:
                raise ValueError("Grievance ID is required")
            
            file_path = recording_data.get('file_path')
            if not file_path:
                raise ValueError("File path is required")
            
            # Extract optional fields with defaults
            recording_type = recording_data.get('recording_type', 'details')
            duration_seconds = recording_data.get('duration_seconds')
            file_size_bytes = recording_data.get('file_size_bytes', 0)
            processing_status = recording_data.get('processing_status', 'pending')
            language_code = recording_data.get('language_code', 'ne') # Default to Nepali
            
            # Insert into database
            cur.execute("""
                INSERT INTO grievance_voice_recordings
                (recording_id, grievance_id, file_path, recording_type, 
                 duration_seconds, file_size_bytes, processing_status, language_code, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING recording_id
            """, (recording_id, grievance_id, file_path, recording_type, 
                  duration_seconds, file_size_bytes, processing_status, language_code))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                return result[0]  # Return the recording_id
            return None
            
        except Exception as e:
            logger.error(f"Error storing voice recording: {str(e)}")
            if conn:
                conn.rollback()
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def store_transcription(self, transcription_data: Dict) -> Optional[str]:
        """Store transcription in the database
        
        Args:
            transcription_data: Dictionary containing transcription data with fields:
                - transcription_id: UUID for the transcription
                - recording_id: Associated recording ID
                - grievance_id: Associated grievance ID
                - automated_transcript: Text from automated transcription
                - verified_transcript: Manually verified text (optional)
                - verification_status: Status of verification (pending, verified, rejected)
                - verified_by: User who verified the transcription (optional)
                - confidence_score: Confidence score from the transcription model (optional)
                - language_code: Language code of the interface (default: 'ne')
                - language_code_detect: Detected language code from audio (optional)
                
        Returns:
            Transcription ID if successful, None otherwise
        """
        try:
            conn = self.get_connection()
            if not conn:
                return None
            
            cur = conn.cursor()
            
            # Extract required fields
            transcription_id = transcription_data.get('transcription_id')
            if not transcription_id:
                transcription_id = str(uuid.uuid4())
            
            recording_id = transcription_data.get('recording_id')
            if not recording_id:
                raise ValueError("Recording ID is required")
            
            grievance_id = transcription_data.get('grievance_id')
            if not grievance_id:
                raise ValueError("Grievance ID is required")
            
            automated_transcript = transcription_data.get('automated_transcript')
            if not automated_transcript:
                raise ValueError("Automated transcript is required")
            
            # Extract optional fields with defaults
            verified_transcript = transcription_data.get('verified_transcript')
            verification_status = transcription_data.get('verification_status', 'pending')
            verified_by = transcription_data.get('verified_by')
            confidence_score = transcription_data.get('confidence_score', 0.0)
            language_code = transcription_data.get('language_code', 'ne')  # Default to Nepali
            language_code_detect = transcription_data.get('language_code_detect')  # Detected language
            
            # Insert into database
            cur.execute("""
                INSERT INTO grievance_transcriptions
                (transcription_id, recording_id, grievance_id, automated_transcript, 
                 verified_transcript, verification_status, verified_by, confidence_score,
                 language_code, language_code_detect, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING transcription_id
            """, (transcription_id, recording_id, grievance_id, automated_transcript, 
                  verified_transcript, verification_status, verified_by, confidence_score,
                  language_code, language_code_detect))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                return result[0]  # Return the transcription_id
            return None
            
        except Exception as e:
            logger.error(f"Error storing transcription: {str(e)}")
            if conn:
                conn.rollback()
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def update_recording_language(self, recording_id: str, language_code: str) -> bool:
        """Update the detected language for a voice recording
        
        Args:
            recording_id: ID of the recording to update
            language_code: Detected language code
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cur = conn.cursor()
            
            # Update the recording with the detected language
            cur.execute("""
                UPDATE grievance_voice_recordings
                SET language_code_detect = %s, updated_at = NOW()
                WHERE recording_id = %s
                RETURNING recording_id
            """, (language_code, recording_id))
            
            result = cur.fetchone()
            conn.commit()
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error updating recording language: {str(e)}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def get_voice_recordings(self, grievance_id: str) -> List[Dict]:
        """Get all voice recordings for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            List[Dict]: List of voice recording records
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT recording_id, file_path, recording_type,
                       duration_seconds, file_size_bytes, processing_status,
                       language_code, language_code_detect, created_at, updated_at
                FROM grievance_voice_recordings
                WHERE grievance_id = %s
                ORDER BY created_at DESC
            """, (grievance_id,))
            
            recordings = cursor.fetchall()
            return [dict(recording) for recording in recordings]
            
        except Exception as e:
            logger.error(f"Error retrieving voice recordings: {e}")
            return []
            
        finally:
            conn.close()

    def get_transcriptions(self, grievance_id: str) -> List[Dict]:
        """Get all transcriptions for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            List[Dict]: List of transcription records
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT t.*, r.recording_type, r.language_code
                FROM grievance_transcriptions t
                JOIN grievance_voice_recordings r ON t.recording_id = r.recording_id
                WHERE t.grievance_id = %s
                ORDER BY t.created_at DESC
            """, (grievance_id,))
            
            transcriptions = cursor.fetchall()
            return [dict(transcription) for transcription in transcriptions]
            
        except Exception as e:
            logger.error(f"Error retrieving transcriptions: {e}")
            return []
            
        finally:
            conn.close()

    def update_recording_status(self, recording_id: str, status: str) -> bool:
        """Update the processing status of a voice recording
        
        Args:
            recording_id (str): ID of the recording
            status (str): New status ('pending', 'transcribing', 'transcribed', 'failed')
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE grievance_voice_recordings SET
                    processing_status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE recording_id = %s
            """, (status, recording_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating recording status: {e}")
            return False
            
        finally:
            conn.close()

    def store_translation(self, translation_data: Dict) -> Optional[str]:
        """Store a translation for a grievance field
        
        Args:
            translation_data (Dict): Dictionary containing translation data:
                - grievance_id: ID of the grievance
                - field_name: Field being translated ('details', 'summary', 'categories')
                - original_text: Original text in source language
                - translated_text: Translated text
                - source_language: Source language code (e.g., 'ne')
                - target_language: Target language code (e.g., 'en')
                - translation_method: Method used ('llm', 'human', 'auto')
                - confidence_score: Translation confidence score (optional)
                
        Returns:
            Optional[str]: The translation ID if successful, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            translation_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO grievance_translations (
                    translation_id, grievance_id, field_name,
                    original_text, translated_text,
                    source_language, target_language,
                    translation_method, confidence_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING translation_id
            """, (
                translation_id,
                translation_data['grievance_id'],
                translation_data['field_name'],
                translation_data['original_text'],
                translation_data['translated_text'],
                translation_data['source_language'],
                translation_data['target_language'],
                translation_data['translation_method'],
                translation_data.get('confidence_score')
            ))
            
            conn.commit()
            return translation_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing translation: {e}")
            return None
            
        finally:
            conn.close()

    def verify_translation(self, translation_id: str, verification_data: Dict) -> bool:
        """Verify a translation
        
        Args:
            translation_id (str): ID of the translation to verify
            verification_data (Dict): Dictionary containing verification data:
                - verified_by: ID or name of the verifier
                - translated_text: Updated translation text (if corrected)
                
        Returns:
            bool: True if verification was successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE grievance_translations SET
                    translated_text = %s,
                    verified_by = %s,
                    verified_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE translation_id = %s
            """, (
                verification_data.get('translated_text'),
                verification_data['verified_by'],
                translation_id
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error verifying translation: {e}")
            return False
            
        finally:
            conn.close()

    def get_translations(self, grievance_id: str, target_language: str = 'en') -> Dict[str, Dict]:
        """Get all translations for a grievance in a specific target language
        
        Args:
            grievance_id (str): ID of the grievance
            target_language (str): Target language code (default: 'en')
            
        Returns:
            Dict[str, Dict]: Dictionary of translations by field
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT field_name, translated_text, confidence_score,
                       verified_by, verified_at, translation_method
                FROM grievance_translations
                WHERE grievance_id = %s
                AND target_language = %s
                ORDER BY field_name, created_at DESC
            """, (grievance_id, target_language))
            
            translations = {}
            for row in cursor.fetchall():
                field = row['field_name']
                if field not in translations:
                    translations[field] = dict(row)
            
            return translations
            
        except Exception as e:
            logger.error(f"Error retrieving translations: {e}")
            return {}
            
        finally:
            conn.close()

    def get_untranslated_grievances(self, source_language: str = 'ne', target_language: str = 'en') -> List[Dict]:
        """Get grievances that need translation
        
        Args:
            source_language (str): Source language code (default: 'ne')
            target_language (str): Target language code (default: 'en')
            
        Returns:
            List[Dict]: List of grievances needing translation
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT g.grievance_id, g.grievance_details,
                       g.grievance_summary, g.grievance_categories
                FROM grievances g
                LEFT JOIN grievance_translations t ON g.grievance_id = t.grievance_id
                    AND t.target_language = %s
                WHERE t.translation_id IS NULL
                AND g.source = 'accessibility'
                ORDER BY g.grievance_creation_date DESC
            """, (target_language,))
            
            grievances = cursor.fetchall()
            return [dict(grievance) for grievance in grievances]
            
        except Exception as e:
            logger.error(f"Error retrieving untranslated grievances: {e}")
            return []
            
        finally:
            conn.close()

    def store_translations(self, translation_data: Dict) -> bool:
        """Store English translations for a grievance
        
        Args:
            translation_data (Dict): Dictionary containing translation data:
                - grievance_id: ID of the grievance
                - grievance_details_en: English translation of details
                - grievance_summary_en: English translation of summary
                - grievance_categories_en: English translation of categories
                - translation_method: Method used ('llm', 'human', 'auto')
                - confidence_scores: Dict with confidence scores for each field
                - source_language: Source language code (defaults to 'ne')
                
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO grievance_translations (
                    grievance_id, grievance_details_en,
                    grievance_summary_en, grievance_categories_en,
                    translation_method, confidence_scores,
                    source_language
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (grievance_id) DO UPDATE SET
                    grievance_details_en = EXCLUDED.grievance_details_en,
                    grievance_summary_en = EXCLUDED.grievance_summary_en,
                    grievance_categories_en = EXCLUDED.grievance_categories_en,
                    translation_method = EXCLUDED.translation_method,
                    confidence_scores = EXCLUDED.confidence_scores,
                    source_language = EXCLUDED.source_language,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                translation_data['grievance_id'],
                translation_data.get('grievance_details_en'),
                translation_data.get('grievance_summary_en'),
                translation_data.get('grievance_categories_en'),
                translation_data['translation_method'],
                json.dumps(translation_data.get('confidence_scores', {})),
                translation_data.get('source_language', 'ne')
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing translations: {e}")
            return False
            
        finally:
            conn.close()

    def verify_translations(self, grievance_id: str, verification_data: Dict) -> bool:
        """Verify translations for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            verification_data (Dict): Dictionary containing verification data:
                - verified_by: ID or name of the verifier
                - grievance_details_en: Updated English translation of details (optional)
                - grievance_summary_en: Updated English translation of summary (optional)
                - grievance_categories_en: Updated English translation of categories (optional)
                
        Returns:
            bool: True if verification was successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            update_fields = []
            update_values = []
            
            # Add any updated translations
            for field in ['details', 'summary', 'categories']:
                en_field = f'grievance_{field}_en'
                if en_field in verification_data:
                    update_fields.append(f"{en_field} = %s")
                    update_values.append(verification_data[en_field])
            
            # Add verification metadata
            update_fields.extend([
                "verified_by = %s",
                "verified_at = CURRENT_TIMESTAMP",
                "updated_at = CURRENT_TIMESTAMP"
            ])
            update_values.extend([verification_data['verified_by'], grievance_id])
            
            query = f"""
                UPDATE grievance_translations SET
                    {', '.join(update_fields)}
                WHERE grievance_id = %s
            """
            
            cursor.execute(query, update_values)
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error verifying translations: {e}")
            return False
            
        finally:
            conn.close()

    def get_translation(self, grievance_id: str) -> Optional[Dict]:
        """Get English translations for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            Optional[Dict]: Dictionary with translations or None if not found
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT grievance_id, grievance_details_en,
                       grievance_summary_en, grievance_categories_en,
                       source_language, translation_method,
                       confidence_scores, verified_by,
                       verified_at, created_at
                FROM grievance_translations
                WHERE grievance_id = %s
            """, (grievance_id,))
            
            translation = cursor.fetchone()
            return dict(translation) if translation else None
            
        except Exception as e:
            logger.error(f"Error retrieving translation: {e}")
            return None
            
        finally:
            conn.close()

    def get_untranslated_grievances(self) -> List[Dict]:
        """Get grievances that need translation to English
        
        Returns:
            List[Dict]: List of grievances needing translation
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT g.grievance_id, g.grievance_details,
                       g.grievance_summary, g.grievance_categories
                FROM grievances g
                LEFT JOIN grievance_translations t ON g.grievance_id = t.grievance_id
                WHERE t.grievance_id IS NULL
                AND g.source = 'accessibility'
                ORDER BY g.grievance_creation_date DESC
            """)
            
            grievances = cursor.fetchall()
            return [dict(grievance) for grievance in grievances]
            
        except Exception as e:
            logger.error(f"Error retrieving untranslated grievances: {e}")
            return []
            
        finally:
            conn.close()

    def get_unverified_translations(self) -> List[Dict]:
        """Get translations that need verification
        
        Returns:
            List[Dict]: List of unverified translations
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT t.*, g.grievance_details, g.grievance_summary, g.grievance_categories
                FROM grievance_translations t
                JOIN grievances g ON t.grievance_id = g.grievance_id
                WHERE t.verified_at IS NULL
                ORDER BY t.created_at ASC
            """)
            
            translations = cursor.fetchall()
            return [dict(translation) for translation in translations]
            
        except Exception as e:
            logger.error(f"Error retrieving unverified translations: {e}")
            return []
            
        finally:
            conn.close()

    def get_grievance_status(self, grievance_id: str, language: str = 'en') -> Optional[Dict]:
        """Get current status of a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            language (str): Language code ('en' or 'ne')
            
        Returns:
            Optional[Dict]: Current status information or None if not found
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
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
            """, (grievance_id, language, language))
            
            status = cursor.fetchone()
            return dict(status) if status else None
            
        except Exception as e:
            logger.error(f"Error retrieving grievance status: {e}")
            return None
            
        finally:
            conn.close()

    def update_grievance_status(self, grievance_id: str, status_code: str, created_by: str,
                              assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update the status of a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            status_code (str): New status code
            created_by (str): ID/name of user making the change
            assigned_to (str, optional): ID/name of user assigned to the grievance
            notes (str, optional): Notes about the status change
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Verify status code exists and is active
            cursor.execute("""
                SELECT status_code FROM grievance_statuses
                WHERE status_code = %s AND is_active = true
            """, (status_code,))
            
            if not cursor.fetchone():
                logger.error(f"Invalid or inactive status code: {status_code}")
                return False
            
            # Add status history entry
            cursor.execute("""
                INSERT INTO grievance_status_history (
                    grievance_id, status_code, assigned_to,
                    notes, created_by
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                grievance_id,
                status_code,
                assigned_to,
                notes,
                created_by
            ))
            
            # Update grievance modification date
            cursor.execute("""
                UPDATE grievances SET
                    grievance_modification_date = CURRENT_TIMESTAMP
                WHERE grievance_id = %s
            """, (grievance_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating grievance status: {e}")
            return False
            
        finally:
            conn.close()

    def get_grievance_status_history(self, grievance_id: str, language: str = 'en') -> List[Dict]:
        """Get status history of a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            language (str): Language code ('en' or 'ne')
            
        Returns:
            List[Dict]: List of status changes in chronological order
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
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
            """, (language, grievance_id))
            
            history = cursor.fetchall()
            return [dict(record) for record in history]
            
        except Exception as e:
            logger.error(f"Error retrieving status history: {e}")
            return []
            
        finally:
            conn.close()

    def get_available_statuses(self, language: str = 'en') -> List[Dict]:
        """Get list of available grievance statuses
        
        Args:
            language (str): Language code ('en' or 'ne')
            
        Returns:
            List[Dict]: List of active statuses ordered by sort_order
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT 
                    status_code,
                    CASE WHEN %s = 'en' THEN status_name_en ELSE status_name_ne END as status_name,
                    CASE WHEN %s = 'en' THEN description_en ELSE description_ne END as description,
                    sort_order
                FROM grievance_statuses
                WHERE is_active = true
                ORDER BY sort_order
            """, (language, language))
            
            statuses = cursor.fetchall()
            return [dict(status) for status in statuses]
            
        except Exception as e:
            logger.error(f"Error retrieving available statuses: {e}")
            return []
            
        finally:
            conn.close()

    # Add a compatibility method to get grievance history
    def get_grievance_history(self, grievance_id: str) -> List[Dict]:
        """Get status history of a grievance from the old format
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            List[Dict]: List of status changes in chronological order
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT id, grievance_id, previous_status, new_status,
                       next_step, notes, created_at
                FROM grievance_history
                WHERE grievance_id = %s
                ORDER BY created_at DESC
            """, (grievance_id,))
            
            history = cursor.fetchall()
            return [dict(record) for record in history]
            
        except Exception as e:
            logger.error(f"Error retrieving grievance history: {e}")
            return []
            
        finally:
            conn.close()

    def get_grievance_review_data(self, grievance_id: str) -> Optional[Dict]:
        """
        Returns all data needed for the review steps for a given grievance_id.
        Includes:
        - Automated transcripts for each field (details, summary, categories, name, phone, municipality, village, address)
        - Categories as a list
        - User/location info
        Uses DB field names.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:
            # Get main grievance and user info
            cursor.execute('''
                SELECT g.*, u.user_full_name, u.user_contact_phone, u.user_municipality, u.user_village, u.user_address
                FROM grievances g
                LEFT JOIN users u ON g.user_id = u.id
                WHERE g.grievance_id = %s
            ''', (grievance_id,))
            grievance = cursor.fetchone()
            if not grievance:
                return None

            # Get all transcriptions for this grievance
            cursor.execute('''
                SELECT t.automated_transcript, r.recording_type
                FROM grievance_transcriptions t
                JOIN grievance_voice_recordings r ON t.recording_id = r.recording_id
                WHERE t.grievance_id = %s
            ''', (grievance_id,))
            transcripts = {row['recording_type']: row['automated_transcript'] for row in cursor.fetchall()}

            # Prepare categories as a list
            categories = []
            if grievance['grievance_categories']:
                # Split by comma or semicolon, strip whitespace
                categories = [c.strip() for c in grievance['grievance_categories'].replace(';', ',').split(',') if c.strip()]

            # Build result dict using DB field names
            result = {
                'grievance_id': grievance['grievance_id'],
                'grievance_details': transcripts.get('details', ''),
                'grievance_summary': transcripts.get('summary', ''),
                'grievance_categories': categories,
                'user_full_name': transcripts.get('user_full_name', grievance.get('user_full_name', '')),
                'user_contact_phone': transcripts.get('user_contact_phone', grievance.get('user_contact_phone', '')),
                'user_municipality': transcripts.get('user_municipality', grievance.get('user_municipality', '')),
                'user_village': transcripts.get('user_village', grievance.get('user_village', '')),
                'user_address': transcripts.get('user_address', grievance.get('user_address', '')),
            }
            return result
        except Exception as e:
            logger.error(f"Error in get_grievance_review_data: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def update_grievance_review_data(self, grievance_id: str, data: Dict) -> bool:
        """
        Updates the grievance and user info, and categories, for the review step.
        Expects all fields in data dict. Updates only after confirmation.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Update categories (as string)
            categories_str = ', '.join(data.get('grievance_categories', []))
            cursor.execute('''
                UPDATE grievances SET grievance_categories = %s WHERE grievance_id = %s
            ''', (categories_str, grievance_id))

            # Update user info
            cursor.execute('''
                UPDATE users SET user_full_name = %s, user_contact_phone = %s, user_municipality = %s, user_village = %s, user_address = %s
                WHERE id = (SELECT user_id FROM grievances WHERE grievance_id = %s)
            ''', (
                data.get('user_full_name', ''),
                data.get('user_contact_phone', ''),
                data.get('user_municipality', ''),
                data.get('user_village', ''),
                data.get('user_address', ''),
                grievance_id
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error in update_grievance_review_data: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

# Create a singleton instance
db_manager = DatabaseManager() 