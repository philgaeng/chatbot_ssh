import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml
from fastapi.testclient import TestClient

# Ensure project root and rasa_chatbot are on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
RASA_DIR = PROJECT_ROOT / "rasa_chatbot"
if str(RASA_DIR) not in sys.path:
    sys.path.insert(0, str(RASA_DIR))

from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker  # noqa: E402
from backend.orchestrator.session_store import create_session  # noqa: E402
from backend.orchestrator.main import app  # noqa: E402


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def domain(project_root: Path) -> Dict[str, Any]:
    """Load Rasa domain.yml once for all tests."""
    path = project_root / "rasa_chatbot" / "domain.yml"
    if not path.exists():
        return {"slots": {}}
    with path.open() as f:
        return yaml.safe_load(f) or {}


@pytest.fixture
def dispatcher() -> CollectingDispatcher:
    return CollectingDispatcher()


@pytest.fixture
def tracker() -> SessionTracker:
    slots: Dict[str, Any] = {"language_code": "en"}
    return SessionTracker(slots=slots, sender_id="test-user")


@pytest.fixture
def base_session() -> Dict[str, Any]:
    """Fresh session using session_store defaults."""
    return create_session("test-user")


@pytest.fixture(scope="session")
def client() -> TestClient:
    """FastAPI TestClient for orchestrator API tests."""
    return TestClient(app)

