"""SH-7 — 4-tier admin ladder: subtree scope-reach, org_category root gating,
attenuated delegation, and the org-scoped catalog filter (doc 11 §2 / §3.3).

Pure (CI): the officer_admin tier + INVITE_OFFICERS gate, catalog_owner_for, appointment
schema. Integration (@pytest.mark.integration, live DB): subtree reach via a real org
tree, root-creation gating, sub-unit/edit/delete subtree enforcement, catalog visibility
filter, and attenuated delegation.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import (
    AdminScopeRow,
    SettingsAction,
    catalog_owner_for,
    is_officer_admin,
    require_settings_write,
)


# ── personas (no DB) ─────────────────────────────────────────────────────────

def _scope(role_key="org_admin", track="standard", organization_id=None, project_id=None, user_id="a@grm.local"):
    return AdminScopeRow(
        admin_scope_id=str(uuid.uuid4()), user_id=user_id, role_key=role_key,
        country_code="NP", project_id=project_id, organization_id=organization_id,
        package_id=None, workflow_track=track,
    )


def _super():
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _org_admin(track="standard", organization_id=None):
    return CurrentUser(user_id="o@grm.local", role_keys=[],
                       admin_scopes=[_scope(track=track, organization_id=organization_id, user_id="o@grm.local")])


def _officer_admin(track="standard", organization_id=None, project_id=None):
    return CurrentUser(user_id="f@grm.local", role_keys=[],
                       admin_scopes=[_scope(role_key="officer_admin", track=track,
                                            organization_id=organization_id, project_id=project_id, user_id="f@grm.local")])


def _project_admin():
    return CurrentUser(user_id="p@grm.local", role_keys=[],
                       admin_scopes=[_scope(role_key="project_admin", project_id="KL_ROAD", user_id="p@grm.local")])


# ── pure ─────────────────────────────────────────────────────────────────────

def test_is_officer_admin():
    assert is_officer_admin(_officer_admin()) is True
    assert is_officer_admin(_officer_admin("seah"), "seah") is True
    assert is_officer_admin(_officer_admin("standard"), "seah") is False
    assert is_officer_admin(_org_admin()) is False


def test_officer_admin_passes_invite_gate():
    # officer_admin — the narrowest tier — may invite officers (doc 11 §2.3b) ...
    require_settings_write(_officer_admin(), SettingsAction.INVITE_OFFICERS)  # no raise
    # ... but not manage org structure / create projects.
    for action in (SettingsAction.MANAGE_ORG_STRUCTURE, SettingsAction.CREATE_PROJECT, SettingsAction.PLATFORM_SETTINGS):
        with pytest.raises(HTTPException) as exc:
            require_settings_write(_officer_admin(), action)
        assert exc.value.status_code == 403


def test_catalog_owner_for():
    assert catalog_owner_for(_super()) is None                       # super → global
    assert catalog_owner_for(_org_admin(organization_id=None)) is None  # country-wide org_admin → global
    assert catalog_owner_for(_org_admin(organization_id="DOR")) == "DOR"  # scoped → its node
    assert catalog_owner_for(_org_admin(track="seah", organization_id="DOR"), "standard") is None  # track mismatch


# ── integration ──────────────────────────────────────────────────────────────

@pytest.fixture
def org_tree():
    """A throwaway forest: A(third_party root) → A_SUB; and B(third_party root, separate)."""
    from ticketing.models.base import SessionLocal
    from ticketing.models.organization import Organization

    sfx = uuid.uuid4().hex[:6].upper()
    a, a_sub, b = f"SH7A_{sfx}", f"SH7ASUB_{sfx}", f"SH7B_{sfx}"
    s = SessionLocal()
    s.add(Organization(organization_id=a, name="SH7 A", org_category="third_party", country_code="NP"))
    s.add(Organization(organization_id=a_sub, name="SH7 A sub", org_category="third_party",
                       parent_organization_id=a, country_code="NP"))
    s.add(Organization(organization_id=b, name="SH7 B", org_category="third_party", country_code="NP"))
    s.commit()
    s.close()
    yield {"A": a, "A_SUB": a_sub, "B": b}
    s = SessionLocal()
    for oid in (a_sub, a, b):
        obj = s.get(Organization, oid)
        if obj:
            s.delete(obj)
    s.commit()
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


@pytest.mark.integration
def test_subtree_reach(org_tree):
    from ticketing.models.base import SessionLocal
    from ticketing.services.admin_access import admin_org_scope_ids, can_admin_org

    db = SessionLocal()
    try:
        admin = _org_admin(organization_id=org_tree["A"])
        reach = admin_org_scope_ids(db, admin)
        assert reach == {org_tree["A"], org_tree["A_SUB"]}
        assert can_admin_org(db, admin, org_tree["A"]) is True
        assert can_admin_org(db, admin, org_tree["A_SUB"]) is True
        assert can_admin_org(db, admin, org_tree["B"]) is False
        # super + country-wide org_admin are unbounded
        assert admin_org_scope_ids(db, _super()) is None
        assert admin_org_scope_ids(db, _org_admin(organization_id=None)) is None
    finally:
        db.close()


@pytest.mark.integration
def test_root_creation_gating():
    """Institutional roots are super-only; a standard org_admin may create third_party roots."""
    created = []
    # super creates a government root
    app, client, db = _client(_super())
    try:
        oid = f"SH7GOV_{uuid.uuid4().hex[:6].upper()}"
        r = client.post("/api/v1/organizations", json={"organization_id": oid, "name": "Gov Root",
                                                        "org_category": "government"})
        assert r.status_code == 201, r.text
        created.append(oid)
    finally:
        app.dependency_overrides.clear(); db.close()
    # a country-wide standard org_admin: government root 403, third_party root 201
    app, client, db = _client(_org_admin(organization_id=None))
    try:
        assert client.post("/api/v1/organizations",
                           json={"name": "Gov By OrgAdmin", "org_category": "government"}).status_code == 403
        oid = f"SH7TP_{uuid.uuid4().hex[:6].upper()}"
        r = client.post("/api/v1/organizations", json={"organization_id": oid, "name": "Contractor",
                                                       "org_category": "third_party"})
        assert r.status_code == 201, r.text
        created.append(oid)
    finally:
        app.dependency_overrides.clear(); db.close()
    # cleanup
    from ticketing.models.base import SessionLocal
    from ticketing.models.organization import Organization
    s = SessionLocal()
    for oid in created:
        obj = s.get(Organization, oid)
        if obj:
            s.delete(obj)
    s.commit(); s.close()


@pytest.mark.integration
def test_sub_unit_and_edit_subtree_enforcement(org_tree):
    """An org_admin scoped at A builds/edits within A's subtree only."""
    admin = _org_admin(organization_id=org_tree["A"])
    app, client, db = _client(admin)
    created = []
    try:
        # create a child under A → allowed
        cid = f"SH7C_{uuid.uuid4().hex[:6].upper()}"
        r = client.post("/api/v1/organizations", json={"organization_id": cid, "name": "Child of A",
                                                       "parent_organization_id": org_tree["A"]})
        assert r.status_code == 201, r.text
        created.append(cid)
        # create under B (outside subtree) → 403
        assert client.post("/api/v1/organizations", json={"name": "Child of B",
                                                          "parent_organization_id": org_tree["B"]}).status_code == 403
        # edit A_SUB (in subtree) → 200; edit B (outside) → 403
        assert client.patch(f"/api/v1/organizations/{org_tree['A_SUB']}", json={"name": "renamed"}).status_code == 200
        assert client.patch(f"/api/v1/organizations/{org_tree['B']}", json={"name": "nope"}).status_code == 403
    finally:
        app.dependency_overrides.clear(); db.close()
        from ticketing.models.base import SessionLocal
        from ticketing.models.organization import Organization
        s = SessionLocal()
        for oid in created:
            obj = s.get(Organization, oid)
            if obj:
                s.delete(obj)
        s.commit(); s.close()


