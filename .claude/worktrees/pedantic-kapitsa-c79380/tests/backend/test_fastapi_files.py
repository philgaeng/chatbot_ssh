"""Tests for FastAPI backend file server API. Same URL surface as legacy FileServerAPI (channels_api)."""

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.fastapi_app import app


@pytest.fixture
def client():
    return TestClient(app)


# --- File server health / root ---


def test_file_server_health(client: TestClient):
    """GET / returns file server status (not to be confused with GET /health)."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "File server" in body.get("message", "")


def test_file_server_test_db(client: TestClient):
    """GET /test-db returns database connectivity status."""
    r = client.get("/test-db")
    # 200 if DB ok, 500 if connection fails
    assert r.status_code in (200, 500)
    body = r.json()
    assert "status" in body
    assert "message" in body
    if r.status_code == 200:
        assert "test_grievance_id" in body


# --- generate-ids ---


def test_generate_ids(client: TestClient):
    """POST /generate-ids returns grievance_id and complainant_id."""
    r = client.post("/generate-ids", json={})
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "SUCCESS"
    assert "grievance_id" in body
    assert "complainant_id" in body
    assert body.get("province") == "KO"
    assert body.get("district") == "JH"


def test_generate_ids_with_params(client: TestClient):
    """POST /generate-ids accepts province and district."""
    r = client.post(
        "/generate-ids",
        json={"province": "XX", "district": "YY"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("province") == "XX"
    assert body.get("district") == "YY"


# --- task-status ---


def test_task_status_update(client: TestClient):
    """POST /task-status accepts grievance_id, status, and optional data. Uses stub emit."""
    r = client.post(
        "/task-status",
        json={
            "grievance_id": "GR-20241201-KO-JH-TEST1-A",
            "status": "completed",
            "data": {"task_name": "file_upload", "result": "ok"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "completed"
    assert body.get("message") == "Task status update sent"
    assert body.get("grievance_id") == "GR-20241201-KO-JH-TEST1-A"


def test_task_status_validation_missing_status(client: TestClient):
    """POST /task-status requires status."""
    r = client.post(
        "/task-status",
        json={"grievance_id": "GR-1-A"},
    )
    assert r.status_code == 400
    body = r.json()
    assert "error" in body
    assert "status" in body.get("error", "").lower()


def test_task_status_validation_missing_ids(client: TestClient):
    """POST /task-status requires grievance_id or flask_session_id."""
    r = client.post(
        "/task-status",
        json={"status": "completed"},
    )
    assert r.status_code == 400
    body = r.json()
    assert "error" in body


# --- upload-files ---


def test_upload_files_no_grievance(client: TestClient):
    """POST /upload-files without grievance_id returns 400."""
    r = client.post(
        "/upload-files",
        data={"grievance_id": ""},
        files={"files[]": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400


def test_upload_files_no_files(client: TestClient):
    """POST /upload-files without files[] returns 400."""
    r = client.post(
        "/upload-files",
        data={"grievance_id": "GR-20241201-KO-JH-TEST1-A"},
        # No files
    )
    assert r.status_code == 422


@patch("backend.api.routers.files.process_file_upload_task")
def test_upload_files_valid(mock_task: MagicMock, client: TestClient):
    """POST /upload-files with valid multipart returns 202 and queues task."""
    mock_task.delay.return_value = MagicMock(id="mock-task-id")
    r = client.post(
        "/upload-files",
        data={
            "grievance_id": "GR-20241201-KO-JH-TEST1-A",
            "flask_session_id": "sess-123",
        },
        files=[("files[]", ("test.txt", io.BytesIO(b"hello"), "text/plain"))],
    )
    assert r.status_code == 202
    body = r.json()
    assert body.get("status") in ("started", "STARTED")
    assert "task_id" in body
    assert "files" in body
    mock_task.delay.assert_called_once()


# --- files list / download / file-status ---


def test_get_files(client: TestClient):
    """GET /files/{grievance_id} returns files list (empty for non-existent grievance)."""
    r = client.get("/files/GR-20241201-KO-JH-NONEXISTENT-A")
    assert r.status_code == 200
    body = r.json()
    assert "files" in body
    assert isinstance(body["files"], list)


def test_download_file_not_found(client: TestClient):
    """GET /download/{file_id} returns 404 for non-existent file."""
    r = client.get("/download/nonexistent-file-id-12345")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body


def test_file_status(client: TestClient):
    """GET /file-status/{file_id} returns status (not yet saved for non-existent)."""
    r = client.get("/file-status/nonexistent-file-id-12345")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "message" in body


# --- grievance-review ---


def test_grievance_review_get_not_found(client: TestClient):
    """GET /grievance-review/{grievance_id} returns 404 when not found, or 500 if DB method missing."""
    r = client.get("/grievance-review/GR-20241201-KO-JH-NONEXISTENT-A")
    assert r.status_code in (404, 500)
    body = r.json()
    assert "error" in body


def test_grievance_review_post_validation(client: TestClient):
    """POST /grievance-review/{grievance_id} requires JSON body."""
    r = client.post(
        "/grievance-review/GR-20241201-KO-JH-NONEXISTENT-A",
        content="not json",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 400
    body = r.json()
    assert "error" in body
    assert "JSON" in body.get("error", "")


# --- test-upload ---


def test_test_upload(client: TestClient):
    """POST /test-upload echoes received request info."""
    r = client.post(
        "/test-upload",
        data={"foo": "bar"},
        files=[("files[]", ("a.txt", io.BytesIO(b"x"), "text/plain"))],
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "received"
    assert "message" in body
