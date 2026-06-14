"""Tests for resolve_ticket_organization (project/package actor routing)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from ticketing.api.schemas.ticket import TicketCreate
from ticketing.constants.projects import KL_ROAD_PROJECT_ID
from ticketing.models.project import Project
from ticketing.services.officer_admin import JurisdictionInput, validate_jurisdiction
from ticketing.services.project_routing import (
    known_project_code_refs,
    load_project_ref,
    resolve_ticket_organization,
)
from ticketing.services.ticket_intake import _effective_organization_id

from tests.ticketing.conftest import ORG_DOR, PROJECT_KL_ROAD, ROLE_L1

pytestmark = pytest.mark.integration


class TestLoadProjectRef:
    def test_resolves_by_stable_project_id(self, db):
        project = load_project_ref(db, KL_ROAD_PROJECT_ID)
        assert project is not None
        assert project.project_id == KL_ROAD_PROJECT_ID

    def test_resolves_legacy_alias_after_short_code_rename(self, db):
        project = db.execute(
            select(Project).where(Project.project_id == KL_ROAD_PROJECT_ID)
        ).scalar_one()
        project.short_code = "52097003"
        db.flush()
        resolved = load_project_ref(db, "KL_ROAD")
        assert resolved is not None
        assert resolved.project_id == KL_ROAD_PROJECT_ID
        assert resolved.short_code == "52097003"

    def test_known_refs_include_legacy_alias(self, db):
        project = db.execute(
            select(Project).where(Project.project_id == KL_ROAD_PROJECT_ID)
        ).scalar_one()
        project.short_code = "52097003"
        db.flush()
        refs = known_project_code_refs(project)
        assert "52097003" in refs
        assert "KL_ROAD" in refs


class TestResolveTicketOrganization:
    def test_kl_road_resolves_to_dor(self, db):
        org = resolve_ticket_organization(db, project_code=PROJECT_KL_ROAD)
        assert org == ORG_DOR

    def test_unknown_project_returns_none(self, db):
        assert resolve_ticket_organization(db, project_code="NO_SUCH_PROJECT") is None

    def test_legacy_kl_road_code_after_short_code_rename(self, db):
        project = db.execute(
            select(Project).where(Project.project_id == KL_ROAD_PROJECT_ID)
        ).scalar_one()
        project.short_code = "52097003"
        db.flush()
        org = resolve_ticket_organization(db, project_code="KL_ROAD")
        assert org == ORG_DOR

    def test_intake_overrides_wrong_payload_org(self, db):
        payload = TicketCreate(
            grievance_id="test-routing-grievance-1",
            organization_id="NP_DC",
            project_code=PROJECT_KL_ROAD,
            location_code="P1_MOR",
        )
        assert _effective_organization_id(db, payload) == ORG_DOR


class TestInviteOrgResolution:
    def test_validate_jurisdiction_keeps_officer_employer_org(self, db):
        project = db.execute(
            select(Project).where(Project.project_id == KL_ROAD_PROJECT_ID)
        ).scalar_one()

        juris = JurisdictionInput(
            organization_id="NP_DC",
            role_key=ROLE_L1,
            project_id=project.project_id,
            location_code="P1_MOR",
        )
        validate_jurisdiction(db, juris, require_jurisdiction=True)
        assert juris.organization_id == "NP_DC"
