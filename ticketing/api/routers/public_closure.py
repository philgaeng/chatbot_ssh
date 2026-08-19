# SPDX-License-Identifier: Apache-2.0

"""Public complainant closure page API (no auth — spec §3.9.6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.base import get_db
from ticketing.models.ticket_resolved_summary import TicketResolvedSummary
from ticketing.services.closure_pdf import build_closure_pdf

router = APIRouter()


def _is_publishable(row) -> bool:
    """
    Is there something here a complainant can usefully read?

    ⚠ **This used to ask a different question — `generation_status == "complete"`, i.e. *did the AI
    succeed*** — and the difference cost complainants their closure document (D-36). When the model
    call returns nothing, `build_public_summary_json` still produces the whole deterministic record:
    the reference number, the dates, how long it took, who resolved it, the original complaint, the
    resolution category, and **the officer's own resolution text**, which is the part that says what
    was actually decided. Only the AI-written investigation narrative is missing.

    Withholding all of that because a model was unavailable means the complainant is told their case
    is resolved and then handed a 404. So publishability is now a property of the **document**:
    there must be a public payload and it must carry a resolution the person can read.
    """
    payload = row.summary_public_json or {}
    return bool(payload.get("resolution_text_public"))


@router.get("/public/closure/{token}")
def get_public_closure(token: str, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        select(TicketResolvedSummary).where(
            TicketResolvedSummary.closure_public_token == token
        )
    ).scalar_one_or_none()
    if not row or not row.summary_public_json:
        raise HTTPException(status_code=404, detail="Closure not found")
    if not _is_publishable(row):
        raise HTTPException(status_code=404, detail="Closure summary not ready yet")
    return {
        "grievance_id": row.grievance_id,
        "primary_language": row.primary_language,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "summary_public_json": row.summary_public_json,
        "summary_text_primary": row.summary_text_primary,
    }


@router.get("/public/closure/{token}/pdf")
def get_public_closure_pdf(token: str, db: Session = Depends(get_db)) -> Response:
    row = db.execute(
        select(TicketResolvedSummary).where(
            TicketResolvedSummary.closure_public_token == token
        )
    ).scalar_one_or_none()
    if not row or not row.summary_public_json:
        raise HTTPException(status_code=404, detail="Closure not found")
    if not _is_publishable(row):
        raise HTTPException(
            status_code=503,
            detail="PDF not available until the closure record has a resolution",
        )
    try:
        pdf_bytes = build_closure_pdf(row.summary_public_json, row.grievance_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"PDF generation failed: {exc}") from exc
    filename = f"GRM-closure-{row.grievance_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
