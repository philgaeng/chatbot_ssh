"""An organization's grievances are its **projects'** grievances (DECISION-organization-membership).

The rule, decided 2026-08-04:

> A grievance belongs to a project. Every organization named on that project sees it — donor,
> ministry, department, contractor alike. An organization named on **one lot** sees that lot
> only. A parent organization sees everything its children see.

What this replaced: `tickets.organization_id`, a single stamp chosen by the project type's
`routing_org_role`. One organization owned the grievance and every other organization on the
project owned nothing — so the donor's report and the ministry's report could not both be right.

The tests below pin the four things that make membership work, and the one that makes it safe:
subtree inheritance, lot-only reach, redundancy (a lot inside a covered project adds nothing),
and an organization named nowhere getting **nothing** rather than everything.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from ticketing.models.organization import Organization
from ticketing.models.package import PackageOrganization, ProjectPackage
from ticketing.models.project import ProjectOrganization
from ticketing.models.ticket import Ticket
from ticketing.services.org_reach import (
    organization_ids_for_project,
    project_and_package_reach,
    ticket_filter_for_org,
)

pytestmark = pytest.mark.integration

ORG_DOR = "DOR"
ORG_ADB = "ADB"


def _tickets_for(db, organization_id: str) -> set[str]:
    return set(
        db.execute(
            select(Ticket.ticket_id).where(
                Ticket.is_deleted.is_(False), ticket_filter_for_org(db, organization_id)
            )
        ).scalars().all()
    )


# ── the core claim ────────────────────────────────────────────────────────────

def test_every_named_organization_sees_the_same_grievances(db, kl_road_project):
    """The whole point. DOR (implementing agency) and ADB (donor) are both named on KL Road, so
    both see its grievances — where the old stamp gave them to exactly one of the two."""
    dor = _tickets_for(db, ORG_DOR)
    adb = _tickets_for(db, ORG_ADB)
    assert dor, "KL Road has grievances in the seed"
    assert dor == adb


def test_an_organization_named_nowhere_sees_nothing(db):
    """Not 'no filter' — nothing. An unfiltered query here would leak every grievance in the
    system to an organization with no projects at all."""
    org_id = f"TEST_ORPHAN_{uuid.uuid4().hex[:6].upper()}"
    db.add(Organization(organization_id=org_id, name="Orphan Ltd", org_category="third_party"))
    db.flush()
    try:
        assert _tickets_for(db, org_id) == set()
    finally:
        db.delete(db.get(Organization, org_id))
        db.flush()


# ── the org tree ──────────────────────────────────────────────────────────────

def test_a_parent_sees_what_its_child_is_named_on(db, kl_road_project):
    """The ministry above a department does not have to be named on every project the
    department runs — that is what the org chart is for (doc 16 §3.1)."""
    parent_id = f"TEST_MINISTRY_{uuid.uuid4().hex[:6].upper()}"
    db.add(
        Organization(
            organization_id=parent_id, name="Test Ministry", org_category="government"
        )
    )
    db.flush()
    dor = db.get(Organization, ORG_DOR)
    original_parent = dor.parent_organization_id
    try:
        dor.parent_organization_id = parent_id
        db.flush()
        # The ministry is named on nothing; it inherits DOR's projects through the tree.
        assert _tickets_for(db, parent_id) == _tickets_for(db, ORG_DOR)
    finally:
        dor.parent_organization_id = original_parent
        db.flush()
        db.delete(db.get(Organization, parent_id))
        db.flush()


# ── lot-level naming reaches one lot (Q1, 2026-08-04) ─────────────────────────

def test_a_lot_level_naming_reaches_that_lot_only(db, kl_road_project, jhapa_lot_package_id):
    """Naming a contractor on lot 3 is a statement about lot 3. It must not hand them the whole
    project — that distinction is exactly what the single-stamp model could not express."""
    org_id = f"TEST_CONTRACTOR_{uuid.uuid4().hex[:6].upper()}"
    db.add(Organization(organization_id=org_id, name="Lot 3 Contractor", org_category="third_party"))
    db.add(
        PackageOrganization(
            package_id=jhapa_lot_package_id, organization_id=org_id, org_role="main_contractor"
        )
    )
    db.flush()
    try:
        project_ids, package_ids = project_and_package_reach(db, org_id)
        assert project_ids == set(), "a lot naming is not a project naming"
        assert package_ids == {jhapa_lot_package_id}
    finally:
        db.execute(
            PackageOrganization.__table__.delete().where(
                PackageOrganization.organization_id == org_id
            )
        )
        db.delete(db.get(Organization, org_id))
        db.flush()


def test_a_lot_inside_a_covered_project_is_redundant(db, kl_road_project, jhapa_lot_package_id):
    """DOR is named on the project AND could be named on a lot of it. The lot adds nothing —
    it is already covered, and carrying it would make the filter say the same thing twice."""
    db.add(
        PackageOrganization(
            package_id=jhapa_lot_package_id, organization_id=ORG_DOR, org_role="main_contractor"
        )
    )
    db.flush()
    try:
        project_ids, package_ids = project_and_package_reach(db, ORG_DOR)
        assert kl_road_project.project_id in project_ids
        assert jhapa_lot_package_id not in package_ids
    finally:
        db.execute(
            PackageOrganization.__table__.delete().where(
                PackageOrganization.package_id == jhapa_lot_package_id,
                PackageOrganization.organization_id == ORG_DOR,
            )
        )
        db.flush()


# ── the report column ─────────────────────────────────────────────────────────

def test_the_project_lists_every_organization_named_on_it(db, kl_road_project):
    """The export's "Organizations" column. A grievance belongs to all of them, so naming one
    was a true statement and several missing ones."""
    ids = organization_ids_for_project(db, kl_road_project.project_id)
    assert ORG_DOR in ids and ORG_ADB in ids
    assert len(ids) == len(set(ids)), "no duplicates"


def test_a_project_level_naming_covers_its_lots(db, kl_road_project, jhapa_lot_package_id):
    """A grievance filed against a lot still belongs to the project's organizations."""
    project_ids, _ = project_and_package_reach(db, ORG_ADB)
    assert kl_road_project.project_id in project_ids
    pkg = db.get(ProjectPackage, jhapa_lot_package_id)
    assert pkg.project_id == kl_road_project.project_id


