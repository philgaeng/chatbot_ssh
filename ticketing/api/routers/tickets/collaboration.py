"""Queue collaboration + SLA endpoints.

  GET  /tickets/{ticket_id}/sla
  GET  /tickets/{ticket_id}/teammates
  POST /tickets/{ticket_id}/seen                     — clear notification badge
  POST /tickets/{ticket_id}/informed                 — add officer to Informed tier
  PUT  /tickets/{ticket_id}/complainant-reply-owner
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.ticket_access import require_ticket_access
from ticketing.api.schemas.ticket import (
    AddInformedRequest,
    AddInformedResponse,
    ReplyOwnerRequest,
)
from ticketing.engine.escalation import _ensure_viewer
from ticketing.engine.events import _add_event
from ticketing.engine.workflow_engine import get_current_step, get_teammates, sla_status
from ticketing.models.ticket import Ticket, TicketEvent

from ._shared import _actor_role

router = APIRouter()


@router.get(
    "/tickets/{ticket_id}/sla",
    summary="SLA status for ticket (deadline, remaining hours, urgency level)",
)
def get_sla(
    ticket_id: str,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
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


@router.get(
    "/tickets/{ticket_id}/teammates",
    summary="List officers that can be reassigned this ticket (same role + scope)",
)
def get_ticket_teammates(
    ticket_id: str,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    """
    Returns user_ids of officers in the same role + jurisdiction as the ticket's
    current step, excluding the currently assigned officer.
    Used to populate the Reassign To dropdown in the case view.
    """
    step = get_current_step(ticket, db)
    if not step:
        return {"ticket_id": ticket_id, "teammates": []}

    teammates = get_teammates(
        role_key=step.assigned_role_key,
        organization_id=ticket.organization_id,
        location_code=ticket.location_code,
        project_code=ticket.project_code,
        exclude_user_id=ticket.assigned_to_user_id,
        db=db,
        ticket_package_id=ticket.package_id,
    )
    return {"ticket_id": ticket_id, "teammates": teammates}


@router.post(
    "/tickets/{ticket_id}/seen",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all unseen events for this ticket as seen (clears badge)",
)
def mark_events_seen(
    ticket_id: str,
    _ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    # HR-02: previously had NO SEAH gate (only a ticket-exists check); the dependency
    # now enforces SEAH + scope before an officer can clear their badges on a ticket.
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


@router.post(
    "/tickets/{ticket_id}/informed",
    response_model=AddInformedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an officer to the Informed tier on this ticket",
    description=(
        "Standard tickets: any Actor at the current step can add someone to Informed.\n\n"
        "SEAH tickets: returns 403 pending supervisor approval (v2 — supervisor flow not yet implemented).\n\n"
        "The added officer gains: read access, ability to add notes, ability to execute assigned tasks. "
        "They do NOT gain workflow actions (escalate / resolve / close)."
    ),
)
def add_to_informed(
    ticket_id: str,
    payload: AddInformedRequest,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> AddInformedResponse:
    # SEAH: adding to Informed requires supervisor approval (spec 12 §1 — v2)
    if ticket.is_seah:
        raise HTTPException(
            status_code=403,
            detail=(
                "On SEAH tickets, adding someone to Informed requires supervisor approval. "
                "This flow is not yet implemented (v2). Contact your supervisor directly."
            ),
        )

    # Permission check: Actor at current step (or admin)
    if not current_user.is_admin:
        if ticket.assigned_to_user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned officer (Actor) or an admin can add to Informed.",
            )

    # Don't add self
    if payload.user_id == current_user.user_id:
        raise HTTPException(status_code=422, detail="Cannot add yourself to Informed.")

    viewer = _ensure_viewer(db, ticket_id, payload.user_id, "informed", current_user.user_id)

    event = _add_event(
        db, ticket, "TIER_CHANGED",
        step_id=ticket.current_step_id,
        note=f"Officer added to Informed tier by {current_user.user_id}.",
        payload={"user_id": payload.user_id, "from_tier": None, "to_tier": "informed", "added_by": current_user.user_id},
        seen=False,
        notify_user_id=payload.user_id,
        created_by=current_user.user_id,
        actor_role=_actor_role(current_user),
        summary_regen_required=False,
    )
    db.commit()
    db.refresh(viewer)

    return AddInformedResponse(
        ticket_id=ticket_id,
        user_id=payload.user_id,
        tier="informed",
        viewer_id=viewer.viewer_id,
        event_id=event.event_id,
    )


@router.put(
    "/tickets/{ticket_id}/complainant-reply-owner",
    summary="Reassign the complainant-reply capability to another officer",
    description=(
        "Defaults to the L1 Actor on ticket creation. "
        "Any Actor at any step can reassign this to another officer. "
        "Returns the updated ticket's complainant_reply_owner_id."
    ),
)
def update_reply_owner(
    ticket_id: str,
    payload: ReplyOwnerRequest,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    # Permission: Actor (assigned) or admin
    if not current_user.is_admin:
        if ticket.assigned_to_user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned officer (Actor) or an admin can reassign the reply owner.",
            )

    old_owner = ticket.complainant_reply_owner_id
    ticket.complainant_reply_owner_id = payload.user_id
    ticket.updated_by_user_id = current_user.user_id

    event = _add_event(
        db, ticket, "REPLY_OWNER_CHANGED",
        step_id=ticket.current_step_id,
        note=f"Complainant reply capability reassigned to {payload.user_id}.",
        payload={"old_owner": old_owner, "new_owner": payload.user_id, "changed_by": current_user.user_id},
        seen=False,
        notify_user_id=payload.user_id,
        created_by=current_user.user_id,
        actor_role=_actor_role(current_user),
        summary_regen_required=False,
    )
    db.commit()

    return {
        "ticket_id": ticket_id,
        "complainant_reply_owner_id": payload.user_id,
        "event_id": event.event_id,
    }
