import os
import uuid
import psycopg2
import psycopg2.extras
import sqlite3
from datetime import datetime
import pytz
import logging
from typing import Dict, List, Optional, Any
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PostgresDB:
    """Helper class for PostgreSQL operations"""
    def __init__(self, db_params: Dict[str, str], nepal_tz: pytz.timezone, default_value: str):
        self.db_params = db_params
        self.nepal_tz = nepal_tz
        self.default_value = default_value

    def get_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(
            **self.db_params,
            cursor_factory=DictCursor
        )

    def init_db(self):
        """Initialize PostgreSQL database"""
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            # Set timezone
            cur.execute("SET timezone = 'Asia/Kathmandu';")
            
            # Create tables
            self._create_tables(cur)
            
            # Create indexes
            self._create_indexes(cur)
            
            conn.commit()
            logger.info("PostgreSQL database initialized successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL initialization error: {e}")
        finally:
            cur.close()
            conn.close()

    def _create_tables(self, cur):
        """Create PostgreSQL tables"""
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_full_name TEXT NOT NULL,
                user_contact_phone TEXT NOT NULL UNIQUE,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievances (
                grievance_id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                grievance_category TEXT,
                grievance_summary TEXT NOT NULL,
                grievance_details TEXT,
                grievance_claimed_amount DECIMAL,
                grievance_location TEXT,
                grievance_creation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                grievance_modification_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                grievance_status TEXT DEFAULT 'TEMP',
                grievance_status_update_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                is_temporary BOOLEAN DEFAULT TRUE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_history (
                id SERIAL PRIMARY KEY,
                grievance_id TEXT REFERENCES grievances(grievance_id),
                previous_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                next_step TEXT,
                expected_resolution_date TIMESTAMP WITH TIME ZONE,
                update_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                notes TEXT
            )
        """)

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

    def _create_indexes(self, cur):
        """Create PostgreSQL indexes"""
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_phone ON users(user_contact_phone);
            CREATE INDEX IF NOT EXISTS idx_grievance_user ON grievances(user_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_status ON grievances(grievance_status);
            CREATE INDEX IF NOT EXISTS idx_grievance_history ON grievance_history(grievance_id, update_date);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id ON file_attachments(grievance_id);
        """)

    def create_grievance(self, grievance_data: Dict) -> Optional[str]:
        """Create a new grievance in PostgreSQL"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SET timezone = 'Asia/Kathmandu';")
            
            # Generate grievance ID if not provided
            grievance_id = grievance_data.get('grievance_id')
            if not grievance_id:
                nepal_time = datetime.now(self.nepal_tz)
                grievance_id = f"GR{nepal_time.strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
            
            # Insert or update user
            cursor.execute("""
                INSERT INTO users (
                    user_full_name, user_contact_phone, user_contact_email,
                    user_province, user_district, user_municipality,
                    user_ward, user_village, user_address
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_contact_phone) DO UPDATE SET
                    user_full_name = EXCLUDED.user_full_name,
                    user_contact_email = EXCLUDED.user_contact_email,
                    user_province = EXCLUDED.user_province,
                    user_district = EXCLUDED.user_district,
                    user_municipality = EXCLUDED.user_municipality,
                    user_ward = EXCLUDED.user_ward,
                    user_village = EXCLUDED.user_village,
                    user_address = EXCLUDED.user_address
                RETURNING id
            """, (
                grievance_data.get('user_full_name', self.default_value),
                grievance_data.get('user_contact_phone', self.default_value),
                grievance_data.get('user_contact_email', self.default_value),
                grievance_data.get('user_province', self.default_value),
                grievance_data.get('user_district', self.default_value),
                grievance_data.get('user_municipality', self.default_value),
                grievance_data.get('user_ward', self.default_value),
                grievance_data.get('user_village', self.default_value),
                grievance_data.get('user_address', self.default_value)
            ))
            
            user_id = cursor.fetchone()[0]

            # Create grievance
            cursor.execute("""
                INSERT INTO grievances (
                    grievance_id, user_id, grievance_category,
                    grievance_summary, grievance_details,
                    grievance_claimed_amount, grievance_location,
                    grievance_status, is_temporary
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(grievance_id),
                int(user_id),
                grievance_data.get('grievance_category', 'PENDING'),
                grievance_data.get('grievance_summary', 'PENDING'),
                grievance_data.get('grievance_details', 'PENDING'),
                grievance_data.get('grievance_claimed_amount', '0'),
                grievance_data.get('grievance_location', self.default_value),
                grievance_data.get('grievance_status', 'TEMP'),
                grievance_data.get('is_temporary', True)
            ))
            
            # Create initial history entry
            cursor.execute("""
                INSERT INTO grievance_history (
                    grievance_id, previous_status, new_status,
                    next_step, notes
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                str(grievance_id),
                '',
                grievance_data.get('grievance_status', 'TEMP'),
                'Pending',
                'Grievance created with temporary status'
            ))
            
            conn.commit()
            return grievance_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating grievance: {e}")
            logger.error(f"Values being inserted - user_id: {user_id}, grievance_id: {grievance_id}")
            logger.error(f"Grievance data values: {grievance_data}")
            return None
            
        finally:
            conn.close()

    def store_file_attachment(self, file_data: Dict) -> bool:
        """Store file attachment metadata in PostgreSQL"""
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
        """Get all files for a grievance from PostgreSQL"""
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
        """Get file metadata by ID from PostgreSQL"""
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

class SQLiteDB:
    """Helper class for SQLite operations"""
    def __init__(self, db_path: str, nepal_tz: pytz.timezone, default_value: str):
        self.db_path = db_path
        self.nepal_tz = nepal_tz
        self.default_value = default_value

    def get_connection(self):
        """Get SQLite connection"""
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialize SQLite database"""
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            # Create tables
            self._create_tables(cur)
            
            # Create indexes
            self._create_indexes(cur)
            
            conn.commit()
            logger.info("SQLite database initialized successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite initialization error: {e}")
        finally:
            cur.close()
            conn.close()

    def create_grievance(self, grievance_data: Dict) -> Optional[str]:
        """Create a new grievance in SQLite"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Generate grievance ID if not provided
            grievance_id = grievance_data.get('grievance_id')
            if not grievance_id:
                nepal_time = datetime.now(self.nepal_tz)
                grievance_id = f"GR{nepal_time.strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
            
            # First check if user exists
            cursor.execute("""
                SELECT id FROM users WHERE user_contact_phone = ?
            """, (grievance_data.get('user_contact_phone', self.default_value),))
            
            result = cursor.fetchone()
            if result:
                # Update existing user
                user_id = result[0]
                cursor.execute("""
                    UPDATE users SET
                        user_full_name = ?,
                        user_contact_email = ?,
                        user_province = ?,
                        user_district = ?,
                        user_municipality = ?,
                        user_ward = ?,
                        user_village = ?,
                        user_address = ?
                    WHERE id = ?
                """, (
                    grievance_data.get('user_full_name', self.default_value),
                    grievance_data.get('user_contact_email', self.default_value),
                    grievance_data.get('user_province', self.default_value),
                    grievance_data.get('user_district', self.default_value),
                    grievance_data.get('user_municipality', self.default_value),
                    grievance_data.get('user_ward', self.default_value),
                    grievance_data.get('user_village', self.default_value),
                    grievance_data.get('user_address', self.default_value),
                    user_id
                ))
            else:
                # Insert new user
                cursor.execute("""
                    INSERT INTO users (
                        user_full_name, user_contact_phone, user_contact_email,
                        user_province, user_district, user_municipality,
                        user_ward, user_village, user_address
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    grievance_data.get('user_full_name', self.default_value),
                    grievance_data.get('user_contact_phone', self.default_value),
                    grievance_data.get('user_contact_email', self.default_value),
                    grievance_data.get('user_province', self.default_value),
                    grievance_data.get('user_district', self.default_value),
                    grievance_data.get('user_municipality', self.default_value),
                    grievance_data.get('user_ward', self.default_value),
                    grievance_data.get('user_village', self.default_value),
                    grievance_data.get('user_address', self.default_value)
                ))
                cursor.execute("SELECT last_insert_rowid()")
                user_id = cursor.fetchone()[0]

            # Create grievance
            cursor.execute("""
                INSERT OR REPLACE INTO grievances (
                    grievance_id, user_id, grievance_category,
                    grievance_summary, grievance_details,
                    grievance_claimed_amount, grievance_location,
                    grievance_status, is_temporary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(grievance_id),
                int(user_id),
                grievance_data.get('grievance_category', 'PENDING'),
                grievance_data.get('grievance_summary', 'PENDING'),
                grievance_data.get('grievance_details', 'PENDING'),
                grievance_data.get('grievance_claimed_amount', '0'),
                grievance_data.get('grievance_location', self.default_value),
                grievance_data.get('grievance_status', 'TEMP'),
                grievance_data.get('is_temporary', True)
            ))
            
            # Create initial history entry
            cursor.execute("""
                INSERT INTO grievance_history (
                    grievance_id, previous_status, new_status,
                    next_step, notes
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                str(grievance_id),
                '',
                grievance_data.get('grievance_status', 'TEMP'),
                'Pending',
                'Grievance created with temporary status'
            ))
            
            conn.commit()
            return grievance_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating grievance: {e}")
            logger.error(f"Values being inserted - user_id: {user_id}, grievance_id: {grievance_id}")
            logger.error(f"Grievance data values: {grievance_data}")
            return None
            
        finally:
            conn.close()

    def _create_tables(self, cur):
        """Create SQLite tables"""
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_full_name TEXT NOT NULL,
                user_contact_phone TEXT NOT NULL UNIQUE,
                user_contact_email TEXT,
                user_province TEXT,
                user_district TEXT,
                user_municipality TEXT,
                user_ward TEXT,
                user_village TEXT,
                user_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievances (
                grievance_id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                grievance_category TEXT,
                grievance_summary TEXT NOT NULL,
                grievance_details TEXT,
                grievance_claimed_amount REAL,
                grievance_location TEXT,
                grievance_creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                grievance_modification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                grievance_status TEXT DEFAULT 'TEMP',
                grievance_status_update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_temporary INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grievance_id TEXT REFERENCES grievances(grievance_id),
                previous_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                next_step TEXT,
                expected_resolution_date TIMESTAMP,
                update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                notes TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS file_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id),
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_indexes(self, cur):
        """Create SQLite indexes"""
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_phone ON users(user_contact_phone)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_grievance_user ON grievances(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_grievance_status ON grievances(grievance_status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_grievance_history ON grievance_history(grievance_id, update_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id ON file_attachments(grievance_id)")

    def store_file_attachment(self, file_data: Dict) -> bool:
        """Store file attachment metadata in SQLite"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO file_attachments (
                    file_id, grievance_id, file_name,
                    file_path, file_type, file_size
                ) VALUES (?, ?, ?, ?, ?, ?)
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
        """Get all files for a grievance from SQLite"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT file_id, file_name, file_type, file_size, upload_timestamp
                FROM file_attachments
                WHERE grievance_id = ?
                ORDER BY upload_timestamp DESC
            """, (grievance_id,))
            
            columns = ['file_id', 'file_name', 'file_type', 'file_size', 'upload_timestamp']
            files = cursor.fetchall()
            return [dict(zip(columns, file)) for file in files]
            
        except Exception as e:
            logger.error(f"Error retrieving grievance files: {e}")
            return []
            
        finally:
            conn.close()

    def get_file_by_id(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by ID from SQLite"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT file_id, grievance_id, file_name, file_path, 
                       file_type, file_size, upload_timestamp
                FROM file_attachments
                WHERE file_id = ?
            """, (file_id,))
            
            columns = ['file_id', 'grievance_id', 'file_name', 'file_path', 
                      'file_type', 'file_size', 'upload_timestamp']
            file = cursor.fetchone()
            return dict(zip(columns, file)) if file else None
            
        except Exception as e:
            logger.error(f"Error retrieving file by ID: {e}")
            return None
            
        finally:
            conn.close()

class DatabaseManager:
    """Main database manager class that handles both PostgreSQL and SQLite"""
    def __init__(self):
        # Common attributes
        self.nepal_tz = pytz.timezone('Asia/Kathmandu')
        self.default_value = 'NOT_PROVIDED'
        
        # Database connection parameters using environment variable names and mapping to postgres connection parameters
        self.db_params = {
            'host': os.environ.get('POSTGRES_HOST'),
            'database': os.environ.get('POSTGRES_DB'),
            'user': os.environ.get('POSTGRES_USER'),
            'password': os.environ.get('POSTGRES_PASSWORD'),
            'port': os.environ.get('POSTGRES_PORT')
        }

        # Determine database type and initialize
        self.db_type = self._determine_db_type()
        if self.db_type == "postgres":
            self.db = PostgresDB(self.db_params, self.nepal_tz, self.default_value)
        else:
            self.db = SQLiteDB("grievances.db", self.nepal_tz, self.default_value)
        
        self.init_db()

    def _determine_db_type(self) -> str:
        """Check if PostgreSQL credentials exist in environment variables"""
        
        if all(self.db_params.values()):
            try:
                conn = psycopg2.connect(**self.db_params)
                conn.close()
                logger.info("Successfully connected to PostgreSQL")
                return "postgres"
            except psycopg2.Error as e:
                logger.error(f"PostgreSQL connection failed: {e}")
                logger.info("Falling back to SQLite")
                return "sqlite"
        else:
            logger.info("PostgreSQL environment variables not found. Using SQLite")
            return "sqlite"

    def get_connection(self):
        """Get database connection"""
        return self.db.get_connection()

    def init_db(self):
        """Initialize the database"""
        self.db.init_db()

    def create_grievance(self, grievance_data: Dict) -> Optional[str]:
        """Create a new grievance"""
        return self.db.create_grievance(grievance_data)

    def store_file_attachment(self, file_data: Dict) -> bool:
        """Store file attachment metadata"""
        return self.db.store_file_attachment(file_data)

    def get_grievance_files(self, grievance_id: str) -> List[Dict]:
        """Get all files for a grievance"""
        return self.db.get_grievance_files(grievance_id)

    def get_file_by_id(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by ID"""
        return self.db.get_file_by_id(file_id)

# Create a singleton instance
db_manager = DatabaseManager() 