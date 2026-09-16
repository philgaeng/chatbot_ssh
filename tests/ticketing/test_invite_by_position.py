"""R7 (BUILD-REVIEW M5) — inviting a NEW officer by position records the officer_positions
row (parity with assign_officer_position), so the directory shows the position."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

import ticketing.services.officer_admin as officer_admin
from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.models.officer_position import OfficerPosition
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.position_type import PositionType
from ticketing.models.user import UserRole

pytestmark = pytest.mark.integration


def _cleanup(db, email):
    from ticketing.models.officer_onboarding import OfficerOnboarding
    from ticketing.services.officer_admin import _lifecycle_user_key

    db.execute(delete(OfficerPosition).where(OfficerPosition.user_id == email))
    db.execute(delete(OfficerScope).where(OfficerScope.user_id == email))
    db.execute(delete(UserRole).where(UserRole.user_id == email))
    ob = db.get(OfficerOnboarding, _lifecycle_user_key(email))
    if ob is not None:
        db.delete(ob)
    db.commit()


def test_invite_with_position_creates_officer_position(db, monkeypatch):
    # A seeded field-role position type (OC-02 seeds DoR position types).
    pt = db.execute(
        select(PositionType).where(PositionType.default_role_key == "site_safeguards_focal_person")
    ).scalars().first()
    if pt is None:
        pt = db.execute(select(PositionType)).scalars().first()
    assert pt is not None, "no position types seeded"

    monkeypatch.setattr(officer_admin, "keycloak_configured", lambda: False)
    monkeypatch.setattr(officer_admin, "sync_officer_keycloak_roles", lambda *a, **k: None)

    email = f"invpos-{uuid.uuid4().hex[:8]}@grm.local"

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="super@grm.local", role_keys=["super_admin"]
    )
    try:
        res = TestClient(app).post("/api/v1/users/invite", json={
            "email": email,
            "role_key": pt.default_role_key,
            "organization_id": "DOR",
            "project_code": "KL_ROAD",
            "location_code": "P1",
            "includes_children": True,
            "position_type_id": pt.position_type_id,
        })
        assert res.status_code == 201, res.text
        # The descriptive position row exists...
        op = db.execute(
            select(OfficerPosition).where(OfficerPosition.user_id == email)
        ).scalar_one_or_none()
        assert op is not None and op.position_type_id == pt.position_type_id
        # ...and the enforcement rows (role + scope) were minted by the pre-fill path.
        assert db.execute(select(UserRole).where(UserRole.user_id == email)).first() is not None
        assert db.execute(select(OfficerScope).where(OfficerScope.user_id == email)).first() is not None
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, email)


def test_invite_without_position_creates_no_position_row(db, monkeypatch):
    monkeypatch.setattr(officer_admin, "keycloak_configured", lambda: False)
    monkeypatch.setattr(officer_admin, "sync_officer_keycloak_roles", lambda *a, **k: None)
    email = f"invnopos-{uuid.uuid4().hex[:8]}@grm.local"

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="super@grm.local", role_keys=["super_admin"]
    )
    try:
        res = TestClient(app).post("/api/v1/users/invite", json={
            "email": email,
            "role_key": "site_safeguards_focal_person",
            "organization_id": "DOR",
            "project_code": "KL_ROAD",
            "location_code": "P1",
            "includes_children": True,
        })
        assert res.status_code == 201, res.text
        assert db.execute(
            select(OfficerPosition).where(OfficerPosition.user_id == email)
        ).scalar_one_or_none() is None
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, email)


def test_invite_by_position_without_role_creates_position_only(db, monkeypatch):
    """DESIGN-cast-model §3.4: a role-free, position-based invite records the descriptive
    position but mints NO enforcement rows — the role/tier is bound later by Cast staffing."""
    pt = db.execute(select(PositionType)).scalars().first()
    assert pt is not None, "no position types seeded"

    monkeypatch.setattr(officer_admin, "keycloak_configured", lambda: False)
    monkeypatch.setattr(officer_admin, "sync_officer_keycloak_roles", lambda *a, **k: None)
    email = f"invcast-{uuid.uuid4().hex[:8]}@grm.local"

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="super@grm.local", role_keys=["super_admin"]
    )
    try:
        res = TestClient(app).post("/api/v1/users/invite", json={
            "email": email,
            "organization_id": "DOR",
            "position_type_id": pt.position_type_id,
        })
        assert res.status_code == 201, res.text
        # Descriptive position row exists...
        op = db.execute(
            select(OfficerPosition).where(OfficerPosition.user_id == email)
        ).scalar_one_or_none()
        assert op is not None and op.position_type_id == pt.position_type_id
        # ...but NO enforcement rows — access comes from Cast staffing, not the invite.
        assert db.execute(select(UserRole).where(UserRole.user_id == email)).first() is None
        assert db.execute(select(OfficerScope).where(OfficerScope.user_id == email)).first() is None
        # ...and the invitee surfaces in the roster (Directory) as position-only.
        roster = TestClient(app).get("/api/v1/users/roster")
        assert roster.status_code == 200, roster.text
        body = roster.json()
        items = body.get("items", body) if isinstance(body, dict) else body
        entry = next((e for e in items if e.get("user_id") == email), None)
        assert entry is not None, "position-only invitee missing from roster"
        assert entry.get("role_keys") == []
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, email)


def test_delete_position_only_officer(db, monkeypatch):
    """A role-free invitee has no user_roles/officer_scopes — deleting them must still work
    (had_db must count officer_positions, else it 404s)."""
    pt = db.execute(select(PositionType)).scalars().first()
    assert pt is not None
    monkeypatch.setattr(officer_admin, "keycloak_configured", lambda: False)
    monkeypatch.setattr(officer_admin, "sync_officer_keycloak_roles", lambda *a, **k: None)
    monkeypatch.setattr(officer_admin, "keycloak_delete_user", lambda *a, **k: False)
    email = f"invdel-{uuid.uuid4().hex[:8]}@grm.local"

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="super@grm.local", role_keys=["super_admin"]
    )
    try:
        client = TestClient(app)
        assert client.post("/api/v1/users/invite", json={
            "email": email, "organization_id": "DOR", "position_type_id": pt.position_type_id,
        }).status_code == 201
        # The position-only officer can be removed (not 404).
        assert client.delete(f"/api/v1/users/{email}").status_code == 204
        assert db.execute(
            select(OfficerPosition).where(OfficerPosition.user_id == email)
        ).scalar_one_or_none() is None
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, email)


def test_invite_without_role_or_position_is_rejected(db, monkeypatch):
    """A role-free invite must still name a position — neither role_key nor position_type_id → 422."""
    monkeypatch.setattr(officer_admin, "keycloak_configured", lambda: False)
    monkeypatch.setattr(officer_admin, "sync_officer_keycloak_roles", lambda *a, **k: None)
    email = f"invbad-{uuid.uuid4().hex[:8]}@grm.local"

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id="super@grm.local", role_keys=["super_admin"]
    )
    try:
        res = TestClient(app).post("/api/v1/users/invite", json={
            "email": email,
            "organization_id": "DOR",
        })
        assert res.status_code == 422, res.text
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, email)
