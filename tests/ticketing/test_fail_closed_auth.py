"""HR-01 — fail-closed auth.

A missing env var must never silently disable authentication. These tests pin the
six acceptance cases from docs/sprints/2026-07_hardening/01-auth-hardening-spec.md §1:

  1. production + no KEYCLOAK_ISSUER      → app refuses to start
  2. production + issuer, no SECRET_KEY   → app refuses to start
  3. dev + nothing set                    → startup OK, demo bypass preserved
  4. production per-request unauthenticated → 503, never a demo super_admin
  5. header identity without a role       → least privilege (no admin)
  6. backend grievance API, empty key list in non-dev → rejected

Settings are controlled by monkeypatching the module-level ``get_settings`` symbol
(imported into each module), following the isolation style of test_auth_dependencies.py.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ticketing.api import dependencies as deps
from ticketing.api import main as main_mod
from ticketing.api.dependencies import (
    CurrentUser,
    _resolve_user_identity,
    require_super_admin,
    verify_api_key,
)
from ticketing.config.settings import TicketingSettings


def _settings(
    *, env: str, issuer: str = "", secret: str = "", auth_mode: str | None = None
) -> TicketingSettings:
    """Build a real settings instance with the auth-relevant fields pinned.

    Explicit kwargs take priority over env / env_file in pydantic-settings, so the
    result is deterministic regardless of the container's environment. auth_mode
    defaults to the real-world pairing (dev→bypass, everything else→keycloak).
    """
    if auth_mode is None:
        auth_mode = "bypass" if env == "dev" else "keycloak"
    return TicketingSettings(
        app_env=env,
        auth_mode=auth_mode,
        keycloak_issuer=issuer,
        ticketing_secret_key=secret,
    )


def _patch_settings(monkeypatch, settings: TicketingSettings) -> None:
    monkeypatch.setattr(main_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(deps, "get_settings", lambda: settings)


# ── 1 & 2: startup guard refuses to boot outside dev ─────────────────────────

def test_startup_raises_without_keycloak_issuer(monkeypatch):
    _patch_settings(monkeypatch, _settings(env="production", issuer="", secret="s3cret"))
    with pytest.raises(RuntimeError) as exc:
        with TestClient(main_mod.app):
            pass
    assert "KEYCLOAK_ISSUER" in str(exc.value)


def test_startup_raises_without_secret_key(monkeypatch):
    _patch_settings(
        monkeypatch,
        _settings(env="production", issuer="http://kc/realms/grm", secret=""),
    )
    with pytest.raises(RuntimeError) as exc:
        with TestClient(main_mod.app):
            pass
    assert "TICKETING_SECRET_KEY" in str(exc.value)


# ── 3: dev keeps the demo bypass ─────────────────────────────────────────────

def test_dev_startup_ok_and_demo_bypass_preserved(monkeypatch):
    _patch_settings(monkeypatch, _settings(env="dev", issuer="", secret=""))
    # Startup guard must NOT raise in dev.
    main_mod._assert_auth_configured(main_mod.get_settings())
    # Demo bypass still resolves the mock super_admin when nothing is configured.
    user = _resolve_user_identity(None, None, None, None, None)
    assert user.is_super_admin
    assert "super_admin" in user.role_keys


# ── 4: per-request hard-fail in production (defense in depth) ─────────────────

def test_unauthenticated_request_never_returns_demo_super_admin(monkeypatch):
    _patch_settings(monkeypatch, _settings(env="production", issuer="", secret="s3cret"))
    with pytest.raises(HTTPException) as exc:
        _resolve_user_identity(None, None, None, None, None)
    assert exc.value.status_code == 503


def test_verify_api_key_503_when_secret_unset_in_production(monkeypatch):
    _patch_settings(
        monkeypatch,
        _settings(env="production", issuer="http://kc/realms/grm", secret=""),
    )
    with pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key="anything")
    assert exc.value.status_code == 503


# ── 5: header identity is least privilege (no default super_admin) ───────────

def test_header_identity_without_role_has_no_admin(monkeypatch):
    _patch_settings(
        monkeypatch,
        _settings(env="production", issuer="http://kc/realms/grm", secret="topsecret"),
    )
    user = _resolve_user_identity(
        credentials=None,
        x_internal_user_id="attacker@evil.test",
        x_internal_role=None,
        x_internal_organization_id=None,
        x_api_key="topsecret",
    )
    assert user.role_keys == []
    assert not user.is_super_admin
    # A super_admin-only endpoint guard rejects this identity.
    with pytest.raises(HTTPException) as exc:
        require_super_admin(current_user=user)
    assert exc.value.status_code == 403


def test_header_identity_with_explicit_role_is_honored(monkeypatch):
    """The dev-bypass proxy always sends x-internal-role — that path must still work."""
    _patch_settings(
        monkeypatch,
        _settings(env="production", issuer="http://kc/realms/grm", secret="topsecret"),
    )
    user = _resolve_user_identity(
        credentials=None,
        x_internal_user_id="l1-officer@grm.local",
        x_internal_role="site_safeguards_focal_person",
        x_internal_organization_id=None,
        x_api_key="topsecret",
    )
    assert user.role_keys == ["site_safeguards_focal_person"]
    assert not user.is_super_admin


# ── 6: backend grievance API empty key list ──────────────────────────────────

def test_backend_grievance_auth_rejects_empty_key_list_in_production(monkeypatch):
    from backend.api.fastapi_app import _assert_backend_auth_configured
    from backend.api.routers.grievance import _ticketing_auth_check

    monkeypatch.delenv("TICKETING_SECRET_KEY", raising=False)
    monkeypatch.delenv("MESSAGING_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "keycloak")

    # Per-request check rejects (503) rather than silently skipping.
    with pytest.raises(HTTPException) as exc:
        _ticketing_auth_check(x_api_key=None)
    assert exc.value.status_code == 503

    # Startup guard refuses to boot.
    with pytest.raises(RuntimeError):
        _assert_backend_auth_configured()

    # dev bypass keeps the local convenience: no keys required.
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("AUTH_MODE", "bypass")
    assert _ticketing_auth_check(x_api_key=None) is None
    assert _assert_backend_auth_configured() is None
