"""Resolved-case summary + AI findings endpoints.

  GET  /tickets/{ticket_id}/resolved-summary
  POST /tickets/{ticket_id}/resolved-summary   — (re)generate closure summary
  POST /tickets/{ticket_id}/findings           — (re)generate AI case findings
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.ticket_access import require_ticket_access
from ticketing.engine.ticket_actions import _has_resolution_record_event
from ticketing.tasks.llm import generate_findings, generate_resolved_case_summary
from ticketing.models.ticket import Ticket
from ticketing.models.ticket_resolved_summary import TicketResolvedSummary

from ._shared import _enqueue_celery

logger = logging.getLogger(__name__)
router = APIRouter()


# Roles permitted to regenerate findings (supervisors + senior observers only)
_FINDINGS_ROLES = {
    "grc_chair", "adb_hq_safeguards", "adb_hq_project",
    "adb_hq_exec", "adb_national_project_director",
    "super_admin", "local_admin",
}


@router.get("/tickets/{ticket_id}/resolved-summary")
def get_resolved_summary(
    ticket_id: str,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    row = db.get(TicketResolvedSummary, ticket_id)
    if not row:
        if ticket.status_code in ("RESOLVED", "CLOSED") and not _has_resolution_record_event(db, ticket_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Resolved summary cannot be generated because this ticket has no "
                    "resolution record event."
                ),
            )
        raise HTTPException(status_code=404, detail="Resolved summary not found")
    from ticketing.services.resolved_summary_builder import build_closure_display_context

    display = build_closure_display_context(
        db,
        ticket,
        row.summary_json if isinstance(row.summary_json, dict) else None,
        row.summary_public_json if isinstance(row.summary_public_json, dict) else None,
    )
    return {
        "ticket_id": ticket_id,
        "grievance_id": row.grievance_id,
        "generation_status": row.generation_status,
        "generation_model": row.generation_model,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "closure_public_url": row.closure_public_url,
        "summary_json": row.summary_json,
        "summary_public_json": row.summary_public_json,
        "summary_text_primary": row.summary_text_primary,
        "primary_language": row.primary_language,
        "case_header": display["case_header"],
        "officer_metrics": display["officer_metrics"],
    }


@router.post(
    "/tickets/{ticket_id}/resolved-summary",
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_resolved_summary(
    ticket_id: str,
    force: bool = Query(False),
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    has_findings_role = current_user.is_admin or bool(
        set(current_user.role_keys) & _FINDINGS_ROLES
    )
    if not has_findings_role:
        raise HTTPException(status_code=403, detail="Supervisor role required")
    if ticket.status_code in ("RESOLVED", "CLOSED") and not _has_resolution_record_event(db, ticket_id):
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot generate summary: no resolution record is saved for this ticket. "
                "Add or redo resolution details in the case thread first."
            ),
        )
    _enqueue_celery(generate_resolved_case_summary, ticket_id, force=force)
    return {"ticket_id": ticket_id, "status": "queued"}


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
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
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

    _enqueue_celery(generate_findings, ticket_id)
    logger.info(
        "Findings generation queued: ticket_id=%s requested_by=%s",
        ticket_id, current_user.user_id,
    )
    return {
        "ticket_id": ticket_id,
        "status": "queued",
        "message": "Findings generation has been queued. Poll GET /tickets/{id} for the result.",
    }
