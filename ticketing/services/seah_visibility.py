"""
Track-derived SEAH visibility (DESIGN-cast-model §3.1).

SEAH access is a **workflow-track** property, not a hardcoded role list: *you can see a SEAH
case because you are cast on a SEAH-track workflow's step.* This module derives the set of
role_keys that appear on any SEAH-track (`workflow_type='seah'`) workflow step — which
naturally includes both the named seed roles (`seah_national_officer`, `seah_hq_officer`) and
any synthetic per-step-tier keys minted for a SEAH workflow.

This is used **additively** — it only ever *grants* SEAH eligibility to genuine track members;
the legacy `SEAH_ROLES` fast-path and the admin-track / oversight paths still stand. Isolation
is preserved because `validate_step_roles` forbids a Standard-scoped role on a SEAH step, so
this set never contains a standard operational role.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ticketing.models.workflow import WorkflowDefinition, WorkflowStep


def seah_track_role_keys(db: Session) -> set[str]:
    """Every role_key cast into any tier of any SEAH-track workflow step."""
    seah_wf_ids = [
        wid
        for (wid,) in db.execute(
            sa.select(WorkflowDefinition.workflow_id).where(
                sa.func.lower(WorkflowDefinition.workflow_type) == "seah"
            )
        ).all()
    ]
    if not seah_wf_ids:
        return set()
    steps = db.execute(
        sa.select(WorkflowStep).where(
            WorkflowStep.workflow_id.in_(seah_wf_ids),
            WorkflowStep.is_deleted.is_(False),
        )
    ).scalars().all()
    keys: set[str] = set()
    for s in steps:
        if s.assigned_role_key:
            keys.add(s.assigned_role_key)
        if s.supervisor_role:
            keys.add(s.supervisor_role)
        keys.update(s.informed_roles or [])
        keys.update(s.observer_roles or [])
    return keys


def user_is_seah_track_member(db: Session, role_keys) -> bool:
    """True if any of ``role_keys`` is cast on a SEAH-track workflow (track-derived SEAH access)."""
    rk = set(role_keys or [])
    if not rk:
        return False
    return bool(rk & seah_track_role_keys(db))
