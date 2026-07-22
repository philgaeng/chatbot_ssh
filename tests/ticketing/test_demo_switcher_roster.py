"""D-65 — the demo officer switcher must not be a one-way door.

`GET /users/roster` feeds the header officer-switcher (bypass builds). It was gated on
`require_admin`, so switching to a NON-admin officer 403'd the roster the switcher needs to
render — locking you out of admin with no UI path back, and (because the portal then shows a
hardcoded super_admin display while the officer cookie survives) reading as "my grievances
vanished". Fix: `require_admin_or_bypass` — open to any authenticated identity in dev bypass,
still admin-only under real auth (the roster exposes officer names / emails / jurisdictions).

Verified RED pre-fix live on 2026-07-16: with the old `require_admin`, call (a) below returned
403 against the running ticketing_api container; after the fix it returns 200. These tests pin
both halves so a revert to `require_admin` fails here instead of in a demo.

Followup: docs/sprints/archive/2026-08_tier3_structural/followups/demo-officer-switcher-one-way-door.md
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import ticketing.api.dependencies as deps
from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.main import app
from ticketing.config.settings import TicketingSettings

API = "/api/v1"
ROLE_L1 = "site_safeguards_focal_person"  # a real non-admin operational role

# A non-admin officer — exactly who the switcher must be able to act as.
_OFFICER = CurrentUser(user_id="l1-officer@grm.local", role_keys=[ROLE_L1])

# Real-auth posture (bypass OFF): APP_ENV!=dev ⇒ bypass_enabled is False.
_KEYCLOAK = TicketingSettings(
    app_env="production",
    auth_mode="keycloak",
    keycloak_issuer="http://kc/realms/grm",
    ticketing_secret_key="d65-secret",
)


@pytest.fixture
def officer_client(db):
    """TestClient whose identity is a NON-admin officer (not the default super_admin)."""
    app.dependency_overrides[get_authenticated_user] = lambda: _OFFICER
    app.dependency_overrides[get_db] = lambda: (yield db)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_bypass_lets_a_nonadmin_officer_read_the_roster(officer_client):
    """Dev bypass: the switcher's roster is readable by a non-admin ⇒ switching back works.

    This is the assertion that goes RED if anyone re-gates the roster on `require_admin`.
    """
    assert officer_client.get(f"{API}/users/roster").status_code == 200
    assert officer_client.get(f"{API}/users/roster/search").status_code == 200


def test_keycloak_still_gates_the_roster_to_admins(officer_client, monkeypatch):
    """Real auth: the roster stays admin-only — the bypass relaxation must never widen prod.

    `require_admin_or_bypass` collapses to `require_admin` when `bypass_enabled` is False, so a
    non-admin officer is refused exactly as before. Guards against the fix leaking officer
    PII (names/emails/jurisdictions) to any authenticated user under Keycloak.
    """
    monkeypatch.setattr(deps, "get_settings", lambda: _KEYCLOAK)
    assert officer_client.get(f"{API}/users/roster").status_code == 403
    assert officer_client.get(f"{API}/users/roster/search").status_code == 403
