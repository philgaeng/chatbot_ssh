"""Roles API + admin_access integration tests (matrix guards)."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.models.base import SessionLocal
from ticketing.models.user import Role
from ticketing.services.admin_access import AdminScopeRow
from ticketing.constants.role_archetypes import validate_operational_permissions

pytestmark = pytest.mark.integration


def _user(
    email: str,
    role_keys: list[str],
    scopes: list[AdminScopeRow] | None = None,
) -> CurrentUser:
    return CurrentUser(
        user_id=email,
        role_keys=role_keys,
        organization_id="DOR",
        admin_scopes=scopes or [],
    )


def _scope_row(**kwargs) -> AdminScopeRow:
    base = dict(
        admin_scope_id=str(uuid.uuid4()),
        user_id=kwargs.get("user_id", "x@grm.local"),
        role_key="country_admin",
        country_code="NP",
        project_id=None,
        organization_id=None,
        package_id=None,
        workflow_track="standard",
    )
    base.update(kwargs)
    return AdminScopeRow(**base)


def _db_override(db):
    def override_get_db():
        yield db

    return override_get_db


@pytest.fixture
def client():
    db = SessionLocal()
    try:
        def override_user():
            return _user("test@grm.local", ["super_admin"])

        app.dependency_overrides[get_authenticated_user] = override_user
        app.dependency_overrides[get_db] = _db_override(db)
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_operational_roles_list_excludes_admin_keys(client: TestClient):
    res = client.get("/api/v1/roles?kind=operational")
    assert res.status_code == 200
    keys = {r["role_key"] for r in res.json()}
    assert "super_admin" not in keys
    assert "country_admin" not in keys
    assert "project_admin" not in keys
    assert "site_safeguards_focal_person" in keys


def test_archetype_rejects_admin_permissions():
    with pytest.raises(ValueError, match="admin permissions"):
        validate_operational_permissions(["tickets:read", "settings:write"])


def test_country_admin_creates_custom_role():
    db = SessionLocal()
    try:
        def override_user():
            return _user(
                "country-admin@grm.local",
                ["country_admin"],
                [_scope_row(user_id="country-admin@grm.local", workflow_track="standard")],
            )

        app.dependency_overrides[get_authenticated_user] = override_user
        app.dependency_overrides[get_db] = _db_override(db)
        c = TestClient(app)

        key = f"test_custom_{uuid.uuid4().hex[:8]}"
        res = c.post(
            "/api/v1/roles",
            json={
                "display_name": "Test Custom Role",
                "role_key": key,
                "workflow_scope": "Standard",
                "jurisdiction_mode": "field",
                "archetype": "field_actor",
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["role_origin"] == "custom"
        assert body["role_key"] == key

        role = db.execute(select(Role).where(Role.role_key == key)).scalar_one()
        db.delete(role)
        db.commit()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_project_admin_cannot_create_role():
    db = SessionLocal()
    try:
        def override_user():
            return _user(
                "project-admin@grm.local",
                ["project_admin"],
                [_scope_row(
                    user_id="project-admin@grm.local",
                    role_key="project_admin",
                    project_id="KL_ROAD",
                    country_code=None,
                )],
            )

        app.dependency_overrides[get_authenticated_user] = override_user
        app.dependency_overrides[get_db] = _db_override(db)
        c = TestClient(app)

        res = c.post(
            "/api/v1/roles",
            json={
                "display_name": "Blocked Role",
                "workflow_scope": "Standard",
                "archetype": "field_actor",
            },
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_seah_country_admin_cannot_create_project():
    db = SessionLocal()
    try:
        def override_user():
            return _user(
                "country-admin-seah@grm.local",
                ["country_admin"],
                [_scope_row(user_id="country-admin-seah@grm.local", workflow_track="seah")],
            )

        app.dependency_overrides[get_authenticated_user] = override_user
        app.dependency_overrides[get_db] = _db_override(db)
        c = TestClient(app)

        res = c.post(
            "/api/v1/projects",
            json={
                "country_code": "NP",
                "short_code": f"T{uuid.uuid4().hex[:6].upper()}",
                "name": "Test Project",
            },
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_standard_country_admin_can_create_project():
    db = SessionLocal()
    try:
        def override_user():
            return _user(
                "country-admin@grm.local",
                ["country_admin"],
                [_scope_row(user_id="country-admin@grm.local", workflow_track="standard")],
            )

        app.dependency_overrides[get_authenticated_user] = override_user
        app.dependency_overrides[get_db] = _db_override(db)
        c = TestClient(app)

        code = f"T{uuid.uuid4().hex[:6].upper()}"
        res = c.post(
            "/api/v1/projects",
            json={
                "country_code": "NP",
                "short_code": code,
                "name": "Matrix Test Project",
                "is_active": False,
            },
        )
        assert res.status_code == 201, res.text

        from ticketing.models.project import Project

        proj = db.execute(select(Project).where(Project.short_code == code)).scalar_one()
        db.delete(proj)
        db.commit()
    finally:
        app.dependency_overrides.clear()
        db.close()
