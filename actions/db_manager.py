import os
import uuid
import psycopg2
import psycopg2.extras
import logging
from datetime import datetime
import pytz
from typing import Dict, List, Optional, Any
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
        return psycopg2.connect(
            **self.db_params,
            cursor_factory=DictCursor
        )

    def generate_grievance_id(self) -> str:
        """Generate a unique grievance ID using Nepal time and UUID.
        
        Returns:
            str: A unique grievance ID in the format GR{YYYYMMDD}{UUID[:6]}
        """
        return f"GR{datetime.now(self.nepal_tz).strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"

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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievances (
                grievance_id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                grievance_categories TEXT,
                grievance_summary TEXT,
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
                previous_status TEXT,
                new_status TEXT,
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

    def create_grievance(self) -> Optional[str]:
        """Create a minimal grievance record with temporary status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SET timezone = 'Asia/Kathmandu';")
            
            # Generate grievance ID
            grievance_id = self.generate_grievance_id()
            
            # Create minimal user record with just an ID
            cursor.execute("""
                INSERT INTO users DEFAULT VALUES
                RETURNING id
            """)
            
            user_id = cursor.fetchone()[0]

            # Create minimal grievance record
            cursor.execute("""
                INSERT INTO grievances (
                    grievance_id, user_id, grievance_status, is_temporary
                ) VALUES (%s, %s, %s, %s)
            """, (
                str(grievance_id),
                int(user_id),
                'TEMP',
                True
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
                'TEMP',
                'Pending',
                'Grievance created with temporary status'
            ))
            
            conn.commit()
            return grievance_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating temporary grievance: {e}")
            return None
            
        finally:
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
                    grievance_status = %s,
                    is_temporary = %s,
                    grievance_modification_date = CURRENT_TIMESTAMP
                WHERE grievance_id = %s
            """, (
                user_id,
                grievance_data.get('grievance_categories', 'PENDING'),
                grievance_data.get('grievance_summary', 'PENDING'),
                grievance_data.get('grievance_details', 'PENDING'),
                claimed_amount,
                grievance_data.get('grievance_location', self.default_value),
                grievance_data.get('grievance_status', 'TEMP'),
                grievance_data.get('is_temporary', False),
                str(grievance_id)
            ))
            
            # Update history entry
            cursor.execute("""
                INSERT INTO grievance_history (
                    grievance_id, previous_status, new_status,
                    next_step, notes
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                str(grievance_id),
                'TEMP',
                grievance_data.get('grievance_status', 'TEMP'),
                'Pending',
                'Grievance updated with complete data'
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

# Create a singleton instance
db_manager = DatabaseManager() 