@pytest.mark.integration
def test_catalog_visibility_filter(org_tree):
    """A role owned by A_SUB is visible to an org_admin over A, hidden from one over B;
    a global (owner NULL) role is visible to both."""
    from ticketing.models.base import SessionLocal
    from ticketing.models.user import Role

    owned_key = f"sh7_owned_{uuid.uuid4().hex[:6]}"
    global_key = f"sh7_global_{uuid.uuid4().hex[:6]}"
    s = SessionLocal()
    s.add(Role(role_key=owned_key, display_name="Owned", role_kind="operational",
               role_origin="custom", workflow_scope="Standard", owner_organization_id=org_tree["A_SUB"]))
    s.add(Role(role_key=global_key, display_name="Global", role_kind="operational",
               role_origin="custom", workflow_scope="Standard", owner_organization_id=None))
    s.commit(); s.close()
    try:
        def _keys(user):
            app, client, db = _client(user)
            try:
                return {r["role_key"] for r in client.get("/api/v1/roles?kind=operational").json()}
            finally:
                app.dependency_overrides.clear(); db.close()

        over_a = _keys(_org_admin(organization_id=org_tree["A"]))
        over_b = _keys(_org_admin(organization_id=org_tree["B"]))
        as_super = _keys(_super())

        assert owned_key in over_a and global_key in over_a       # A covers A_SUB → sees owned + global
        assert owned_key not in over_b and global_key in over_b   # B doesn't cover A_SUB → global only
        assert owned_key in as_super and global_key in as_super   # super sees all
    finally:
        s = SessionLocal()
        for k in (owned_key, global_key):
            obj = s.execute(__import__("sqlalchemy").select(Role).where(Role.role_key == k)).scalar_one_or_none()
            if obj:
                s.delete(obj)
        s.commit(); s.close()


