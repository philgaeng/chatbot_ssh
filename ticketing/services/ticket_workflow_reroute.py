"""Re-resolve workflow when officer reclassifies a ticket."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ticketing.engine.escalation import _apply_step_tier_roles
from ticketing.engine.workflow_engine import auto_assign_for_workflow_step, get_first_step
from ticketing.services.project_routing import load_project_for_ticket
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.services.workflow_routing import (
    effective_intake_route_for_reroute,
    resolve_project_workflow,
    workflow_is_seah,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def maybe_reroute_ticket_workflow(
    db: Session,
    ticket: Ticket,
    *,
    actor_user_id: str,
    note: str | None = None,
) -> bool:
    """
    Re-resolve workflow from categories + stored intake signals.
    Returns True if workflow changed (resets to L1 of new workflow).
    """
    if not ticket.project_id and not ticket.project_code:
        return False

    project = load_project_for_ticket(db, ticket)
    if not project:
        return False

    effective_route = effective_intake_route_for_reroute(
        db,
        ticket.grievance_categories,
        stored_intake_route=ticket.intake_route,
    )
    new_wf = resolve_project_workflow(
        db,
        project.project_id,
        grievance_categories=ticket.grievance_categories,
        intake_route=effective_route,
        legacy_is_seah=False,
        use_classification_rules=True,
    )
    if not new_wf or new_wf.workflow_id == ticket.current_workflow_id:
        new_is_seah = workflow_is_seah(new_wf)
        if ticket.is_seah != new_is_seah:
            ticket.is_seah = new_is_seah
        return False

    first_step = get_first_step(new_wf.workflow_id, db)
    old_wf_id = ticket.current_workflow_id

    ticket.current_workflow_id = new_wf.workflow_id
    ticket.current_step_id = first_step.step_id if first_step else None
    ticket.step_started_at = None
    ticket.is_seah = workflow_is_seah(new_wf)
    ticket.sla_breached = False

    assigned_id = None
    if first_step:
        assigned_id = auto_assign_for_workflow_step(
            step_role_key=first_step.assigned_role_key,
            organization_id=ticket.organization_id,
            location_code=ticket.location_code,
            project_code=ticket.project_code,
            db=db,
            ticket_package_id=ticket.package_id,
        )
    ticket.assigned_to_user_id = assigned_id
    ticket.complainant_reply_owner_id = assigned_id

    event = TicketEvent(
        event_id=str(__import__("uuid").uuid4()),
        ticket_id=ticket.ticket_id,
        event_type="WORKFLOW_REROUTED",
        old_status_code=ticket.status_code,
        new_status_code=ticket.status_code,
        workflow_step_id=first_step.step_id if first_step else None,
        note=note or f"Workflow changed after classification update ({new_wf.display_name})",
        payload={
            "old_workflow_id": old_wf_id,
            "new_workflow_id": new_wf.workflow_id,
            "workflow_key": new_wf.workflow_key,
        },
        seen=True,
        created_by_user_id=actor_user_id,
        created_at=_now(),
        case_sensitivity="seah" if ticket.is_seah else "standard",
    )
    db.add(event)

    if first_step:
        _apply_step_tier_roles(db, ticket, first_step)

    logger.info(
        "ticket rerouted ticket_id=%s old_wf=%s new_wf=%s",
        ticket.ticket_id,
        old_wf_id,
        new_wf.workflow_id,
    )
    return True
