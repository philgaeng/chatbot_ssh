"""R4 (BUILD-REVIEW MO2) — attenuated delegation for project_admin appointment: an org_admin
may only appoint a project_admin on a project whose implementing agency is in its subtree."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.api.routers.users import _org_admin_covers_project
from ticketing.services.admin_access import AdminScopeRow

pytestmark = pytest.mark.integration


def _org_admin(org_id: str) -> CurrentUser:
    return CurrentUser(
        user_id=f"oa-{org_id.lower()}@grm.local",
        role_keys=["org_admin"],
        admin_scopes=[AdminScopeRow(
            admin_scope_id=str(uuid.uuid4()), user_id=f"oa-{org_id.lower()}@grm.local",
            role_key="org_admin", country_code="NP", project_id=None,
            organization_id=org_id, package_id=None, workflow_track="standard",
        )],
    )


def test_org_admin_covers_project_helper(db, kl_road_project):
    # KL Road's implementing agency is DOR (government root); ADB is a donor participant root.
    dor_admin = _org_admin("DOR")
    adb_admin = _org_admin("ADB")
    assert _org_admin_covers_project(db, dor_admin, kl_road_project.project_id, "standard") is True
    # A donor's org_admin (participant, not the IA) must NOT cover the funded project.
    assert _org_admin_covers_project(db, adb_admin, kl_road_project.project_id, "standard") is False


def test_org_admin_cannot_appoint_project_admin_outside_subtree(db, kl_road_project):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        app.dependency_overrides[get_authenticated_user] = lambda: _org_admin("ADB")
        client = TestClient(app)
        res = client.post("/api/v1/admin-scopes", json={
            "user_id": f"newpa-{uuid.uuid4().hex[:6]}@grm.local",
            "role_key": "project_admin",
            "project_id": kl_road_project.project_id,
            "workflow_track": "standard",
        })
        assert res.status_code == 403, res.text
        assert "within your subtree" in res.text
    finally:
        app.dependency_overrides.clear()
        db.rollback()
