"""
Quarterly XLSX report endpoint.

Session 3 will implement the full Celery-driven scheduled report.
This endpoint provides an on-demand export for officers.
"""
import io
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db
from ticketing.models.ticket import Ticket, TicketEvent

router = APIRouter()


def _build_xlsx(tickets: list[Ticket]) -> bytes:
    """Build a quarterly GRM report as XLSX bytes (openpyxl)."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "GRM Report"

    headers = [
        "Reference No.",
        "Date Submitted",
        "Nature / Categories",
        "AI Summary",
        "Location",
        "Organization",
        "Escalation Level",
        "Current Status",
        "SLA Breached?",
        "Instance",
        "Days Open",
    ]

    # Header styling
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True)
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        ws.column_dimensions[cell.column_letter].width = max(15, len(header) + 4)

    for row_num, ticket in enumerate(tickets, 2):
        days_open = (date.today() - ticket.created_at.date()).days if ticket.created_at else ""
        ws.cell(row=row_num, column=1, value=ticket.grievance_id)
        ws.cell(row=row_num, column=2, value=ticket.created_at.strftime("%Y-%m-%d") if ticket.created_at else "")
        ws.cell(row=row_num, column=3, value=ticket.grievance_categories or "")
        ws.cell(row=row_num, column=4, value=ticket.grievance_summary or "")
        ws.cell(row=row_num, column=5, value=ticket.grievance_location or ticket.location_code or "")
        ws.cell(row=row_num, column=6, value=ticket.organization_id)
        ws.cell(row=row_num, column=7, value=ticket.current_step_id or "")
        ws.cell(row=row_num, column=8, value=ticket.status_code)
        ws.cell(row=row_num, column=9, value="Y" if ticket.sla_breached else "N")
        ws.cell(row=row_num, column=10, value="SEAH" if ticket.is_seah else "Standard")
        ws.cell(row=row_num, column=11, value=days_open)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


@router.get(
    "/reports/export",
    summary="Download quarterly GRM report as XLSX",
    response_class=StreamingResponse,
)
def export_report(
    date_from: Optional[date] = Query(None, description="Start date (default: 90 days ago)"),
    date_to: Optional[date] = Query(None, description="End date (default: today)"),
    organization_id: Optional[str] = Query(None),
    include_seah: bool = Query(False, description="Include SEAH tickets (requires SEAH role)"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    if include_seah and not current_user.can_see_seah:
        include_seah = False  # silently strip — no error, just omit

    if date_from is None:
        date_from = date.today() - timedelta(days=90)
    if date_to is None:
        date_to = date.today()

    from sqlalchemy import func
    q = (
        select(Ticket)
        .where(
            Ticket.is_deleted.is_(False),
            func.date(Ticket.created_at) >= date_from,
            func.date(Ticket.created_at) <= date_to,
        )
        .order_by(Ticket.created_at)
    )
    if not include_seah:
        q = q.where(Ticket.is_seah.is_(False))
    if organization_id:
        q = q.where(Ticket.organization_id == organization_id)

    tickets = db.execute(q).scalars().all()
    xlsx_bytes = _build_xlsx(tickets)

    filename = f"grm_report_{date_from}_{date_to}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
