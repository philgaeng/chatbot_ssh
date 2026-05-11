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
import re
from datetime import datetime, timezone
from typing import Optional
import uuid

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select, text
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
    ComplainantPatch,
    ComplainantPatchResponse,
    InboundMessageRequest,
    InboundMessageResponse,
    AddInformedRequest,
    AddInformedResponse,
    ReplyOwnerRequest,
)
from ticketing.clients.grievance_api import patch_complainant
from ticketing.clients.orchestrator import send_message_to_complainant
from ticketing.engine.escalation import (
    convene_grc, escalate_ticket, grc_decide,
    _apply_step_tier_roles, _ensure_viewer,
)
from ticketing.tasks.notifications import notify_complainant
from ticketing.tasks.llm import generate_findings, translate_note
from ticketing.engine.workflow_engine import auto_assign_officer, get_current_step, get_teammates, sla_status
from ticketing.models.country import Location
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_file import TicketFile
from ticketing.models.ticket_task import TicketTask
from ticketing.models.ticket_viewer import TicketViewer
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


def _actor_role(current_user: CurrentUser) -> Optional[str]:
    """Snapshot the first role key at write time for audit correlation."""
    return current_user.role_keys[0] if getattr(current_user, "role_keys", None) else None


def _extract_mentions(text: str) -> list[str]:
    """Return list of @mention targets from note text (e.g. ['piu-l2', 'all'])."""
    return re.findall(r"@([\w][\w.-]*)", text)


def _is_viewer(db: "Session", ticket_id: str, user_id: str) -> bool:
    """True if this user is a viewer of the ticket."""
    return db.execute(
        select(TicketViewer).where(
            TicketViewer.ticket_id == ticket_id,
            TicketViewer.user_id == user_id,
        )
    ).scalar_one_or_none() is not None


