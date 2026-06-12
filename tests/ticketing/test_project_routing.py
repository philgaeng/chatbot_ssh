"""Tests for resolve_ticket_organization (project/package actor routing)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from ticketing.api.schemas.ticket import TicketCreate
from ticketing.models.project import Project
from ticketing.services.officer_admin import JurisdictionInput, validate_jurisdiction
from ticketing.services.project_routing import resolve_ticket_organization
from ticketing.services.ticket_intake import _effective_organization_id

from tests.ticketing.conftest import ORG_DOR, PROJECT_KL_ROAD, ROLE_L1

pytestmark = pytest.mark.integration


class TestResolveTicketOrganization:
    def test_kl_road_resolves_to_dor(self, db):
        org = resolve_ticket_organization(db, project_code=PROJECT_KL_ROAD)
        assert org == ORG_DOR

    def test_unknown_project_returns_none(self, db):
        assert resolve_ticket_organization(db, project_code="NO_SUCH_PROJECT") is None

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
            select(Project).where(Project.short_code == PROJECT_KL_ROAD)
        ).scalar_one()

        juris = JurisdictionInput(
            organization_id="NP_DC",
            role_key=ROLE_L1,
            project_id=project.project_id,
            location_code="P1_MOR",
        )
        validate_jurisdiction(db, juris, require_jurisdiction=True)
        assert juris.organization_id == "NP_DC"
