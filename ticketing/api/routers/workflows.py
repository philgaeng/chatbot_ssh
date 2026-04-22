"""
Workflow management endpoints — full CRUD for the no-code workflow editor.

Read endpoints: any authenticated officer
Mutating endpoints: admin only (super_admin, local_admin)
SEAH workflows: additionally gated by can_see_seah
"""
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ticketing.api.dependencies import get_db, get_current_user, CurrentUser
from ticketing.api.schemas.workflow import (
    StepReorderRequest,
    WorkflowAssignmentCreate,
    WorkflowAssignmentResponse,
    WorkflowCreate,
    WorkflowDefinitionResponse,
    WorkflowListResponse,
    WorkflowStepCreate,
    WorkflowStepResponse,
    WorkflowStepUpdate,
    WorkflowUpdate,
)
from ticketing.models.workflow import WorkflowAssignment, WorkflowDefinition, WorkflowStep

router = APIRouter()

BUILT_IN_TEMPLATES = {
    "default_grm": {
        "display_name": "Default GRM",
        "workflow_type": "standard",
        "description": "Standard 4-level GRM workflow (L1 Site → L2 PIU → L3 GRC → L4 Legal)",
        "steps": [
            {"step_key": "LEVEL_1_SITE",  "display_name": "Level 1 — Site Safeguards", "assigned_role_key": "site_safeguards_focal_person", "response_time_hours": 24,  "resolution_time_days": 2},
            {"step_key": "LEVEL_2_PIU",   "display_name": "Level 2 — PD/PIU",          "assigned_role_key": "pd_piu_safeguards_focal",      "response_time_hours": 48,  "resolution_time_days": 7},
            {"step_key": "LEVEL_3_GRC",   "display_name": "Level 3 — GRC",             "assigned_role_key": "grc_chair",                   "response_time_hours": 72,  "resolution_time_days": 21},
            {"step_key": "LEVEL_4_LEGAL", "display_name": "Level 4 — Legal",           "assigned_role_key": "adb_hq_safeguards",           "response_time_hours": None, "resolution_time_days": None},
        ],
    },
    "default_seah": {
        "display_name": "Default SEAH",
        "workflow_type": "seah",
        "description": "Standard 2-level SEAH workflow (L1 National → L2 HQ)",
        "steps": [
            {"step_key": "SEAH_LEVEL_1_NATIONAL", "display_name": "SEAH L1 — National Officer", "assigned_role_key": "seah_national_officer", "response_time_hours": 24, "resolution_time_days": 7},
            {"step_key": "SEAH_LEVEL_2_HQ",       "display_name": "SEAH L2 — HQ Officer",       "assigned_role_key": "seah_hq_officer",       "response_time_hours": 48, "resolution_time_days": 14},
        ],
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


def _slug(text: str) -> str:
    """Generate a step_key from display name: 'Level 2 — PD/PIU' → 'LEVEL_2_PDPIU'"""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").upper()
    return s[:64]


def _require_admin(current_user: CurrentUser) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _require_seah(current_user: CurrentUser) -> None:
    if not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="SEAH admin access required")


def _load_workflow(workflow_id: str, db: Session, current_user: CurrentUser) -> WorkflowDefinition:
    wf = db.execute(
        select(WorkflowDefinition)
        .options(
            selectinload(WorkflowDefinition.steps),
            selectinload(WorkflowDefinition.assignments),
        )
        .where(WorkflowDefinition.workflow_id == workflow_id)
    ).scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.workflow_type == "seah" and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="SEAH admin access required")
    return wf


# ── List / get ────────────────────────────────────────────────────────────────