@pytest.mark.integration
def test_attenuated_delegation(org_tree, monkeypatch):
    """A scoped org_admin may appoint a lower org_admin only inside its own subtree, and
    never a country-wide (org-less) org_admin."""
    # Keep this authz test keycloak-independent: with keycloak_configured() False, admin-scope
    # provisioning short-circuits to "active" (same seam test_admin_scope_keycloak patches).
    # The authz checks — the SUT — run before provisioning regardless.
    monkeypatch.setattr(
        "ticketing.services.officer_admin.keycloak_configured", lambda: False
    )
    admin = _org_admin(organization_id=org_tree["A"])
    app, client, db = _client(admin)
    try:
        target = f"deleg-{uuid.uuid4().hex[:6]}@grm.local"
        # within subtree (A_SUB) → allowed
        r = client.post("/api/v1/admin-scopes", json={
            "user_id": target, "role_key": "org_admin", "organization_id": org_tree["A_SUB"],
            "workflow_track": "standard"})
        assert r.status_code in (201, 200), r.text
        # outside subtree (B) → 403
        assert client.post("/api/v1/admin-scopes", json={
            "user_id": target, "role_key": "org_admin", "organization_id": org_tree["B"],
            "workflow_track": "standard"}).status_code == 403
        # country-wide (no org) → 403 (super only)
        assert client.post("/api/v1/admin-scopes", json={
            "user_id": target, "role_key": "org_admin", "country_code": "NP",
            "workflow_track": "standard"}).status_code == 403
    finally:
        app.dependency_overrides.clear(); db.close()
        # cleanup any admin_scopes/user_roles the allowed grant created
        from ticketing.models.base import SessionLocal
        from ticketing.models.admin_scope import AdminScope
        import sqlalchemy as sa
        s = SessionLocal()
        s.execute(sa.delete(AdminScope).where(AdminScope.user_id.like("deleg-%@grm.local")))
        s.commit(); s.close()
