"""
Create ticketing.tickets from chatbot intake — shared by POST /api/v1/tickets and sync backfill.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.api.schemas.ticket import TicketCreate
from ticketing.engine.escalation import _apply_step_tier_roles
from ticketing.engine.workflow_engine import auto_assign_for_workflow_step, resolve_workflow
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowStep
from ticketing.services.grievance_content import _coerce_categories
from ticketing.services.project_routing import resolve_ticket_organization

logger = logging.getLogger(__name__)


class TicketIntakeError(Exception):
    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class DuplicateTicketError(TicketIntakeError):
    def __init__(self, grievance_id: str, ticket_id: str) -> None:
        super().__init__(
            f"Ticket already exists for grievance_id={grievance_id} (ticket_id={ticket_id})",
            status_code=409,
        )
        self.grievance_id = grievance_id
        self.ticket_id = ticket_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _first_step(db: Session, workflow_id: str) -> Optional[WorkflowStep]:
    return db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()


def _effective_organization_id(db: Session, payload: TicketCreate) -> str:
    """Resolve routing org from project/package actors; fall back to payload when no project context."""
    has_project_context = bool(
        (payload.project_code or "").strip() or (payload.package_id or "").strip()
    )
    if not has_project_context:
        return payload.organization_id

    resolved = resolve_ticket_organization(
        db,
        project_code=payload.project_code,
        package_id=payload.package_id,
        location_code=payload.location_code,
    )
    if not resolved:
        raise TicketIntakeError(
            (
                f"No routing organization for project={payload.project_code} "
                f"package={payload.package_id}. "
                "Assign an implementing agency under Project actors."
            ),
            status_code=422,
        )
    if resolved != payload.organization_id:
        logger.info(
            "ticket_intake: organization_id %s -> %s (project routing)",
            payload.organization_id,
            resolved,
        )
    return resolved


def _validate_project_intake(db: Session, project_code: Optional[str]) -> None:
    if not project_code:
        return
    from ticketing.services import project_go_live as go_live_svc

    proj = db.execute(
        select(Project).where(Project.short_code == project_code)
    ).scalar_one_or_none()
    if not proj:
        return
    if not proj.is_active:
        raise TicketIntakeError(
            f"Project '{project_code}' is not active",
            status_code=422,
        )
    block = go_live_svc.ticket_intake_block_message(db, proj.project_id)
    if block:
        raise TicketIntakeError(block, status_code=422)


def create_ticket_from_intake(
    db: Session,
    payload: TicketCreate,
    *,
    source: str = "webhook",
    created_by_user_id: str = "system",
    created_event_note: Optional[str] = None,
) -> Ticket:
    """
    Create ticket + CREATED event + step tier viewers. Caller must commit.

    source: "webhook" (chatbot dispatch) | "sync_backfill" (grievance_sync safety net)
    """
    existing = db.execute(
        select(Ticket).where(
            Ticket.grievance_id == payload.grievance_id,
            Ticket.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if existing:
        raise DuplicateTicketError(payload.grievance_id, existing.ticket_id)

    _validate_project_intake(db, payload.project_code)

    organization_id = _effective_organization_id(db, payload)

    workflow = resolve_workflow(
        organization_id=organization_id,
        location_code=payload.location_code,
        project_code=payload.project_code,
        is_seah=payload.is_seah,
        priority=payload.priority,
        db=db,
        grievance_categories=payload.grievance_categories,
        intake_route=payload.intake_route,
        intake_fast_path=payload.intake_fast_path,
    )
    if not workflow:
        raise TicketIntakeError(
            (
                f"No workflow found for org={organization_id} "
                f"location={payload.location_code} project={payload.project_code} "
                f"is_seah={payload.is_seah} priority={payload.priority}."
            ),
            status_code=422,
        )
    from ticketing.services.workflow_routing import workflow_is_seah

    ticket_is_seah = workflow_is_seah(workflow)

    first_step = _first_step(db, workflow.workflow_id)

    auto_assigned_id: Optional[str] = None
    if first_step:
        auto_assigned_id = auto_assign_for_workflow_step(
            step_role_key=first_step.assigned_role_key,
            organization_id=organization_id,
            location_code=payload.location_code,
            project_code=payload.project_code,
            db=db,
            ticket_package_id=payload.package_id,
            supervisor_role=first_step.supervisor_role,
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
        organization_id=organization_id,
        location_code=payload.location_code,
        project_code=payload.project_code,
        status_code="OPEN",
        current_workflow_id=workflow.workflow_id,
        current_step_id=first_step.step_id if first_step else None,
        assigned_to_user_id=auto_assigned_id,
        complainant_reply_owner_id=auto_assigned_id,
        priority=payload.priority,
        is_seah=ticket_is_seah,
        intake_route=payload.intake_route,
        intake_fast_path=payload.intake_fast_path,
        package_id=payload.package_id,
        is_deleted=False,
        sla_breached=False,
    )
    db.add(ticket)

    event_payload = {"workflow_key": workflow.workflow_key, "source": source}
    if source == "sync_backfill":
        event_payload["backfill"] = True

    note = created_event_note
    if note is None:
        note = (
            "Backfill created by grievance sync (chatbot webhook did not create a ticket)"
            if source == "sync_backfill"
            else None
        )

    event = TicketEvent(
        event_id=_new_id(),
        ticket_id=ticket.ticket_id,
        event_type="CREATED",
        new_status_code="OPEN",
        workflow_step_id=first_step.step_id if first_step else None,
        note=note,
        payload=event_payload,
        seen=True,
        created_by_user_id=created_by_user_id,
        created_at=_now(),
        case_sensitivity="seah" if ticket_is_seah else "standard",
    )
    db.add(event)

    if first_step:
        _apply_step_tier_roles(db, ticket, first_step)

    logger.info(
        "ticket_intake created ticket_id=%s grievance_id=%s source=%s assigned=%s package=%s",
        ticket.ticket_id,
        payload.grievance_id,
        source,
        auto_assigned_id,
        payload.package_id,
    )
    return ticket


def build_backfill_payload_from_grievance_row(g: dict) -> TicketCreate:
    """Best-effort TicketCreate from public.grievances (+ optional complainant join)."""
    is_seah = bool(g.get("grievance_sensitive_issue", False))
    priority = "HIGH" if is_seah or bool(g.get("grievance_high_priority", False)) else "NORMAL"
    cats = _coerce_categories(g.get("grievance_categories"))

    location_code = g.get("location_code")
    if location_code in (None, "", "NOT_PROVIDED", "Not provided"):
        location_code = None
    else:
        location_code = str(location_code).strip() or None

    return TicketCreate(
        grievance_id=g["grievance_id"],
        complainant_id=g.get("complainant_id"),
        session_id=None,
        chatbot_id="nepal_grievance_bot",
        country_code="NP",
        organization_id="DOR",
        location_code=location_code,
        project_code="KL_ROAD",
        package_id=None,
        priority=priority,
        is_seah=is_seah,
        grievance_summary=g.get("grievance_summary"),
        grievance_categories=cats,
        grievance_location=g.get("grievance_location"),
    )
