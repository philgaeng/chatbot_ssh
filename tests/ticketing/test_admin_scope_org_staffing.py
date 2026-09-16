"""Gap A + Gap B (2026-07-24) — org_admin contractor ownership + project-staffing scope.

Gap A — a ``third_party`` contractor an org_admin creates is stamped with the creator's org
node (``owner_organization_id``). It is a root outside every subtree, so the plain subtree
guard would leave only super_admin able to edit it; ``can_admin_org_or_owned`` grants the
creator + any *ancestor*-org admin edit/delete rights (owner ∈ caller subtree).

Gap B — an org_admin may staff/attach only on projects its subtree manages (the project's
implementing agency ∈ subtree). An *unanchored* project (no IA yet) stays open so setup is not
locked out; the referenced actor/officer org is never constrained.

DB-backed (needs the seeded demo DB: DOR = government root, ADB = donor root, both real orgs).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from ticketing.api.dependencies import CurrentUser
from ticketing.api.routers.locations import OrganizationCreate, create_organization
from ticketing.models.organization import Organization
from ticketing.models.project import Project
from ticketing.services.admin_access import (
    AdminScopeRow,
    can_admin_org_or_owned,
    org_admin_manages_project,
    require_org_admin_project_scope,
)

pytestmark = pytest.mark.integration

ORG_DOR = "DOR"
ORG_ADB = "ADB"


def _org_admin(org_id: str, track: str = "standard") -> CurrentUser:
    uid = f"oa-{org_id.lower()}@grm.local"
    return CurrentUser(
        user_id=uid,
        role_keys=[],
        admin_scopes=[
            AdminScopeRow(
                admin_scope_id=str(uuid.uuid4()),
                user_id=uid,
                role_key="org_admin",
                country_code=None,
                project_id=None,
                organization_id=org_id,
                package_id=None,
                workflow_track=track,
            )
        ],
    )


def _project_admin(project_id: str) -> CurrentUser:
    return CurrentUser(
        user_id="pa@grm.local",
        role_keys=[],
        admin_scopes=[
            AdminScopeRow(
                admin_scope_id=str(uuid.uuid4()),
                user_id="pa@grm.local",
                role_key="project_admin",
                country_code=None,
                project_id=project_id,
                organization_id=None,
                package_id=None,
                workflow_track="standard",
            )
        ],
    )


def _super() -> CurrentUser:
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


@pytest.fixture
def make_org(db):
    """Create temp org nodes (flushed, visible to the CTE) and delete them on teardown."""
    created: list[str] = []

    def _make(org_id, name, *, category="government", parent=None, owner=None):
        o = Organization(
            organization_id=org_id,
            name=name,
            org_category=category,
            parent_organization_id=parent,
            owner_organization_id=owner,
        )
        db.add(o)
        db.flush()
        created.append(org_id)
        return o

    yield _make
    for oid in reversed(created):
        obj = db.get(Organization, oid)
        if obj is not None:
            db.delete(obj)
    db.commit()


@pytest.fixture
def make_project(db):
    created: list[str] = []

    def _make(ia=None):
        p = Project(
            project_id=str(uuid.uuid4()),
            country_code="NP",
            short_code=f"T{uuid.uuid4().hex[:6].upper()}",
            name="Temp project",
            implementing_agency_org_id=ia,
        )
        db.add(p)
        db.flush()
        created.append(p.project_id)
        return p

    yield _make
    for pid in created:
        obj = db.get(Project, pid)
        if obj is not None:
            db.delete(obj)
    db.commit()


# ── Gap A: contractor authorship ─────────────────────────────────────────────


def test_owned_contractor_editable_by_creator_and_ancestor_not_sibling(db, make_org):
    sfx = uuid.uuid4().hex[:6]
    dept = make_org(f"DEPT_{sfx}", "Roads Division", parent=ORG_DOR)
    dept2 = make_org(f"DEPT2_{sfx}", "Bridges Division", parent=ORG_DOR)
    contractor = make_org(
        f"CON_{sfx}", "Acme Contractors", category="third_party", owner=dept.organization_id
    )

    # creator's org node — owns it
    assert can_admin_org_or_owned(db, _org_admin(dept.organization_id), contractor, "standard") is True
    # ancestor org (DOR) — its subtree contains the owner node
    assert can_admin_org_or_owned(db, _org_admin(ORG_DOR), contractor, "standard") is True
    # sibling org — owner node not in its subtree → denied
    assert can_admin_org_or_owned(db, _org_admin(dept2.organization_id), contractor, "standard") is False


def test_unowned_root_contractor_reachable_only_by_super(db, make_org):
    sfx = uuid.uuid4().hex[:6]
    orphan = make_org(f"ORPH_{sfx}", "Legacy Contractor", category="third_party")  # owner=None
    # No org_admin covers a rootless, unowned node...
    assert can_admin_org_or_owned(db, _org_admin(ORG_DOR), orphan, "standard") is False
    # ...but super_admin always can (via can_admin_org).
    assert can_admin_org_or_owned(db, _super(), orphan, "standard") is True


def _drop_org(db, created) -> None:
    """Delete an organization the test created, by its stored id."""
    if created is None:
        return
    obj = db.get(Organization, created.organization_id)
    if obj is not None:
        db.delete(obj)
        db.commit()


def test_create_third_party_stamps_creator_org_node(db):
    sfx = uuid.uuid4().hex[:6]
    out = None
    try:
        out = create_organization(
            OrganizationCreate(organization_id=f"CONX_{sfx}", name="Beta Builders", org_category="third_party"),
            db=db,
            current_user=_org_admin(ORG_DOR),
        )
        assert out.org_category == "third_party"
        assert out.owner_organization_id == ORG_DOR  # stamped with the creator's org node
    finally:
        # Clean up by the id the API RETURNED, never the one we asked for: it upper-cases and
        # strips (`ascii_alnum(raw.upper())`), so `CONX_ab12cd` is stored as `CONX_AB12CD` and a
        # lookup by the requested id silently finds nothing. That is how 69 orphan contractors
        # accumulated in the dev database, two per suite run.
        _drop_org(db, out)


def test_super_created_third_party_is_unowned(db):
    sfx = uuid.uuid4().hex[:6]
    out = None
    try:
        out = create_organization(
            OrganizationCreate(organization_id=f"CONS_{sfx}", name="Gamma Ltd", org_category="third_party"),
            db=db,
            current_user=_super(),
        )
        assert out.owner_organization_id is None  # super creations stay global/unowned
    finally:
        _drop_org(db, out)


# ── Gap B: project-staffing scope ────────────────────────────────────────────


def test_org_admin_manages_project_by_ia_subtree(db, make_project):
    proj = make_project(ia=ORG_DOR)
    assert org_admin_manages_project(db, _org_admin(ORG_DOR), proj) is True
    # ADB (donor root, separate tree) does not cover DOR
    assert org_admin_manages_project(db, _org_admin(ORG_ADB), proj) is False


def test_unanchored_project_open_to_any_org_admin(db, make_project):
    proj = make_project(ia=None)
    assert org_admin_manages_project(db, _org_admin(ORG_ADB), proj) is True


def test_require_scope_raises_for_foreign_org_admin(db, make_project):
    proj = make_project(ia=ORG_DOR)
    require_org_admin_project_scope(db, _super(), proj)  # no raise
    require_org_admin_project_scope(db, _org_admin(ORG_DOR), proj)  # no raise
    with pytest.raises(HTTPException) as exc:
        require_org_admin_project_scope(db, _org_admin(ORG_ADB), proj)
    assert exc.value.status_code == 403


def test_require_scope_is_noop_for_non_org_admin(db, make_project):
    """Only the org_admin tier is constrained here — a project_admin passes through (its own
    guard handles project scoping), so this fix does not regress the narrower tiers."""
    proj = make_project(ia=ORG_DOR)
    require_org_admin_project_scope(db, _project_admin("KL_ROAD"), proj)  # no raise
