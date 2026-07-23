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

def _scope(role_key="org_admin", track="standard", project_id=None, user_id="a@grm.local"):
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


# The seed guarantees these standard-track roles exist in the test DB.
_ROLE_STD = "site_safeguards_focal_person"


@pytest.mark.integration
def test_create_and_list(cleanup_pts):
    app, client, db = _client(_super())
    try:
        title = "Senior Divisional Engineer " + uuid.uuid4().hex[:6]
        res = client.post("/api/v1/position-types", json={
            "display_name": title,
            "display_name_ne": "वरिष्ठ इन्जिनियर",
            "allowed_unit_types": ["division_office"],
        })
        assert res.status_code == 201, res.text
        body = res.json()
        cleanup_pts.append(body["position_type_id"])
        # position_key is server-minted from the title (never user-supplied)
        assert body["position_key"] == _slugify_key(title)
        # a title carries no role at create (DESIGN-cast-model §3.2)
        assert body["default_role_key"] is None
        # visible in the standard-track filtered list (positions default to standard track)
        listed = client.get("/api/v1/position-types?workflow_track=standard").json()
        assert any(p["position_type_id"] == body["position_type_id"] for p in listed)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_create_validations(cleanup_pts):
    app, client, db = _client(_super())
    try:
        # invalid unit_type (default_role_key is no longer a create field — a title has no role)
        assert client.post("/api/v1/position-types", json={
            "display_name": "X",
            "allowed_unit_types": ["spaceship"],
        }).status_code == 422
        # self-reference: the minted key equals slugify(title), so point reports_to at it
        selftitle = "Self " + uuid.uuid4().hex[:6]
        assert client.post("/api/v1/position-types", json={
            "display_name": selftitle,
            "reports_to_position_key": _slugify_key(selftitle),
        }).status_code == 422
        # unknown reports_to
        assert client.post("/api/v1/position-types", json={
            "display_name": "X",
            "reports_to_position_key": "ghost_position",
        }).status_code == 422
        # owner_organization_id is server-stamped, not taken from the body — an unknown owner
        # in the body is ignored (no longer a create field), so this now succeeds.
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_create_without_default_role(cleanup_pts):
    """DESIGN-cast-model §3.2: a position is a display-only title — creatable with no role.
    The tier is chosen later at per-package staffing."""
    app, client, db = _client(_super())
    try:
        title = "Untiered Title " + uuid.uuid4().hex[:6]
        res = client.post("/api/v1/position-types", json={"display_name": title})
        assert res.status_code == 201, res.text
        body = res.json()
        cleanup_pts.append(body["position_type_id"])
        assert body["position_key"] == _slugify_key(title)
        assert body["default_role_key"] is None
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_duplicate_title_gets_unique_key(cleanup_pts):
    """Two positions with the same title get distinct server-minted keys (auto-suffixed).
    The old user-supplied-key 409 path is gone — a duplicate key can no longer be requested."""
    app, client, db = _client(_super())
    try:
        title = "Dup " + uuid.uuid4().hex[:6]
        r1 = client.post("/api/v1/position-types", json={
            "display_name": title, "default_role_key": _ROLE_STD})
        r2 = client.post("/api/v1/position-types", json={
            "display_name": title, "default_role_key": _ROLE_STD})
        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text
        cleanup_pts.extend([r1.json()["position_type_id"], r2.json()["position_type_id"]])
        k1, k2 = r1.json()["position_key"], r2.json()["position_key"]
        assert k1 == _slugify_key(title)
        assert k2 == f"{_slugify_key(title)}_2"  # auto-suffixed, never a collision
        assert k1 != k2
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_patch_key_immutable_and_fields(cleanup_pts):
    app, client, db = _client(_super())
    try:
        created = client.post("/api/v1/position-types", json={
            "display_name": "Before " + uuid.uuid4().hex[:6], "default_role_key": _ROLE_STD}).json()
        pid = created["position_type_id"]
        genkey = created["position_key"]  # server-minted
        cleanup_pts.append(pid)
        # sending position_key is ignored (field not on the update schema); display_name changes
        res = client.patch(f"/api/v1/position-types/{pid}", json={
            "position_key": "hacked_key", "display_name": "After", "visibility_mode": "direct_reports"})
        assert res.status_code == 200, res.text
        assert res.json()["position_key"] == genkey  # immutable
        assert res.json()["display_name"] == "After"
        assert res.json()["visibility_mode"] == "direct_reports"
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_delete_guard_on_reports_to(cleanup_pts):
    app, client, db = _client(_super())
    try:
        parent = client.post("/api/v1/position-types", json={
            "display_name": "Parent " + uuid.uuid4().hex[:6], "default_role_key": _ROLE_STD}).json()
        child = client.post("/api/v1/position-types", json={
            "display_name": "Child " + uuid.uuid4().hex[:6], "default_role_key": _ROLE_STD,
            "reports_to_position_key": parent["position_key"], "reports_to_locus": "parent_unit"}).json()
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
            "display_name": "X", "default_role_key": _ROLE_STD}).status_code == 403
    finally:
        app.dependency_overrides.clear()
        db.close()
