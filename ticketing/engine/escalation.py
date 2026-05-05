"""
Escalation logic for GRM Ticketing.

Used by:
  1. Celery SLA watchdog (auto-escalation on SLA breach)
  2. Officer action endpoint (manual escalation via ESCALATE action)
  3. GRC actions (CONVENE, DECIDE)

All escalation paths go through escalate_ticket() — single code path,
no duplication between manual and auto.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.engine.workflow_engine import (
    auto_assign_officer,
    get_current_step,
    get_grc_member_user_ids,
    get_next_step,
    is_sla_breached,
    _scope_candidates,
)
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_viewer import TicketViewer

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


def _case_sensitivity(ticket: Ticket) -> str:
    return "seah" if ticket.is_seah else "standard"


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
    seen: bool = False,
    notify_user_id: Optional[str] = None,
    created_by: Optional[str] = None,
    # ── SEAH audit fields (seah-privacy-worktree-handoff.md) ──
    actor_role: Optional[str] = None,
    case_sensitivity: Optional[str] = None,   # derived from ticket when None
    summary_regen_required: bool = False,
) -> TicketEvent:
    event = TicketEvent(
        event_id=_id(),
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
        case_sensitivity=case_sensitivity if case_sensitivity is not None else _case_sensitivity(ticket),
        summary_regen_required=summary_regen_required,
    )
    db.add(event)
    return event


# ── Tier management helpers ───────────────────────────────────────────────────

def _ensure_viewer(
    db: Session,
    ticket_id: str,
    user_id: str,
    tier: str,
    added_by: str,
) -> TicketViewer:
    """
    Upsert a TicketViewer row for (ticket_id, user_id).
    If the row already exists, updates tier to the new value.
    Returns the viewer row.
    """
    from sqlalchemy import select
    existing = db.execute(
        select(TicketViewer).where(
            TicketViewer.ticket_id == ticket_id,
            TicketViewer.user_id == user_id,
        )
    ).scalar_one_or_none()

    if existing:
        if existing.tier != tier:
            existing.tier = tier
            logger.debug("Tier updated: user=%s ticket=%s tier=%s", user_id, ticket_id, tier)
        return existing

    viewer = TicketViewer(
        ticket_id=ticket_id,
        user_id=user_id,
        added_by_user_id=added_by,
        tier=tier,
    )
    db.add(viewer)
    logger.debug("Tier assigned: user=%s ticket=%s tier=%s", user_id, ticket_id, tier)
    return viewer


def _apply_step_tier_roles(
    db: Session,
    ticket: Ticket,
    step,  # WorkflowStep
) -> None:
    """
    Auto-add users to the ticket's viewer list based on the step's
    informed_roles and observer_roles configuration.

    Called on both ticket creation (first step) and escalation (new step).
    Scoped to the ticket's org / location / project.
    """
    from ticketing.models.workflow import WorkflowStep as _Step

    if not isinstance(step, _Step):
        return

    for role_key in (step.informed_roles or []):
        candidates = _scope_candidates(
            role_key=role_key,
            organization_id=ticket.organization_id,
            location_code=ticket.location_code,
            project_code=ticket.project_code,
            db=db,
        )
        for uid in candidates:
            _ensure_viewer(db, ticket.ticket_id, uid, "informed", "system")

    for role_key in (step.observer_roles or []):
        candidates = _scope_candidates(
            role_key=role_key,
            organization_id=ticket.organization_id,
            location_code=ticket.location_code,
            project_code=ticket.project_code,
            db=db,
        )
        for uid in candidates:
            # Don't demote an existing Informed to Observer
            from sqlalchemy import select as _select
            existing = db.execute(
                _select(TicketViewer).where(
                    TicketViewer.ticket_id == ticket.ticket_id,
                    TicketViewer.user_id == uid,
                )
            ).scalar_one_or_none()
            if existing is None or existing.tier == "observer":
                _ensure_viewer(db, ticket.ticket_id, uid, "observer", "system")


# ── Core escalation ───────────────────────────────────────────────────────────

def escalate_ticket(
    ticket: Ticket,
    db: Session,
    *,
    triggered_by: str = "SLA_AUTO",
    note: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
    actor_role: Optional[str] = None,
) -> Optional[TicketEvent]:
    """
    Advance ticket to the next workflow step.

    triggered_by: "SLA_AUTO" | "MANUAL" | "GRC_DECIDE"

    Returns the ESCALATED TicketEvent, or None if ticket is at final step.
    Does NOT commit — caller must db.commit() after.
    """
    next_step = get_next_step(ticket, db)
    if next_step is None:
        logger.info(
            "ticket_id=%s is at final step — no further escalation possible",
            ticket.ticket_id,
        )
        return None

    old_status = ticket.status_code
    old_step_id = ticket.current_step_id
    old_assigned = ticket.assigned_to_user_id

    # ── Move previous Actor to Informed (tier lifecycle, spec 12 §2) ─────────
    if old_assigned:
        _ensure_viewer(db, ticket.ticket_id, old_assigned, "informed", "system")
        _add_event(
            db, ticket, "TIER_CHANGED",
            step_id=old_step_id,
            note=f"Officer moved from Actor to Informed on escalation.",
            payload={"user_id": old_assigned, "from_tier": "actor", "to_tier": "informed"},
            seen=False,
            notify_user_id=old_assigned,
            created_by="system",
            actor_role="system",
            summary_regen_required=False,
        )

    ticket.current_step_id = next_step.step_id
    ticket.status_code = "ESCALATED"
    ticket.sla_breached = (triggered_by == "SLA_AUTO")
    ticket.step_started_at = None  # clock resets at new step; starts on ACKNOWLEDGE
    ticket.updated_by_user_id = created_by_user_id or "system"

    # Auto-add informed_roles + observer_roles from the new step
    _apply_step_tier_roles(db, ticket, next_step)

    # Auto-assign to the least-loaded officer at the next step's role
    new_assigned = auto_assign_officer(
        role_key=next_step.assigned_role_key,
        organization_id=ticket.organization_id,
        location_code=ticket.location_code,
        project_code=ticket.project_code,
        db=db,
    )
    if new_assigned:
        ticket.assigned_to_user_id = new_assigned
        logger.info(
            "Auto-assigned ticket_id=%s to %s at step %s",
            ticket.ticket_id, new_assigned, next_step.step_key,
        )
    else:
        logger.warning(
            "No officer found for role=%s org=%s loc=%s proj=%s — ticket_id=%s unassigned at new step",
            next_step.assigned_role_key, ticket.organization_id,
            ticket.location_code, ticket.project_code, ticket.ticket_id,
        )

    event_note = note or (
        f"Auto-escalated: SLA exceeded at previous step."
        if triggered_by == "SLA_AUTO"
        else f"Manually escalated to {next_step.display_name}."
    )

    event = _add_event(
        db, ticket, "ESCALATED",
        old_status=old_status,
        new_status="ESCALATED",
        old_assigned=old_assigned,
        new_assigned=ticket.assigned_to_user_id,
        step_id=next_step.step_id,
        note=event_note,
        payload={
            "triggered_by": triggered_by,
            "from_step_id": old_step_id,
            "to_step_id": next_step.step_id,
            "to_step_key": next_step.step_key,
        },
        seen=False,
        notify_user_id=ticket.assigned_to_user_id,  # new officer, not the old one
        created_by=created_by_user_id or "system",
        actor_role=actor_role or ("system" if triggered_by == "SLA_AUTO" else None),
        summary_regen_required=True,
    )

    logger.info(
        "Ticket escalated: ticket_id=%s %s→%s triggered_by=%s",
        ticket.ticket_id, old_step_id, next_step.step_id, triggered_by,
    )
    return event


# ── GRC-specific actions ──────────────────────────────────────────────────────

def convene_grc(
    ticket: Ticket,
    db: Session,
    *,
    note: Optional[str] = None,
    convened_by_user_id: str,
    hearing_date: Optional[str] = None,
    actor_role: Optional[str] = None,
) -> list[TicketEvent]:
    """
    GRC Chair convenes a hearing.
    Creates one CONVENED event + one unseen notification event per GRC member.
    Does NOT advance the step — chair must DECIDE to advance.
    """
    ticket.status_code = "GRC_HEARING_SCHEDULED"
    ticket.updated_by_user_id = convened_by_user_id

    events: list[TicketEvent] = []

    convene_event = _add_event(
        db, ticket, "GRC_CONVENED",
        new_status="GRC_HEARING_SCHEDULED",
        step_id=ticket.current_step_id,
        note=note or f"GRC hearing convened.{' Date: ' + hearing_date if hearing_date else ''}",
        payload={"convened_by": convened_by_user_id, "hearing_date": hearing_date},
        seen=True,
        created_by=convened_by_user_id,
        actor_role=actor_role,
        summary_regen_required=True,
    )
    events.append(convene_event)

    # Notify all GRC members (creates unseen events → badge++)
    member_ids = get_grc_member_user_ids(
        ticket.organization_id, ticket.location_code, db
    )
    for member_id in member_ids:
        if member_id == convened_by_user_id:
            continue  # don't notify self
        notif = _add_event(
            db, ticket, "GRC_HEARING_NOTIFICATION",
            step_id=ticket.current_step_id,
            note=f"GRC hearing convened by chair.{' Date: ' + hearing_date if hearing_date else ''}",
            seen=False,
            notify_user_id=member_id,
            created_by=convened_by_user_id,
            actor_role=actor_role,
            # badge-only notification — summary regen not needed
            summary_regen_required=False,
        )
        events.append(notif)

    logger.info(
        "GRC convened: ticket_id=%s notified %d members",
        ticket.ticket_id, len(member_ids) - 1,
    )
    return events


def grc_decide(
    ticket: Ticket,
    db: Session,
    *,
    decision: str,
    note: Optional[str] = None,
    decided_by_user_id: str,
    actor_role: Optional[str] = None,
) -> TicketEvent:
    """
    GRC Chair records the committee's decision and optionally advances to L4
    (if unresolved) or marks ticket resolved.

    decision: "RESOLVED" | "ESCALATE_TO_LEGAL"
    """
    if decision == "RESOLVED":
        ticket.status_code = "RESOLVED"
        ticket.updated_by_user_id = decided_by_user_id
        event = _add_event(
            db, ticket, "GRC_DECIDED",
            old_status="GRC_HEARING_SCHEDULED",
            new_status="RESOLVED",
            step_id=ticket.current_step_id,
            note=note or "GRC decision: resolved.",
            payload={"decision": decision, "decided_by": decided_by_user_id},
            seen=True,
            created_by=decided_by_user_id,
            actor_role=actor_role,
            summary_regen_required=True,
        )
    elif decision == "ESCALATE_TO_LEGAL":
        event = _add_event(
            db, ticket, "GRC_DECIDED",
            old_status="GRC_HEARING_SCHEDULED",
            new_status="ESCALATED",
            step_id=ticket.current_step_id,
            note=note or "GRC decision: escalate to legal institutions.",
            payload={"decision": decision, "decided_by": decided_by_user_id},
            seen=True,
            created_by=decided_by_user_id,
            actor_role=actor_role,
            summary_regen_required=True,
        )
        # Advance step to L4 (legal)
        escalate_ticket(
            ticket, db,
            triggered_by="GRC_DECIDE",
            note="GRC referred case to legal institutions.",
            created_by_user_id=decided_by_user_id,
            actor_role=actor_role,
        )
    else:
        raise ValueError(f"Unknown GRC decision: {decision}")

    logger.info(
        "GRC decided: ticket_id=%s decision=%s", ticket.ticket_id, decision
    )
    return event


# ── Batch SLA check ───────────────────────────────────────────────────────────

def get_tickets_needing_escalation(db: Session) -> list[Ticket]:
    """
    Return tickets that have exceeded their current step's SLA.

    Conditions:
      - Status is active (not RESOLVED, CLOSED, ESCALATED-already-counted)
      - Current step has a resolution_time_days defined
      - step_started_at is set (officer acknowledged)
      - SLA deadline has passed
      - sla_breached is False (avoid double-processing)
    """
    from ticketing.models.workflow import WorkflowStep

    active_statuses = ("OPEN", "IN_PROGRESS", "GRC_HEARING_SCHEDULED")

    # Load all active, non-breached tickets with a step
    candidates = db.execute(
        select(Ticket).where(
            Ticket.status_code.in_(active_statuses),
            Ticket.is_deleted.is_(False),
            Ticket.current_step_id.is_not(None),
            Ticket.step_started_at.is_not(None),
            Ticket.sla_breached.is_(False),
        )
    ).scalars().all()

    breached = []
    for ticket in candidates:
        step = db.get(WorkflowStep, ticket.current_step_id)
        if step and is_sla_breached(ticket, step):
            breached.append(ticket)

    return breached


def run_sla_check(db: Session) -> dict:
    """
    Check all active tickets for SLA breach and escalate as needed.
    Returns a summary dict for logging.
    """
    tickets = get_tickets_needing_escalation(db)
    escalated = 0
    final_step = 0
    errors = 0

    for ticket in tickets:
        try:
            result = escalate_ticket(
                ticket, db,
                triggered_by="SLA_AUTO",
                note=None,
            )
            if result is None:
                # Ticket is at final step — mark breached but don't escalate
                ticket.sla_breached = True
                ticket.updated_by_user_id = "system"
                _add_event(
                    db, ticket, "SLA_BREACH_FINAL_STEP",
                    step_id=ticket.current_step_id,
                    note="SLA breached at final escalation level. Manual intervention required.",
                    payload={"triggered_by": "SLA_AUTO"},
                    seen=False,
                    notify_user_id=ticket.assigned_to_user_id,
                    created_by="system",
                    actor_role="system",
                    summary_regen_required=True,
                )
                final_step += 1
            else:
                escalated += 1
        except Exception as exc:
            logger.exception(
                "Error escalating ticket_id=%s: %s", ticket.ticket_id, exc
            )
            errors += 1

    if escalated or final_step:
        db.commit()

    summary = {
        "checked": len(tickets),
        "escalated": escalated,
        "final_step_breach": final_step,
        "errors": errors,
    }
    logger.info("SLA check complete: %s", summary)
    return summary
