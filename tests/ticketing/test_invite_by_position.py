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
