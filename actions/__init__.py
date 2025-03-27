import os
import sys

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from .form_contact import *
from .custom_policy import *
from .generic_actions import *
from .form_grievance import *
from .form_location import *