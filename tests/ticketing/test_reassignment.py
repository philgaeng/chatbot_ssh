"""Reassignment authority resolution + go-live guard (DESIGN-cast-model §3.4).

Integration (live seeded DB): the fallback chain (Dispatcher → Supervisor → Actor self-serve →
project_admin) never dead-ends; Dispatcher takes precedence; the Actor self-serve toggle grants
the assignee reassignment authority; and go-live blocks a step with no reachable reassigner.
"""
from __future__ import annotations

import uuid

import pytest

from ticketing.api.dependencies import CurrentUser
from ticketing.services.reassignment import (
    DISPATCHER_ROLE_KEY,
    resolve_reassignment_authority,
    step_has_reachable_reassigner,
)

pytestmark = pytest.mark.integration

_ROLE_L1 = "site_safeguards_focal_person"


def test_reassignment_never_dead_ends(db, ctx):
    """A bounced ticket always resolves to someone — KL Road has a project_admin backstop."""
    ticket = ctx.add_open_ticket("assignee@grm.local", location_code="P1_JHA")
    auth = resolve_reassignment_authority(db, ticket, exclude_self=True)
    assert auth.user_id is not None
    assert auth.source in ("dispatcher", "supervisor", "project_admin")


def test_dispatcher_takes_precedence(db, ctx):
    """A staffed Dispatcher wins over Supervisor / project_admin (chain rung 1)."""
    ticket = ctx.add_open_ticket("assignee@grm.local", location_code="P1_JHA")
    disp = f"dispatcher-{uuid.uuid4().hex[:6]}@grm.local"
    ctx.add_scope(disp, role_key=DISPATCHER_ROLE_KEY, project_code="KL_ROAD")
    auth = resolve_reassignment_authority(db, ticket, exclude_self=True)
    assert auth.source == "dispatcher"
    assert auth.user_id == disp


def test_actor_self_serve_toggle_grants_assign(db, ctx):
    """With the per-step Actor self-serve toggle on, the assigned Actor may reassign (§3.4)."""
    from ticketing.api.routers.tickets.crud import _can_assign_ticket
    from ticketing.engine.workflow_engine import get_current_step

    assignee = f"l1-actor-{uuid.uuid4().hex[:6]}@grm.local"
    ticket = ctx.add_open_ticket(assignee, location_code="P1_JHA")
    step = get_current_step(ticket, db)
    saved = step.actor_can_reassign
    user = CurrentUser(user_id=assignee, role_keys=[step.assigned_role_key])
    try:
        step.actor_can_reassign = True
        db.flush()
        assert _can_assign_ticket(db, ticket, user) is True
    finally:
        step.actor_can_reassign = saved
        db.flush()


def test_go_live_r1_passes_for_demo(db, kl_road_project):
    """R1 is a block-severity check that passes for the demo (project_admin backstop)."""
    from ticketing.services import project_go_live as svc

    report = svc.evaluate_go_live(db, kl_road_project.project_id)
    r1 = next(c for c in report.checks if c.id == "R1")
    assert r1.severity == "block"
    assert r1.status == "pass"


def test_go_live_r1_step_logic(db, kl_road_project):
    """step_has_reachable_reassigner resolves via the project_admin backstop for any step."""
    from ticketing.models.workflow import WorkflowStep
    import sqlalchemy as sa

    step = db.execute(
        sa.select(WorkflowStep)
        .where(WorkflowStep.workflow_id == kl_road_project.standard_workflow_id,
               WorkflowStep.is_deleted.is_(False))
        .order_by(WorkflowStep.step_order)
    ).scalars().first()
    assert step is not None
    assert step_has_reachable_reassigner(db, project=kl_road_project, step=step) is True
