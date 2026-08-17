# SPDX-License-Identifier: Apache-2.0

"""Officer action + messaging endpoints.

  POST /tickets/{ticket_id}/actions   — validate + authz → engine dispatch table
  POST /tickets/{ticket_id}/reply     — officer reply via chatbot orchestrator
  POST /tickets/{ticket_id}/inbound   — inbound complainant follow-up (API key)

Action logic itself lives in ``ticketing.engine.ticket_actions`` (pure, no HTTP);
this module validates, guards, dispatches, and applies the ``ActionOutcome``.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db, verify_api_key
from ticketing.api.ticket_access import require_ticket_access
from ticketing.api.schemas.ticket import (
    InboundMessageRequest,
    InboundMessageResponse,
    TicketActionRequest,
    TicketActionResponse,
    TicketReplyRequest,
    TicketReplyResponse,
)
from ticketing.clients.orchestrator import send_message_to_complainant
from ticketing.engine.events import _add_event
from ticketing.engine.ticket_actions import (
    ACTION_HANDLERS,
    ActionError,
    _auto_acknowledge_if_assigned_actor,
)
from ticketing.engine.workflow_engine import get_current_step
from ticketing.constants.tiers import SUPERVISOR
from ticketing.services.tier_permissions import user_holds_tier_on_step
from ticketing.tasks.notifications import enqueue_assignment_notifications, notify_complainant
from ticketing.tasks.llm import generate_findings, generate_resolved_case_summary, translate_note
from ticketing.models.ticket import Ticket

from ._shared import _actor_role, _enqueue_celery

logger = logging.getLogger(__name__)
router = APIRouter()


def _can_resolve_ticket(db: Session, ticket: Ticket, current_user: CurrentUser) -> bool:
    """Assignee, admin, or current step Supervisor tier may resolve (spec §2.1 Q1-b).

    The supervisor branch is the Supervisor-tier membership axis (DESIGN-cast-model §6):
    ``RESOLVE`` is in the Supervisor tier's capabilities, gated by holding that tier.
    """
    if current_user.is_admin:
        return True
    if ticket.assigned_to_user_id and current_user.matches_assignee(ticket.assigned_to_user_id):
        return True
    step = get_current_step(ticket, db)
    if step and user_holds_tier_on_step(step, current_user.role_keys, SUPERVISOR):
        return True
    return False


VALID_ACTIONS = {
    "ACKNOWLEDGE", "ESCALATE", "RESOLVE", "NOTE", "FIELD_REPORT",
    "GRC_CONVENE", "REASSIGNMENT_REQUESTED",
}


@router.post(
    "/tickets/{ticket_id}/actions",
    response_model=TicketActionResponse,
    summary="Perform an officer action on a ticket",
    description=(
        "**action_type** values:\n"
        "- `ACKNOWLEDGE` — officer takes ownership, starts SLA clock\n"
        "- `ESCALATE` — manual escalation to next workflow step\n"
        "- `RESOLVE` — mark ticket resolved (resolution record — see spec §2)\n"
        "- `NOTE` — add internal officer note (invisible to complainant)\n"
        "- `GRC_CONVENE` — GRC chair schedules hearing, notifies all GRC members\n"
    ),
)
def perform_action(
    ticket_id: str,
    payload: TicketActionRequest,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> TicketActionResponse:
    action = payload.action_type.upper()
    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action_type={action!r}. Valid: {sorted(VALID_ACTIONS)}",
        )

    # Assignment guard — only the assigned officer (or admin) may change ticket status.
    # NOTE is always allowed so any officer can add internal notes.
    ASSIGNMENT_REQUIRED = {"ACKNOWLEDGE", "ESCALATE", "RESOLVE", "GRC_CONVENE", "REASSIGNMENT_REQUESTED"}
    if action in ASSIGNMENT_REQUIRED and not current_user.is_admin:
        if action == "RESOLVE":
            if not _can_resolve_ticket(db, ticket, current_user):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Only the assigned officer, step supervisor, or an admin "
                        "can resolve this ticket."
                    ),
                )
        elif ticket.assigned_to_user_id and not current_user.matches_assignee(
            ticket.assigned_to_user_id
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Only the assigned officer ({ticket.assigned_to_user_id}) "
                    "can change the status of this ticket. You can still add notes."
                ),
            )

    # Status guard — once ESCALATED only ACKNOWLEDGE or NOTE are allowed until
    # the next-level officer acknowledges and takes ownership.
    ESCALATED_BLOCKED = {"ESCALATE", "RESOLVE", "GRC_CONVENE"}
    if ticket.status_code == "ESCALATED" and action in ESCALATED_BLOCKED:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot perform {action!r} on an ESCALATED ticket. "
                "Acknowledge the ticket first to take ownership at the new level."
            ),
        )

    old_status = ticket.status_code

    handler = ACTION_HANDLERS[action]  # action ∈ VALID_ACTIONS ⇒ always present
    try:
        outcome = handler(db, ticket, current_user, payload)
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    ticket = outcome.ticket  # ESCALATE re-fetches under a row lock; others echo it back
    event = outcome.event

    # L2: reopen clears archive flags when leaving RESOLVED/CLOSED
    if old_status in ("RESOLVED", "CLOSED") and ticket.status_code not in ("RESOLVED", "CLOSED"):
        from ticketing.services.archiving import clear_archive_on_reopen

        clear_archive_on_reopen(db, ticket)

    db.commit()
    db.refresh(ticket)

    # OC-04 §5.5: notify the escalated step's resolved supervisor after commit (SEAH-
    # suppressed in the helper). Side-effect only — never alters assignment/target.
    if outcome.supervisor_notify_from_step is not None:
        from ticketing.engine.escalation import notify_escalation_supervisor

        try:
            notify_escalation_supervisor(db, ticket, outcome.supervisor_notify_from_step)
            db.commit()
        except Exception:  # pragma: no cover - notify failure must not fail the escalation
            db.rollback()

    if outcome.assignment_notify:
        new_uid, old_uid, assign_event = outcome.assignment_notify
        enqueue_assignment_notifications(
            ticket.ticket_id,
            new_uid,
            ticket.current_step_id,
            old_assigned=old_uid,
            event=assign_event,
        )

    # Fire async complainant notification after commit so the task sees the updated ticket
    if outcome.notify_complainant_text:
        _enqueue_celery(
            notify_complainant,
            ticket.ticket_id,
            outcome.notify_complainant_text,
            action,  # event_type label in the notification log
        )

    # Fire LLM translation task for NOTE events (7a — translate to English for supervisors)
    if outcome.translate_note_event_id:
        _enqueue_celery(translate_note, outcome.translate_note_event_id)

    # Fire findings generation on RESOLVE (7b — AI summary for GRC/supervisors)
    if outcome.generate_findings:
        _enqueue_celery(generate_findings, ticket.ticket_id)
    if outcome.translate_resolution_event_id:
        _enqueue_celery(translate_note, outcome.translate_resolution_event_id)
    if outcome.generate_resolved_summary:
        _enqueue_celery(generate_resolved_case_summary, ticket.ticket_id)

    return TicketActionResponse(
        ticket_id=ticket.ticket_id,
        action_type=action,
        new_status_code=ticket.status_code,
        current_step_id=ticket.current_step_id,
        event_id=event.event_id,
    )


@router.post(
    "/tickets/{ticket_id}/reply",
    response_model=TicketReplyResponse,
    summary="Send officer reply to complainant via chatbot orchestrator",
)
def reply_to_complainant(
    ticket_id: str,
    payload: TicketReplyRequest,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> TicketReplyResponse:
    # Only the assigned officer (or admin) may reply to the complainant.
    if not current_user.is_admin:
        if ticket.assigned_to_user_id and ticket.assigned_to_user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned officer can reply to the complainant.",
            )

    _auto_acknowledge_if_assigned_actor(db, ticket, current_user)

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
    _enqueue_celery(translate_note, event.event_id)

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
