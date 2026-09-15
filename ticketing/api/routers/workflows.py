# SPDX-License-Identifier: Apache-2.0

"""
Workflow management endpoints — full CRUD for the no-code workflow editor.

Read endpoints: any authenticated officer
Mutating endpoints: matrix-aware admin (org_admin by track, super_admin)
Sensitive (SEAH) workflows: additionally gated by ``can_configure_sensitive`` — the
**configure** capability. This is deliberately *not* ``can_see_seah`` (case access, cast-only):
an admin administers the sensitive catalog without being able to open a single sensitive
grievance. See `DECISION-sensitive-workflows.md` §3.
"""
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ticketing.api.dependencies import get_db, get_authenticated_user, CurrentUser
from ticketing.services.admin_access import (
    SettingsAction,
    apply_catalog_scope,
    can_mutate_workflow,
    catalog_owner_for,
    require_settings_write,
    workflow_track_from_type,
)
from ticketing.services.resolution_catalog import (
    ResolutionCatalogError,
    copy_workflow_actions,
    is_sensitive_workflow,
    selected_codes,
)
from ticketing.services.role_scope import (
    require_named_jobs,
    unnamed_jobs,
    validate_step_roles,
)
from ticketing.api.schemas.workflow import (
    SaveAsTemplateBody,
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
from ticketing.models.ticket import Ticket
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


def _require_workflow_write(current_user: CurrentUser, workflow_type: str) -> None:
    if not can_mutate_workflow(current_user, workflow_type):
        track = workflow_track_from_type(workflow_type)
        raise HTTPException(
            status_code=403,
            detail=f"Workflow admin access required for track={track}",
        )


def _require_seah(current_user: CurrentUser) -> None:
    """Configure-side gate for the sensitive-workflow catalog — not case access.
    DECISION-sensitive-workflows §3."""
    if not current_user.can_configure_sensitive:
        raise HTTPException(status_code=403, detail="Sensitive-workflow admin access required")


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
    if workflow_track_from_type(wf.workflow_type) == "seah" and not current_user.can_configure_sensitive:
        raise HTTPException(status_code=403, detail="Sensitive-workflow admin access required")
    return wf


# ── List / get ────────────────────────────────────────────────────────────────

@router.get("/workflows", response_model=WorkflowListResponse, summary="List workflows")
def list_workflows(
    workflow_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_template: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowListResponse:
    q = select(WorkflowDefinition).options(
        selectinload(WorkflowDefinition.steps),
        selectinload(WorkflowDefinition.assignments),
    )
    # Hide sensitive workflow definitions from admins without the configure capability
    if not current_user.can_configure_sensitive:
        q = q.where(func.lower(WorkflowDefinition.workflow_type) != "seah")
    if workflow_type:
        q = q.where(func.lower(WorkflowDefinition.workflow_type) == workflow_type.lower())
    if status:
        q = q.where(WorkflowDefinition.status == status)
    if is_template is not None:
        q = q.where(WorkflowDefinition.is_template == is_template)
    # SH-7 §S5: org-scoped catalog — a scoped org_admin sees global + own-subtree-owned only.
    q = apply_catalog_scope(q, db, current_user, WorkflowDefinition.owner_organization_id)

    workflows = db.execute(q.order_by(WorkflowDefinition.display_name)).scalars().all()
    return WorkflowListResponse(
        items=[WorkflowDefinitionResponse.model_validate(w) for w in workflows],
        total=len(workflows),
    )


@router.get("/workflows/routing-options", summary="Classifications + intake routes for project workflow editor")
def list_workflow_routing_options(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    from ticketing.constants.workflow_routing import INTAKE_ROUTE_CATALOG
    from ticketing.services.workflow_routing import list_catalog_classifications

    intake_routes = list(INTAKE_ROUTE_CATALOG)
    if not current_user.can_configure_sensitive:
        intake_routes = [r for r in intake_routes if r["key"] != "seah_intake"]
    return {
        "classifications": list_catalog_classifications(db),
        "intake_routes": intake_routes,
    }


@router.get("/workflows/templates", response_model=WorkflowListResponse, summary="List templates")
def list_templates(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowListResponse:
    """Returns built-in template definitions + admin-created templates."""
    built_ins = []
    for key, tpl in BUILT_IN_TEMPLATES.items():
        if key == "default_seah" and not current_user.can_configure_sensitive:
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
    if not current_user.can_configure_sensitive:
        q = q.where(func.lower(WorkflowDefinition.workflow_type) != "seah")
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
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowDefinitionResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    return WorkflowDefinitionResponse.model_validate(wf)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/workflows", response_model=WorkflowDefinitionResponse, status_code=201, summary="Create workflow")
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowDefinitionResponse:
    normalized_type = workflow_track_from_type(payload.workflow_type)
    _require_workflow_write(current_user, normalized_type)
    if normalized_type == "seah":
        _require_seah(current_user)

    wf_id = _new_id()
    if payload.is_template:
        wf_key = f"tpl_{_slug(payload.display_name)}_{wf_id[:8]}"
    else:
        wf_key = _slug(payload.display_name) + "_" + wf_id[:8]

    wf = WorkflowDefinition(
        workflow_id=wf_id,
        workflow_key=wf_key,
        display_name=payload.display_name,
        description=payload.description,
        workflow_type=normalized_type,
        status="published" if payload.is_template else "draft",
        version=1,
        is_template=payload.is_template,
        updated_by_user_id=current_user.user_id,
        # GRM-116 (Q-10): templates belong to an organization like workflows do — a template with
        # none could not name an organization's resolution actions. A platform admin's gets none
        # until GRM-122 lets them choose; it can then list no action and cannot be published.
        owner_organization_id=catalog_owner_for(current_user, workflow_track_from_type(normalized_type)),
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
                        "supervisor_role": s.supervisor_role,
                        "informed_roles": s.informed_roles,
                        "observer_roles": s.observer_roles,
                        "informed_pii_access": s.informed_pii_access,
                        "tier_labels": dict(s.tier_labels or {}),
                        "required_tiers": list(s.required_tiers or []),
                        "staff_per_package": bool(s.staff_per_package),
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
            supervisor_role=s.get("supervisor_role"),
            informed_roles=s.get("informed_roles") or [],
            observer_roles=s.get("observer_roles") or [],
            informed_pii_access=bool(s.get("informed_pii_access")),
            tier_labels=s.get("tier_labels") or {},
            required_tiers=s.get("required_tiers") or [],
            staff_per_package=bool(s.get("staff_per_package")),
            stakeholders=s.get("stakeholders"),
            expected_actions=s.get("expected_actions"),
        ))

    # GRM-116: a copy of a database workflow or template gets a COPY of its resolution actions —
    # never inherited, so a later change to the source does not reach it. From a built-in template or
    # from scratch it starts with none, and cannot be published until it has one.
    clone_src = (
        payload.clone_from_id
        if payload.clone_from_id and not payload.clone_from_id.startswith("__builtin_")
        and db.get(WorkflowDefinition, payload.clone_from_id)
        else None
    )
    if clone_src:
        try:
            copy_workflow_actions(db, clone_src, wf)
        except ResolutionCatalogError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    db.refresh(wf)
    return WorkflowDefinitionResponse.model_validate(wf)


# ── Update metadata ───────────────────────────────────────────────────────────

@router.patch("/workflows/{workflow_id}", response_model=WorkflowDefinitionResponse, summary="Update workflow metadata")
def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowDefinitionResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)
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
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowDefinitionResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)
    if wf.status == "archived":
        raise HTTPException(status_code=422, detail="Cannot publish an archived workflow")
    # GRM-116: only a published workflow can be bound to a project, so this is what guarantees a case
    # never meets an empty list on a non-sensitive workflow — the empty list stays the resolve form's
    # signal for a sensitive one.
    if not is_sensitive_workflow(wf) and not selected_codes(db, wf.workflow_id):
        raise HTTPException(
            status_code=422,
            detail="Add at least one resolution action before publishing.",
        )
    active_steps = [s for s in wf.steps if not s.is_deleted]
    missing = [s.display_name for s in active_steps if not s.assigned_role_key]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot publish: steps missing assigned role: {', '.join(missing)}",
        )
    # Every job at every level must be named before the workflow can be used by a project —
    # the names are what officers read, and a project cannot supply them (doc 12 §6.2).
    unnamed = [
        f"{s.display_name}: {', '.join(unnamed_jobs(s))}"
        for s in active_steps
        if unnamed_jobs(s)
    ]
    if unnamed:
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot publish: name every job at each level first — "
                + "; ".join(unnamed[:5])
            ),
        )
    # One role key may back only ONE slot in a workflow (2026-08-09). A cast assignment is
    # stored as a role_key with no step or tier beside it, so two slots sharing a key are
    # indistinguishable in the data: officers staffed into the earlier slot surface against the
    # later one, and — worse — assignment and go-live resolve by role_key, so being "kept
    # informed" at one level silently makes someone a candidate Actor at another.
    from ticketing.services.cast_staffing import duplicate_slot_keys

    dupes = duplicate_slot_keys(active_steps)
    if dupes:
        detail = "; ".join(f"{key} is used at {' and '.join(slots)}" for key, slots in sorted(dupes.items()))
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot publish: one job cannot be filled by the same role at two levels, "
                "because officers assigned to one would appear at the other. "
                f"Give each its own job: {detail}"
            ),
        )

    # SH-2: every step's role references must exist and match the workflow track —
    # publish is the full-workflow gate that also catches legacy/wrong-track bindings.
    for s in active_steps:
        validate_step_roles(
            db,
            workflow_type=wf.workflow_type,
            assigned_role_key=s.assigned_role_key,
            supervisor_role=s.supervisor_role,
            informed_roles=s.informed_roles,
            observer_roles=s.observer_roles,
        )
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
    body: SaveAsTemplateBody | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowDefinitionResponse:
    src = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, src.workflow_type)
    if src.is_template:
        raise HTTPException(status_code=422, detail="Workflow is already a template")

    tpl_name = (
        body.display_name.strip()
        if body and body.display_name and body.display_name.strip()
        else f"{src.display_name} (template)"
    )

    tpl_id = _new_id()
    tpl = WorkflowDefinition(
        workflow_id=tpl_id,
        workflow_key=f"tpl_{_slug(tpl_name)}_{tpl_id[:8]}",
        display_name=tpl_name,
        description=src.description,
        workflow_type=src.workflow_type,
        status="published",
        version=1,
        is_template=True,
        template_source_id=workflow_id,
        updated_by_user_id=current_user.user_id,
        # A template takes the workflow's organization (GRM-122's rule, needed here so its copied
        # resolution actions stay usable — an ownerless template could list none).
        owner_organization_id=src.owner_organization_id,
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
                supervisor_role=s.supervisor_role,
                informed_roles=s.informed_roles or [],
                observer_roles=s.observer_roles or [],
                informed_pii_access=s.informed_pii_access,
                tier_labels=dict(s.tier_labels or {}),
                required_tiers=list(s.required_tiers or []),
                staff_per_package=bool(s.staff_per_package),
                stakeholders=s.stakeholders, expected_actions=s.expected_actions,
            ))
    try:
        copy_workflow_actions(db, workflow_id, tpl)  # GRM-116 — a copy, never inherited
    except ResolutionCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(tpl)
    return WorkflowDefinitionResponse.model_validate(tpl)