def _get_viewer_ids(db: "Session", ticket_id: str) -> list[str]:
    """Return list of all viewer user_ids for a ticket."""
    viewers = db.execute(
        select(TicketViewer).where(TicketViewer.ticket_id == ticket_id)
    ).scalars().all()
    return [v.user_id for v in viewers]



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
    # ── SEAH audit fields (seah-privacy-worktree-handoff.md) ──
    actor_role: Optional[str] = None,
    case_sensitivity: Optional[str] = None,   # derived from ticket when None
    summary_regen_required: bool = False,
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
        actor_role=actor_role,
        case_sensitivity=case_sensitivity if case_sensitivity is not None else ("seah" if ticket.is_seah else "standard"),
        summary_regen_required=summary_regen_required,
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

    # Auto-assign to least-loaded officer for the first workflow step
    auto_assigned_id: Optional[str] = None
    if first_step:
        auto_assigned_id = auto_assign_officer(
            role_key=first_step.assigned_role_key,
            organization_id=payload.organization_id,
            location_code=payload.location_code,
            project_code=payload.project_code,
            db=db,
        )

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
        assigned_to_user_id=auto_assigned_id,
        # Spec 12: reply-to-complainant capability defaults to the L1 actor
        complainant_reply_owner_id=auto_assigned_id,
        priority=payload.priority,
        is_seah=payload.is_seah,
        package_id=payload.package_id,
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
        # No summary to regenerate at creation; actor is the inbound chatbot/API key
        summary_regen_required=False,
    )

    # Spec 12: seed Informed + Observer tiers from the first step's role configuration
    if first_step:
        _apply_step_tier_roles(db, ticket, first_step)

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
    tab: Optional[str] = Query(
        None,
        description=(
            "Role-tier tab filter. "
            "actor = tickets I am the action owner of (or have a pending task on); "
            "supervisor | informed | observer = tickets where I have that viewer tier; "
            "high_priority = HIGH/CRITICAL priority or SLA-breached tickets; "
            "omit for all visible tickets."
        ),
    ),
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

    # ── Scope filter: non-admins only see tickets in their jurisdictions ──
    # Admins (super_admin, local_admin) and observers see all; field officers are scoped.
    # Viewers also see their watched tickets regardless of scope.
    if not current_user.is_admin:
        scopes = db.execute(
            select(OfficerScope).where(OfficerScope.user_id == current_user.user_id)
        ).scalars().all()

        # Tickets this user is a viewer of — always visible regardless of scope
        viewed_ticket_ids = db.execute(
            select(TicketViewer.ticket_id).where(TicketViewer.user_id == current_user.user_id)
        ).scalars().all()

        if not scopes:
            # No scope rows → only assigned tickets OR watched tickets
            q = q.where(or_(
                Ticket.assigned_to_user_id == current_user.user_id,
                Ticket.ticket_id.in_(viewed_ticket_ids),
            ))
        else:
            scope_conditions = []
            for scope in scopes:
                parts: list = [Ticket.organization_id == scope.organization_id]
                if scope.location_code:
                    # Hierarchical match: exact location OR any direct child location
                    # (e.g. province-scope NP_P1 matches district-level ticket NP_D006
                    #  because NP_D006.parent_location_code = NP_P1)
                    child_locs = select(Location.location_code).where(
                        Location.parent_location_code == scope.location_code
                    )
                    parts.append(or_(
                        Ticket.location_code == scope.location_code,
                        Ticket.location_code.in_(child_locs),
                    ))
                if scope.project_code:
                    parts.append(Ticket.project_code == scope.project_code)
                scope_conditions.append(and_(*parts))
            # Also include viewed tickets outside the normal scope
            if viewed_ticket_ids:
                scope_conditions.append(Ticket.ticket_id.in_(viewed_ticket_ids))
            q = q.where(or_(*scope_conditions))

    if tab:
        tab_lower = tab.lower()
        if tab_lower == "actor":
            # Actor = tickets where I am the action owner OR have a pending task
            pending_task_ticket_ids = select(TicketTask.ticket_id).where(
                TicketTask.assigned_to_user_id == current_user.user_id,
                TicketTask.status == "PENDING",
            )
            q = q.where(or_(
                Ticket.assigned_to_user_id == current_user.user_id,
                Ticket.ticket_id.in_(pending_task_ticket_ids),
            ))
        elif tab_lower in ("supervisor", "informed", "observer"):
            # Tier tabs: only tickets where I have a viewer row with that tier
            tier_ticket_ids = select(TicketViewer.ticket_id).where(
                TicketViewer.user_id == current_user.user_id,
                TicketViewer.tier == tab_lower,
            )
            q = q.where(Ticket.ticket_id.in_(tier_ticket_ids))
        elif tab_lower == "high_priority":
            q = q.where(or_(
                Ticket.priority.in_(["HIGH", "CRITICAL"]),
                Ticket.sla_breached.is_(True),
            ))
        # tab="all" or unrecognised: no additional filter

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

    ticket_ids = [t.ticket_id for t in tickets]

    # Unseen event counts per ticket for this user
    unseen_counts: dict[str, int] = {}
    if ticket_ids:
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

    # SLA deadline: step_started_at + step.resolution_time_days per ticket
    # Single bulk query — no N+1
    from datetime import timedelta
    step_ids = list({t.current_step_id for t in tickets if t.current_step_id})
    step_map: dict[str, WorkflowStep] = {}
    if step_ids:
        step_rows = db.execute(
            select(WorkflowStep).where(WorkflowStep.step_id.in_(step_ids))
        ).scalars().all()
        step_map = {s.step_id: s for s in step_rows}

    sla_deadlines: dict[str, Optional[datetime]] = {}
    for t in tickets:
        step = step_map.get(t.current_step_id) if t.current_step_id else None
        # Mirror compute_sla_deadline(): use step_started_at, fall back to created_at
        # so unacknowledged tickets still show an SLA countdown from submission date.
        clock_start = t.step_started_at or t.created_at
        if step and clock_start and step.resolution_time_days:
            sla_deadlines[t.ticket_id] = clock_start + timedelta(days=step.resolution_time_days)
        else:
            sla_deadlines[t.ticket_id] = None

    # Earliest pending task due date per ticket assigned to the current user
    # Single bulk query — no N+1
    earliest_task_due: dict[str, Optional[datetime]] = {}
    if ticket_ids:
        task_rows = db.execute(
            select(TicketTask.ticket_id, func.min(TicketTask.due_date))
            .where(
                TicketTask.ticket_id.in_(ticket_ids),
                TicketTask.assigned_to_user_id == current_user.user_id,
                TicketTask.status == "PENDING",
                TicketTask.due_date.is_not(None),
            )
            .group_by(TicketTask.ticket_id)
        ).all()
        earliest_task_due = {row[0]: row[1] for row in task_rows}

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
            sla_deadline_at=sla_deadlines.get(t.ticket_id),
            my_earliest_task_due_at=earliest_task_due.get(t.ticket_id),
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

    # Viewer access — allow through even if not in normal scope
    # (scope enforcement happens at list level; detail allows any authenticated viewer)
    # Admins, assigned officer, and viewers all have access. Others with no scope
    # record for this ticket are rejected.
    if not current_user.is_admin:
        if (
            ticket.assigned_to_user_id != current_user.user_id
            and not _is_viewer(db, ticket_id, current_user.user_id)
        ):
            # Task-holder check: officer with a pending task on this ticket always gets access
            # (task assignment grants implicit read access so the officer can work the task)
            has_pending_task = db.execute(
                select(TicketTask).where(
                    TicketTask.ticket_id == ticket_id,
                    TicketTask.assigned_to_user_id == current_user.user_id,
                    TicketTask.status == "PENDING",
                ).limit(1)
            ).scalar_one_or_none() is not None

            if not has_pending_task:
                # Fall back to scope check — mirrors the hierarchical list-endpoint logic:
                # a province-scoped officer (NP_P1) can access district-level tickets (NP_D006).
                from ticketing.models.officer_scope import OfficerScope as _OfficerScope
                scopes = db.execute(
                    select(_OfficerScope).where(_OfficerScope.user_id == current_user.user_id)
                ).scalars().all()

                # Pre-fetch child locations for any scope that has a location_code
                in_scope = False
                for s in scopes:
                    if s.organization_id != ticket.organization_id:
                        continue
                    if s.project_code and s.project_code != ticket.project_code:
                        continue
                    # Exact location match or no location restriction
                    if s.location_code is None or s.location_code == ticket.location_code:
                        in_scope = True
                        break
                    # Hierarchical match: scope covers a parent location
                    child_loc_codes = db.execute(
                        select(Location.location_code).where(
                            Location.parent_location_code == s.location_code
                        )
                    ).scalars().all()
                    if ticket.location_code in child_loc_codes:
                        in_scope = True
                        break

                if not in_scope:
                    raise HTTPException(status_code=403, detail="Access denied")

    # Attach viewer list (used by @mention autocomplete on the client)
    viewers = db.execute(
        select(TicketViewer).where(TicketViewer.ticket_id == ticket_id)
        .order_by(TicketViewer.added_at)
    ).scalars().all()
    # Attach as a synthetic attribute so the Pydantic schema can pick it up
    ticket.__dict__["viewers"] = [
        {
            "viewer_id": v.viewer_id,
            "user_id": v.user_id,
            "added_by_user_id": v.added_by_user_id,
            "added_at": v.added_at.isoformat(),
            "tier": v.tier,
        }
        for v in viewers
    ]

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
            actor_role=_actor_role(current_user),
            summary_regen_required=False,
        )

    if payload.priority is not None:
        ticket.priority = payload.priority
        ticket.updated_by_user_id = current_user.user_id
        _add_event(
            db, ticket, "PRIORITY_CHANGED",
            payload={"new_priority": payload.priority},
            created_by=current_user.user_id,
            seen=True,
            actor_role=_actor_role(current_user),
            summary_regen_required=False,
        )

    db.commit()
    db.refresh(ticket)
    return ticket


