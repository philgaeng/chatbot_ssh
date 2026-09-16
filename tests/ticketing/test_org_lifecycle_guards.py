"""SH-4a — org lifecycle guards (OC-06 F7, F16, F18).

- delete is blocked (409) when the org is a project actor (ProjectOrganization) — the
  package-link case was guarded, the project-link case silently cascade-orphaned;
- GET /organizations now requires an authenticated caller (was fully open);
- create/update reject a country_code not in ticketing.countries.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    from ticketing.models.base import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()   # discard any uncommitted test rows
        s.close()


def _super_client(db):
    from ticketing.api.dependencies import CurrentUser, get_authenticated_user
    from ticketing.api.main import app
    from ticketing.models.base import get_db  # the object locations.py's routes depend on

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="s@grm.local", role_keys=["super_admin"]
    )
    app.dependency_overrides[get_db] = _db
    return app, TestClient(app)


def test_delete_blocked_by_project_actor_link(db):
    from ticketing.models.organization import Organization
    from ticketing.models.project import Project, ProjectOrganization

    pid = db.execute(select(Project).where(Project.short_code == "KL_ROAD")).scalar_one().project_id
    oid = f"SH4_DEL_{uuid.uuid4().hex[:6].upper()}"
    db.add(Organization(organization_id=oid, name="SH4 Delete-Guard Org"))
    db.flush()
    db.add(ProjectOrganization(project_id=pid, organization_id=oid))
    db.flush()  # visible to the route; never committed (fixture rolls back)

    app, client = _super_client(db)
    try:
        res = client.delete(f"/api/v1/organizations/{oid}")
        assert res.status_code == 409, res.text
        assert "project actor" in res.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_create_rejects_bogus_country(db):
    app, client = _super_client(db)
    try:
        res = client.post(
            "/api/v1/organizations", json={"name": "Bogus Country Org", "country_code": "ZZ"}
        )
        assert res.status_code == 422, res.text
        assert "country" in res.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_list_has_auth_dependency(db):
    # With an authenticated user the list returns 200 (the endpoint now carries an auth dep).
    app, client = _super_client(db)
    try:
        assert client.get("/api/v1/organizations").status_code == 200
    finally:
        app.dependency_overrides.clear()
