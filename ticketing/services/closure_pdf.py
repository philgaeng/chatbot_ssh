"""Complainant closure PDF (reportlab — spec §3.9.5)."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _p(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_closure_pdf(public_json: dict[str, Any], grievance_id: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>GRM Case Closure</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Reference: {_p(grievance_id)}", styles["Normal"]))
    story.append(Paragraph(f"Project: {_p(public_json.get('project_name', ''))}", styles["Normal"]))
    if public_json.get("resolved_at"):
        story.append(Paragraph(f"Resolved: {_p(public_json['resolved_at'][:10])}", styles["Normal"]))
    story.append(Spacer(1, 16))

    story.append(Paragraph("<b>Your complaint</b>", styles["Heading2"]))
    story.append(Paragraph(_p(public_json.get("original_complaint", "")), styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Outcome</b>", styles["Heading2"]))
    story.append(Paragraph(_p(public_json.get("resolution_category_label", "")), styles["Normal"]))
    story.append(Paragraph(_p(public_json.get("resolution_text_public", "")), styles["Normal"]))
    story.append(Spacer(1, 12))

    findings = public_json.get("findings_summary_public") or ""
    if findings:
        story.append(Paragraph("<b>Summary</b>", styles["Heading2"]))
        story.append(Paragraph(_p(findings), styles["Normal"]))

    doc.build(story)
    return buf.getvalue()
