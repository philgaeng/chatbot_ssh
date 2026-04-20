"""
Workflow definition endpoints — read-only for UI, admin can seed/modify via seed scripts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ticketing.api.dependencies import get_db, get_current_user, CurrentUser
from ticketing.api.schemas.workflow import WorkflowDefinitionResponse, WorkflowListResponse
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

router = APIRouter()


@router.get(
    "/workflows",
    response_model=WorkflowListResponse,
    summary="List all workflow definitions with their steps",
)
def list_workflows(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> WorkflowListResponse:
    workflows = db.execute(
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.steps))
        .order_by(WorkflowDefinition.workflow_key)
    ).scalars().all()

    return WorkflowListResponse(
        items=[WorkflowDefinitionResponse.model_validate(w) for w in workflows],
        total=len(workflows),
    )


@router.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowDefinitionResponse,
    summary="Get a single workflow definition with steps",
)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> WorkflowDefinitionResponse:
    workflow = db.execute(
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.steps))
        .where(WorkflowDefinition.workflow_id == workflow_id)
    ).scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowDefinitionResponse.model_validate(workflow)
