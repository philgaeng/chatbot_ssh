"""XLSX export helpers shared by HTTP routes and Celery quarterly reports."""
from __future__ import annotations

import io

from ticketing.services.report_rows import FIELD_LABELS, MAX_EXPORT_ROWS


def pivot_workbook_bytes(pivot_result: dict) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pivot"
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True)
    group_fill = PatternFill("solid", fgColor="D6E4F0")
    group_font = Font(bold=True)

    columns = pivot_result["columns"]
    rows = pivot_result["rows"]
    header_rows = pivot_result.get("header_rows") or []
    data_start = 1
    row_dim_count = len(pivot_result.get("row_dims") or [])

    if header_rows:
        excel_row = 1
        for hi, hrow in enumerate(header_rows):
            excel_col = row_dim_count + 1 if hi > 0 and row_dim_count else 1
            for cell in hrow:
                c = ws.cell(row=excel_row, column=excel_col, value=cell.get("text", ""))
                rs = int(cell.get("row_span") or 1)
                cs = int(cell.get("col_span") or 1)
                if rs > 1 or cs > 1:
                    ws.merge_cells(
                        start_row=excel_row,
                        start_column=excel_col,
                        end_row=excel_row + rs - 1,
                        end_column=excel_col + cs - 1,
                    )
                if cell.get("kind") == "col_group":
                    c.fill = group_fill
                    c.font = group_font
                    c.alignment = Alignment(horizontal="center")
                elif cell.get("kind") == "row_dim":
                    c.fill = header_fill
                    c.font = header_font
                else:
                    c.font = Font(bold=True)
                excel_col += cs
            excel_row += 1
        data_start = excel_row
    else:
        labels = [FIELD_LABELS.get(c, c) for c in columns]
        for col, label in enumerate(labels, 1):
            cell = ws.cell(row=1, column=col, value=label)
            cell.fill = header_fill
            cell.font = header_font
        data_start = 2

    for r, row in enumerate(rows[:MAX_EXPORT_ROWS], data_start):
        for c, key in enumerate(columns, 1):
            ws.cell(row=r, column=c, value=row.get(key, ""))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
