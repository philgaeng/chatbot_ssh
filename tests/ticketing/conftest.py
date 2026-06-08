"""Shared fixtures for ticketing engine integration tests (requires live DB + seed)."""
from __future__ import annotations

from tests.ticketing._host_env import configure_host_test_env

configure_host_test_env()

import uuid
from dataclasses import dataclass, field
from typing import Optional

import pytest
from sqlalchemy import delete, select

from ticketing.models.base import SessionLocal
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket
from ticketing.models.workflow import WorkflowDefinition

# ── Stable constants (match kl_road_standard seed) ────────────────────────────

ORG_DOR = "DOR"
ORG_ADB = "ADB"
PROJECT_KL_ROAD = "KL_ROAD"
ROLE_L1 = "site_safeguards_focal_person"
COUNTRY_L1_FALLBACK_ROLE = "country_l1_fallback"

LOC_P1 = "P1"              # Koshi province
LOC_P1_JHA = "P1_JHA"      # Jhapa district
LOC_P1_JHA_BIR = "P1_JHA_BIR"
LOC_P1_MOR = "P1_MOR"      # Morang district
LOC_P2_PAR_BIR = "P2_PAR_BIR"  # Birtamod, Parsa — different province, no seeded L1

WORKFLOW_STANDARD_KEY = "KL_ROAD_STANDARD"
WORKFLOW_SEAH_KEY = "KL_ROAD_SEAH"


def _uid(prefix: str) -> str:
    return f"test-{prefix}-{uuid.uuid4().hex[:10]}"


@dataclass
class AssignmentTestContext:
    """Insert temporary scopes/tickets; delete on cleanup."""

    db: object
    scope_ids: list[str] = field(default_factory=list)
    ticket_ids: list[str] = field(default_factory=list)

    def add_scope(
        self,
        user_id: str,
        *,
        role_key: str = ROLE_L1,
        organization_id: str = ORG_DOR,
        location_code: Optional[str] = None,
        project_code: Optional[str] = PROJECT_KL_ROAD,
        package_id: Optional[str] = None,
        includes_children: bool = False,
    ) -> OfficerScope:
        row = OfficerScope(
            scope_id=str(uuid.uuid4()),
            user_id=user_id,
            role_key=role_key,
            organization_id=organization_id,
            location_code=location_code,
            project_code=project_code,
            package_id=package_id,
            includes_children=includes_children,
        )
        self.db.add(row)
        self.db.flush()
        self.scope_ids.append(row.scope_id)
        return row

    def add_open_ticket(
        self,
        assigned_to_user_id: str,
        *,
        location_code: str = LOC_P1_JHA_BIR,
        project_code: str = PROJECT_KL_ROAD,
        package_id: Optional[str] = None,
    ) -> Ticket:
        from ticketing.models.workflow import WorkflowStep

        wf = self.db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.workflow_key == WORKFLOW_STANDARD_KEY
            )
        ).scalar_one()
        step = self.db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == wf.workflow_id)
            .order_by(WorkflowStep.step_order)
            .limit(1)
        ).scalar_one()

        row = Ticket(
            ticket_id=str(uuid.uuid4()),
            grievance_id=_uid("grv"),
            organization_id=ORG_DOR,
            location_code=location_code,
            project_code=project_code,
            package_id=package_id,
            current_workflow_id=wf.workflow_id,
            current_step_id=step.step_id,
            assigned_to_user_id=assigned_to_user_id,
            status_code="OPEN",
            is_seah=False,
            is_deleted=False,
            sla_breached=False,
            priority="NORMAL",
        )
        self.db.add(row)
        self.db.flush()
        self.ticket_ids.append(row.ticket_id)
        return row

    def cleanup(self) -> None:
        if self.ticket_ids:
            self.db.execute(delete(Ticket).where(Ticket.ticket_id.in_(self.ticket_ids)))
        if self.scope_ids:
            self.db.execute(delete(OfficerScope).where(OfficerScope.scope_id.in_(self.scope_ids)))
        self.db.commit()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def ctx(db):
    """Mutable assignment scenario with guaranteed teardown."""
    context = AssignmentTestContext(db=db)
    try:
        yield context
    finally:
        context.cleanup()


@pytest.fixture
def kl_road_project(db) -> Project:
    return db.execute(
        select(Project).where(Project.short_code == PROJECT_KL_ROAD)
    ).scalar_one()


@pytest.fixture
def jhapa_lot_package_id(db, kl_road_project) -> str:
    """Lot 1 package (SHEP/OCB/KL/01) — linked to P1_JHA in package_locations."""
    from ticketing.models.package import ProjectPackage

    pkg = db.execute(
        select(ProjectPackage).where(
            ProjectPackage.project_id == kl_road_project.project_id,
            ProjectPackage.package_code == "SHEP/OCB/KL/01",
        )
    ).scalar_one()
    return pkg.package_id