# ─── PATCH /tickets/{ticket_id}/complainant — edit complainant info ───────────

# Roles that may edit complainant info (assigned officer + managers).
_COMPLAINANT_EDIT_ROLES = {
    "site_safeguards_focal_person", "pd_piu_safeguards_focal",
    "seah_national_officer", "seah_hq_officer",
    "super_admin", "local_admin",
}


@router.patch(
    "/tickets/{ticket_id}/complainant",
    response_model=ComplainantPatchResponse,
    summary="Update whitelisted complainant fields",
    description=(
        "Proxies the update to the local chatbot backend "
        "(`ticketing.projects.chatbot_base_url`). "
        "Identity fields (full_name, phone) are never writable from ticketing. "
        "Requires assigned officer or manager role."
    ),
)
def patch_ticket_complainant(
    ticket_id: str,
    payload: ComplainantPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ComplainantPatchResponse:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    # Role check: assigned officer OR a manager role
    is_assigned = ticket.assigned_to_user_id == current_user.user_id
    is_manager  = current_user.role in _COMPLAINANT_EDIT_ROLES
    if not (is_assigned or is_manager):
        raise HTTPException(status_code=403, detail="Only the assigned officer or a manager can edit complainant info")

    if not ticket.complainant_id:
        raise HTTPException(status_code=422, detail="Ticket has no linked complainant_id")

    fields = payload.non_null_fields()
    if not fields:
        raise HTTPException(status_code=422, detail="No fields provided to update")

    # Resolve the chatbot URL for this project (multi-country support)
    chatbot_url: str | None = None
    if ticket.project_code:
        project = db.execute(
            select(Project).where(Project.short_code == ticket.project_code)
        ).scalar_one_or_none()
        if project:
            chatbot_url = project.chatbot_base_url  # None → settings fallback

    # Proxy to chatbot backend — raises httpx.HTTPError on non-recoverable failures
    try:
        result = patch_complainant(
            complainant_id=ticket.complainant_id,
            fields=fields,
            chatbot_base_url=chatbot_url,
        )
    except Exception as exc:
        logger.error("complainant patch failed: ticket=%s error=%s", ticket_id, exc)
        raise HTTPException(status_code=502, detail=f"Chatbot backend unavailable: {exc}")

    # Audit trail: log which fields were changed (no values — PII must not enter ticketing events)
    updated_fields = result.get("updated_fields", list(fields.keys()))
    event = _add_event(
        db, ticket, "COMPLAINANT_UPDATED",
        payload={"fields_changed": updated_fields, "proto_mode": result.get("_proto_mode", False)},
        created_by=current_user.user_id,
        seen=True,
        actor_role=_actor_role(current_user),
        summary_regen_required=False,
    )
    db.commit()

    return ComplainantPatchResponse(
        ticket_id=ticket_id,
        complainant_id=ticket.complainant_id,
        fields_updated=updated_fields,
        event_id=event.event_id,
    )


# ─── POST /tickets/{ticket_id}/actions — officer actions ─────────────────────

VALID_ACTIONS = {
    "ACKNOWLEDGE", "ESCALATE", "RESOLVE", "CLOSE", "NOTE", "FIELD_REPORT",
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

    # Assignment guard — only the assigned officer (or admin) may change ticket status.
    # NOTE is always allowed so any officer can add internal notes.
    ASSIGNMENT_REQUIRED = {"ACKNOWLEDGE", "ESCALATE", "RESOLVE", "CLOSE", "GRC_CONVENE", "GRC_DECIDE"}
    if action in ASSIGNMENT_REQUIRED and not current_user.is_admin:
        if ticket.assigned_to_user_id and ticket.assigned_to_user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Only the assigned officer ({ticket.assigned_to_user_id}) "
                    "can change the status of this ticket. You can still add notes."
                ),
            )

    # Status guard — once ESCALATED only ACKNOWLEDGE or NOTE are allowed until
    # the next-level officer acknowledges and takes ownership.
    ESCALATED_BLOCKED = {"ESCALATE", "RESOLVE", "CLOSE", "GRC_CONVENE", "GRC_DECIDE"}
    if ticket.status_code == "ESCALATED" and action in ESCALATED_BLOCKED:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot perform {action!r} on an ESCALATED ticket. "
                "Acknowledge the ticket first to take ownership at the new level."
            ),
        )

    old_status = ticket.status_code
    event_step_id = ticket.current_step_id
    event = None
    _notify_complainant_text: Optional[str] = None  # set below to trigger async notification
    _translate_note_event_id: Optional[str] = None  # set for NOTE action → translate_note task
    _generate_findings: bool = False                 # set for RESOLVE → generate_findings task

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
            actor_role=_actor_role(current_user),
            summary_regen_required=True,
        )

    elif action == "ESCALATE":
        # Delegate to engine — single code path for manual + auto escalation
        result = escalate_ticket(
            ticket, db,
            triggered_by="MANUAL",
            note=payload.note,
            created_by_user_id=current_user.user_id,
            actor_role=_actor_role(current_user),
        )
        if result is None:
            raise HTTPException(
                status_code=422,
                detail="No next step available — ticket is already at the final escalation level",
            )
        event = result
        _notify_complainant_text = (
            "Your grievance is being reviewed at the next level. "
            "We will continue to keep you updated."
        )

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
            actor_role=_actor_role(current_user),
            summary_regen_required=True,
        )
        _notify_complainant_text = (
            "Your grievance has been resolved. "
            "Thank you for bringing this to our attention."
        )
        # Fire findings generation after commit (7b — AI summary for supervisors/GRC)
        _generate_findings = True

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
            actor_role=_actor_role(current_user),
            summary_regen_required=True,
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
            actor_role=_actor_role(current_user),
            summary_regen_required=True,
        )
        # Fire translation task after commit (7a — translate note to English for supervisors)
        _translate_note_event_id = event.event_id

        # ── @mention notifications (UI_SPEC.md §2.8) ──────────────────────────
        # Parse @mentions and create lightweight MENTION notification events.
        # These events have seen=False (drive badge) but are NOT rendered in the thread.
        mentions = _extract_mentions(payload.note)
        if mentions:
            viewer_ids = _get_viewer_ids(db, ticket_id)
            assigned_id = ticket.assigned_to_user_id
            all_participant_ids = list({*viewer_ids, *([assigned_id] if assigned_id else [])})

            notify_set: set[str] = set()
            for mention in mentions:
                if mention.lower() == "all":
                    notify_set.update(all_participant_ids)
                elif mention != current_user.user_id:
                    notify_set.add(mention)

            for target_uid in notify_set:
                _add_event(
                    db, ticket, "MENTION",
                    step_id=event_step_id,
                    note=f"@mentioned by {current_user.user_id}",
                    payload={"mentioned_by": current_user.user_id, "source_event_id": event.event_id},
                    seen=False,
                    notify_user_id=target_uid,
                    created_by=current_user.user_id,
                    actor_role=_actor_role(current_user),
                    summary_regen_required=False,
                )

    elif action == "FIELD_REPORT":
        if not payload.note:
            raise HTTPException(status_code=422, detail="note is required for action_type=FIELD_REPORT")
        # Officer field report — structured finding, no status change, not visible to complainant.
        # Stored as NOTE_ADDED with is_field_report=True so the UI can render it distinctly
        # and the AI findings pipeline picks it up (NOTE_ADDED is already in _FINDINGS_EVENT_TYPES).
        event = _add_event(
            db, ticket, "NOTE_ADDED",
            step_id=event_step_id,
            note=payload.note,
            payload={"internal": True, "is_field_report": True},
            created_by=current_user.user_id,
            seen=True,
            actor_role=_actor_role(current_user),
            summary_regen_required=True,
        )
        _translate_note_event_id = event.event_id

    elif action == "GRC_CONVENE":
        # GRC Chair schedules hearing — notifies all GRC members (unseen events → badges)
        hearing_date = (payload.grc_hearing_date if hasattr(payload, "grc_hearing_date") else None)
        events = convene_grc(
            ticket, db,
            note=payload.note,
            convened_by_user_id=current_user.user_id,
            hearing_date=hearing_date,
            actor_role=_actor_role(current_user),
        )
        event = events[0]  # first event is the CONVENED event

    elif action == "GRC_DECIDE":
        decision = getattr(payload, "grc_decision", None) or "RESOLVED"
        event = grc_decide(
            ticket, db,
            decision=decision.upper(),
            note=payload.note,
            decided_by_user_id=current_user.user_id,
            actor_role=_actor_role(current_user),
        )

    db.commit()
    db.refresh(ticket)

    # Fire async complainant notification after commit so the task sees the updated ticket
    if _notify_complainant_text:
        notify_complainant.delay(
            ticket.ticket_id,
            _notify_complainant_text,
            action,  # event_type label in the notification log
        )

    # Fire LLM translation task for NOTE events (7a — translate to English for supervisors)
    if _translate_note_event_id:
        translate_note.delay(_translate_note_event_id)

    # Fire findings generation on RESOLVE (7b — AI summary for GRC/supervisors)
    if _generate_findings:
        generate_findings.delay(ticket.ticket_id)

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

    # Only the assigned officer (or admin) may reply to the complainant.
    if not current_user.is_admin:
        if ticket.assigned_to_user_id and ticket.assigned_to_user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned officer can reply to the complainant.",
            )

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
        actor_role=_actor_role(current_user),
        summary_regen_required=False,
    )
    db.commit()

    return TicketReplyResponse(
        ticket_id=ticket.ticket_id,
        event_id=event.event_id,
        delivered=delivered,
        detail=detail,
    )


