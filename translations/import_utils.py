import sys
import os

def setup_imports():
    """Setup the Python path to include the root directory."""
    # Get the absolute path of the root directory (one level up from translations)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Add root directory to Python path if not already there
    if root_dir not in sys.path:
        sys.path.append(root_dir)
        print(f"Added to Python path: {root_dir}")
    
    return root_dir

# Setup imports when this module is imported
root_dir = setup_imports() 