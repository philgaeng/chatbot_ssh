import os
import pytest
from dotenv import load_dotenv

# Load test environment variables
# Load environment variables
load_dotenv('/home/ubuntu/nepal_chatbot/.env')


# Set test database configuration
os.environ['POSTGRES_DB'] = os.getenv('POSTGRES_DB', 'nepal_chatbot_test')
os.environ['POSTGRES_USER'] = os.getenv('POSTGRES_USER', 'postgres')
os.environ['POSTGRES_PASSWORD'] = os.getenv('POSTGRES_PASSWORD', 'postgres')
os.environ['POSTGRES_HOST'] = os.getenv('POSTGRES_HOST', 'localhost')
os.environ['POSTGRES_PORT'] = os.getenv('POSTGRES_PORT', '5432')

@pytest.fixture(scope="session")
def test_db():
    """Create a test database and return the database manager instance"""
    from actions_server.db_manager import db_manager
    # Initialize test database
    db_manager.table.init_db()
    yield db_manager
    # Cleanup after tests
    db_manager.table.recreate_db() 