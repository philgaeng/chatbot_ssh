"""
Frame-11 officer directory & lifecycle (RB-0 backend gaps).

Covers:
  * roster search filter + pagination + total (X-Total-Count and {items,total,...})
  * soft deactivate flips GRM access; reactivate restores it
  * open-case guard blocks deactivate AND hard delete with 409 + open_count
  * deactivate succeeds once the officer's open cases are reassigned

Uses the shared db/ctx fixtures in conftest.py and TestClient dependency overrides
(the same pattern as test_officer_admin_access.py). Keycloak is unconfigured in the
test env, so the lifecycle is exercised purely through the ticketing.* DB state.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from tests.ticketing.conftest import ORG_DOR, ROLE_L1
from ticketing.api.dependencies import (
    CurrentUser,
    enrich_user,
    get_authenticated_user,
    get_db,
)
from ticketing.api.main import app
from ticketing.models.officer_onboarding import OfficerOnboarding
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.ticket import Ticket
from ticketing.models.user import Role, UserRole
from ticketing.services.officer_admin import officer_is_active

pytestmark = pytest.mark.integration

API = "/api/v1"


def _admin_user() -> CurrentUser:
    return CurrentUser(user_id="admin@grm.local", role_keys=["super_admin"], organization_id=ORG_DOR)


@pytest.fixture
def client(db):
    """TestClient wired to the shared session and a super_admin identity."""

    def override_user():
        return _admin_user()

    def override_db():
        yield db

    app.dependency_overrides[get_authenticated_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def officers(db):
    """Create disposable officers (email + a user_roles row); clean all footprint on teardown."""
    created: list[str] = []
    role = db.execute(select(Role).where(Role.role_key == ROLE_L1)).scalar_one()

    def make(email: str, *, org: str = ORG_DOR) -> str:
        db.add(UserRole(user_id=email, role_id=role.role_id, organization_id=org))
        db.commit()
        created.append(email)
        return email

    try:
        yield make
    finally:
        for email in created:
            db.execute(delete(Ticket).where(Ticket.assigned_to_user_id == email))
            db.execute(delete(UserRole).where(UserRole.user_id == email))
            db.execute(delete(OfficerScope).where(OfficerScope.user_id == email))
            db.execute(delete(OfficerOnboarding).where(OfficerOnboarding.user_id == email))
        db.commit()


# ── Roster search + pagination + total ────────────────────────────────────────

def test_roster_search_filter_pagination_and_total(client, officers):
    token = uuid.uuid4().hex[:8]
    emails = sorted(
        officers(f"life-{token}-{suffix}@grm.local") for suffix in ("a", "b", "c")
    )

    # Structured envelope: total is the full match count, items is the page.
    res = client.get(f"{API}/users/roster/search", params={"q": token})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 3
    assert body["offset"] == 0
    assert {e["user_id"] for e in body["items"]} == set(emails)

    # Page 1 of 2 per page.
    page1 = client.get(f"{API}/users/roster/search", params={"q": token, "limit": 2, "offset": 0}).json()
    assert page1["total"] == 3 and page1["limit"] == 2
    assert len(page1["items"]) == 2

    # Page 2: remaining one, total unchanged.
    page2 = client.get(f"{API}/users/roster/search", params={"q": token, "limit": 2, "offset": 2}).json()
    assert page2["total"] == 3
    assert len(page2["items"]) == 1

    # No overlap across the two pages; union == all three.
    seen = {e["user_id"] for e in page1["items"]} | {e["user_id"] for e in page2["items"]}
    assert seen == set(emails)

    # Case-insensitive q on the legacy bare-list endpoint + X-Total-Count header.
    res2 = client.get(f"{API}/users/roster", params={"q": token.upper()})
    assert res2.status_code == 200
    assert res2.headers["X-Total-Count"] == "3"
    assert isinstance(res2.json(), list)
    assert {e["user_id"] for e in res2.json()} == set(emails)


def test_roster_no_args_backward_compatible(client, officers):
    """No query params → full bare list (unchanged contract) + a total header."""
    email = officers(f"compat-{uuid.uuid4().hex[:8]}@grm.local")
    res = client.get(f"{API}/users/roster")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert email in {e["user_id"] for e in data}
    assert res.headers["X-Total-Count"] == str(len(data))


# ── Deactivate flips access; reactivate restores ──────────────────────────────

def test_deactivate_flips_access_reactivate_restores(client, officers, db):
    email = officers(f"deact-{uuid.uuid4().hex[:8]}@grm.local")

    # Baseline: active officer resolves their DB role via enrich_user.
    assert officer_is_active(db, email) is True
    active = enrich_user(db, CurrentUser(user_id=email, role_keys=[]))
    assert ROLE_L1 in active.role_keys

    # Deactivate → access revoked.
    res = client.post(f"{API}/users/{email}/deactivate")
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False
    assert officer_is_active(db, email) is False
    revoked = enrich_user(db, CurrentUser(user_id=email, role_keys=[]))
    assert revoked.role_keys == []
    assert revoked.admin_scopes == []

    # Roster reflects deactivated state.
    entry = next(e for e in client.get(f"{API}/users/roster", params={"q": email}).json())
    assert entry["is_active"] is False

    # Reactivate → access restored, onboarding status preserved.
    res2 = client.post(f"{API}/users/{email}/reactivate")
    assert res2.status_code == 200, res2.text
    assert res2.json()["is_active"] is True
    assert officer_is_active(db, email) is True
    restored = enrich_user(db, CurrentUser(user_id=email, role_keys=[]))
    assert ROLE_L1 in restored.role_keys


def test_deactivate_unknown_officer_404(client):
    res = client.post(f"{API}/users/ghost-{uuid.uuid4().hex[:6]}@grm.local/deactivate")
    assert res.status_code == 404


# ── Open-case guard ───────────────────────────────────────────────────────────

def test_open_case_guard_blocks_deactivate_and_delete(client, officers, ctx):
    email = officers(f"guard-{uuid.uuid4().hex[:8]}@grm.local")
    ctx.add_open_ticket(assigned_to_user_id=email)

    # Guard endpoint reports the open case.
    oc = client.get(f"{API}/users/{email}/open-cases")
    assert oc.status_code == 200, oc.text
    assert oc.json()["open_count"] == 1
    assert oc.json()["tickets"][0]["status"] == "OPEN"

    # Deactivate blocked with 409 + count.
    dres = client.post(f"{API}/users/{email}/deactivate")
    assert dres.status_code == 409
    assert dres.json()["detail"]["open_count"] == 1

    # Hard delete blocked with 409 + count.
    delres = client.request("DELETE", f"{API}/users/{email}")
    assert delres.status_code == 409
    assert delres.json()["detail"]["open_count"] == 1


def test_deactivate_succeeds_after_cases_reassigned(client, officers, ctx, db):
    email = officers(f"reassign-{uuid.uuid4().hex[:8]}@grm.local")
    ticket = ctx.add_open_ticket(assigned_to_user_id=email)

    # Blocked while it owns the open case.
    assert client.post(f"{API}/users/{email}/deactivate").status_code == 409

    # Reassign the case to another officer, then the guard clears.
    ticket.assigned_to_user_id = "other-officer@grm.local"
    db.flush()

    assert client.get(f"{API}/users/{email}/open-cases").json()["open_count"] == 0
    ok = client.post(f"{API}/users/{email}/deactivate")
    assert ok.status_code == 200, ok.text
    assert ok.json()["is_active"] is False
