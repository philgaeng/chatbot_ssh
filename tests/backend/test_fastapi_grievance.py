"""Tests for FastAPI backend API. Health, grievance. Same URL surface as Flask.
Run with the chatbot-rest env (conda activate chatbot-rest) so full app and celery load.

Note: the accessible-voice router (/accessible-file-upload, /submit-grievance,
/grievance-status/{id}) and the gsheet monitoring feed (/gsheet-get-grievances) were
removed with the legacy channels (CL-02); their tests were dropped with them. The
webchat voice-note path (/upload-voice-chunk, /upload-voice-complete) lives in the
file server router and is exercised by test_fastapi_files.py."""

import pytest
from fastapi.testclient import TestClient

from backend.api.fastapi_app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client: TestClient):
    """GET /health returns 200 with plain text 'OK' (Flask contract)."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.text == "OK"


def test_get_grievance_statuses(client: TestClient):
    """GET /api/grievance/statuses returns SUCCESS and list of statuses."""
    r = client.get("/api/grievance/statuses")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "SUCCESS"
    assert "data" in body
    assert isinstance(body["data"], list)


def test_get_grievance_not_found(client: TestClient):
    """GET /api/grievance/{id} returns 404 with status ERROR when grievance does not exist."""
    r = client.get("/api/grievance/nonexistent-id-12345")
    assert r.status_code == 404
    body = r.json()
    assert body["status"] == "ERROR"
    assert "not found" in body.get("message", "").lower()


def test_post_status_not_found(client: TestClient):
    """POST /api/grievance/{id}/status returns 404 when grievance does not exist."""
    r = client.post(
        "/api/grievance/nonexistent-id-12345/status",
        json={"status_code": "RESOLVED"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["status"] == "ERROR"


def test_post_status_validation(client: TestClient):
    """POST /api/grievance/{id}/status requires status_code in body."""
    r = client.post(
        "/api/grievance/some-id/status",
        json={},
    )
    assert r.status_code == 422
