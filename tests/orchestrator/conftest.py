import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml
from fastapi.testclient import TestClient

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.orchestrator.paths import DOMAIN_YAML_PATH
from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker  # noqa: E402
from backend.orchestrator.session_store import create_session  # noqa: E402
from backend.orchestrator.main import app  # noqa: E402


def run_async(coro):
    """Run async test coroutines without relying on a persistent event loop."""
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _ensure_seah_flow_enabled(monkeypatch):
    """Dedicated SEAH menu entry is on by default in production."""
    monkeypatch.setenv("ENABLE_SEAH_DEDICATED_FLOW", "true")


@pytest.fixture
def mock_flow_db(monkeypatch):
    """
    In-memory DB stand-in for orchestrator flow tests (no Postgres required).
    """
    from backend.services.database_services.postgres_services import DatabaseManager
    from backend.services.messaging import Messaging

    store: Dict[str, Any] = {"grievances": {}, "complainants": {}, "files": {}}

    def _gid(data):
        return (data or {}).get("grievance_id") or "GR-TEST-FLOW-001"

    def create_or_update_complainant(self, data):
        cid = (data or {}).get("complainant_id") or "CM-TEST-FLOW-001"
        store["complainants"][cid] = dict(data or {})
        return cid

    def create_or_update_grievance(self, data):
        gid = _gid(data)
        store["grievances"][gid] = {**dict(data or {}), "grievance_id": gid}
        return gid

    def update_grievance(self, grievance_id, data):
        store["grievances"].setdefault(grievance_id, {})
        store["grievances"][grievance_id].update(data or {})
        return True

    def submit_grievance_to_db(self, data):
        gid = _gid(data)
        store["grievances"][gid] = {**dict(data or {}), "grievance_id": gid}
        return {"ok": True, "grievance_id": gid, "complainant_id": data.get("complainant_id")}

    def submit_seah_to_db(self, data):
        gid = _gid(data)
        store["grievances"][gid] = {**dict(data or {}), "grievance_id": gid}
        return {"ok": True, "grievance_id": gid, "complainant_id": data.get("complainant_id")}

    def get_grievance_by_id(self, grievance_id):
        return store["grievances"].get(grievance_id) or {
            "grievance_id": grievance_id,
            "grievance_categories": ["ENVIRONMENT - Dust"],
            "grievance_summary": "Test summary",
            "grievance_description": "Test description",
            "grievance_classification_status": "LLM_skipped",
        }

    def get_grievance_files(self, _gid):
        return store["files"].get(_gid, [])

    def check_entry_exists_for_entity_key(self, *_args, **_kwargs):
        return False

    def find_seah_contact_point(self, *_args, **_kwargs):
        return None

    def find_seah_service_providers_for_tracker(self, *_args, **_kwargs):
        return []

    async def fake_classification(_form, tracker, dispatcher, **kwargs):
        return {
            "grievance_categories": ["ENVIRONMENT - Other"],
            "grievance_summary": tracker.get_slot("grievance_description")
            or "Test grievance summary",
            "grievance_classification_status": "LLM_generated",
            "grievance_summary_temp": tracker.get_slot("grievance_description")
            or "Test grievance summary",
        }

    async def fake_sensitive(_form, text, **kwargs):
        return {"grievance_sensitive_issue": False}

    monkeypatch.setattr(DatabaseManager, "create_or_update_complainant", create_or_update_complainant)
    monkeypatch.setattr(DatabaseManager, "create_or_update_grievance", create_or_update_grievance)
    monkeypatch.setattr(DatabaseManager, "update_grievance", update_grievance)
    monkeypatch.setattr(DatabaseManager, "submit_grievance_to_db", submit_grievance_to_db)
    monkeypatch.setattr(DatabaseManager, "submit_seah_to_db", submit_seah_to_db)
    monkeypatch.setattr(DatabaseManager, "get_grievance_by_id", get_grievance_by_id)
    monkeypatch.setattr(DatabaseManager, "get_grievance_files", get_grievance_files)
    monkeypatch.setattr(DatabaseManager, "check_entry_exists_for_entity_key", check_entry_exists_for_entity_key)
    monkeypatch.setattr(DatabaseManager, "find_seah_contact_point", find_seah_contact_point)

    monkeypatch.setattr(
        "backend.actions.grievance_intake.classification.trigger_async_classification",
        fake_classification,
    )
    monkeypatch.setattr(
        "backend.actions.grievance_intake.sensitive.get_sensitive_issue_slots_on_submit",
        fake_sensitive,
    )
    monkeypatch.setattr(Messaging, "send_sms", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "backend.shared_functions.location_mapping.resolve_pin_to_location_code",
        lambda *_a, **_k: "P1_JHA",
    )
    monkeypatch.setattr(
        "backend.shared_functions.location_mapping.resolve_location_code_to_names",
        lambda *_a, **_k: {"province_name": "Koshi", "district_name": "Jhapa"},
    )

    return store


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def domain() -> Dict[str, Any]:
    """Load Rasa domain.yml once for all tests."""
    path = DOMAIN_YAML_PATH
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

