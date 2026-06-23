import os
import sys
import logging

# Ensure project root is on path (backend.actions is under backend at repo root)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logger = logging.getLogger(__name__)

# Eagerly initialise the shared database manager singleton on package import.
from backend.services.database_services.postgres_services import db_manager  # noqa: E402,F401
