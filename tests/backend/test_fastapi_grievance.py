"""Tests for FastAPI backend API. Health, grievance. Same URL surface as Flask.
Run with the chatbot-rest env (conda activate chatbot-rest) so full app and celery load.

Note: the accessible-voice router (/accessible-file-upload, /submit-grievance,
/grievance-status/{id}) and the gsheet monitoring feed (/gsheet-get-grievances) were
removed with the legacy channels (CL-02); their tests were dropped with them. The
webchat voice-note path (/upload-voice-chunk, /upload-voice-complete) lives in the
file server router and is exercised by test_fastapi_files.py."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.fastapi_app import app

# T3-06: GET /{id} and POST /{id}/status now require x-api-key. These tests pin the
# key into the environment and send it, so they assert their actual subject (404 /
# 422 handling) rather than depending on ambient auth config. Without pinning they
# pass on a host via the env.local dev bypass (empty key + AUTH_MODE=bypass) but
# 401 in CI, which configures TICKETING_SECRET_KEY=ci-test-secret.
# Auth itself is covered in test_grievance_auth.py.
KEY = "fastapi-grievance-test-key"
AUTH = {"x-api-key": KEY}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def keyed():
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": KEY, "MESSAGING_API_KEY": ""}):
        yield


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
    r = client.get("/api/grievance/nonexistent-id-12345", headers=AUTH)
    assert r.status_code == 404
    body = r.json()
    assert body["status"] == "ERROR"
    assert "not found" in body.get("message", "").lower()


def test_post_status_not_found(client: TestClient):
    """POST /api/grievance/{id}/status returns 404 when grievance does not exist."""
    r = client.post(
        "/api/grievance/nonexistent-id-12345/status",
        json={"status_code": "RESOLVED"},
        headers=AUTH,
    )
    assert r.status_code == 404
    body = r.json()
    assert body["status"] == "ERROR"


def test_post_status_validation(client: TestClient):
    """POST /api/grievance/{id}/status requires status_code in body."""
    r = client.post(
        "/api/grievance/some-id/status",
        json={},
        headers=AUTH,
    )
    assert r.status_code == 422
