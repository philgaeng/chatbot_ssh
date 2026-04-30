import os
import uuid
import mysql.connector
import mysql.connector.pooling
import logging
from datetime import datetime
import pytz
from typing import Dict, List, Optional, Any, TypeVar, Generic
import json
import traceback
from contextlib import contextmanager
import sys
import time
from icecream import ic

# Import database configuration from constants.py
from backend.config.constants import DB_CONFIG

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
operations_logger = setup_logger('mysql_operations', 'logs/mysql_operations.log')
migrations_logger = setup_logger('mysql_migrations', 'logs/mysql_migrations.log')
backup_logger = setup_logger('mysql_backup', 'logs/mysql_backup.log')

class DatabaseError(Exception):
    """Base exception for database operations"""
    pass

class DatabaseConnectionError(DatabaseError):
    """Exception for database connection issues"""
    pass

class DatabaseQueryError(DatabaseError):
    """Exception for database query issues"""
    pass

class MySQLDatabaseManager:
    """MySQL database manager for GRM system integration"""
    
    def __init__(self, nepal_tz: Optional[pytz.timezone] = None):
        self.nepal_tz = nepal_tz or pytz.timezone('Asia/Kathmandu')
        
        # GRM MySQL configuration - can be overridden by environment variables
        self.grm_db_config = {
            'host': os.getenv('GRM_MYSQL_HOST', 'localhost'),
            'database': os.getenv('GRM_MYSQL_DB', 'grm_database'),
            'user': os.getenv('GRM_MYSQL_USER', 'grm_complainant'),
            'password': os.getenv('GRM_MYSQL_PASSWORD', ''),
            'port': int(os.getenv('GRM_MYSQL_PORT', '3306')),
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': False,
            'pool_name': 'grm_pool',
            'pool_size': 5,
            'pool_reset_session': True
        }
        
        # Connection pool for better performance
        self.connection_pool = None
        self._setup_connection_pool()

    def _setup_connection_pool(self):
        """Setup MySQL connection pool"""
        try:
            self.connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                **self.grm_db_config
            )
            operations_logger.info(f"MySQL connection pool established for {self.grm_db_config['database']}")
        except Exception as e:
            operations_logger.error(f"Failed to setup MySQL connection pool: {str(e)}")
            self.connection_pool = None

    def _validate_db_params(self):
        """Validate database connection parameters"""
        required_params = ['host', 'database', 'user', 'password', 'port']
        missing_params = [param for param in required_params if not self.grm_db_config.get(param)]
        if missing_params:
            raise DatabaseConnectionError(f"Missing required database parameters: {', '.join(missing_params)}")

    @contextmanager
    def get_connection(self):
        """Get MySQL connection with context management and logging"""
        conn = None
        start_time = datetime.now()
        try:
            operations_logger.info(f"Connecting to GRM MySQL database: {self.grm_db_config['database']}")
            
            if self.connection_pool:
                conn = self.connection_pool.get_connection()
            else:
                # Fallback to direct connection if pool fails
                conn = mysql.connector.connect(**self.grm_db_config)
            
            yield conn
        except Exception as e:
            operations_logger.error(f"MySQL connection error: {str(e)}")
            raise DatabaseConnectionError(f"Failed to connect to GRM MySQL database: {str(e)}")
        finally:
            if conn:
                duration = (datetime.now() - start_time).total_seconds()
                operations_logger.info(f"MySQL connection closed. Duration: {duration:.2f}s")
                conn.close()

    @contextmanager
    def transaction(self):
        """Transaction context manager with logging"""
        with self.get_connection() as conn:
            try:
                operations_logger.info("Starting MySQL transaction")
                yield conn
                conn.commit()
                operations_logger.info("MySQL transaction committed successfully")
            except Exception as e:
                conn.rollback()
                operations_logger.error(f"MySQL transaction rolled back: {str(e)}")
                raise DatabaseQueryError(f"MySQL transaction failed: {str(e)}")

    def execute_query(self, query: str, params: tuple = None, operation: str = "query") -> List[Dict]:
        """Execute a query with logging"""
        start_time = datetime.now()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                operations_logger.info(f"Executing {operation}: {query[:100]}...")
                cursor.execute(query, params or ())
                results = cursor.fetchall()
                duration = (datetime.now() - start_time).total_seconds()
                operations_logger.info(f"{operation} completed in {duration:.2f}s. Rows: {len(results)}")
                return results
        except Exception as e:
            operations_logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"MySQL query execution failed: {str(e)}")

    def execute_update(self, query: str, params: tuple = None, operation: str = "update") -> int:
        """Execute an update query with logging"""
        start_time = datetime.now()
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                operations_logger.info(f"Executing {operation}: {query[:100]}...")
                cursor.execute(query, params or ())
                affected_rows = cursor.rowcount
                duration = (datetime.now() - start_time).total_seconds()
                operations_logger.info(f"{operation} completed in {duration:.2f}s. Affected rows: {affected_rows}")
                return affected_rows
        except Exception as e:
            operations_logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"MySQL update execution failed: {str(e)}")

    def execute_insert(self, query: str, params: tuple = None, operation: str = "insert") -> Any:
        """Execute an insert query with logging"""
        start_time = datetime.now()
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                operations_logger.info(f"Executing {operation}: {query[:100]}...")
                cursor.execute(query, params or ())
                result = cursor.fetchone()
                duration = (datetime.now() - start_time).total_seconds()
                operations_logger.info(f"{operation} completed in {duration:.2f}s")
                return result
        except Exception as e:
            operations_logger.error(f"{operation} failed: {str(e)}")
            raise DatabaseQueryError(f"MySQL insert execution failed: {str(e)}")

    def test_connection(self) -> bool:
        """Test the connection to the GRM MySQL database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                operations_logger.info("MySQL connection test successful")
                return True
        except Exception as e:
            operations_logger.error(f"MySQL connection test failed: {str(e)}")
            return False

    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the connected database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Get database name
                cursor.execute("SELECT DATABASE() as db_name")
                db_info = cursor.fetchone()
                
                # Get MySQL version
                cursor.execute("SELECT VERSION() as version")
                version_info = cursor.fetchone()
                
                # Get table count
                cursor.execute("""
                    SELECT COUNT(*) as table_count 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                """)
                table_info = cursor.fetchone()
                
                return {
                    'database_name': db_info['db_name'],
                    'mysql_version': version_info['version'],
                    'table_count': table_info['table_count'],
                    'connection_host': self.grm_db_config['host'],
                    'connection_port': self.grm_db_config['port']
                }
        except Exception as e:
            operations_logger.error(f"Failed to get database info: {str(e)}")
            return {}

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema information for a specific table"""
        query = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMN_KEY,
                EXTRA
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = %s
            ORDER BY ORDINAL_POSITION
        """
        try:
            return self.execute_query(query, (table_name,), f"get_schema_{table_name}")
        except Exception as e:
            operations_logger.error(f"Failed to get schema for table {table_name}: {str(e)}")
            return []

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            ORDER BY table_name
        """
        try:
            results = self.execute_query(query, operation="get_all_tables")
            return [row['table_name'] for row in results]
        except Exception as e:
            operations_logger.error(f"Failed to get table list: {str(e)}")
            return []

