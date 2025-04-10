import os
import sys
from typing import List, Type
from rasa_sdk import Action
import logging
from importlib import import_module
from pathlib import Path
from .generic_actions import ActionWrapper
import threading
from .file_server import app
import time


# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import the database manager
from .db_manager import db_manager

# Import all action modules
from .form_contact import *
from .custom_policy import *
from .generic_actions import *
from .form_grievance import *

def start_file_server():
    """Start the file server in a background thread"""
    try:
        logger.info("Starting file server on port 5001...")
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(project_root, 'test_webchat', 'actions', 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            logger.info(f"Created uploads directory: {upload_dir}")
        
        # Start Flask app
        app.run(host='0.0.0.0', port=5001, use_reloader=False, debug=False)
    except Exception as e:
        logger.error(f"Error starting file server: {str(e)}", exc_info=True)

# Start file server in a background thread
file_server_thread = threading.Thread(target=start_file_server, daemon=True)
file_server_thread.start()

# Wait a moment to ensure the server starts
time.sleep(1)

# Check if the server is running
try:
    import requests
    response = requests.get('http://localhost:5001/')
    logger.info("File server is running successfully")
except Exception as e:
    logger.error(f"File server may not be running: {str(e)}")

def get_action_classes() -> List[Type[Action]]:
    """Get all action classes from the actions package"""
    action_classes = []
    actions_dir = Path(__file__).parent
    
    # List all Python files in the actions directory
    for file_path in actions_dir.glob("*.py"):
        if file_path.name.startswith("__"):
            continue
            
        try:
            # Import the module
            module_name = f"actions.{file_path.stem}"
            module = import_module(module_name)
            
            # Find all Action classes in the module
            for item_name in dir(module):
                item = getattr(module, item_name)
                if (isinstance(item, type) and 
                    issubclass(item, Action) and 
                    item != Action):
                    logger.debug(f"Found action class: {item_name}")
                    action_classes.append(item)
        except Exception as e:
            logger.error(f"Error loading actions from {file_path}: {str(e)}")
            
    return action_classes

def get_all_actions() -> List[Action]:
    """Get instances of all action classes with error checking"""
    actions = []
    for action_class in get_action_classes():
        try:
            # Use the wrapper to create and validate the action
            action = ActionWrapper.wrap_action(action_class)
            if action:
                actions.append(action)
        except Exception as e:
            logger.error(f"Failed to initialize action {action_class.__name__}: {str(e)}")
            # Continue with other actions even if one fails
            continue
    return actions