@router.get("/workflows", response_model=WorkflowListResponse, summary="List workflows")
def list_workflows(
    workflow_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_template: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowListResponse:
    q = select(WorkflowDefinition).options(
        selectinload(WorkflowDefinition.steps),
        selectinload(WorkflowDefinition.assignments),
    )
    # Hide SEAH workflows from non-SEAH users
    if not current_user.can_see_seah:
        q = q.where(WorkflowDefinition.workflow_type != "seah")
    if workflow_type:
        q = q.where(WorkflowDefinition.workflow_type == workflow_type)
    if status:
        q = q.where(WorkflowDefinition.status == status)
    if is_template is not None:
        q = q.where(WorkflowDefinition.is_template == is_template)

    workflows = db.execute(q.order_by(WorkflowDefinition.display_name)).scalars().all()
    return WorkflowListResponse(
        items=[WorkflowDefinitionResponse.model_validate(w) for w in workflows],
        total=len(workflows),
    )


@router.get("/workflows/templates", response_model=WorkflowListResponse, summary="List templates")
def list_templates(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowListResponse:
    """Returns built-in template definitions + admin-created templates."""
    built_ins = []
    for key, tpl in BUILT_IN_TEMPLATES.items():
        if key == "default_seah" and not current_user.can_see_seah:
            continue
        built_ins.append({
            "workflow_id": f"__builtin_{key}",
            "workflow_key": key,
            "display_name": tpl["display_name"],
            "description": tpl["description"],
            "workflow_type": tpl["workflow_type"],
            "status": "template",
            "version": 1,
            "is_template": True,
            "template_source_id": None,
            "steps": [
                {**s, "step_id": f"__builtin_{i}", "workflow_id": f"__builtin_{key}",
                 "step_order": i + 1, "stakeholders": None, "expected_actions": None,
                 "is_deleted": False,
                 "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
                for i, s in enumerate(tpl["steps"])
            ],
            "assignments": [],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        })

    # Admin-created templates from DB
    q = select(WorkflowDefinition).options(
        selectinload(WorkflowDefinition.steps),
        selectinload(WorkflowDefinition.assignments),
    ).where(WorkflowDefinition.is_template.is_(True))
    if not current_user.can_see_seah:
        q = q.where(WorkflowDefinition.workflow_type != "seah")
    db_templates = db.execute(q).scalars().all()

    items = [WorkflowDefinitionResponse.model_validate(t) for t in db_templates]
    # Prepend built-ins (they use raw dicts — parse manually)
    from pydantic import TypeAdapter
    ta = TypeAdapter(WorkflowDefinitionResponse)
    built_in_parsed = [ta.validate_python(b) for b in built_ins]

    return WorkflowListResponse(items=built_in_parsed + items, total=len(built_in_parsed) + len(items))


@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinitionResponse, summary="Get workflow detail")
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowDefinitionResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    return WorkflowDefinitionResponse.model_validate(wf)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/workflows", response_model=WorkflowDefinitionResponse, status_code=201, summary="Create workflow")
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowDefinitionResponse:
    _require_admin(current_user)
    if payload.workflow_type == "seah":
        _require_seah(current_user)

    wf_id = _new_id()
    wf_key = _slug(payload.display_name) + "_" + wf_id[:8]

    wf = WorkflowDefinition(
        workflow_id=wf_id,
        workflow_key=wf_key,
        display_name=payload.display_name,
        description=payload.description,
        workflow_type=payload.workflow_type,
        status="draft",
        version=1,
        is_template=False,
        updated_by_user_id=current_user.user_id,
    )
    db.add(wf)

    # Clone steps from source workflow or built-in template
    source_steps: list[dict] = []
    if payload.clone_from_id:
        if payload.clone_from_id.startswith("__builtin_"):
            tpl_key = payload.clone_from_id.replace("__builtin_", "")
            tpl = BUILT_IN_TEMPLATES.get(tpl_key)
            if tpl:
                source_steps = [dict(s) for s in tpl["steps"]]
                wf.template_source_id = payload.clone_from_id
        else:
            src = db.get(WorkflowDefinition, payload.clone_from_id)
            if src:
                source_steps = [
                    {
                        "step_key": s.step_key,
                        "display_name": s.display_name,
                        "assigned_role_key": s.assigned_role_key,
                        "response_time_hours": s.response_time_hours,
                        "resolution_time_days": s.resolution_time_days,
                        "stakeholders": s.stakeholders,
                        "expected_actions": s.expected_actions,
                    }
                    for s in sorted(src.steps, key=lambda x: x.step_order)
                    if not s.is_deleted
                ]
                wf.template_source_id = payload.clone_from_id

    for i, s in enumerate(source_steps):
        db.add(WorkflowStep(
            step_id=_new_id(),
            workflow_id=wf_id,
            step_order=i + 1,
            step_key=s.get("step_key") or _slug(s["display_name"]),
            display_name=s["display_name"],
            assigned_role_key=s["assigned_role_key"],
            response_time_hours=s.get("response_time_hours"),
            resolution_time_days=s.get("resolution_time_days"),
            stakeholders=s.get("stakeholders"),
            expected_actions=s.get("expected_actions"),
        ))

    db.commit()
    db.refresh(wf)
    return WorkflowDefinitionResponse.model_validate(wf)


# ── Update metadata ───────────────────────────────────────────────────────────

@router.patch("/workflows/{workflow_id}", response_model=WorkflowDefinitionResponse, summary="Update workflow metadata")
def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowDefinitionResponse:
    _require_admin(current_user)
    wf = _load_workflow(workflow_id, db, current_user)
    if payload.display_name is not None:
        wf.display_name = payload.display_name
    if payload.description is not None:
        wf.description = payload.description
    if payload.workflow_key is not None:
        wf.workflow_key = payload.workflow_key
    wf.updated_by_user_id = current_user.user_id
    db.commit()
    db.refresh(wf)
    return WorkflowDefinitionResponse.model_validate(wf)


# ── Publish ───────────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/publish", response_model=WorkflowDefinitionResponse, summary="Publish workflow")
def publish_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowDefinitionResponse:
    _require_admin(current_user)
    wf = _load_workflow(workflow_id, db, current_user)
    if wf.status == "archived":
        raise HTTPException(status_code=422, detail="Cannot publish an archived workflow")
    wf.status = "published"
    wf.version = (wf.version or 0) + 1
    wf.updated_by_user_id = current_user.user_id
    db.commit()
    db.refresh(wf)
    return WorkflowDefinitionResponse.model_validate(wf)


# ── Save as template ──────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/save-as-template", response_model=WorkflowDefinitionResponse, status_code=201, summary="Save workflow as reusable template")
def save_as_template(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowDefinitionResponse:
    _require_admin(current_user)
    src = _load_workflow(workflow_id, db, current_user)

    tpl_id = _new_id()
    tpl = WorkflowDefinition(
        workflow_id=tpl_id,
        workflow_key=f"tpl_{_slug(src.display_name)}_{tpl_id[:8]}",
        display_name=f"{src.display_name} (template)",
        description=src.description,
        workflow_type=src.workflow_type,
        status="published",
        version=1,
        is_template=True,
        template_source_id=workflow_id,
        updated_by_user_id=current_user.user_id,
    )
    db.add(tpl)
    for s in sorted(src.steps, key=lambda x: x.step_order):
        if not s.is_deleted:
            db.add(WorkflowStep(
                step_id=_new_id(), workflow_id=tpl_id,
                step_order=s.step_order, step_key=s.step_key,
                display_name=s.display_name, assigned_role_key=s.assigned_role_key,
                response_time_hours=s.response_time_hours,
                resolution_time_days=s.resolution_time_days,
                stakeholders=s.stakeholders, expected_actions=s.expected_actions,
            ))
    db.commit()
    db.refresh(tpl)
    return WorkflowDefinitionResponse.model_validate(tpl)


# ── Archive ───────────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/archive", response_model=WorkflowDefinitionResponse, summary="Archive workflow")
def archive_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowDefinitionResponse:
    _require_admin(current_user)
    wf = _load_workflow(workflow_id, db, current_user)
    wf.status = "archived"
    wf.updated_by_user_id = current_user.user_id
    db.commit()
    db.refresh(wf)
    return WorkflowDefinitionResponse.model_validate(wf)


# ── Steps ─────────────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/steps", response_model=WorkflowStepResponse, status_code=201, summary="Add step")
def add_step(
    workflow_id: str,
    payload: WorkflowStepCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowStepResponse:
    _require_admin(current_user)
    _load_workflow(workflow_id, db, current_user)  # access check

    # Append at the end
    max_order = db.execute(
        select(WorkflowStep.step_order)
        .where(WorkflowStep.workflow_id == workflow_id, WorkflowStep.is_deleted.is_(False))
        .order_by(WorkflowStep.step_order.desc()).limit(1)
    ).scalar_one_or_none() or 0

    step = WorkflowStep(
        step_id=_new_id(),
        workflow_id=workflow_id,
        step_order=max_order + 1,
        step_key=payload.step_key or _slug(payload.display_name),
        display_name=payload.display_name,
        assigned_role_key=payload.assigned_role_key,
        response_time_hours=payload.response_time_hours,
        resolution_time_days=payload.resolution_time_days,
        stakeholders=payload.stakeholders,
        expected_actions=payload.expected_actions,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return WorkflowStepResponse.model_validate(step)


@router.patch("/workflows/{workflow_id}/steps/{step_id}", response_model=WorkflowStepResponse, summary="Edit step")
def update_step(
    workflow_id: str,
    step_id: str,
    payload: WorkflowStepUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowStepResponse:
    _require_admin(current_user)
    _load_workflow(workflow_id, db, current_user)

    step = db.get(WorkflowStep, step_id)
    if not step or step.workflow_id != workflow_id or step.is_deleted:
        raise HTTPException(status_code=404, detail="Step not found")

    if payload.display_name is not None:
        step.display_name = payload.display_name
    if payload.step_key is not None:
        step.step_key = payload.step_key
    if payload.assigned_role_key is not None:
        step.assigned_role_key = payload.assigned_role_key
    if payload.response_time_hours is not None:
        step.response_time_hours = payload.response_time_hours
    if payload.resolution_time_days is not None:
        step.resolution_time_days = payload.resolution_time_days
    if payload.stakeholders is not None:
        step.stakeholders = payload.stakeholders
    if payload.expected_actions is not None:
        step.expected_actions = payload.expected_actions

    db.commit()
    db.refresh(step)
    return WorkflowStepResponse.model_validate(step)


@router.delete("/workflows/{workflow_id}/steps/{step_id}", status_code=204, summary="Remove step (blocked if tickets active on it)")
def delete_step(
    workflow_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    _load_workflow(workflow_id, db, current_user)

    step = db.get(WorkflowStep, step_id)
    if not step or step.workflow_id != workflow_id or step.is_deleted:
        raise HTTPException(status_code=404, detail="Step not found")

    # Block if any active tickets are currently on this step
    from ticketing.models.ticket import Ticket
    active_count = db.execute(
        select(Ticket).where(
            Ticket.current_step_id == step_id,
            Ticket.status_code.notin_(["RESOLVED", "CLOSED"]),
            Ticket.is_deleted.is_(False),
        )
    ).scalars().first()

    if active_count:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot delete step '{step.display_name}' — there are active tickets on it. Resolve or reassign them first.",
        )

    step.is_deleted = True
    db.commit()


@router.post("/workflows/{workflow_id}/steps/reorder", response_model=list[WorkflowStepResponse], summary="Reorder steps")
def reorder_steps(
    workflow_id: str,
    payload: StepReorderRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[WorkflowStepResponse]:
    _require_admin(current_user)
    _load_workflow(workflow_id, db, current_user)

    steps = {
        s.step_id: s
        for s in db.execute(
            select(WorkflowStep).where(
                WorkflowStep.workflow_id == workflow_id,
                WorkflowStep.is_deleted.is_(False),
            )
        ).scalars().all()
    }

    for new_order, step_id in enumerate(payload.step_ids, start=1):
        if step_id not in steps:
            raise HTTPException(status_code=422, detail=f"Unknown step_id: {step_id}")
        steps[step_id].step_order = new_order

    db.commit()
    return [WorkflowStepResponse.model_validate(steps[sid]) for sid in payload.step_ids]


# ── Assignments ───────────────────────────────────────────────────────────────

@router.get("/workflows/{workflow_id}/assignments", response_model=list[WorkflowAssignmentResponse], summary="List assignments")
def list_assignments(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[WorkflowAssignmentResponse]:
    _load_workflow(workflow_id, db, current_user)
    rows = db.execute(
        select(WorkflowAssignment).where(WorkflowAssignment.workflow_id == workflow_id)
    ).scalars().all()
    return [WorkflowAssignmentResponse.model_validate(r) for r in rows]


@router.post("/workflows/{workflow_id}/assignments", response_model=WorkflowAssignmentResponse, status_code=201, summary="Add assignment")
def add_assignment(
    workflow_id: str,
    payload: WorkflowAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowAssignmentResponse:
    _require_admin(current_user)
    wf = _load_workflow(workflow_id, db, current_user)

    # Conflict check: warn if another published workflow already matches this tuple
    conflict = db.execute(
        select(WorkflowDefinition)
        .join(WorkflowAssignment, WorkflowAssignment.workflow_id == WorkflowDefinition.workflow_id)
        .where(
            WorkflowDefinition.status == "published",
            WorkflowDefinition.workflow_id != workflow_id,
            WorkflowAssignment.organization_id == payload.organization_id,
            WorkflowAssignment.location_code == payload.location_code,
            WorkflowAssignment.project_code == payload.project_code,
            WorkflowAssignment.priority == payload.priority,
        )
    ).scalar_one_or_none()

    headers = {}
    if conflict:
        headers["X-Conflict-Warning"] = f"Workflow '{conflict.display_name}' already matches this assignment tuple"

    row = WorkflowAssignment(
        assignment_id=_new_id(),
        workflow_id=workflow_id,
        organization_id=payload.organization_id,
        location_code=payload.location_code,
        project_code=payload.project_code,
        priority=payload.priority,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    from fastapi.responses import JSONResponse
    result = WorkflowAssignmentResponse.model_validate(row)
    if headers:
        return JSONResponse(content=result.model_dump(), headers=headers, status_code=201)
    return result


@router.delete("/workflows/{workflow_id}/assignments/{assignment_id}", status_code=204, summary="Remove assignment")
def remove_assignment(
    workflow_id: str,
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    row = db.get(WorkflowAssignment, assignment_id)
    if not row or row.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(row)
    db.commit()