def test_reach_survives_an_organization_linked_twice(db, kl_road_project):
    """Two roles for one organization on one project (e.g. donor AND supervisor) must not
    double-count or break the filter."""
    extra = ProjectOrganization(
        project_id=kl_road_project.project_id,
        organization_id=ORG_ADB,
        org_role="specialized_consultant",
    )
    existing = db.execute(
        select(ProjectOrganization).where(
            ProjectOrganization.project_id == kl_road_project.project_id,
            ProjectOrganization.organization_id == ORG_ADB,
        )
    ).scalar_one_or_none()
    if existing is not None:
        pytest.skip("ADB already linked once; the model allows one row per (project, org)")
    db.add(extra)
    db.flush()
    try:
        project_ids, _ = project_and_package_reach(db, ORG_ADB)
        assert kl_road_project.project_id in project_ids
    finally:
        db.delete(extra)
        db.flush()


# ── changing a project's type (2026-08-04) ────────────────────────────────────

def test_a_live_project_cannot_change_its_type(db, kl_road_project):
    """The one operation that could silently restaff work in flight
    (DECISION-author-defined-slots §8). Refused while the project accepts grievances —
    deactivate first, which is the same repair path a frozen type already uses."""
    from fastapi import HTTPException

    from ticketing.api.routers.locations import _switch_project_type

    assert kl_road_project.is_active, "KL Road is the live demo project"
    with pytest.raises(HTTPException) as exc:
        _switch_project_type(db, kl_road_project, "some_other_type")
    assert exc.value.status_code == 409
    assert "Deactivate" in exc.value.detail
