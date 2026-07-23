"""Ensure admin_scopes are always loaded and org_admin can manage officers."""
from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import ticketing.api.dependencies as deps
import ticketing.services.officer_admin as officer_admin_mod
from ticketing.api.dependencies import (
    CurrentUser,
    _resolve_user_identity,
    enrich_user,
    get_authenticated_user,
    get_db,
)
from ticketing.api.main import app
from ticketing.models.base import SessionLocal
from ticketing.models.officer_onboarding import OfficerOnboarding
from ticketing.services import auth_sync_cache
from ticketing.services.admin_access import AdminScopeRow, is_any_admin

pytestmark = pytest.mark.integration

ROUTERS_DIR = Path(__file__).resolve().parents[2] / "ticketing" / "api" / "routers"


def _scope_row(**kwargs) -> AdminScopeRow:
    base = dict(
        admin_scope_id=str(uuid.uuid4()),
        user_id=kwargs.get("user_id", "admin@grm.local"),
        role_key="org_admin",
        country_code="NP",
        project_id=None,
        organization_id=None,
        package_id=None,
        workflow_track="standard",
    )
    base.update(kwargs)
    return AdminScopeRow(**base)


def test_enrich_user_grants_org_admin_is_admin():
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


def test_org_admin_can_get_and_post_scopes():
    db = SessionLocal()
    try:
        # Unique target so a committed scope from a prior run doesn't collide (409).
        target = f"scope-target-{uuid.uuid4().hex[:8]}@grm.local"
        org_admin = "country-admin@grm.local"

        def override_user():
            return CurrentUser(
                user_id=org_admin,
                role_keys=["pd_piu_safeguards_focal"],
                organization_id="DOR",
                admin_scopes=[_scope_row(user_id=org_admin)],
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
        import sqlalchemy as _sa

        from ticketing.models.officer_scope import OfficerScope

        db.execute(_sa.delete(OfficerScope).where(OfficerScope.user_id == target))
        db.commit()
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


# ── H2-05: onboarding-status sync TTL cache ──────────────────────────────────

_CACHE_UID = "cache-officer@grm.local"


@pytest.fixture
def cache_env(monkeypatch):
    """Force the onboarding-sync path on (bypass off) with a stubbed identity + a sync spy.

    The spy stands in for ``sync_officer_onboarding_status`` and returns False (no DB change),
    so the test never touches the real Keycloak admin path while still counting invocations —
    the acceptance signal for "sync runs once per TTL".
    """
    auth_sync_cache.clear()
    calls = {"sync": 0}

    def _spy_sync(db, email):
        calls["sync"] += 1
        return False

    monkeypatch.setattr(officer_admin_mod, "sync_officer_onboarding_status", _spy_sync)
    monkeypatch.setattr(
        deps,
        "_resolve_user_identity",
        lambda *a, **k: CurrentUser(
            user_id=_CACHE_UID, role_keys=["site_safeguards_focal_person"]
        ),
    )
    monkeypatch.setattr(deps, "get_settings", lambda: SimpleNamespace(bypass_enabled=False))
    try:
        yield SimpleNamespace(calls=calls)
    finally:
        auth_sync_cache.clear()


def _invoke(db):
    return deps.get_current_user(
        credentials=None,
        x_internal_user_id=None,
        x_internal_role=None,
        x_internal_organization_id=None,
        x_api_key=None,
        db=db,
    )


def test_onboarding_sync_runs_once_within_ttl(cache_env):
    db = SessionLocal()
    try:
        _invoke(db)
        _invoke(db)
        _invoke(db)
    finally:
        db.close()
    assert cache_env.calls["sync"] == 1


def test_onboarding_sync_reruns_after_ttl_expiry(cache_env, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(auth_sync_cache, "_now", lambda: clock["t"])
    db = SessionLocal()
    try:
        _invoke(db)                 # sync #1, stamped at t=1000
        clock["t"] = 1000.0 + 299   # still inside the 300 s TTL
        _invoke(db)
        assert cache_env.calls["sync"] == 1
        clock["t"] = 1000.0 + 301   # past the TTL
        _invoke(db)                 # sync #2
    finally:
        db.close()
    assert cache_env.calls["sync"] == 2


def test_invalidation_forces_immediate_resync(cache_env):
    db = SessionLocal()
    try:
        _invoke(db)
        assert cache_env.calls["sync"] == 1
        auth_sync_cache.invalidate(_CACHE_UID)  # e.g. webhook activation / invite
        _invoke(db)                             # re-syncs immediately, no TTL wait
    finally:
        db.close()
    assert cache_env.calls["sync"] == 2


def test_ttl_zero_syncs_every_request(cache_env, monkeypatch):
    monkeypatch.setenv("TICKETING_AUTH_SYNC_TTL_SECONDS", "0")
    db = SessionLocal()
    try:
        _invoke(db)
        _invoke(db)
    finally:
        db.close()
    assert cache_env.calls["sync"] == 2  # escape hatch: per-request as before


def test_warm_cache_request_does_not_run_sync(cache_env):
    db = SessionLocal()
    try:
        _invoke(db)                             # cold: sync runs (onboarding read/possible write)
        assert cache_env.calls["sync"] == 1
        _invoke(db)                             # warm: sync skipped → no onboarding read/write
    finally:
        db.close()
    assert cache_env.calls["sync"] == 1


def test_activation_writer_invalidates_cache():
    """The real onboarding writer busts the cache — proves the webhook/invite invalidation wiring."""
    from sqlalchemy import delete

    from ticketing.services.officer_admin import activate_officer_onboarding

    auth_sync_cache.clear()
    db = SessionLocal()
    try:
        db.execute(delete(OfficerOnboarding).where(OfficerOnboarding.user_id == _CACHE_UID))
        db.commit()

        auth_sync_cache.mark_synced(_CACHE_UID)
        assert auth_sync_cache.is_fresh(_CACHE_UID)

        activate_officer_onboarding(db, _CACHE_UID)  # writes the row → invalidate()
        db.commit()

        assert not auth_sync_cache.is_fresh(_CACHE_UID), "activation must bust the cache entry"
    finally:
        db.execute(delete(OfficerOnboarding).where(OfficerOnboarding.user_id == _CACHE_UID))
        db.commit()
        db.close()
        auth_sync_cache.clear()
