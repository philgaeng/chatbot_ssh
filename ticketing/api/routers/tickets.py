"""
Ticket CRUD and action endpoints.

Inbound (chatbot → ticketing):
  POST   /api/v1/tickets                      — create ticket (API key auth)

Officer UI (JWT auth — stub for proto):
  GET    /api/v1/tickets                      — list tickets (filtered)
  GET    /api/v1/tickets/{ticket_id}          — ticket detail + event history
  PATCH  /api/v1/tickets/{ticket_id}          — assign / change priority
  POST   /api/v1/tickets/{ticket_id}/actions  — acknowledge / escalate / resolve / close /
                                               note / grc_convene / grc_decide
  POST   /api/v1/tickets/{ticket_id}/reply    — send message to complainant
  POST   /api/v1/tickets/{ticket_id}/seen     — mark unseen events as read (badge)
  GET    /api/v1/tickets/{ticket_id}/sla      — SLA status for UI countdown
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db, verify_api_key
from ticketing.api.schemas.ticket import (
    TicketActionRequest,
    TicketActionResponse,
    TicketCreate,
    TicketDetail,
    TicketCreateResponse,
    TicketDetail,
    TicketListItem,
    TicketListResponse,
    TicketPatch,
    TicketReplyRequest,
    TicketReplyResponse,
)
from ticketing.clients.orchestrator import send_message_to_complainant
from ticketing.engine.escalation import convene_grc, escalate_ticket, grc_decide
from ticketing.engine.workflow_engine import get_current_step, sla_status
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowAssignment, WorkflowDefinition, WorkflowStep

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── helpers ─────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _lookup_workflow(
    db: Session,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    is_seah: bool,
    priority: str,
) -> WorkflowDefinition:
    """
    Find the best-matching workflow for this ticket.

    Lookup key for SEAH tickets: priority overridden to 'SEAH'.
    Fallback cascade: exact → (org, None, project, priority) → (org, None, None, priority)
    → (org, None, None, None) to handle sparse assignment table.
    """
    lookup_priority = "SEAH" if is_seah else priority

    for loc in ([location_code, None] if location_code else [None]):
        for proj in ([project_code, None] if project_code else [None]):
            for pri in ([lookup_priority, None]):
                assignment = db.execute(
                    select(WorkflowAssignment).where(
                        WorkflowAssignment.organization_id == organization_id,
                        WorkflowAssignment.location_code == loc,
                        WorkflowAssignment.project_code == proj,
                        WorkflowAssignment.priority == pri,
                    )
                ).scalar_one_or_none()
                if assignment:
                    workflow = db.get(WorkflowDefinition, assignment.workflow_id)
                    if workflow:
                        return workflow

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f"No workflow assignment found for org={organization_id} "
            f"location={location_code} project={project_code} "
            f"is_seah={is_seah} priority={priority}. "
            "Seed the workflow_assignments table first."
        ),
    )


def _first_step(db: Session, workflow_id: str) -> Optional[WorkflowStep]:
    return db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()


def _next_step(db: Session, workflow_id: str, current_order: int) -> Optional[WorkflowStep]:
    return db.execute(
        select(WorkflowStep)
        .where(
            WorkflowStep.workflow_id == workflow_id,
            WorkflowStep.step_order > current_order,
        )
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()


def _add_event(
    db: Session,
    ticket: Ticket,
    event_type: str,
    *,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    old_assigned: Optional[str] = None,
    new_assigned: Optional[str] = None,
    step_id: Optional[str] = None,
    note: Optional[str] = None,
    payload: Optional[dict] = None,
    created_by: Optional[str] = None,
    seen: bool = False,
    notify_user_id: Optional[str] = None,
) -> TicketEvent:
    event = TicketEvent(
        event_id=_new_id(),
        ticket_id=ticket.ticket_id,
        event_type=event_type,
        old_status_code=old_status,
        new_status_code=new_status,
        old_assigned_to=old_assigned,
        new_assigned_to=new_assigned,
        workflow_step_id=step_id,
        note=note,
        payload=payload,
        seen=seen,
        assigned_to_user_id=notify_user_id,
        created_by_user_id=created_by,
    )
    db.add(event)
    return event


# ─── POST /tickets — create (chatbot/backend) ─────────────────────────────────

@router.post(
    "/tickets",
    response_model=TicketCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket from submitted grievance",
    description="Called by chatbot backend after grievance is stored. Requires x-api-key header.",
)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> TicketCreateResponse:
    # Guard: don't create duplicate tickets for same grievance
    existing = db.execute(
        select(Ticket).where(
            Ticket.grievance_id == payload.grievance_id,
            Ticket.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if existing:
        logger.warning("Duplicate ticket request for grievance_id=%s", payload.grievance_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket already exists for grievance_id={payload.grievance_id} (ticket_id={existing.ticket_id})",
        )

    # Workflow lookup
    workflow = _lookup_workflow(
        db,
        organization_id=payload.organization_id,
        location_code=payload.location_code,
        project_code=payload.project_code,
        is_seah=payload.is_seah,
        priority=payload.priority,
    )
    first_step = _first_step(db, workflow.workflow_id)

    ticket = Ticket(
        ticket_id=_new_id(),
        grievance_id=payload.grievance_id,
        complainant_id=payload.complainant_id,
        session_id=payload.session_id,
        chatbot_id=payload.chatbot_id,
        grievance_summary=payload.grievance_summary,
        grievance_categories=payload.grievance_categories,
        grievance_location=payload.grievance_location,
        country_code=payload.country_code,
        organization_id=payload.organization_id,
        location_code=payload.location_code,
        project_code=payload.project_code,
        status_code="OPEN",
        current_workflow_id=workflow.workflow_id,
        current_step_id=first_step.step_id if first_step else None,
        priority=payload.priority,
        is_seah=payload.is_seah,
        is_deleted=False,
        sla_breached=False,
    )
    db.add(ticket)

    _add_event(
        db, ticket, "CREATED",
        new_status="OPEN",
        step_id=first_step.step_id if first_step else None,
        payload={"workflow_key": workflow.workflow_key},
        seen=True,  # creation event is not an unread notification
    )
    db.commit()
    db.refresh(ticket)

    logger.info(
        "Ticket created: ticket_id=%s grievance_id=%s workflow=%s is_seah=%s",
        ticket.ticket_id, payload.grievance_id, workflow.workflow_key, payload.is_seah,
    )
    return ticket


# ─── GET /tickets — list ──────────────────────────────────────────────────────

@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List tickets (officer queue)",
)
def list_tickets(
    my_queue: bool = Query(False, description="Only tickets assigned to current user"),
    status_code: Optional[str] = Query(None),
    is_seah: Optional[bool] = Query(None, description="Filter by SEAH flag (omit = all visible to role)"),
    organization_id: Optional[str] = Query(None),
    location_code: Optional[str] = Query(None),
    project_code: Optional[str] = Query(None),
    sla_breached: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TicketListResponse:
    q = select(Ticket).where(Ticket.is_deleted.is_(False))

    # ── SEAH visibility gate (DB-level) ──
    if not current_user.can_see_seah:
        q = q.where(Ticket.is_seah.is_(False))
    elif is_seah is not None:
        q = q.where(Ticket.is_seah.is_(is_seah))

    if my_queue:
        q = q.where(Ticket.assigned_to_user_id == current_user.user_id)
    if status_code:
        q = q.where(Ticket.status_code == status_code)
    if organization_id:
        q = q.where(Ticket.organization_id == organization_id)
    if location_code:
        q = q.where(Ticket.location_code == location_code)
    if project_code:
        q = q.where(Ticket.project_code == project_code)
    if sla_breached is not None:
        q = q.where(Ticket.sla_breached.is_(sla_breached))

    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()

    tickets = db.execute(
        q.order_by(Ticket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    # Unseen event counts per ticket for this user
    unseen_counts: dict[str, int] = {}
    if tickets:
        ticket_ids = [t.ticket_id for t in tickets]
        rows = db.execute(
            select(TicketEvent.ticket_id, func.count())
            .where(
                TicketEvent.ticket_id.in_(ticket_ids),
                TicketEvent.assigned_to_user_id == current_user.user_id,
                TicketEvent.seen.is_(False),
            )
            .group_by(TicketEvent.ticket_id)
        ).all()
        unseen_counts = {row[0]: row[1] for row in rows}

    items = []
    for t in tickets:
        item = TicketListItem(
            ticket_id=t.ticket_id,
            grievance_id=t.grievance_id,
            grievance_summary=t.grievance_summary,
            status_code=t.status_code,
            priority=t.priority,
            is_seah=t.is_seah,
            organization_id=t.organization_id,
            location_code=t.location_code,
            project_code=t.project_code,
            assigned_to_user_id=t.assigned_to_user_id,
            sla_breached=t.sla_breached,
            step_started_at=t.step_started_at,
            created_at=t.created_at,
            unseen_event_count=unseen_counts.get(t.ticket_id, 0),
        )
        items.append(item)

    return TicketListResponse(items=items, total=total, page=page, page_size=page_size)


# ─── GET /tickets/{ticket_id} — detail ───────────────────────────────────────

@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetail,
    summary="Ticket detail with event history",
)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TicketDetail:
    ticket = db.execute(
        select(Ticket)
        .options(
            joinedload(Ticket.current_step),
            joinedload(Ticket.events),
        )
        .where(Ticket.ticket_id == ticket_id, Ticket.is_deleted.is_(False))
    ).unique().scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # SEAH visibility gate
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    return ticket


# ─── PATCH /tickets/{ticket_id} — assign / priority ──────────────────────────

@router.patch(
    "/tickets/{ticket_id}",
    response_model=TicketCreateResponse,
    summary="Update ticket assignment or priority",
)
def patch_ticket(
    ticket_id: str,
    payload: TicketPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    old_assigned = ticket.assigned_to_user_id

    if payload.assign_to_user_id is not None:
        ticket.assigned_to_user_id = payload.assign_to_user_id
        ticket.assigned_role_id = payload.assigned_role_id
        ticket.updated_by_user_id = current_user.user_id

        _add_event(
            db, ticket, "ASSIGNED",
            old_assigned=old_assigned,
            new_assigned=payload.assign_to_user_id,
            created_by=current_user.user_id,
            seen=False,
            notify_user_id=payload.assign_to_user_id,
        )

    if payload.priority is not None:
        ticket.priority = payload.priority
        ticket.updated_by_user_id = current_user.user_id
        _add_event(
            db, ticket, "PRIORITY_CHANGED",
            payload={"new_priority": payload.priority},
            created_by=current_user.user_id,
            seen=True,
        )

    db.commit()
    db.refresh(ticket)
    return ticket


# ─── POST /tickets/{ticket_id}/actions — officer actions ─────────────────────

VALID_ACTIONS = {
    "ACKNOWLEDGE", "ESCALATE", "RESOLVE", "CLOSE", "NOTE",
    "GRC_CONVENE", "GRC_DECIDE",
}

@router.post(
    "/tickets/{ticket_id}/actions",
    response_model=TicketActionResponse,
    summary="Perform an officer action on a ticket",
    description=(
        "**action_type** values:\n"
        "- `ACKNOWLEDGE` — officer takes ownership, starts SLA clock\n"
        "- `ESCALATE` — manual escalation to next workflow step\n"
        "- `RESOLVE` — mark ticket resolved\n"
        "- `CLOSE` — close without resolution\n"
        "- `NOTE` — add internal officer note (invisible to complainant)\n"
        "- `GRC_CONVENE` — GRC chair schedules hearing, notifies all GRC members\n"
        "- `GRC_DECIDE` — GRC chair records decision (`payload.decision`: RESOLVED | ESCALATE_TO_LEGAL)\n"
    ),
)
def perform_action(
    ticket_id: str,
    payload: TicketActionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TicketActionResponse:
    action = payload.action_type.upper()
    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action_type={action!r}. Valid: {sorted(VALID_ACTIONS)}",
        )

    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    old_status = ticket.status_code
    event_step_id = ticket.current_step_id
    event = None

    if action == "ACKNOWLEDGE":
        ticket.status_code = "IN_PROGRESS"
        ticket.step_started_at = _now()
        ticket.updated_by_user_id = current_user.user_id
        event = _add_event(
            db, ticket, "ACKNOWLEDGED",
            old_status=old_status, new_status="IN_PROGRESS",
            step_id=event_step_id,
            note=payload.note,
            created_by=current_user.user_id,
            seen=True,
        )

    elif action == "ESCALATE":
        # Delegate to engine — single code path for manual + auto escalation
        result = escalate_ticket(
            ticket, db,
            triggered_by="MANUAL",
            note=payload.note,
            created_by_user_id=current_user.user_id,
        )
        if result is None:
            raise HTTPException(
                status_code=422,
                detail="No next step available — ticket is already at the final escalation level",
            )
        event = result

    elif action == "RESOLVE":
        ticket.status_code = "RESOLVED"
        ticket.updated_by_user_id = current_user.user_id
        event = _add_event(
            db, ticket, "RESOLVED",
            old_status=old_status, new_status="RESOLVED",
            step_id=event_step_id,
            note=payload.note,
            created_by=current_user.user_id,
            seen=True,
        )

    elif action == "CLOSE":
        ticket.status_code = "CLOSED"
        ticket.updated_by_user_id = current_user.user_id
        event = _add_event(
            db, ticket, "CLOSED",
            old_status=old_status, new_status="CLOSED",
            step_id=event_step_id,
            note=payload.note,
            created_by=current_user.user_id,
            seen=True,
        )

    elif action == "NOTE":
        if not payload.note:
            raise HTTPException(status_code=422, detail="note is required for action_type=NOTE")
        # Internal note — no status change, not visible to complainant
        event = _add_event(
            db, ticket, "NOTE_ADDED",
            step_id=event_step_id,
            note=payload.note,
            payload={"internal": True},
            created_by=current_user.user_id,
            seen=True,
        )

    elif action == "GRC_CONVENE":
        # GRC Chair schedules hearing — notifies all GRC members (unseen events → badges)
        hearing_date = (payload.grc_hearing_date if hasattr(payload, "grc_hearing_date") else None)
        events = convene_grc(
            ticket, db,
            note=payload.note,
            convened_by_user_id=current_user.user_id,
            hearing_date=hearing_date,
        )
        event = events[0]  # first event is the CONVENED event

    elif action == "GRC_DECIDE":
        decision = getattr(payload, "grc_decision", None) or "RESOLVED"
        event = grc_decide(
            ticket, db,
            decision=decision.upper(),
            note=payload.note,
            decided_by_user_id=current_user.user_id,
        )

    db.commit()
    db.refresh(ticket)

    return TicketActionResponse(
        ticket_id=ticket.ticket_id,
        action_type=action,
        new_status_code=ticket.status_code,
        current_step_id=ticket.current_step_id,
        event_id=event.event_id,
    )


# ─── POST /tickets/{ticket_id}/reply — officer → complainant ─────────────────

@router.post(
    "/tickets/{ticket_id}/reply",
    response_model=TicketReplyResponse,
    summary="Send officer reply to complainant via chatbot orchestrator",
)
def reply_to_complainant(
    ticket_id: str,
    payload: TicketReplyRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TicketReplyResponse:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    delivered = False
    detail = None

    if ticket.session_id:
        try:
            send_message_to_complainant(
                session_id=ticket.session_id,
                text=payload.text,
                chatbot_id=ticket.chatbot_id,
            )
            delivered = True
        except Exception as exc:
            logger.warning(
                "Orchestrator delivery failed for ticket_id=%s: %s", ticket_id, exc
            )
            detail = f"Orchestrator unreachable: {exc}"
            # INTEGRATION POINT: fall back to SMS via messaging_api.py
    else:
        detail = "No session_id on ticket — cannot deliver via chatbot. Use SMS fallback."
        # INTEGRATION POINT: call messaging_api.send_sms with complainant_id lookup

    event = _add_event(
        db, ticket, "REPLY_SENT",
        note=payload.text,
        payload={"delivered_via_chatbot": delivered, "sent_by": current_user.user_id},
        created_by=current_user.user_id,
        seen=True,
    )
    db.commit()

    return TicketReplyResponse(
        ticket_id=ticket.ticket_id,
        event_id=event.event_id,
        delivered=delivered,
        detail=detail,
    )


# ─── POST /tickets/{ticket_id}/seen — clear notification badge ───────────────

# ─── GET /tickets/{ticket_id}/sla — SLA countdown for UI ──────────────────────

@router.get(
    "/tickets/{ticket_id}/sla",
    summary="SLA status for ticket (deadline, remaining hours, urgency level)",
)
def get_sla(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    step = get_current_step(ticket, db)
    info = sla_status(ticket, step)
    return {
        "ticket_id": ticket_id,
        "step_key": step.step_key if step else None,
        "step_display_name": step.display_name if step else None,
        "resolution_time_days": step.resolution_time_days if step else None,
        "step_started_at": ticket.step_started_at,
        **info,
    }


# ─── POST /tickets/{ticket_id}/seen — clear notification badge ───────────────

@router.post(
    "/tickets/{ticket_id}/seen",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all unseen events for this ticket as seen (clears badge)",
)
def mark_events_seen(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db.execute(
        TicketEvent.__table__.update()
        .where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.assigned_to_user_id == current_user.user_id,
            TicketEvent.seen.is_(False),
        )
        .values(seen=True)
    )
    db.commit()


# ─── GET /tickets/{id}/files — list chatbot-uploaded attachments ──────────────

@router.get(
    "/tickets/{ticket_id}/files",
    summary="List file attachments uploaded by complainant via chatbot",
)
def list_ticket_files(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """
    Reads public.file_attachments for the grievance linked to this ticket.
    Read-only — no join, separate query per architecture rules.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    rows = db.execute(
        text(
            """
            SELECT file_id::text, file_name, file_path, file_type, file_size, upload_timestamp
            FROM public.file_attachments
            WHERE grievance_id = :grievance_id
            ORDER BY upload_timestamp
            """
        ),
        {"grievance_id": ticket.grievance_id},
    ).mappings().all()

    return [dict(r) for r in rows]


# ─── GET /files/{file_id} — stream attachment from disk ───────────────────────

@router.get(
    "/files/{file_id}",
    summary="Download a file attachment by file_id",
)
def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    """
    Streams a file from disk using the path stored in public.file_attachments.
    """
    row = db.execute(
        text(
            "SELECT file_name, file_path, file_type "
            "FROM public.file_attachments WHERE file_id = :fid"
        ),
        {"fid": file_id},
    ).mappings().one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = row["file_path"]
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not on disk")

    media_type = (
        "image/jpeg" if file_path.lower().endswith((".jpg", ".jpeg")) else
        "image/png"  if file_path.lower().endswith(".png") else
        "application/pdf" if file_path.lower().endswith(".pdf") else
        "application/octet-stream"
    )
    return FileResponse(path=file_path, filename=row["file_name"], media_type=media_type)
