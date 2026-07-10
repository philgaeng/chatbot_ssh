"""OC-02 — position types + the position→role matrix.

Pure (no DB, CI): slug normalization, role↔position-track compatibility, the authoring
gate. Integration (@pytest.mark.integration, live DB + seed): /position-types CRUD,
matrix validation, position_key immutability, and the in-use delete guard.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from ticketing.api.dependencies import CurrentUser
from ticketing.api.routers.position_types import _role_ok_for_position_track, _slugify_key
from ticketing.services.admin_access import (
    AdminScopeRow,
    SettingsAction,
    require_settings_write,
)


# ── personas ─────────────────────────────────────────────────────────────────

def _scope(role_key="country_admin", track="standard", project_id=None, user_id="a@grm.local"):
    return AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()), user_id=user_id, role_key=role_key,
        country_code="NP", project_id=project_id, organization_id=None,
        package_id=None, workflow_track=track,
    )


def _super():
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _country(track):
    return CurrentUser(user_id="c@grm.local", role_keys=[],
                       admin_scopes=[_scope(track=track, user_id="c@grm.local")])


def _project():
    return CurrentUser(user_id="p@grm.local", role_keys=[],
                       admin_scopes=[_scope(role_key="project_admin", project_id="KL_ROAD", user_id="p@grm.local")])


_MATRIX = [
    ("super", _super(), True),
    ("country_standard", _country("standard"), True),
    ("country_seah", _country("seah"), False),
    ("project", _project(), False),
]


@pytest.mark.parametrize("name,user,allowed", _MATRIX)
def test_position_types_authoring_gate(name, user, allowed):
    """Authoring position types is the standard-track MANAGE_ORG_STRUCTURE action (doc 16 §7)."""
    if allowed:
        require_settings_write(user, SettingsAction.MANAGE_ORG_STRUCTURE)
    else:
        with pytest.raises(HTTPException) as exc:
            require_settings_write(user, SettingsAction.MANAGE_ORG_STRUCTURE)
        assert exc.value.status_code == 403


# ── pure logic ───────────────────────────────────────────────────────────────

def test_slugify_key():
    assert _slugify_key("Senior Divisional Engineer") == "senior_divisional_engineer"
    assert _slugify_key("  GRC-Chair!! ") == "grc_chair"
    assert _slugify_key("already_ok") == "already_ok"
    assert _slugify_key("###") == ""


def test_role_track_compatibility():
    # single-track position: reuse the SH-2 predicate
    assert _role_ok_for_position_track("Standard", "standard") is True
    assert _role_ok_for_position_track("Standard", "seah") is False
    assert _role_ok_for_position_track("SEAH", "seah") is True
    assert _role_ok_for_position_track("SEAH", "standard") is False
    assert _role_ok_for_position_track("Both", "standard") is True
    assert _role_ok_for_position_track(None, "seah") is True  # unscoped role → any track
    # 'both'-track position needs a role usable on BOTH tracks
    assert _role_ok_for_position_track("Both", "both") is True
    assert _role_ok_for_position_track(None, "both") is True
    assert _role_ok_for_position_track("Standard", "both") is False
    assert _role_ok_for_position_track("SEAH", "both") is False


# ── integration ──────────────────────────────────────────────────────────────

@pytest.fixture
def cleanup_pts():
    ids: list[str] = []
    yield ids
    from ticketing.models.base import SessionLocal
    from ticketing.models.position_type import PositionType

    s = SessionLocal()
    try:
        for pid in ids:
            obj = s.get(PositionType, pid)
            if obj:
                s.delete(obj)
        s.commit()
    finally:
        s.close()


def _client(user):
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import get_authenticated_user, get_db
    from ticketing.api.main import app
    from ticketing.models.base import SessionLocal

    db = SessionLocal()

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: user
    app.dependency_overrides[get_db] = _db
    return app, TestClient(app), db


def _key(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


# The seed guarantees these standard-track roles exist in the test DB.
_ROLE_STD = "site_safeguards_focal_person"


@pytest.mark.integration
def test_create_and_list(cleanup_pts):
    app, client, db = _client(_super())
    try:
        key = _key("sde")
        res = client.post("/api/v1/position-types", json={
            "position_key": key.upper() + " raw",  # exercises slugify
            "display_name": "Senior Divisional Engineer",
            "display_name_ne": "वरिष्ठ इन्जिनियर",
            "allowed_unit_types": ["division_office"],
            "default_role_key": _ROLE_STD,
            "visibility_mode": "none",
            "workflow_track": "standard",
        })
        assert res.status_code == 201, res.text
        body = res.json()
        cleanup_pts.append(body["position_type_id"])
        assert body["position_key"] == _slugify_key(key.upper() + " raw")
        assert body["default_role_key"] == _ROLE_STD
        # visible in the standard-track filtered list
        listed = client.get("/api/v1/position-types?workflow_track=standard").json()
        assert any(p["position_type_id"] == body["position_type_id"] for p in listed)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_create_validations(cleanup_pts):
    app, client, db = _client(_super())
    try:
        # unknown default_role_key
        assert client.post("/api/v1/position-types", json={
            "position_key": _key("x"), "display_name": "X", "default_role_key": "no_such_role",
        }).status_code == 422
        # invalid unit_type
        assert client.post("/api/v1/position-types", json={
            "position_key": _key("x"), "display_name": "X", "default_role_key": _ROLE_STD,
            "allowed_unit_types": ["spaceship"],
        }).status_code == 422
        # self-reference
        selfkey = _key("selfref")
        assert client.post("/api/v1/position-types", json={
            "position_key": selfkey, "display_name": "Self", "default_role_key": _ROLE_STD,
            "reports_to_position_key": _slugify_key(selfkey),
        }).status_code == 422
        # unknown reports_to
        assert client.post("/api/v1/position-types", json={
            "position_key": _key("x"), "display_name": "X", "default_role_key": _ROLE_STD,
            "reports_to_position_key": "ghost_position",
        }).status_code == 422
        # unknown owner org
        assert client.post("/api/v1/position-types", json={
            "position_key": _key("x"), "display_name": "X", "default_role_key": _ROLE_STD,
            "owner_organization_id": "NO_SUCH_ORG",
        }).status_code == 422
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_duplicate_key_conflict(cleanup_pts):
    app, client, db = _client(_super())
    try:
        key = _key("dup")
        r1 = client.post("/api/v1/position-types", json={
            "position_key": key, "display_name": "First", "default_role_key": _ROLE_STD})
        assert r1.status_code == 201, r1.text
        cleanup_pts.append(r1.json()["position_type_id"])
        r2 = client.post("/api/v1/position-types", json={
            "position_key": key, "display_name": "Second", "default_role_key": _ROLE_STD})
        assert r2.status_code == 409, r2.text
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_patch_key_immutable_and_fields(cleanup_pts):
    app, client, db = _client(_super())
    try:
        key = _key("patch")
        created = client.post("/api/v1/position-types", json={
            "position_key": key, "display_name": "Before", "default_role_key": _ROLE_STD}).json()
        pid = created["position_type_id"]
        cleanup_pts.append(pid)
        # sending position_key is ignored (field not on the update schema); display_name changes
        res = client.patch(f"/api/v1/position-types/{pid}", json={
            "position_key": "hacked_key", "display_name": "After", "visibility_mode": "direct_reports"})
        assert res.status_code == 200, res.text
        assert res.json()["position_key"] == _slugify_key(key)  # unchanged
        assert res.json()["display_name"] == "After"
        assert res.json()["visibility_mode"] == "direct_reports"
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_delete_guard_on_reports_to(cleanup_pts):
    app, client, db = _client(_super())
    try:
        parent_key = _key("parent")
        parent = client.post("/api/v1/position-types", json={
            "position_key": parent_key, "display_name": "Parent", "default_role_key": _ROLE_STD}).json()
        child = client.post("/api/v1/position-types", json={
            "position_key": _key("child"), "display_name": "Child", "default_role_key": _ROLE_STD,
            "reports_to_position_key": _slugify_key(parent_key), "reports_to_locus": "parent_unit"}).json()
        cleanup_pts.extend([parent["position_type_id"], child["position_type_id"]])
        # parent is referenced by child.reports_to → blocked
        blocked = client.delete(f"/api/v1/position-types/{parent['position_type_id']}")
        assert blocked.status_code == 409, blocked.text
        assert "in use" in blocked.text.lower()
        # delete child first, then parent succeeds
        assert client.delete(f"/api/v1/position-types/{child['position_type_id']}").status_code == 204
        assert client.delete(f"/api/v1/position-types/{parent['position_type_id']}").status_code == 204
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_authz_blocks_project_admin():
    app, client, db = _client(_project())
    try:
        assert client.post("/api/v1/position-types", json={
            "position_key": "x", "display_name": "X", "default_role_key": _ROLE_STD}).status_code == 403
    finally:
        app.dependency_overrides.clear()
        db.close()
