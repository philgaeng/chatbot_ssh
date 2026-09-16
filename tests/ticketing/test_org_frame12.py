"""Frame-12 (org lifecycle at scale) backend — server-side search + delete-impact preview."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app

pytestmark = pytest.mark.integration


def _client(db):
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="super@grm.local", role_keys=["super_admin"]
    )
    app.dependency_overrides[get_db] = lambda: iter([db])
    return TestClient(app)


def test_org_search_q_filters_by_name(db):
    try:
        client = _client(db)
        res = client.get("/api/v1/organizations", params={"q": "roads"})
        assert res.status_code == 200, res.text
        ids = [o["organization_id"] for o in res.json()]
        assert "DOR" in ids  # "Department of Roads"
        # A term that matches nothing returns an empty list, not everything.
        empty = client.get("/api/v1/organizations", params={"q": f"zzz-{uuid.uuid4().hex}"})
        assert empty.status_code == 200 and empty.json() == []
    finally:
        app.dependency_overrides.clear()


def test_delete_impact_reports_blocking_refs(db):
    try:
        client = _client(db)
        res = client.get("/api/v1/organizations/DOR/delete-impact")
        assert res.status_code == 200, res.text
        body = res.json()
        # DOR is the demo implementing agency — it has tickets/roles/scopes → not deletable.
        assert body["organization_id"] == "DOR"
        assert body["deletable"] is False
        assert body["role_count"] >= 1 and body["scope_count"] >= 1
        # Every guard field is present for the combined impact line.
        for key in (
            "child_count", "ticket_count", "role_count", "scope_count", "position_count",
            "workflow_assignment_count", "package_actor_count", "project_actor_count",
        ):
            assert key in body
    finally:
        app.dependency_overrides.clear()


def test_delete_impact_404_for_unknown_org(db):
    try:
        client = _client(db)
        res = client.get(f"/api/v1/organizations/NOPE_{uuid.uuid4().hex[:6]}/delete-impact")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()
