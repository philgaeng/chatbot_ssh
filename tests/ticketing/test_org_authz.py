"""SH-1 — org CRUD authz (OC-06 F3/F4).

Org create/update/delete are **standard-track** structural actions (doc 16 §7):
super_admin or a standard-track country_admin only. A SEAH-only country_admin and
any project_admin (who previously passed the blanket ``require_admin``) are refused.

The gate matrix is tested at the enforcement-function level (no app/DB, runs in CI);
the route wiring is asserted by the ``integration``-marked TestClient tests.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import (
    AdminScopeRow,
    SettingsAction,
    can_manage_org_structure,
    can_manage_structure,
    require_settings_write,
)


def _scope(role_key="country_admin", track="standard", project_id=None, user_id="a@grm.local"):
    return AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()),
        user_id=user_id,
        role_key=role_key,
        country_code="NP",
        project_id=project_id,
        organization_id=None,
        package_id=None,
        workflow_track=track,
    )


def _super():
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _country(track):
    return CurrentUser(
        user_id="c@grm.local", role_keys=[], admin_scopes=[_scope(track=track, user_id="c@grm.local")]
    )


def _project():
    return CurrentUser(
        user_id="p@grm.local",
        role_keys=[],
        admin_scopes=[_scope(role_key="project_admin", project_id="KL_ROAD", user_id="p@grm.local")],
    )


def _operational():
    return CurrentUser(user_id="o@grm.local", role_keys=["site_safeguards_focal_person"])


# name → (persona, may edit the org tree / org CRUD per doc 16 §7?)
_MATRIX = [
    ("super", _super(), True),
    ("country_standard", _country("standard"), True),
    ("country_seah", _country("seah"), False),
    ("project", _project(), False),
    ("operational", _operational(), False),
]


@pytest.mark.parametrize("name,user,allowed", _MATRIX)
def test_manage_org_structure_gate(name, user, allowed):
    """require_settings_write(MANAGE_ORG_STRUCTURE) is the org-CRUD gate (doc 16 §7)."""
    if allowed:
        require_settings_write(user, SettingsAction.MANAGE_ORG_STRUCTURE)  # no raise
    else:
        with pytest.raises(HTTPException) as exc:
            require_settings_write(user, SettingsAction.MANAGE_ORG_STRUCTURE)
        assert exc.value.status_code == 403


def test_can_manage_org_structure_is_standard_track_only():
    """F3/F4 fix: org structure is standard-track — SEAH country admin and project_admin refused."""
    assert can_manage_org_structure(_country("standard")) is True
    assert can_manage_org_structure(_country("seah")) is False
    assert can_manage_org_structure(_project()) is False
    assert can_manage_org_structure(_operational()) is False
    assert can_manage_org_structure(_super()) is True


def test_can_manage_structure_flag_remains_track_agnostic():
    """The project-structure display flag is unchanged — any-track country admin still passes,
    so SEAH project-structure affordances are not regressed by the new org gate."""
    assert can_manage_structure(_country("seah")) is True
    assert can_manage_structure(_country("standard")) is True
    assert can_manage_structure(_operational()) is False


# --- route wiring (integration: imports the app + runs lifespan) ---


@pytest.mark.integration
@pytest.mark.parametrize("name,user,allowed", _MATRIX)
def test_org_create_route_authz(name, user, allowed):
    """POST /organizations enforces the gate before body validation.

    Authorized personas fall through to the empty-name 400; unauthorized ones 403.
    """
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.models.base import SessionLocal

    db = SessionLocal()

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: user
    app.dependency_overrides[get_db] = _db
    try:
        client = TestClient(app)
        res = client.post("/api/v1/organizations", json={"name": ""})
        if allowed:
            assert res.status_code == 400, res.text  # guard passed; empty name rejected
        else:
            assert res.status_code == 403, res.text
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_org_update_delete_block_unauthorized():
    """PATCH/DELETE /organizations 403 for a project_admin (blanket require_admin used to allow it)."""
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.models.base import SessionLocal

    db = SessionLocal()

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: _project()
    app.dependency_overrides[get_db] = _db
    try:
        client = TestClient(app)
        assert client.patch("/api/v1/organizations/DOR", json={"name": "x"}).status_code == 403
        assert client.delete("/api/v1/organizations/DOR").status_code == 403
    finally:
        app.dependency_overrides.clear()
        db.close()
