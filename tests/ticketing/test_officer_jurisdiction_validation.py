"""SH-3 — invite/add-scope jurisdiction validation (OC-06 F6/O4).

validate_jurisdiction is the shared write-path validator for both the invite and the
add-scope routes. It now rejects a non-existent org and an org that is not a participant
on the scoped project — closing the "out-of-jurisdiction / non-existent org bound as an
enforcement scope" gap for both callers.

Integration-only: exercises the real Organization/Project/ProjectOrganization tables
against the seeded KL_ROAD project (DOR + ADB are its participants).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from ticketing.services.officer_admin import JurisdictionInput, validate_jurisdiction

pytestmark = pytest.mark.integration

STD_ROLE = "site_safeguards_focal_person"


@pytest.fixture
def db():
    from ticketing.models.base import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()   # discard any uncommitted test rows
        s.close()


def _kl_road_id(db) -> str:
    from ticketing.models.project import Project

    return db.execute(select(Project).where(Project.short_code == "KL_ROAD")).scalar_one().project_id


def test_linked_org_on_project_passes(db):
    pid = _kl_road_id(db)
    # DOR is a seeded participant on KL_ROAD → no raise
    validate_jurisdiction(
        db, JurisdictionInput(organization_id="DOR", role_key=STD_ROLE, project_id=pid)
    )


def test_org_only_scope_no_project_passes(db):
    # A country/org-only scope (no project) checks org existence but not a project link.
    validate_jurisdiction(
        db,
        JurisdictionInput(organization_id="DOR", role_key=STD_ROLE),
        require_jurisdiction=False,
    )


def test_nonexistent_org_rejected(db):
    with pytest.raises(HTTPException) as exc:
        validate_jurisdiction(
            db,
            JurisdictionInput(organization_id="GHOST_ORG_XYZ", role_key=STD_ROLE),
            require_jurisdiction=False,
        )
    assert exc.value.status_code == 422
    assert "not found" in exc.value.detail.lower()


def test_org_not_linked_to_project_rejected(db):
    from ticketing.models.organization import Organization

    pid = _kl_road_id(db)
    oid = f"SH3_UNLINKED_{uuid.uuid4().hex[:6].upper()}"
    db.add(Organization(organization_id=oid, name="SH3 Unlinked Test Org"))
    db.flush()  # visible to this session; never committed (fixture rolls back)

    with pytest.raises(HTTPException) as exc:
        validate_jurisdiction(
            db, JurisdictionInput(organization_id=oid, role_key=STD_ROLE, project_id=pid)
        )
    assert exc.value.status_code == 422
    assert "not linked" in exc.value.detail.lower()
