"""Sensitive-data disclosure endpoints (PII broker + vault reveal).

  GET  /tickets/{ticket_id}/pii            — brokered complainant PII from backend
  POST /tickets/{ticket_id}/reveal         — open a vault reveal session
  POST /tickets/{ticket_id}/reveal/close   — close a vault reveal session
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel as _BaseModel
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.ticket_access import require_ticket_access
from ticketing.engine.events import _add_event
from ticketing.models.ticket import Ticket

from ._shared import _actor_role

logger = logging.getLogger(__name__)
router = APIRouter()


class RevealRequest(_BaseModel):
    reason_code: str
    reason_text: str = ""


class RevealCloseRequest(_BaseModel):
    reveal_session_id: str
    close_reason: str = "user_closed"


@router.get(
    "/tickets/{ticket_id}/pii",
    summary="Fetch complainant PII from the grievance backend (brokered — no direct browser call)",
)
def get_ticket_pii(
    ticket_id: str,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    from ticketing.clients.grievance_api import get_grievance_detail

    # HR-02: previously SEAH-gated but NOT jurisdiction-gated — any officer could pull
    # PII for any standard ticket by ID. require_ticket_access adds the scope gate.
    # PII masking rules (TP-15: standard decrypted / SEAH masked) below are unchanged.
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

    from ticketing.services.pii_vault import grievance_pii_for_officer_card

    # Standard GRM: decrypted contact in card. SEAH: masked until vault reveal.
    return {
        "grievance_id": ticket.grievance_id,
        "pii_masked": bool(ticket.is_seah),
        **grievance_pii_for_officer_card(
            grievance,
            mask_sensitive_contact=bool(ticket.is_seah),
        ),
    }


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
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    from ticketing.clients.grievance_api import begin_reveal_session
    from ticketing.services.demo_reveal import ticket_reveal_fallback_grievance

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
        fallback_grievance=ticket_reveal_fallback_grievance(ticket),
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
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    from ticketing.clients.grievance_api import close_reveal_session

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
