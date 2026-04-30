"""
Viewer (watcher) endpoints — UI_SPEC.md §2.7.

POST   /api/v1/tickets/{ticket_id}/viewers               — add viewer (senior role / assigned officer)
DELETE /api/v1/tickets/{ticket_id}/viewers/{user_id}     — remove viewer
GET    /api/v1/tickets/{ticket_id}/viewers               — list viewers
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_viewer import TicketViewer

logger = logging.getLogger(__name__)
router = APIRouter()

# Roles that may add viewers to a case (UI_SPEC.md §2.7)
VIEWER_MANAGER_ROLES = {
    "pd_piu_safeguards_focal",
    "grc_chair", "grc_member",
    "seah_national_officer", "seah_hq_officer",
    "adb_national_project_director", "adb_hq_safeguards", "adb_hq_project", "adb_hq_exec",
    "super_admin", "local_admin",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _can_manage_viewers(current_user: CurrentUser, ticket: Ticket) -> bool:
    """True if this user is allowed to add/remove viewers."""
    if current_user.is_admin:
        return True
    if ticket.assigned_to_user_id == current_user.user_id:
        return True
    return bool(set(current_user.role_keys) & VIEWER_MANAGER_ROLES)


def _viewer_to_dict(v: TicketViewer) -> dict:
    return {
        "viewer_id": v.viewer_id,
        "ticket_id": v.ticket_id,
        "user_id": v.user_id,
        "added_by_user_id": v.added_by_user_id,
        "added_at": v.added_at.isoformat(),
    }


# ── GET /tickets/{id}/viewers ─────────────────────────────────────────────────

@router.get(
    "/tickets/{ticket_id}/viewers",
    summary="List viewers (watchers) of a ticket",
)
def list_viewers(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    viewers = db.execute(
        select(TicketViewer)
        .where(TicketViewer.ticket_id == ticket_id)
        .order_by(TicketViewer.added_at)
    ).scalars().all()

    return [_viewer_to_dict(v) for v in viewers]


# ── POST /tickets/{id}/viewers — add viewer ────────────────────────────────────

class AddViewerRequest(BaseModel):
    user_id: str = Field(..., max_length=128, description="user_id of officer to add as viewer")


@router.post(
    "/tickets/{ticket_id}/viewers",
    status_code=status.HTTP_201_CREATED,
    summary="Add a viewer to a ticket (senior role / assigned officer only)",
)
def add_viewer(
    ticket_id: str,
    body: AddViewerRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    if not _can_manage_viewers(current_user, ticket):
        raise HTTPException(
            status_code=403,
            detail=(
                "Adding viewers requires a senior role (L2, GRC, SEAH, ADB, admin) "
                "or being the assigned officer."
            ),
        )

    viewer = TicketViewer(
        viewer_id=_new_id(),
        ticket_id=ticket_id,
        user_id=body.user_id,
        added_by_user_id=current_user.user_id,
    )
    db.add(viewer)

    # Audit event — renders as system pill in thread
    event = TicketEvent(
        event_id=_new_id(),
        ticket_id=ticket_id,
        event_type="VIEWER_ADDED",
        workflow_step_id=ticket.current_step_id,
        note=f"@{body.user_id} added as viewer",
        payload={"added_user_id": body.user_id, "added_by": current_user.user_id},
        seen=True,
        created_by_user_id=current_user.user_id,
        case_sensitivity="seah" if ticket.is_seah else "standard",
        summary_regen_required=False,
    )
    db.add(event)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"{body.user_id} is already a viewer of this ticket")

    db.refresh(viewer)

    logger.info(
        "Viewer added: ticket_id=%s user_id=%s added_by=%s",
        ticket_id, body.user_id, current_user.user_id,
    )
    return _viewer_to_dict(viewer)


# ── DELETE /tickets/{id}/viewers/{user_id} — remove viewer ────────────────────

@router.delete(
    "/tickets/{ticket_id}/viewers/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a viewer from a ticket",
)
def remove_viewer(
    ticket_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    if not _can_manage_viewers(current_user, ticket):
        raise HTTPException(status_code=403, detail="Insufficient permissions to remove viewers")

    viewer = db.execute(
        select(TicketViewer).where(
            TicketViewer.ticket_id == ticket_id,
            TicketViewer.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not viewer:
        raise HTTPException(status_code=404, detail="Viewer not found")

    db.delete(viewer)
    db.commit()

    logger.info("Viewer removed: ticket_id=%s user_id=%s", ticket_id, user_id)
