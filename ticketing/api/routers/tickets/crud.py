"""Ticket lifecycle CRUD endpoints.

  POST  /tickets                       — create ticket from grievance (API key)
  GET   /tickets                       — officer queue (filtered / paged)
  GET   /tickets/{ticket_id}           — ticket detail + event history
  GET   /reference/grievance-categories
  PATCH /tickets/{ticket_id}/classification
  PATCH /tickets/{ticket_id}           — assign / priority
  PATCH /tickets/{ticket_id}/complainant
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db, verify_api_key
from ticketing.api.ticket_access import assert_ticket_visibility, require_ticket_access
from ticketing.api.schemas.ticket import (
    ClassificationValidateRequest,
    ClassificationValidateResponse,
    ComplainantPatch,
    ComplainantPatchResponse,
    TicketCreate,
    TicketCreateResponse,
    TicketDetail,
    TicketListItem,
    TicketListResponse,
    TicketPatch,
)
from ticketing.clients.grievance_api import patch_complainant, patch_grievance_classification
from ticketing.constants.classification import OFFICER_CONFIRMED
from ticketing.constants.tiers import ACTOR, SUPERVISOR
from ticketing.services.tier_permissions import user_holds_tier_on_step
from ticketing.services.grievance_content import (
    fetch_grievance_row,
    merge_grievance_into_ticket,
)
from ticketing.services.overdue_episodes import overdue_days_display
from ticketing.services.ticket_intake import (
    DuplicateTicketError,
    TicketIntakeError,
    create_ticket_from_intake,
)
from ticketing.engine.events import _add_event
from ticketing.engine.workflow_engine import (
    _find_supervisor_user_id,
    get_current_step,
    is_step_assignee_eligible,
)
from ticketing.tasks.notifications import enqueue_assignment_notifications
from ticketing.tasks.llm import generate_findings
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_overdue_episode import TicketOverdueEpisode
from ticketing.models.ticket_task import TicketTask
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowStep

from ._shared import _actor_role, _enqueue_celery, _now

logger = logging.getLogger(__name__)
router = APIRouter()


def _step_supervisor_available(db: Session, ticket: Ticket) -> bool:
    """True when the current step has a configured supervisor who can be resolved in scope."""
    return _find_supervisor_user_id(db, ticket) is not None


def _can_assign_ticket(db: Session, ticket: Ticket, current_user: CurrentUser) -> bool:
    """Supervisor tier for current step, admin, or assigned Actor when no supervisor (TP-12).

    Tier membership drives both branches (DESIGN-cast-model §6): the Supervisor-tier holder
    may reassign; the Actor-tier holder may self-reassign only as the assignee-of-record and
    only when no supervisor is resolvable. This will be superseded by the ``can_reassign``
    resolution chain in Phase 4.
    """
    if current_user.is_admin:  # covers project_admin+ (the §3.4 backstop)
        return True
    step = get_current_step(ticket, db)
    if step and user_holds_tier_on_step(step, current_user.role_keys, SUPERVISOR):
        return True
    # §3.4 Dispatcher for the ticket's project/package.
    from ticketing.services.reassignment import dispatcher_for_ticket

    disp = dispatcher_for_ticket(db, ticket)
    if disp and current_user.matches_assignee(disp):
        return True
    # §3.4 Actor self-serve: the per-step toggle grants the assignee reassignment authority.
    if (
        step and getattr(step, "actor_can_reassign", False)
        and ticket.assigned_to_user_id and current_user.matches_assignee(ticket.assigned_to_user_id)
        and user_holds_tier_on_step(step, current_user.role_keys, ACTOR)
    ):
        return True
    # TP-12 legacy fallback: assigned Actor may self-reassign when no supervisor is resolvable.
    if not _step_supervisor_available(db, ticket):
        if ticket.assigned_to_user_id and current_user.matches_assignee(ticket.assigned_to_user_id):
            if step and user_holds_tier_on_step(step, current_user.role_keys, ACTOR):
                return True
    return False


# Roles that may edit complainant info (assigned officer + managers).
_COMPLAINANT_EDIT_ROLES = {
    "site_safeguards_focal_person", "pd_piu_safeguards_focal",
    "seah_national_officer", "seah_hq_officer",
    "super_admin", "local_admin",
}


@router.post(
    "/tickets",
    response_model=TicketCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket from submitted grievance",
    description="Called by chatbot backend after grievance is stored. Requires x-api-key header.",
)
def create_ticket(
    payload: TicketCreate,
    response: Response,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> TicketCreateResponse:
    try:
        ticket = create_ticket_from_intake(
            db,
            payload,
            source="webhook",
            created_by_user_id="system",
        )
    except DuplicateTicketError as exc:
        # HR-03: intake is idempotent — a webhook retry or a race for an already
        # existing grievance is a no-op, not an error. Return the existing ticket with
        # 200 (not 409) so the chatbot dispatcher treats it as success (it calls
        # raise_for_status(), which only trips on 4xx/5xx).
        db.rollback()
        existing = db.execute(
            select(Ticket).where(
                Ticket.grievance_id == payload.grievance_id,
                Ticket.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if existing is None:
            logger.warning("Duplicate ticket request for grievance_id=%s", payload.grievance_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=exc.detail,
            ) from exc
        logger.info(
            "Idempotent ticket intake for grievance_id=%s → existing ticket_id=%s",
            payload.grievance_id,
            existing.ticket_id,
        )
        response.status_code = status.HTTP_200_OK
        return existing
    except TicketIntakeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    db.commit()
    db.refresh(ticket)

    if ticket.assigned_to_user_id:
        enqueue_assignment_notifications(
            ticket.ticket_id,
            ticket.assigned_to_user_id,
            ticket.current_step_id,
            event="assignment",
        )

    if (payload.grievance_summary or "").strip():
        _enqueue_celery(generate_findings, ticket.ticket_id)

    logger.info(
        "Ticket created: ticket_id=%s grievance_id=%s is_seah=%s assigned=%s",
        ticket.ticket_id,
        payload.grievance_id,
        payload.is_seah,
        ticket.assigned_to_user_id,
    )
    return ticket


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
    package_id: Optional[str] = Query(None, description="Filter by ticketing.tickets.package_id"),
    priority: Optional[str] = Query(None, description="NORMAL | HIGH | CRITICAL"),
    search: Optional[str] = Query(None, alias="q", description="Search grievance_id, summary, or assignee email"),
    created_from: Optional[date] = Query(None, description="Created on or after (calendar date, UTC day boundary)"),
    created_to: Optional[date] = Query(None, description="Created on or before (calendar date, UTC day boundary)"),
    sla_breached: Optional[bool] = Query(None),
    include_archived: Optional[bool] = Query(
        False,
        description="Include archived tickets (super_admin / local_admin only). Default excludes archived.",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> TicketListResponse:
    stmt = select(Ticket).where(Ticket.is_deleted.is_(False))

    # ── Archived filter — hidden from default officer queues (L5) ──
    if include_archived:
        if not current_user.can_view_archived:
            raise HTTPException(status_code=403, detail="Admin access required to view archived tickets")
    else:
        stmt = stmt.where(Ticket.is_archived.is_(False))

    # ── SEAH visibility gate (DB-level) ──
    if not current_user.can_see_seah:
        stmt = stmt.where(Ticket.is_seah.is_(False))
    elif is_seah is not None:
        stmt = stmt.where(Ticket.is_seah.is_(is_seah))

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

        # OC-04 §5.3 — supervisor visibility: additionally see reports' tickets (org chart,
        # bounded by each position's visibility_mode). The SEAH predicate is carried INLINE
        # on this branch so a non-SEAH supervisor of a SEAH officer sees NONE of their SEAH
        # tickets (doc 16 §6) — even when the viewer can otherwise see SEAH.
        from ticketing.models.user import SEAH_ROLES
        from ticketing.services.chart_behaviors import visible_report_user_ids

        _report_conditions = []
        _report_uids = visible_report_user_ids(db, current_user.user_id)
        if _report_uids:
            _rc = Ticket.assigned_to_user_id.in_(_report_uids)
            if not (set(current_user.role_keys) & SEAH_ROLES):
                _rc = and_(_rc, Ticket.is_seah.is_(False))
            _report_conditions.append(_rc)

        if not scopes:
            # No scope rows → only assigned tickets OR watched tickets OR reports' tickets
            stmt = stmt.where(or_(
                Ticket.assigned_to_user_id == current_user.user_id,
                Ticket.ticket_id.in_(viewed_ticket_ids),
                *_report_conditions,
            ))
        else:
            from ticketing.services.officer_jurisdiction import scope_ticket_filter

            scope_conditions = [scope_ticket_filter(db, scope) for scope in scopes]
            # Assigned / watched tickets stay visible even when jurisdiction is narrower
            # (e.g. package-scoped officer auto-assigned a project-wide ticket).
            scope_conditions.append(Ticket.assigned_to_user_id == current_user.user_id)
            if viewed_ticket_ids:
                scope_conditions.append(Ticket.ticket_id.in_(viewed_ticket_ids))
            scope_conditions.extend(_report_conditions)
            stmt = stmt.where(or_(*scope_conditions))

    if tab:
        tab_lower = tab.lower()
        if tab_lower == "actor":
            # Actor = tickets where I am the action owner OR have a pending task
            pending_task_ticket_ids = select(TicketTask.ticket_id).where(
                TicketTask.assigned_to_user_id == current_user.user_id,
                TicketTask.status == "PENDING",
            )
            stmt = stmt.where(or_(
                Ticket.assigned_to_user_id == current_user.user_id,
                Ticket.ticket_id.in_(pending_task_ticket_ids),
            ))
        elif tab_lower in ("supervisor", "informed", "observer"):
            # Tier tabs: only tickets where I have a viewer row with that tier
            tier_ticket_ids = select(TicketViewer.ticket_id).where(
                TicketViewer.user_id == current_user.user_id,
                TicketViewer.tier == tab_lower,
            )
            stmt = stmt.where(Ticket.ticket_id.in_(tier_ticket_ids))
        elif tab_lower == "high_priority":
            stmt = stmt.where(or_(
                Ticket.priority.in_(["HIGH", "CRITICAL"]),
                Ticket.sla_breached.is_(True),
            ))
        # tab="all" or unrecognised: no additional filter

    if status_code:
        stmt = stmt.where(Ticket.status_code == status_code)
    if organization_id:
        # An organization's grievances are the ones on its projects — and on its packages, and on
        # everything its child organizations are named on (DECISION-organization-membership,
        # 2026-08-04). Not the ones stamped with its id: that stamp could only ever name one
        # body per grievance, so it answered wrongly for every other organization involved.
        from ticketing.services.org_reach import ticket_filter_for_org

        stmt = stmt.where(ticket_filter_for_org(db, organization_id))
    if location_code:
        stmt = stmt.where(Ticket.location_code == location_code)
    if project_code:
        stmt = stmt.where(Ticket.project_code == project_code)
    if package_id:
        stmt = stmt.where(Ticket.package_id == package_id)
    if priority:
        stmt = stmt.where(Ticket.priority == priority.upper())
    if search:
        term = search.strip()
        if term:
            pattern = f"%{term.replace('%', '').replace('_', '')}%"
            stmt = stmt.where(
                or_(
                    Ticket.grievance_id.ilike(pattern),
                    Ticket.grievance_summary.ilike(pattern),
                    Ticket.assigned_to_user_id.ilike(pattern),
                )
            )
    if created_from:
        start = datetime.combine(created_from, time.min, tzinfo=timezone.utc)
        stmt = stmt.where(Ticket.created_at >= start)
    if created_to:
        end = datetime.combine(created_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        stmt = stmt.where(Ticket.created_at < end)
    if sla_breached is not None:
        stmt = stmt.where(Ticket.sla_breached.is_(sla_breached))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    tickets = db.execute(
        stmt.order_by(Ticket.created_at.desc())
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

    episode_by_id: dict[str, TicketOverdueEpisode] = {}
    ep_ids = [t.current_overdue_episode_id for t in tickets if t.current_overdue_episode_id]
    if ep_ids:
        for ep in db.execute(
            select(TicketOverdueEpisode).where(TicketOverdueEpisode.episode_id.in_(ep_ids))
        ).scalars():
            episode_by_id[ep.episode_id] = ep

    items = []
    for t in tickets:
        open_ep = episode_by_id.get(t.current_overdue_episode_id) if t.current_overdue_episode_id else None
        item = TicketListItem(
            ticket_id=t.ticket_id,
            grievance_id=t.grievance_id,
            grievance_summary=t.grievance_summary,
            status_code=t.status_code,
            priority=t.priority,
            is_seah=t.is_seah,
            intake_route=t.intake_route,
            organization_id=t.organization_id,
            location_code=t.location_code,
            project_code=t.project_code,
            assigned_to_user_id=t.assigned_to_user_id,
            sla_breached=bool(t.current_overdue_episode_id or t.sla_breached),
            overdue_days_display=overdue_days_display(open_ep),
            step_started_at=t.step_started_at,
            created_at=t.created_at,
            sla_deadline_at=sla_deadlines.get(t.ticket_id),
            my_earliest_task_due_at=earliest_task_due.get(t.ticket_id),
            unseen_event_count=unseen_counts.get(t.ticket_id, 0),
            needs_assignment=t.assigned_to_user_id is None,
        )
        items.append(item)

    return TicketListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetail,
    summary="Ticket detail with event history",
)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
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

    # Access gate: SEAH + admin/assignee/viewer/pending-task/jurisdiction-scope.
    # HR-02 single source of truth (was inlined here — this is the reference impl).
    assert_ticket_visibility(db, ticket, current_user)

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

    # H2-04: read-only GET. Grievance fields are live-merged for display below; the ticket
    # cache write-back (persist + commit) that used to run here was removed so detail reads
    # are idempotent (no write races between concurrent readers). Cache freshness is owned by
    # the 2-min grievance_sync task. No UI flow depends on GET-triggered persistence.
    g_row = fetch_grievance_row(db, ticket.grievance_id)
    merged: dict = {}
    if g_row:
        merged = merge_grievance_into_ticket(ticket, g_row)

    payload = TicketDetail.model_validate(ticket, from_attributes=True).model_dump()
    payload.update(merged)
    payload["step_supervisor_available"] = _step_supervisor_available(db, ticket)
    return TicketDetail(**payload)


@router.get(
    "/reference/grievance-categories",
    summary="List grievance category options from classification taxonomy (TP-14)",
)
def list_grievance_categories(
    db: Session = Depends(get_db),
    _current_user: CurrentUser = Depends(get_authenticated_user),
) -> list[dict]:
    from ticketing.services.grievance_taxonomy import list_grievance_category_options

    return list_grievance_category_options(db)


@router.patch(
    "/tickets/{ticket_id}/classification",
    response_model=ClassificationValidateResponse,
    summary="Officer validates/edits grievance summary and categories",
)
def validate_ticket_classification(
    ticket_id: str,
    payload: ClassificationValidateRequest,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> ClassificationValidateResponse:
    import json as _json

    cats_raw = payload.grievance_categories.strip()
    try:
        parsed = _json.loads(cats_raw)
        if not isinstance(parsed, list):
            raise ValueError("categories must be a JSON array")
        categories_for_api = parsed
        categories_cache = cats_raw
    except _json.JSONDecodeError:
        categories_for_api = [
            c.strip() for c in cats_raw.split(",") if c.strip()
        ]
        categories_cache = _json.dumps(categories_for_api)

    try:
        patch_grievance_classification(
            ticket.grievance_id,
            grievance_classification_status=OFFICER_CONFIRMED,
            grievance_summary=payload.grievance_summary.strip(),
            grievance_categories=categories_for_api,
        )
    except Exception as exc:
        logger.error("validate_ticket_classification backend failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not save classification on grievance record",
        ) from exc

    ticket.grievance_summary = payload.grievance_summary.strip()
    ticket.grievance_categories = categories_cache
    ticket.updated_at = _now()
    ticket.updated_by_user_id = current_user.user_id

    from ticketing.services.ticket_workflow_reroute import maybe_reroute_ticket_workflow

    # Re-resolve workflow from the updated categories (side-effecting; the bool
    # return is intentionally unused — no response field surfaces it). H2-02 Pass 4
    # dropped the dead `rerouted` binding flagged by the tickets-router pyflakes debt.
    maybe_reroute_ticket_workflow(
        db,
        ticket,
        actor_user_id=current_user.user_id,
        note="Workflow re-resolved after officer classification update",
    )

    event = _add_event(
        db,
        ticket,
        "CLASSIFICATION_VALIDATED",
        old_status=ticket.status_code,
        new_status=ticket.status_code,
        step_id=ticket.current_step_id,
        note=payload.note or "Officer confirmed summary and categories",
        created_by=current_user.user_id,
        seen=True,
        actor_role=_actor_role(current_user),
    )
    db.commit()

    return ClassificationValidateResponse(
        ticket_id=ticket.ticket_id,
        grievance_id=ticket.grievance_id,
        grievance_classification_status=OFFICER_CONFIRMED,
        event_id=event.event_id,
    )


@router.patch(
    "/tickets/{ticket_id}",
    response_model=TicketCreateResponse,
    summary="Update ticket assignment or priority",
)
def patch_ticket(
    ticket_id: str,
    payload: TicketPatch,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> Ticket:
    old_assigned = ticket.assigned_to_user_id

    if payload.assign_to_user_id is not None:
        if not _can_assign_ticket(db, ticket, current_user):
            raise HTTPException(
                status_code=403,
                detail="Only a step supervisor or admin may assign tickets to another officer.",
            )
        if not is_step_assignee_eligible(db, ticket, payload.assign_to_user_id):
            raise HTTPException(
                status_code=422,
                detail="Officer is not eligible for this ticket at the current step.",
            )
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

    if (
        payload.assign_to_user_id is not None
        and payload.assign_to_user_id != old_assigned
    ):
        enqueue_assignment_notifications(
            ticket.ticket_id,
            payload.assign_to_user_id,
            ticket.current_step_id,
            old_assigned=old_assigned,
            event="reassign",
        )

    return ticket


@router.patch(
    "/tickets/{ticket_id}/complainant",
    response_model=ComplainantPatchResponse,
    summary="Update whitelisted complainant fields",
    description=(
        "Proxies the update to the local chatbot backend "
        "(`ticketing.projects.chatbot_base_url`). "
        "Name and phone are fill-missing only when chatbot left them empty. "
        "Requires assigned officer or manager role."
    ),
)
def patch_ticket_complainant(
    ticket_id: str,
    payload: ComplainantPatch,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> ComplainantPatchResponse:
    # Role check: assigned officer OR whitelisted role (or admin)
    is_assigned = current_user.matches_assignee(ticket.assigned_to_user_id)
    is_editor = current_user.is_admin or bool(
        set(current_user.role_keys) & _COMPLAINANT_EDIT_ROLES
    )
    if not (is_assigned or is_editor):
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
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
