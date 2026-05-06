"""
Task assignment endpoints — in-thread coordination for the mobile UI.

POST   /api/v1/tickets/{ticket_id}/tasks               — assign a task
POST   /api/v1/tickets/{ticket_id}/tasks/{task_id}/complete — mark done
GET    /api/v1/tickets/{ticket_id}/tasks               — list tasks for a ticket
GET    /api/v1/users/me/tasks                          — all pending tasks for the current officer
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_task import TicketTask

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_TASK_TYPES = {"SITE_VISIT", "FOLLOW_UP_CALL", "SYSTEM_NOTE", "DOCUMENT_PHOTO", "ESCALATION_REVIEW"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _task_to_dict(task: TicketTask) -> dict:
    return {
        "task_id": task.task_id,
        "ticket_id": task.ticket_id,
        "task_type": task.task_type,
        "assigned_to_user_id": task.assigned_to_user_id,
        "assigned_by_user_id": task.assigned_by_user_id,
        "description": task.description,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "completed_by_user_id": task.completed_by_user_id,
        "created_at": task.created_at.isoformat(),
    }


def _add_task_event(
    db: Session,
    ticket: Ticket,
    event_type: str,
    task: TicketTask,
    created_by: str,
    note: Optional[str] = None,
) -> TicketEvent:
    """Create a TASK_ASSIGNED or TASK_COMPLETED event that renders as a task card in the thread."""
    event = TicketEvent(
        event_id=_new_id(),
        ticket_id=ticket.ticket_id,
        event_type=event_type,
        workflow_step_id=ticket.current_step_id,
        note=note,
        payload={
            "task_id": task.task_id,
            "task_type": task.task_type,
            "assigned_to_user_id": task.assigned_to_user_id,
            "assigned_by_user_id": task.assigned_by_user_id,
            "description": task.description,
            "due_date": task.due_date.isoformat() if task.due_date else None,
        },
        seen=False,
        assigned_to_user_id=task.assigned_to_user_id,  # drives unread badge for assignee
        created_by_user_id=created_by,
        actor_role=None,  # set by caller if needed
        case_sensitivity="seah" if ticket.is_seah else "standard",
        summary_regen_required=False,  # task assignment doesn't change narrative
    )
    db.add(event)
    return event


# ── POST /tickets/{id}/tasks — assign a task ──────────────────────────────────

class TaskCreateRequest(BaseModel):
    task_type: str = Field(..., description="SITE_VISIT | FOLLOW_UP_CALL | SYSTEM_NOTE | DOCUMENT_PHOTO")
    assigned_to_user_id: str = Field(..., max_length=128)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[str] = Field(None, description="ISO date string YYYY-MM-DD")


@router.post(
    "/tickets/{ticket_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    summary="Assign a task to an officer in the ticket thread",
)
def create_task(
    ticket_id: str,
    body: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    task_type = body.task_type.upper()
    if task_type not in VALID_TASK_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid task_type={task_type!r}. Valid: {sorted(VALID_TASK_TYPES)}",
        )

    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    due: Optional[date] = None
    if body.due_date:
        try:
            due = date.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="due_date must be YYYY-MM-DD")

    task = TicketTask(
        task_id=_new_id(),
        ticket_id=ticket_id,
        task_type=task_type,
        assigned_to_user_id=body.assigned_to_user_id,
        assigned_by_user_id=current_user.user_id,
        description=body.description,
        due_date=due,
        status="PENDING",
    )
    db.add(task)

    _add_task_event(
        db, ticket, "TASK_ASSIGNED", task,
        created_by=current_user.user_id,
        note=f"Task assigned: {task_type.replace('_', ' ').title()} → {body.assigned_to_user_id}",
    )

    db.commit()
    db.refresh(task)

    logger.info(
        "Task assigned: task_id=%s ticket_id=%s type=%s to=%s by=%s",
        task.task_id, ticket_id, task_type, body.assigned_to_user_id, current_user.user_id,
    )
    return _task_to_dict(task)


# ── POST /tickets/{id}/tasks/{task_id}/complete — mark done ───────────────────

@router.post(
    "/tickets/{ticket_id}/tasks/{task_id}/complete",
    summary="Mark a task as completed (assigned officer or admin)",
)
def complete_task(
    ticket_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    task = db.get(TicketTask, task_id)
    if not task or task.ticket_id != ticket_id:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "PENDING":
        raise HTTPException(status_code=422, detail=f"Task is already {task.status}")

    # Only the assigned officer or an admin may complete the task
    if not current_user.is_admin and task.assigned_to_user_id != current_user.user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned officer can complete this task.",
        )

    task.status = "DONE"
    task.completed_at = _now()
    task.completed_by_user_id = current_user.user_id

    _add_task_event(
        db, ticket, "TASK_COMPLETED", task,
        created_by=current_user.user_id,
        note=f"Task completed: {task.task_type.replace('_', ' ').title()}",
    )

    db.commit()
    db.refresh(task)

    logger.info(
        "Task completed: task_id=%s ticket_id=%s by=%s",
        task_id, ticket_id, current_user.user_id,
    )
    return _task_to_dict(task)


# ── GET /tickets/{id}/tasks — list tasks for a ticket ────────────────────────

@router.get(
    "/tickets/{ticket_id}/tasks",
    summary="List all tasks for a ticket",
)
def list_ticket_tasks(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    tasks = db.execute(
        select(TicketTask)
        .where(TicketTask.ticket_id == ticket_id)
        .order_by(TicketTask.created_at)
    ).scalars().all()

    return [_task_to_dict(t) for t in tasks]


# ── GET /users/me/tasks — all pending tasks for current officer ───────────────

@router.get(
    "/users/me/tasks",
    summary="All pending tasks assigned to the current officer (across tickets)",
)
def list_my_tasks(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    tasks = db.execute(
        select(TicketTask)
        .where(
            TicketTask.assigned_to_user_id == current_user.user_id,
            TicketTask.status == "PENDING",
        )
        .order_by(TicketTask.due_date.asc().nulls_last(), TicketTask.created_at)
    ).scalars().all()

    return [_task_to_dict(t) for t in tasks]