# ─── POST /tickets/{ticket_id}/inbound — complainant follow-up via chatbot ───

# Intents that warrant a new event on the ticket (officer action / badge)
_INBOUND_EVENT_INTENTS = {"ADDITIONAL_INFO", "AMENDMENT", "WITHDRAW_REQUEST", "OTHER"}
# Intents that trigger LLM summary regen (new substantive case content)
_INBOUND_REGEN_INTENTS = {"ADDITIONAL_INFO", "AMENDMENT", "OTHER"}

@router.post(
    "/tickets/{ticket_id}/inbound",
    response_model=InboundMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive inbound complainant message from chatbot",
    description=(
        "Called by chatbot backend when a complainant sends a follow-up message on an "
        "active ticket. Requires x-api-key header.\n\n"
        "- **STATUS_CHECK**: no event created — returns current status for the chatbot to relay.\n"
        "- **ADDITIONAL_INFO / AMENDMENT / OTHER**: creates COMPLAINANT_MESSAGE event, "
        "sets unseen badge on assigned officer, fires translation task if non-English.\n"
        "- **WITHDRAW_REQUEST**: same as above but officer decides — no auto-close.\n\n"
        "# INTEGRATION POINT\n"
        "Chatbot must look up ticket_id from session_id before calling this endpoint.\n"
        "Lookup: `GET /api/v1/tickets?session_id={session_id}` (add this query param "
        "to the list endpoint, or store ticket_id on the chatbot session at creation time)."
    ),
)
def inbound_complainant_message(
    ticket_id: str,
    payload: InboundMessageRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> InboundMessageResponse:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")

    step_display = ticket.current_step.display_name if ticket.current_step else None

    # STATUS_CHECK: no event — chatbot reads status and auto-replies to complainant
    if payload.intent == "STATUS_CHECK":
        logger.info(
            "inbound STATUS_CHECK ticket_id=%s status=%s", ticket_id, ticket.status_code
        )
        return InboundMessageResponse(
            ticket_id=ticket_id,
            event_id=None,
            status="skipped_status_check",
            ticket_status=ticket.status_code,
            current_step=step_display,
        )

    # All other intents: create event + badge for assigned officer
    intent = payload.intent.upper()
    if intent not in _INBOUND_EVENT_INTENTS:
        intent = "OTHER"

    event = _add_event(
        db, ticket, "COMPLAINANT_MESSAGE",
        step_id=ticket.current_step_id,
        note=payload.message,
        payload={
            "intent": intent,
            "channel": payload.channel,
            "from_complainant": True,
            **({"session_id": payload.session_id} if payload.session_id else {}),
        },
        seen=False,
        notify_user_id=ticket.assigned_to_user_id,
        created_by=None,        # complainant has no officer user_id
        actor_role="complainant",
        summary_regen_required=(intent in _INBOUND_REGEN_INTENTS),
    )

    db.commit()

    # Fire translation if message looks non-English (translate_note handles skip-if-English)
    translate_note.delay(event.event_id)

    logger.info(
        "inbound_complainant_message: ticket_id=%s intent=%s event_id=%s",
        ticket_id, intent, event.event_id,
    )
    return InboundMessageResponse(
        ticket_id=ticket_id,
        event_id=event.event_id,
        status="received",
        ticket_status=ticket.status_code,
        current_step=step_display,
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


# ─── GET /tickets/{ticket_id}/teammates — reassign dropdown ──────────────────

@router.get(
    "/tickets/{ticket_id}/teammates",
    summary="List officers that can be reassigned this ticket (same role + scope)",
)
def get_ticket_teammates(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Returns user_ids of officers in the same role + jurisdiction as the ticket's
    current step, excluding the currently assigned officer.
    Used to populate the Reassign To dropdown in the case view.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

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
    )
    return {"ticket_id": ticket_id, "teammates": teammates}


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


# ─── POST /tickets/{ticket_id}/informed — add officer to Informed tier ────────

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
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AddInformedResponse:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

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


# ─── PUT /tickets/{ticket_id}/complainant-reply-owner ─────────────────────────

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
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

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

    try:
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
    except Exception as exc:
        # public.file_attachments may not exist in dev/test environments that
        # only run the ticketing stack without the full chatbot DB.  Return an
        # empty list so the UI degrades gracefully instead of crashing.
        logger.warning("list_ticket_files: public.file_attachments unavailable — %s", exc)
        db.rollback()  # clear the aborted transaction so the session stays usable
        return []


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


# ─── POST /tickets/{ticket_id}/attachments — officer file upload ──────────────

@router.post(
    "/tickets/{ticket_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file attachment as an officer (with optional caption)",
)
async def upload_officer_attachment(
    ticket_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    # Save file to uploads/ticketing/{ticket_id}/
    upload_dir = Path("uploads") / "ticketing" / ticket_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = _new_id()
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix or ""
    dest = upload_dir / f"{file_id}{suffix}"

    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    file_size = dest.stat().st_size
    # Derive a simple file_type category from MIME or extension
    mime = file.content_type or ""
    if mime.startswith("image/"):
        file_type = "image"
    elif mime == "application/pdf" or suffix.lower() == ".pdf":
        file_type = "pdf"
    else:
        file_type = "document"

    tf = TicketFile(
        file_id=file_id,
        ticket_id=ticket_id,
        file_name=original_name,
        file_path=str(dest),
        file_type=file_type,
        file_size=file_size,
        caption=caption.strip() or None,
        uploaded_by_user_id=current_user.user_id,
    )
    db.add(tf)

    # Add an internal note event so the upload appears in the case timeline
    note_text = f"📎 Attached: {original_name}"
    if caption.strip():
        note_text += f" — {caption.strip()}"
    _add_event(
        db, ticket, "NOTE_ADDED",
        step_id=ticket.current_step_id,
        note=note_text,
        payload={"file_id": file_id, "internal": True},
        created_by=current_user.user_id,
        seen=True,
        actor_role=_actor_role(current_user),
        summary_regen_required=True,
    )

    db.commit()
    db.refresh(tf)

    return {
        "file_id": tf.file_id,
        "ticket_id": tf.ticket_id,
        "file_name": tf.file_name,
        "file_type": tf.file_type,
        "file_size": tf.file_size,
        "caption": tf.caption,
        "uploaded_by_user_id": tf.uploaded_by_user_id,
        "uploaded_at": tf.uploaded_at,
    }


# ─── GET /tickets/{ticket_id}/attachments — list officer uploads ──────────────

@router.get(
    "/tickets/{ticket_id}/attachments",
    summary="List officer-uploaded attachments for a ticket",
)
def list_officer_attachments(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    files = db.execute(
        select(TicketFile)
        .where(TicketFile.ticket_id == ticket_id)
        .order_by(TicketFile.uploaded_at)
    ).scalars().all()

    return [
        {
            "file_id": f.file_id,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "caption": f.caption,
            "uploaded_by_user_id": f.uploaded_by_user_id,
            "uploaded_at": f.uploaded_at,
        }
        for f in files
    ]


# ─── GET /attachments/{file_id} — download officer upload ─────────────────────

@router.get(
    "/attachments/{file_id}",
    summary="Download an officer-uploaded attachment",
)
def download_officer_attachment(
    file_id: str,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    tf = db.get(TicketFile, file_id)
    if not tf:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not os.path.isfile(tf.file_path):
        raise HTTPException(status_code=404, detail="File not on disk")

    media_type = (
        "image/jpeg" if tf.file_path.lower().endswith((".jpg", ".jpeg")) else
        "image/png"  if tf.file_path.lower().endswith(".png") else
        "application/pdf" if tf.file_path.lower().endswith(".pdf") else
        "application/octet-stream"
    )
    return FileResponse(path=tf.file_path, filename=tf.file_name, media_type=media_type)


# ─── GET /tickets/{ticket_id}/pii — broker complainant PII from backend ──────────
# Per PRIVACY.md: browser must never call backend directly — ticketing API brokers all
# sensitive reads so they go through the internal Docker network (backend:5001).

@router.get(
    "/tickets/{ticket_id}/pii",
    summary="Fetch complainant PII from the grievance backend (brokered — no direct browser call)",
)
def get_ticket_pii(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    from ticketing.clients.grievance_api import get_grievance_detail

    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")
    if not ticket.grievance_id:
        return {}

    try:
        raw = get_grievance_detail(ticket.grievance_id)
    except Exception as exc:
        logger.warning("get_ticket_pii: backend unavailable — %s", exc)
        # Degrade gracefully: return null-filled record so the UI shows "—"
        # instead of crashing.  The _backend_unavailable flag lets the UI
        # display a "Backend offline" notice without treating it as an error.
        return {
            "grievance_id": ticket.grievance_id,
            "complainant_name": None,
            "phone_number": None,
            "email": None,
            "address": None,
            "_backend_unavailable": True,
        }

    # get_grievance_detail returns the full API envelope:
    #   {"status": "SUCCESS", "data": {"grievance": {...complainant fields...}, ...}}
    # Unwrap to the grievance dict where PII fields live.
    grievance = (raw.get("data") or {}).get("grievance") or raw  # raw fallback for any future shape change

    # Return the safe PII subset (name + contact + location).
    # Phone is included here; the UI gates its display behind the "Reveal contact" button.
    # The full grievance narrative requires a vault reveal session (POST /tickets/{id}/reveal).
    return {
        "grievance_id": ticket.grievance_id,
        # Identity
        "complainant_name": grievance.get("complainant_full_name"),
        "phone_number":     grievance.get("complainant_phone"),
        "email":            grievance.get("complainant_email"),
        # Location (used by complainant edit form pre-fill)
        "address":          grievance.get("complainant_address"),
        "village":          grievance.get("complainant_village"),
        "ward":             grievance.get("complainant_ward"),
        "municipality":     grievance.get("complainant_municipality"),
        "district":         grievance.get("complainant_district"),
        "province":         grievance.get("complainant_province"),
    }


# ─── POST /tickets/{ticket_id}/findings — regenerate AI findings ──────────────

# Roles permitted to regenerate findings (supervisors + senior observers only)
_FINDINGS_ROLES = {
    "grc_chair", "adb_hq_safeguards", "adb_hq_project",
    "adb_hq_exec", "adb_national_project_director",
    "super_admin", "local_admin",
}


@router.post(
    "/tickets/{ticket_id}/findings",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger (re)generation of the AI case-findings summary (admin/supervisor only)",
    description=(
        "Queues a Celery task that reads all key events for the ticket, "
        "calls OpenAI gpt-4, and stores the result in `ai_summary_en`. "
        "Returns 202 Accepted immediately; poll `GET /tickets/{id}` for the updated field. "
        "Restricted to: grc_chair, adb_*, super_admin, local_admin."
    ),
)
def trigger_findings(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    # Role gate — only supervisors and senior observers may trigger findings
    has_findings_role = current_user.is_admin or bool(
        set(current_user.role_keys) & _FINDINGS_ROLES
    )
    if not has_findings_role:
        raise HTTPException(
            status_code=403,
            detail=(
                "Findings generation is restricted to supervisors and senior observers. "
                f"Your roles ({current_user.role_keys!r}) do not have permission."
            ),
        )

    generate_findings.delay(ticket_id)
    logger.info(
        "Findings generation queued: ticket_id=%s requested_by=%s",
        ticket_id, current_user.user_id,
    )
    return {
        "ticket_id": ticket_id,
        "status": "queued",
        "message": "Findings generation has been queued. Poll GET /tickets/{id} for the result.",
    }


# ─── POST /tickets/{ticket_id}/reveal — open vault reveal session ─────────────

from pydantic import BaseModel as _BaseModel


class RevealRequest(_BaseModel):
    reason_code: str
    reason_text: str = ""


class RevealCloseRequest(_BaseModel):
    reveal_session_id: str
    close_reason: str = "user_closed"


@router.post(
    "/tickets/{ticket_id}/reveal",
    summary="Open a time-limited vault reveal session for the original grievance statement",
    description=(
        "Validates officer access, logs a REVEAL_ORIGINAL audit event, then calls the "
        "grievance API to obtain a short-lived reveal session. "
        "Standard TTL: 120 s. SEAH TTL: 60 s. "
        "Every access attempt is logged regardless of outcome."
    ),
)
def begin_reveal(
    ticket_id: str,
    body: RevealRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    from ticketing.clients.grievance_api import begin_reveal_session

    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")
    if not ticket.grievance_id:
        raise HTTPException(status_code=422, detail="Ticket has no linked grievance_id")

    case_sensitivity = "seah" if ticket.is_seah else "standard"

    # Call grievance API (proto: falls back to GET /api/grievance/{id})
    session = begin_reveal_session(
        grievance_id=ticket.grievance_id,
        reason_code=body.reason_code,
        reason_text=body.reason_text,
        actor_id=current_user.user_id,
        case_sensitivity=case_sensitivity,
    )

    # Log REVEAL_ORIGINAL audit event regardless of grant/deny
    _add_event(
        db, ticket, "REVEAL_ORIGINAL",
        step_id=ticket.current_step_id,
        note=f"Reveal requested: {body.reason_code}" + (f" — {body.reason_text}" if body.reason_text else ""),
        payload={
            "reason_code": body.reason_code,
            "reason_text": body.reason_text,
            "granted": session.get("granted", False),
            "reveal_session_id": session.get("reveal_session_id"),
            "case_sensitivity": case_sensitivity,
            "deny_code": session.get("deny_code"),
        },
        created_by=current_user.user_id,
        seen=True,
        actor_role=_actor_role(current_user),
        case_sensitivity=case_sensitivity,
        summary_regen_required=False,  # reveal access doesn't change case content
    )
    db.commit()

    if not session.get("granted"):
        raise HTTPException(
            status_code=403,
            detail=f"Reveal denied: {session.get('deny_code', 'policy_check_failed')}",
        )

    return session


@router.post(
    "/tickets/{ticket_id}/reveal/close",
    summary="Close a vault reveal session and record duration",
)
def close_reveal(
    ticket_id: str,
    body: RevealCloseRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    from ticketing.clients.grievance_api import close_reveal_session

    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.is_deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")
    if not ticket.grievance_id:
        raise HTTPException(status_code=422, detail="Ticket has no linked grievance_id")

    result = close_reveal_session(
        grievance_id=ticket.grievance_id,
        reveal_session_id=body.reveal_session_id,
        close_reason=body.close_reason,
    )

    # Log session closure for audit trail
    _add_event(
        db, ticket, "REVEAL_ORIGINAL_CLOSED",
        step_id=ticket.current_step_id,
        note=f"Reveal session closed: {body.close_reason}",
        payload={
            "reveal_session_id": body.reveal_session_id,
            "close_reason": body.close_reason,
        },
        created_by=current_user.user_id,
        seen=True,
        actor_role=_actor_role(current_user),
        summary_regen_required=False,
    )
    db.commit()

    return result
