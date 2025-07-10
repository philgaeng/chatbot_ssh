"""
Initialize the actions_server package.
This package contains shared code for both the Rasa action server and accessible interface.
"""

import os
import sys
import logging

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import database managers from the new modular structure
try:
    from .services.database_services import db_manager
    logger.info("Database manager imported successfully")
except ImportError as e:
    logger.warning(f"Could not import database manager: {e}")
    db_manager = None 