"""
Per-package cast staffing (DESIGN-cast-model §3.3, §3.6).

    GET    /projects/{project_id}/cast      read the cast (officers per step/tier/package)
    POST   /projects/{project_id}/cast      staff one (step, tier) slot for a package/project-wide
    DELETE /projects/{project_id}/cast/{scope_id}   remove a staffing row

An orchestration over existing primitives — every enforcement row lands through the
sanctioned writer (`create_scope_row`), so the §5 invariants hold (officer_scopes stays the
single source of truth; positions never gate access). The tier is the slot; no role is chosen.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user
from ticketing.constants.tiers import ACTOR, OBSERVER, PARTICIPANT, SUPERVISOR, TIERS
from ticketing.models.base import get_db
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.project import Project
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep
from ticketing.services.admin_access import SettingsAction, require_settings_write
from ticketing.services.cast_staffing import is_synthetic_key, self_escalation_conflict

router = APIRouter()


def resolve_step_tier_role_key(step: WorkflowStep, tier: str) -> str | None:
    """The role_key backing a (step, tier) slot — the synthetic per-step-tier key in the
    simplified model, or the first named member for legacy multi-role steps."""
    if tier == ACTOR:
        return step.assigned_role_key or None
    if tier == SUPERVISOR:
        return step.supervisor_role or None
    if tier == PARTICIPANT:
        return (list(step.informed_roles or []) or [None])[0]
    if tier == OBSERVER:
        return (list(step.observer_roles or []) or [None])[0]
    return None


class CastAssignRequest(BaseModel):
    workflow_id: str
    step_id: str
    tier: str
    user_id: str
    organization_id: str
    package_id: str | None = None
    location_code: str | None = None
    includes_children: bool | None = None


class CastScopeOut(BaseModel):
    scope_id: str
    user_id: str
    role_key: str
    tier: str
    step_id: str
    package_id: str | None
    location_code: str | None
    organization_id: str


def _load_workflow_step(db: Session, workflow_id: str, step_id: str) -> tuple[WorkflowDefinition, WorkflowStep]:
    wf = db.get(WorkflowDefinition, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    step = db.get(WorkflowStep, step_id)
    if step is None or step.workflow_id != workflow_id or step.is_deleted:
        raise HTTPException(status_code=404, detail="Step not found on this workflow")
    return wf, step


@router.post(
    "/projects/{project_id}/cast",
    response_model=CastScopeOut,
    status_code=201,
    summary="Staff a (step, tier) cast slot for a package (or project-wide)",
)
def staff_cast_slot(
    project_id: str,
    body: CastAssignRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> CastScopeOut:
    require_settings_write(current_user, SettingsAction.INVITE_OFFICERS)
    if body.tier not in TIERS:
        raise HTTPException(status_code=422, detail=f"Unknown tier '{body.tier}'")

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    wf, step = _load_workflow_step(db, body.workflow_id, body.step_id)
    role_key = resolve_step_tier_role_key(step, body.tier)
    if not role_key:
        raise HTTPException(
            status_code=422,
            detail=f"The {body.tier} tier is not enabled on this step — enable it in the step editor first.",
        )

    email = body.user_id.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Staffing requires an email user id.")

    # §3.3 self-escalation guard — never the same person as Actor AND Supervisor of the same
    # (step, package). Derivable from the synthetic per-step-tier keys.
    if is_synthetic_key(role_key) and self_escalation_conflict(
        db,
        workflow_key=wf.workflow_key,
        step_key=step.step_key,
        tier=body.tier,
        user_id=email,
        package_id=body.package_id,
        project_id=project_id,
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "This officer is already the Actor or Supervisor of this step for this package. "
                "One person cannot be both (self-escalation)."
            ),
        )

    from ticketing.services.officer_admin import (
        JurisdictionInput,
        create_scope_row,
        upsert_user_role_row,
        validate_jurisdiction,
    )
    from ticketing.models.user import Role

    juris = JurisdictionInput(
        organization_id=body.organization_id,
        role_key=role_key,
        location_code=body.location_code,
        project_id=project_id,
        package_id=body.package_id,
        includes_children=bool(body.includes_children),
    )
    resolved_pc = validate_jurisdiction(db, juris, require_jurisdiction=True)
    role = db.execute(select(Role).where(Role.role_key == role_key)).scalar_one_or_none()
    if role is None:  # should not happen — synthetic keys mint their roles at step save
        raise HTTPException(status_code=404, detail=f"Role not found: {role_key}")

    upsert_user_role_row(db, email, role, body.organization_id, juris.location_code)
    scope = create_scope_row(db, email, juris, resolved_pc)
    db.commit()
    db.refresh(scope)
    return CastScopeOut(
        scope_id=scope.scope_id, user_id=scope.user_id, role_key=scope.role_key, tier=body.tier,
        step_id=step.step_id, package_id=scope.package_id, location_code=scope.location_code,
        organization_id=scope.organization_id,
    )


@router.get(
    "/projects/{project_id}/cast",
    response_model=list[CastScopeOut],
    summary="Read the cast for a workflow (officers per step/tier), project-wide or per-package",
)
def read_cast(
    project_id: str,
    workflow_id: str = Query(...),
    package_id: str | None = Query(None, description="Package to read; omit for project-wide"),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_authenticated_user),
) -> list[CastScopeOut]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    steps = db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id, WorkflowStep.is_deleted.is_(False))
        .order_by(WorkflowStep.step_order)
    ).scalars().all()

    # role_key -> (step_id, tier) for every enabled slot across the workflow's steps.
    key_slot: dict[str, tuple[str, str]] = {}
    for step in steps:
        for tier in TIERS:
            rk = resolve_step_tier_role_key(step, tier)
            if rk:
                key_slot[rk] = (step.step_id, tier)
    if not key_slot:
        return []

    stmt = select(OfficerScope).where(
        OfficerScope.role_key.in_(list(key_slot.keys())),
        OfficerScope.project_id == project_id,
    )
    if package_id:
        stmt = stmt.where(OfficerScope.package_id == package_id)
    else:
        stmt = stmt.where(OfficerScope.package_id.is_(None))
    rows = db.execute(stmt).scalars().all()

    out: list[CastScopeOut] = []
    for s in rows:
        step_id, tier = key_slot[s.role_key]
        out.append(CastScopeOut(
            scope_id=s.scope_id, user_id=s.user_id, role_key=s.role_key, tier=tier,
            step_id=step_id, package_id=s.package_id, location_code=s.location_code,
            organization_id=s.organization_id,
        ))
    return out


@router.delete(
    "/projects/{project_id}/cast/{scope_id}",
    status_code=204,
    summary="Remove a cast staffing row (deletes the officer_scope)",
)
def unstaff_cast_slot(
    project_id: str,
    scope_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    require_settings_write(current_user, SettingsAction.INVITE_OFFICERS)
    scope = db.get(OfficerScope, scope_id)
    if scope is None or scope.project_id != project_id:
        raise HTTPException(status_code=404, detail="Cast staffing row not found for this project")
    db.delete(scope)
    db.commit()
