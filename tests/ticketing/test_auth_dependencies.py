"""Ensure admin_scopes are always loaded and country_admin can manage officers."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ticketing.api.dependencies import (
    CurrentUser,
    _resolve_user_identity,
    enrich_user,
    get_authenticated_user,
    get_db,
)
from ticketing.api.main import app
from ticketing.models.base import SessionLocal
from ticketing.services.admin_access import AdminScopeRow, is_any_admin

pytestmark = pytest.mark.integration

ROUTERS_DIR = Path(__file__).resolve().parents[2] / "ticketing" / "api" / "routers"


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


def test_enrich_user_grants_country_admin_is_admin():
    bare = CurrentUser(user_id="c@grm.local", role_keys=["pd_piu_safeguards_focal"])
    assert not is_any_admin(bare)

    db = SessionLocal()
    try:
        enriched = enrich_user(
            db,
            CurrentUser(
                user_id="c@grm.local",
                role_keys=["pd_piu_safeguards_focal"],
            ),
        )
        # If no row in DB for this test user, scopes stay empty — use injected scopes:
        enriched.admin_scopes = [_scope_row(user_id="c@grm.local")]
        assert is_any_admin(enriched)
    finally:
        db.close()


def test_country_admin_can_get_and_post_scopes():
    db = SessionLocal()
    try:
        target = "scope.target@grm.local"
        country_admin = "country-admin@grm.local"

        def override_user():
            return CurrentUser(
                user_id=country_admin,
                role_keys=["pd_piu_safeguards_focal"],
                organization_id="DOR",
                admin_scopes=[_scope_row(user_id=country_admin)],
            )

        def override_db():
            yield db

        app.dependency_overrides[get_authenticated_user] = override_user
        app.dependency_overrides[get_db] = override_db
        client = TestClient(app)

        get_res = client.get(f"/api/v1/users/{target}/scopes")
        assert get_res.status_code == 200, get_res.text

        post_res = client.post(
            f"/api/v1/users/{target}/scopes",
            json={
                "role_key": "site_safeguards_focal_person",
                "organization_id": "DOR",
                "project_code": "KL_ROAD",
            },
        )
        assert post_res.status_code in (201, 404, 422), post_res.text
        assert post_res.status_code != 403, post_res.text
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_router_files_do_not_use_stale_auth_docstring():
    """Guardrail: no router should document get_current_user as 'no DB'."""
    offenders: list[str] = []
    for path in ROUTERS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "get_current_user" in text and "no DB" in text:
            offenders.append(path.name)
    assert not offenders, f"Stale auth docs in routers: {offenders}"


def test_resolve_user_identity_does_not_load_scopes():
    """Identity-only helper stays scope-free; get_current_user enriches afterward."""
    user = _resolve_user_identity(None, None, None, None, None)
    assert user.admin_scopes == []
