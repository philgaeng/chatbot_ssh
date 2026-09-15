# SPDX-License-Identifier: Apache-2.0

"""The resolution panel of a workflow (GRM-119): its list of actions, and creating and editing them.

Every rule lives in ``services/resolution_authoring.py`` and ``services/resolution_catalog.py``; this
router loads, maps errors to status codes, and returns the flags the panel renders. Workflow endpoints
load through ``_load_workflow`` (the sensitive-workflow gate) and ``_require_workflow_write`` (the
track) **and then** check reach on the workflow's organization — the track check alone would let any
``org_admin`` change any organization's workflow.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.routers.workflows import _load_workflow, _require_workflow_write
from ticketing.constants.resolution import MAX_RESOLUTION_ACTIONS
from ticketing.models.resolution_action import ResolutionAction
from ticketing.services.resolution_authoring import (
    ResolutionPermissionError,
    available_actions,
    can_change_list,
    can_create_national,
    can_edit_action,
    create_into_workflow,
    national_choices,
    update_action,
    used_by_counts,
)
from ticketing.services.resolution_catalog import (
    ResolutionCatalogError,
    selected_codes,
    set_workflow_actions,
)

router = APIRouter()


class ResolutionActionRow(BaseModel):
    code: str
    label: str
    default_wording: str
    counts_as_code: Optional[str] = None
    counts_as_label: Optional[str] = None
    can_edit: bool = False
    used_by_count: int = 0


class NationalChoice(BaseModel):
    code: str
    label: str


class WorkflowResolutionPanel(BaseModel):
    actions: list[ResolutionActionRow]
    can_change: bool
    max: int = MAX_RESOLUTION_ACTIONS
    national_choices: list[NationalChoice]
    can_create_national: bool
    is_sensitive: bool
    # The workflow belongs to a ministry itself: a new action is national, and no "counts as" is asked.
    owner_is_ministry: bool


class ResolutionListUpdate(BaseModel):
    codes: list[str]


class ResolutionActionCreate(BaseModel):
    label: str = Field(..., max_length=120)
    default_wording: str = Field(..., max_length=1000)
    counts_as_code: Optional[str] = Field(None, max_length=64)
    national: bool = False


class ResolutionActionUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=120)
    default_wording: Optional[str] = Field(None, max_length=1000)
    counts_as_code: Optional[str] = Field(None, max_length=64)


def _rows(db: Session, user: CurrentUser, actions: list[ResolutionAction]) -> list[ResolutionActionRow]:
    labels = {
        a.code: a.label
        for a in db.query(ResolutionAction).filter(
            ResolutionAction.code.in_({a.counts_as_code for a in actions if a.counts_as_code})
        )
    } if any(a.counts_as_code for a in actions) else {}
    counts = used_by_counts(db, [a.code for a in actions])
    return [
        ResolutionActionRow(
            code=a.code, label=a.label, default_wording=a.default_wording,
            counts_as_code=a.counts_as_code, counts_as_label=labels.get(a.counts_as_code or ""),
            can_edit=can_edit_action(db, user, a), used_by_count=counts.get(a.code, 0),
        )
        for a in actions
    ]


def _panel(db: Session, user: CurrentUser, workflow) -> WorkflowResolutionPanel:
    from ticketing.services.resolution_catalog import is_sensitive_workflow, ministry_of

    codes = selected_codes(db, workflow.workflow_id, active_only=False)
    by_code = {a.code: a for a in db.query(ResolutionAction).filter(ResolutionAction.code.in_(codes))} if codes else {}
    return WorkflowResolutionPanel(
        actions=_rows(db, user, [by_code[c] for c in codes if c in by_code]),
        can_change=can_change_list(db, user, workflow),
        national_choices=[NationalChoice(code=a.code, label=a.label) for a in national_choices(db, workflow)],
        can_create_national=can_create_national(db, user, workflow),
        is_sensitive=is_sensitive_workflow(workflow),
        owner_is_ministry=bool(workflow.owner_organization_id)
        and ministry_of(db, workflow.owner_organization_id) == workflow.owner_organization_id,
    )


def _writable_workflow(workflow_id: str, db: Session, user: CurrentUser):
    wf = _load_workflow(workflow_id, db, user)
    _require_workflow_write(user, wf.workflow_type)
    if not can_change_list(db, user, wf):
        if (wf.workflow_type or "").lower() == "seah":
            raise HTTPException(status_code=422, detail="A sensitive workflow does not record a resolution action.")
        raise HTTPException(status_code=403, detail="You can only change workflows of organizations you manage.")
    return wf


@router.get("/workflows/{workflow_id}/resolution-actions", response_model=WorkflowResolutionPanel,
            summary="A workflow's resolution actions, and what the viewer may do with them")
def get_workflow_resolution_actions(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowResolutionPanel:
    return _panel(db, current_user, _load_workflow(workflow_id, db, current_user))


@router.get("/workflows/{workflow_id}/resolution-actions/available", response_model=list[ResolutionActionRow],
            summary="Actions this workflow can use and does not already offer")
def list_available_resolution_actions(
    workflow_id: str,
    q: Optional[str] = Query(None, max_length=120),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> list[ResolutionActionRow]:
    wf = _load_workflow(workflow_id, db, current_user)
    return _rows(db, current_user, available_actions(db, wf, q))


@router.put("/workflows/{workflow_id}/resolution-actions", response_model=WorkflowResolutionPanel,
            summary="Replace a workflow's list of resolution actions (order included)")
def put_workflow_resolution_actions(
    workflow_id: str,
    payload: ResolutionListUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowResolutionPanel:
    wf = _writable_workflow(workflow_id, db, current_user)
    try:
        set_workflow_actions(db, wf, payload.codes)
    except ResolutionCatalogError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _panel(db, current_user, wf)


@router.post("/workflows/{workflow_id}/resolution-actions/new", response_model=WorkflowResolutionPanel,
             status_code=201, summary="Create a resolution action and add it to this workflow")
def create_workflow_resolution_action(
    workflow_id: str,
    payload: ResolutionActionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> WorkflowResolutionPanel:
    wf = _writable_workflow(workflow_id, db, current_user)
    try:
        create_into_workflow(
            db, current_user, wf, label=payload.label, default_wording=payload.default_wording,
            counts_as_code=payload.counts_as_code, national=payload.national,
        )
    except ResolutionPermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ResolutionCatalogError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _panel(db, current_user, wf)


@router.patch("/resolution-actions/{code}", response_model=ResolutionActionRow,
              summary="Edit a resolution action — the change applies to every workflow using it")
def patch_resolution_action(
    code: str,
    payload: ResolutionActionUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> ResolutionActionRow:
    action = db.get(ResolutionAction, code)
    if action is None:
        raise HTTPException(status_code=404, detail="Resolution action not found")
    fields = payload.model_fields_set
    try:
        update_action(
            db, current_user, action,
            label=payload.label if "label" in fields else None,
            default_wording=payload.default_wording if "default_wording" in fields else None,
            counts_as_code=payload.counts_as_code, counts_as_set="counts_as_code" in fields,
        )
    except ResolutionPermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ResolutionCatalogError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _rows(db, current_user, [action])[0]