# ── Archive ───────────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/archive", response_model=WorkflowDefinitionResponse, summary="Archive workflow")
def archive_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowDefinitionResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)
    wf.status = "archived"
    wf.updated_by_user_id = current_user.user_id
    db.commit()
    db.refresh(wf)
    return WorkflowDefinitionResponse.model_validate(wf)


@router.delete(
    "/workflows/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workflow (blocked when tickets reference it)",
)
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    if workflow_id.startswith("__builtin_"):
        raise HTTPException(status_code=403, detail="Built-in templates cannot be deleted")

    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)
    ticket_count = db.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.current_workflow_id == workflow_id)
    ) or 0
    if ticket_count:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete: {ticket_count} ticket(s) use this workflow. "
                "Archive it instead so existing cases keep their workflow."
            ),
        )
    db.delete(wf)
    db.commit()


# ── Steps ─────────────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/steps", response_model=WorkflowStepResponse, status_code=201, summary="Add step")
def add_step(
    workflow_id: str,
    payload: WorkflowStepCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowStepResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)

    tier_toggle_mode = any(
        f in payload.model_fields_set
        for f in ("supervisor_enabled", "participants_enabled", "observers_enabled")
    )

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
        assigned_role_key=payload.assigned_role_key or "",
        response_time_hours=payload.response_time_hours,
        resolution_time_days=payload.resolution_time_days,
        supervisor_role=payload.supervisor_role,
        informed_roles=payload.informed_roles or [],
        observer_roles=payload.observer_roles or [],
        informed_pii_access=payload.informed_pii_access,
        actor_can_reassign=payload.actor_can_reassign,
        tier_labels={k: v.model_dump() for k, v in (payload.tier_labels or {}).items()},
        required_tiers=list(payload.required_tiers or []),
        staff_per_package=bool(payload.staff_per_package),
        stakeholders=payload.stakeholders,
        expected_actions=payload.expected_actions,
    )
    # Tier-toggle editor (DESIGN-cast-model §3.5): derive tier fields from on/off toggles,
    # minting synthetic per-step-tier keys (+ their plumbing role rows) for enabled empty slots.
    if tier_toggle_mode:
        from ticketing.services.cast_staffing import set_step_tier_keys

        set_step_tier_keys(
            db, wf, step,
            supervisor=bool(payload.supervisor_enabled),
            participants=bool(payload.participants_enabled),
            observers=bool(payload.observers_enabled),
        )

    # SH-2: role references must exist and match the workflow track (final state).
    validate_step_roles(
        db,
        workflow_type=wf.workflow_type,
        assigned_role_key=step.assigned_role_key or None,
        supervisor_role=step.supervisor_role,
        informed_roles=step.informed_roles,
        observer_roles=step.observer_roles,
    )
    # Every enabled job carries the author's name (doc 12 §6.2). Checked on the FINAL state,
    # after the toggles above decided which jobs this level has.
    require_named_jobs(step)

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
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowStepResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)

    step = db.get(WorkflowStep, step_id)
    if not step or step.workflow_id != workflow_id or step.is_deleted:
        raise HTTPException(status_code=404, detail="Step not found")

    fields_set = payload.model_fields_set

    # SH-2: validate any role field being SET here (existing refs untouched by this
    # PATCH aren't re-checked — publish gates the whole workflow).
    validate_step_roles(
        db,
        workflow_type=wf.workflow_type,
        assigned_role_key=payload.assigned_role_key if "assigned_role_key" in fields_set else None,
        supervisor_role=payload.supervisor_role if "supervisor_role" in fields_set else None,
        informed_roles=payload.informed_roles if "informed_roles" in fields_set else None,
        observer_roles=payload.observer_roles if "observer_roles" in fields_set else None,
    )

    if "display_name" in fields_set:
        step.display_name = payload.display_name
    if "step_key" in fields_set:
        step.step_key = payload.step_key
    if "assigned_role_key" in fields_set:
        step.assigned_role_key = payload.assigned_role_key
    if "response_time_hours" in fields_set:
        step.response_time_hours = payload.response_time_hours
    if "resolution_time_days" in fields_set:
        step.resolution_time_days = payload.resolution_time_days
    if "supervisor_role" in fields_set:
        step.supervisor_role = payload.supervisor_role
    if "informed_roles" in fields_set:
        step.informed_roles = payload.informed_roles or []
    if "observer_roles" in fields_set:
        step.observer_roles = payload.observer_roles or []
    if "informed_pii_access" in fields_set:
        step.informed_pii_access = bool(payload.informed_pii_access)
    if "actor_can_reassign" in fields_set:
        step.actor_can_reassign = bool(payload.actor_can_reassign)
    if "tier_labels" in fields_set:
        step.tier_labels = {k: v.model_dump() for k, v in (payload.tier_labels or {}).items()}
    if "required_tiers" in fields_set:
        step.required_tiers = list(payload.required_tiers or [])
    if "staff_per_package" in fields_set:
        step.staff_per_package = bool(payload.staff_per_package)
    if "stakeholders" in fields_set:
        step.stakeholders = payload.stakeholders
    if "expected_actions" in fields_set:
        step.expected_actions = payload.expected_actions

    # Tier-toggle editor (DESIGN-cast-model §3.5): re-derive tier fields from on/off toggles.
    # An omitted toggle keeps the tier's current state (partial update never clobbers).
    if any(f in fields_set for f in ("supervisor_enabled", "participants_enabled", "observers_enabled")):
        from ticketing.services.cast_staffing import set_step_tier_keys

        supervisor = (
            bool(payload.supervisor_enabled) if "supervisor_enabled" in fields_set
            else step.supervisor_role is not None
        )
        participants = (
            bool(payload.participants_enabled) if "participants_enabled" in fields_set
            else bool(step.informed_roles)
        )
        observers = (
            bool(payload.observers_enabled) if "observers_enabled" in fields_set
            else bool(step.observer_roles)
        )
        set_step_tier_keys(db, wf, step, supervisor=supervisor, participants=participants, observers=observers)

    # Every enabled job carries the author's name (doc 12 §6.2) — checked on the final state,
    # so enabling a job and forgetting to name it is refused rather than silently falling back
    # to the bound role's name.
    require_named_jobs(step)

    db.commit()
    db.refresh(step)
    return WorkflowStepResponse.model_validate(step)


@router.delete("/workflows/{workflow_id}/steps/{step_id}", status_code=204, summary="Remove step (blocked if tickets active on it)")
def delete_step(
    workflow_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)

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
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> list[WorkflowStepResponse]:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)

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
    current_user: CurrentUser = Depends(get_authenticated_user),
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
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowAssignmentResponse:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)

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
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    wf = _load_workflow(workflow_id, db, current_user)
    _require_workflow_write(current_user, wf.workflow_type)
    row = db.get(WorkflowAssignment, assignment_id)
    if not row or row.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(row)
    db.commit()