class GRMIntegrationService:
    """Service for integrating with the GRM system database"""
    
    def __init__(self):
        self.db_manager = MySQLDatabaseManager()
        
    def sync_grievance_data(self, grievance_data: Dict[str, Any]) -> bool:
        """Sync grievance data to the GRM system"""
        try:
            # This is a placeholder - you'll need to map your data to GRM schema
            # Example mapping based on typical GRM systems
            grm_data = {
                'grievance_id': grievance_data.get('grievance_id'),
                'complainant_name': grievance_data.get('complainant_full_name'),
                'contact_phone': grievance_data.get('complainant_phone'),
                'contact_email': grievance_data.get('complainant_email'),
                'grievance_description': grievance_data.get('grievance_description'),
                'location': grievance_data.get('grievance_location'),
                'submission_date': datetime.now(),
                'status': 'pending'
            }
            
            # Insert into GRM system
            query = """
                INSERT INTO grievances (
                    grievance_id, complainant_name, contact_phone, contact_email,
                    grievance_description, location, submission_date, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    complainant_name = VALUES(complainant_name),
                    contact_phone = VALUES(contact_phone),
                    contact_email = VALUES(contact_email),
                    grievance_description = VALUES(grievance_description),
                    location = VALUES(location),
                    status = VALUES(status)
            """
            
            params = (
                grm_data['grievance_id'],
                grm_data['complainant_name'],
                grm_data['contact_phone'],
                grm_data['contact_email'],
                grm_data['grievance_description'],
                grm_data['location'],
                grm_data['submission_date'],
                grm_data['status']
            )
            
            self.db_manager.execute_insert(query, params, "sync_grievance")
            operations_logger.info(f"Successfully synced grievance {grievance_data.get('grievance_id')} to GRM system")
            return True
            
        except Exception as e:
            operations_logger.error(f"Failed to sync grievance data: {str(e)}")
            return False
    
    def get_grm_grievance_status(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance status from GRM system"""
        query = """
            SELECT grievance_id, status, assigned_officer, 
                   resolution_date, resolution_notes
            FROM grievances 
            WHERE grievance_id = %s
        """
        try:
            results = self.db_manager.execute_query(query, (grievance_id,), "get_grm_status")
            return results[0] if results else None
        except Exception as e:
            operations_logger.error(f"Failed to get GRM grievance status: {str(e)}")
            return None
    
    def update_grievance_status(self, grievance_id: str, status: str, notes: str = None) -> bool:
        """Update grievance status in GRM system"""
        query = """
            UPDATE grievances 
            SET status = %s, 
                resolution_notes = %s,
                last_updated = NOW()
            WHERE grievance_id = %s
        """
        try:
            affected_rows = self.db_manager.execute_update(
                query, (status, notes, grievance_id), "update_grm_status"
            )
            return affected_rows > 0
        except Exception as e:
            operations_logger.error(f"Failed to update GRM grievance status: {str(e)}")
            return False

# Example usage and configuration
if __name__ == "__main__":
    # Test the MySQL connection
    grm_service = GRMIntegrationService()
    
    # Test connection
    if grm_service.db_manager.test_connection():
        print("✅ MySQL connection successful")
        
        # Get database info
        db_info = grm_service.db_manager.get_database_info()
        print(f"Database: {db_info.get('database_name')}")
        print(f"MySQL Version: {db_info.get('mysql_version')}")
        print(f"Tables: {db_info.get('table_count')}")
        
        # Get all tables
        tables = grm_service.db_manager.get_all_tables()
        print(f"Available tables: {tables[:10]}...")  # Show first 10 tables
    else:
        print("❌ MySQL connection failed") 