"""Tests for FastAPI backend API (Agent 8A, 8D). Health, grievance, voice, gsheet. Same URL surface as Flask.
Run with the chatbot-rest env (conda activate chatbot-rest) so full app and celery load."""

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


# --- Voice router (8D.1) ---


def test_accessible_file_upload_missing_grievance_id(client: TestClient):
    """POST /accessible-file-upload without grievance_id returns 422 (validation)."""
    r = client.post("/accessible-file-upload", data={}, files=[])
    assert r.status_code == 422


def test_grievance_status_not_found(client: TestClient):
    """GET /grievance-status/{id} returns 404 when grievance does not exist."""
    r = client.get("/grievance-status/nonexistent-grv-123")
    assert r.status_code == 404
    body = r.json()
    assert "not found" in (body.get("error") or body.get("message") or body.get("detail") or "").lower()


def test_submit_grievance_no_audio(client: TestClient):
    """POST /submit-grievance with form but no audio files returns 400."""
    r = client.post(
        "/submit-grievance",
        data={
            "complainant_id": "cmp1",
            "grievance_id": "GRV001",
            "province": "Province 1",
            "district": "Kathmandu",
        },
    )
    assert r.status_code == 400
    body = r.json()
    assert "status" in body and body.get("error")


# --- Gsheet router (8D.2) ---


def test_gsheet_get_grievances_unauthorized(client: TestClient):
    """GET /gsheet-get-grievances without Bearer returns 403."""
    r = client.get("/gsheet-get-grievances")
    assert r.status_code == 403
    body = r.json()
    assert "message" in body or "invalid" in str(body).lower()
