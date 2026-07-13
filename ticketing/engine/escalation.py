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
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.engine.workflow_engine import (
    auto_assign_for_workflow_step,
    get_current_step,
    get_grc_member_user_ids,
    get_next_step,
    is_sla_breached,
    _scope_candidates,
)
from ticketing.engine.events import _add_event
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowStep
from ticketing.services.overdue_episodes import (
    close_open_episode,
    ensure_breach_episode,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# _add_event now lives in ticketing/engine/events.py (H2-02 — was duplicated here
# and in the tickets router); imported at module top.


# ── Tier management helpers ───────────────────────────────────────────────────

def _get_viewer(db: Session, ticket_id: str, user_id: str) -> TicketViewer | None:
    """Return viewer row from DB or pending session inserts (pre-flush)."""
    existing = db.execute(
        select(TicketViewer).where(
            TicketViewer.ticket_id == ticket_id,
            TicketViewer.user_id == user_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    for pending in db.new:
        if (
            isinstance(pending, TicketViewer)
            and pending.ticket_id == ticket_id
            and pending.user_id == user_id
        ):
            return pending
    return None


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
    existing = _get_viewer(db, ticket_id, user_id)

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
    from ticketing.models.user import BOTH_WORKFLOWS_ROLES, SEAH_ROLES
    from ticketing.models.workflow import WorkflowStep as _Step

    if not isinstance(step, _Step):
        return

    # R1/B2 SEAH leak-proof: on a SEAH ticket, cast ONLY SEAH-eligible roles — a WHITELIST
    # (SEAH operational + both-workflows oversight), not a donor-only blacklist. A donor, GRC
    # member, or ADB observer in a SEAH step's cast must receive nothing that reveals the
    # case. Applies to ALL tiers (informed, observer, supervisor). On the standard track this
    # is a no-op, so the donor last-step-informed guardrail (doc 13 §3 / OC-04 §5.6) is intact.
    _seah_eligible = SEAH_ROLES | BOTH_WORKFLOWS_ROLES

    def _seah_suppressed(role_key: str) -> bool:
        return bool(ticket.is_seah) and role_key not in _seah_eligible

    for role_key in (step.informed_roles or []):
        if _seah_suppressed(role_key):
            continue
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
        if _seah_suppressed(role_key):
            continue
        candidates = _scope_candidates(
            role_key=role_key,
            organization_id=ticket.organization_id,
            location_code=ticket.location_code,
            project_code=ticket.project_code,
            db=db,
        )
        for uid in candidates:
            # Don't demote an existing Informed to Observer
            existing = _get_viewer(db, ticket.ticket_id, uid)
            if existing is None or existing.tier == "observer":
                _ensure_viewer(db, ticket.ticket_id, uid, "observer", "system")

    # Supervisor tier — use this step's configured supervisor_role field
    # (set in Settings → Workflows → step editor; maps to WorkflowStep.supervisor_role)
    if step.supervisor_role and not _seah_suppressed(step.supervisor_role):
        for uid in _scope_candidates(
            role_key=step.supervisor_role,
            organization_id=ticket.organization_id,
            location_code=ticket.location_code,
            project_code=ticket.project_code,
            db=db,
        ):
            existing = _get_viewer(db, ticket.ticket_id, uid)
            # Add as supervisor; don't demote someone who is already Informed (higher tier)
            if existing is None or existing.tier == "observer":
                _ensure_viewer(db, ticket.ticket_id, uid, "supervisor", "system")


def notify_escalation_supervisor(db: Session, ticket: Ticket, from_step) -> list[str]:
    """OC-04 §5.5 — after a ticket escalates off ``from_step``, notify that step's resolved
    supervisor (the per-(project, step) resolver, OC-03). Side-effect only: a courtesy
    in-app notice + a ``supervisor`` viewer row — it never changes assignment, the
    escalation target, or visibility.

    **SEAH leak-proof:** on a SEAH ticket, a supervisor is notified only if they
    independently hold a SEAH role; a non-SEAH supervisor of a SEAH officer receives
    **nothing**. Call AFTER the escalation commits (does not re-open that transaction); the
    caller commits the notify rows. Returns the notified user_ids.
    """
    from ticketing.services.chart_behaviors import user_holds_seah_role
    from ticketing.services.supervisor import resolve_supervisor

    if from_step is None:
        return []
    res = resolve_supervisor(db, from_step, project_code=ticket.project_code)
    if res.user_id:
        users = [res.user_id]
    elif res.role_pool:
        users = _scope_candidates(
            role_key=res.role_pool,
            organization_id=ticket.organization_id,
            location_code=ticket.location_code,
            project_code=ticket.project_code,
            db=db,
        )
    else:
        return []

    label = getattr(from_step, "display_name", None) or getattr(from_step, "step_key", "a step")
    notified: list[str] = []
    for uid in users:
        if uid == ticket.assigned_to_user_id:
            continue  # the new OIC already received the ESCALATED notification
        if ticket.is_seah and not user_holds_seah_role(db, uid):
            continue  # SEAH leak-proof — a non-SEAH supervisor receives nothing
        _add_event(
            db, ticket, "ESCALATION_SUPERVISOR_NOTICE",
            step_id=ticket.current_step_id,
            note=f"A ticket escalated off {label}; you are its supervisor.",
            seen=False,
            notify_user_id=uid,
            created_by="system",
            actor_role="system",
        )
        _ensure_viewer(db, ticket.ticket_id, uid, "supervisor", "system")
        notified.append(uid)
    return notified


# ── Core escalation ───────────────────────────────────────────────────────────

def escalate_ticket(
    ticket: Ticket,
    db: Session,
    *,
    triggered_by: str = "SLA_AUTO",
    note: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    escalation_date: Optional[str] = None,
    persons_involved: Optional[list[str]] = None,
    escalation_notes: Optional[str] = None,
) -> Optional[TicketEvent]:
    """
    Advance ticket to the next workflow step.

    triggered_by: "SLA_AUTO" | "MANUAL" | "GRC_DECIDE"

    Returns the ESCALATED TicketEvent, or None if ticket is at final step (or, for
    SLA_AUTO, if the idempotence re-check finds it no longer needs escalation).
    Does NOT commit — caller must db.commit() after.
    """
    # HR-04 idempotence guard (SLA_AUTO only): the watchdog selects breach candidates
    # under a FOR UPDATE lock, but re-verify under that lock that the ticket is *still*
    # breached on its current step before mutating. If a manual escalation or an earlier
    # loop iteration already advanced it (step_started_at resets ⇒ no deadline ⇒ not
    # breached), skip rather than double-escalate. Manual/GRC callers are intentionally
    # exempt — an officer may escalate a ticket that has not breached SLA.
    if triggered_by == "SLA_AUTO":
        current_step = get_current_step(ticket, db)
        if not is_sla_breached(ticket, current_step):
            logger.info(
                "ticket_id=%s no longer SLA-breached under lock — skipping auto-escalation",
                ticket.ticket_id,
            )
            return None

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

    close_open_episode(
        db,
        ticket,
        "ESCALATED",
        ended_at=_now(),
    )

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
    ticket.sla_breached = False
    ticket.step_started_at = None  # clock resets at new step; starts on ACKNOWLEDGE
    ticket.updated_by_user_id = created_by_user_id or "system"

    # Auto-add informed_roles + observer_roles from the new step
    _apply_step_tier_roles(db, ticket, next_step)

    # Auto-assign to the least-loaded officer at the next step's role
    new_assigned = auto_assign_for_workflow_step(
        step_role_key=next_step.assigned_role_key,
        organization_id=ticket.organization_id,
        location_code=ticket.location_code,
        project_code=ticket.project_code,
        db=db,
        ticket_package_id=ticket.package_id,
        supervisor_role=next_step.supervisor_role,
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
            **(
                {
                    "escalation_date": escalation_date,
                    "persons_involved": persons_involved or [],
                    "escalation_notes": escalation_notes,
                }
                if triggered_by == "MANUAL" and escalation_notes
                else {}
            ),
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
    from ticketing.services.chart_behaviors import user_can_see_seah

    member_ids = get_grc_member_user_ids(
        ticket.organization_id, ticket.location_code, db
    )
    notified = 0
    for member_id in member_ids:
        if member_id == convened_by_user_id:
            continue  # don't notify self
        # R1 SEAH leak-proof: GRC members are standard roles — a non-SEAH member must not be
        # notified of (and thereby learn of) a SEAH case.
        if ticket.is_seah and not user_can_see_seah(db, member_id):
            continue
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
        notified += 1

    logger.info(
        "GRC convened: ticket_id=%s notified %d members",
        ticket.ticket_id, notified,
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
    Legacy GRC decision path — **no longer exposed via API** (use RESOLVE / ESCALATE).

    Kept for historical event replay and tests. GRC chairs close cases with RESOLVE
    + resolution record per docs/ticketing_system/08_ticket_resolution_and_case_summary.md.

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

    # HR-04: lock candidate rows FOR UPDATE SKIP LOCKED so overlapping watchdog runs,
    # redelivered tasks, and the manual-escalation API path can never process the same
    # ticket concurrently — a locked ticket is silently skipped this pass and picked up
    # on the next one. The lock is held until the caller's transaction commits/rolls back.
    candidates = db.execute(
        select(Ticket)
        .where(
            Ticket.status_code.in_(active_statuses),
            Ticket.is_deleted.is_(False),
            Ticket.current_step_id.is_not(None),
            Ticket.step_started_at.is_not(None),
            Ticket.sla_breached.is_(False),
        )
        .with_for_update(skip_locked=True)
    ).scalars().all()

    if not candidates:
        return []

    # HR-04: bulk-load the current WorkflowSteps in one query (kills the per-ticket N+1).
    # These land in the session identity map, so later db.get(WorkflowStep, ...) calls in
    # run_sla_check / escalate_ticket resolve without extra round-trips.
    step_ids = {t.current_step_id for t in candidates if t.current_step_id}
    steps_by_id = {
        s.step_id: s
        for s in db.execute(
            select(WorkflowStep).where(WorkflowStep.step_id.in_(step_ids))
        ).scalars().all()
    }

    breached = []
    for ticket in candidates:
        step = steps_by_id.get(ticket.current_step_id)
        if step and is_sla_breached(ticket, step):
            breached.append(ticket)

    return breached


def run_sla_check(db: Session) -> dict:
    """
    Check all active tickets for SLA breach and escalate as needed.
    Returns a summary dict for logging.
    """
    from ticketing.models.workflow import WorkflowStep

    tickets = get_tickets_needing_escalation(db)
    escalated = 0
    final_step = 0
    skipped = 0
    errors = 0
    escalated_pairs: list = []  # (ticket, from_step) for the post-commit supervisor notify

    for ticket in tickets:
        try:
            # HR-04: each ticket's escalation runs in its own SAVEPOINT. If anything
            # throws mid-escalation (after mutating current_step_id/status but before the
            # ESCALATED event/assignment are written), roll back only this ticket's changes
            # and continue — the outer commit then persists ONLY fully-escalated tickets,
            # never a step-advanced ticket with no audit event and no assignee.
            with db.begin_nested():
                step = (
                    db.get(WorkflowStep, ticket.current_step_id)
                    if ticket.current_step_id
                    else None
                )
                ensure_breach_episode(db, ticket, step, triggered_by="SLA_AUTO_ESCALATE")
                result = escalate_ticket(
                    ticket, db,
                    triggered_by="SLA_AUTO",
                    note=None,
                )
                if result is not None:
                    outcome = "escalated"
                elif get_next_step(ticket, db) is None:
                    # Genuine final-step breach — mark breached but don't escalate.
                    ensure_breach_episode(db, ticket, step, triggered_by="SLA_WATCHDOG")
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
                    outcome = "final"
                else:
                    # Idempotence guard skipped it (no longer breached under the lock).
                    outcome = "skipped"
            # Savepoint released cleanly — tally only after the nested tx succeeds.
            if outcome == "escalated":
                escalated += 1
                escalated_pairs.append((ticket, step))  # step = the step it escalated OFF
            elif outcome == "final":
                final_step += 1
            else:
                skipped += 1
        except Exception as exc:
            # begin_nested() has already rolled the savepoint back on exception.
            logger.exception(
                "Error escalating ticket_id=%s: %s", ticket.ticket_id, exc
            )
            errors += 1

    if escalated or final_step:
        db.commit()
    else:
        # Release FOR UPDATE locks / any skipped-episode bookkeeping cleanly.
        db.rollback()

    # OC-04 §5.5: notify each escalated step's resolved supervisor AFTER the escalation
    # commits (courtesy side-effect, SEAH-suppressed in the helper). A fresh transaction —
    # never re-opens the HR-04-hardened escalation savepoints above.
    if escalated_pairs:
        for tkt, from_step in escalated_pairs:
            try:
                notify_escalation_supervisor(db, tkt, from_step)
            except Exception:  # pragma: no cover - a notify failure must not undo escalation
                logger.exception("supervisor-notify failed for ticket_id=%s", tkt.ticket_id)
        db.commit()

    summary = {
        "checked": len(tickets),
        "escalated": escalated,
        "final_step_breach": final_step,
        "skipped": skipped,
        "errors": errors,
    }
    logger.info("SLA check complete: %s", summary)
    return summary
