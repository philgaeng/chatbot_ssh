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


@router.get("/public/closure/{token}")
def get_public_closure(token: str, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        select(TicketResolvedSummary).where(
            TicketResolvedSummary.closure_public_token == token
        )
    ).scalar_one_or_none()
    if not row or not row.summary_public_json:
        raise HTTPException(status_code=404, detail="Closure not found")
    if row.generation_status != "complete":
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
    if row.generation_status != "complete":
        raise HTTPException(
            status_code=503,
            detail="PDF not available until summary generation completes",
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
