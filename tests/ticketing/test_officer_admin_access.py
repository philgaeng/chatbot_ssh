"""Country/project admin must load admin_scopes before is_admin checks (scope API)."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.models.base import SessionLocal
from ticketing.services.admin_access import AdminScopeRow, is_any_admin

pytestmark = pytest.mark.integration


def _scope_row(**kwargs) -> AdminScopeRow:
    base = dict(
        admin_scope_id=str(uuid.uuid4()),
        user_id=kwargs.get("user_id", "admin@grm.local"),
        role_key="country_admin",
        country_code="NP",
        project_id=None,
        organization_id=None,
        package_id=None,
        workflow_track="standard",
    )
    base.update(kwargs)
    return AdminScopeRow(**base)


def test_is_admin_requires_loaded_admin_scopes():
    """JWT operational roles alone do not grant admin; admin_scopes rows must be loaded."""
    bare = CurrentUser(user_id="c@grm.local", role_keys=["site_safeguards_focal_person"])
    assert not is_any_admin(bare)

    scoped = CurrentUser(
        user_id="c@grm.local",
        role_keys=["site_safeguards_focal_person"],
        admin_scopes=[_scope_row(user_id="c@grm.local")],
    )
    assert is_any_admin(scoped)


def test_country_admin_can_list_other_officer_scopes():
    db = SessionLocal()
    try:
        target = "officer.target@grm.local"

        def override_user():
            return CurrentUser(
                user_id="country-admin@grm.local",
                role_keys=["pd_piu_safeguards_focal"],
                organization_id="DOR",
                admin_scopes=[_scope_row(user_id="country-admin@grm.local")],
            )

        def override_db():
            yield db

        app.dependency_overrides[get_authenticated_user] = override_user
        app.dependency_overrides[get_db] = override_db
        client = TestClient(app)

        res = client.get(f"/api/v1/users/{target}/scopes")
        assert res.status_code == 200, res.text
    finally:
        app.dependency_overrides.clear()
        db.close()
