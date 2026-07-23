"""
Per-(project, step) supervisor resolver (OC-03, DECISION 2026-07-10 §5).

The supervisor is the OIC's manager **in the project ladder**, per workflow step — the
reassignment authority when auto-assign fails at a step (OC-04 wires the notify/park/
reassign). It is deliberately **not** an org-tree reporting line: there is **no**
`parent_organization_id` walk (that mis-resolves across project/forest boundaries).
`officer_positions.reports_to_user_id` / `position_types.reports_to_position_key` are
HR/admin-only and never feed this resolver.

Resolution order (DECISION §56–60):
  1. Explicit per-(project, step) supervisor — a store does not exist yet, so this tier is
     currently always empty (future work; the signature carries `project_code` for it).
  2. Default = the **next step's Handler pool** (`assigned_role_key`), same workflow.
  3. Top step (no next step) → explicit is required; with no store that means none.
  4. Else null → the caller falls back to the step's `supervisor_role` tier pool.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ticketing.models.workflow import WorkflowStep


@dataclass(frozen=True)
class SupervisorResolution:
    """The resolved supervisor for a step. ``role_pool`` is a role_key pool (the common
    case); ``user_id`` is a specific person (explicit tier — future). ``source`` is the
    provenance for UI ("Supervisor: L2 handler pool — change")."""

    role_pool: str | None
    user_id: str | None
    source: str  # explicit_user | explicit_pool | next_step_handler | step_supervisor_role | none


def _next_step(db: Session, workflow_id: str, step_order: int) -> WorkflowStep | None:
    return db.execute(
        sa.select(WorkflowStep)
        .where(
            WorkflowStep.workflow_id == workflow_id,
            WorkflowStep.step_order > step_order,
            WorkflowStep.is_deleted.is_(False),
        )
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()


def resolve_supervisor(
    db: Session, step: WorkflowStep, *, project_code: str | None = None
) -> SupervisorResolution:
    """Resolve the supervisor for ``step`` (optionally scoped to ``project_code``).

    No org-tree walk. See module docstring for the order. Returns a role pool for the
    non-top-step default; on the top step with no explicit store, returns the step's
    ``supervisor_role`` fallback, else ``none``.
    """
    # 1. Explicit per-(project, step) supervisor — no store yet (future). project_code is
    #    carried so the explicit lookup can key on it once the store exists.
    _ = project_code

    # 2. Non-top step → the next step's Handler pool.
    nxt = _next_step(db, step.workflow_id, step.step_order)
    if nxt is not None:
        return SupervisorResolution(role_pool=nxt.assigned_role_key, user_id=None, source="next_step_handler")

    # 3. Top step → explicit required (none available) → 4. null → step.supervisor_role fallback.
    if step.supervisor_role:
        return SupervisorResolution(
            role_pool=step.supervisor_role, user_id=None, source="step_supervisor_role"
        )
    return SupervisorResolution(role_pool=None, user_id=None, source="none")
