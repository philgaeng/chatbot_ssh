"""Assemble officer + public closure documents (spec §3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import math
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ticketing.clients.grievance_api import get_grievance_detail
from ticketing.config.settings import get_settings
from ticketing.constants.resolution import resolution_category_label
from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_resolved_summary import TicketResolvedSummary
from ticketing.models.workflow import WorkflowStep
from ticketing.services.overdue_episodes import load_episodes_for_tickets, overdue_days_display
from ticketing.services.pii_vault import grievance_pii_masked, reveal_field
from ticketing.services.report_rows import _fetch_auxiliary_maps, build_report_row, normalize_complaint_category

_MODEL_STANDARD = "gpt-4o-mini"
_MODEL_SEAH = "gpt-4o"
_PHONE_NOTE_RE = re.compile(r"\b(call|calls|called|phone|voic(?:e|ing))\b", re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_address(g: dict[str, Any]) -> str:
    parts = [
        g.get("address") or g.get("complainant_address"),
        g.get("village") or g.get("complainant_village"),
        g.get("ward") or g.get("complainant_ward"),
        g.get("municipality") or g.get("complainant_municipality"),
        g.get("district") or g.get("complainant_district"),
        g.get("province") or g.get("complainant_province"),
    ]
    return ", ".join(str(p).strip() for p in parts if p and str(p).strip())


def _unwrap_grievance(raw: dict) -> dict:
    return (raw.get("data") or {}).get("grievance") or raw


def _officer_display_name(db: Session, user_id: Optional[str]) -> str:
    if not user_id:
        return "Officer"
    return user_id


def _collect_officers(db: Session, ticket_id: str, ticket: Ticket) -> list[dict]:
    events = db.execute(
        select(TicketEvent)
        .where(TicketEvent.ticket_id == ticket_id)
        .order_by(TicketEvent.created_at)
    ).scalars().all()
    seen: set[str] = set()
    out: list[dict] = []
    for ev in events:
        uid = ev.created_by_user_id
        if not uid or uid in seen:
            continue
        seen.add(uid)
        participation = "noted"
        if uid == ticket.assigned_to_user_id:
            participation = "assigned"
        if ev.event_type == "ACKNOWLEDGED" and uid == ev.created_by_user_id:
            participation = "acknowledged"
        if ev.event_type == "ESCALATED":
            participation = "escalated"
        if ev.event_type == "RESOLVED":
            participation = "resolved"
        out.append({
            "user_id": uid,
            "display_name": _officer_display_name(db, uid),
            "role_key": ev.actor_role or "",
            "participation": participation,
        })
    return out


def _latest_resolution_event(db: Session, ticket_id: str) -> Optional[TicketEvent]:
    events = db.execute(
        select(TicketEvent)
        .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "NOTE_ADDED")
        .order_by(TicketEvent.created_at.desc())
    ).scalars().all()
    for ev in events:
        payload = ev.payload or {}
        if payload.get("is_resolution_record"):
            return ev
    return None


def _notes_for_llm(db: Session, ticket_id: str) -> tuple[list[dict], list[dict], Optional[TicketEvent]]:
    events = db.execute(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "NOTE_ADDED",
        )
        .order_by(TicketEvent.created_at)
    ).scalars().all()
    field_reports: list[dict] = []
    other_notes: list[dict] = []
    resolution_ev: Optional[TicketEvent] = None
    for ev in events:
        payload = ev.payload or {}
        if payload.get("is_resolution_record"):
            resolution_ev = ev
            continue
        entry = {
            "at": ev.created_at.isoformat() if ev.created_at else None,
            "by_role": ev.actor_role,
            "text": (payload.get("translation_en") or ev.note or ""),
        }
        if payload.get("is_field_report"):
            field_reports.append(entry)
        elif payload.get("internal"):
            other_notes.append(entry)
    return field_reports, other_notes, resolution_ev


def assemble_summary_input(db: Session, ticket_id: str) -> dict[str, Any]:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise ValueError(f"Ticket not found: {ticket_id}")

    grievance_raw: dict = {}
    grievance: dict = {}
    backend_down = False
    try:
        grievance_raw = get_grievance_detail(ticket.grievance_id)
        grievance = _unwrap_grievance(grievance_raw)
    except Exception:
        backend_down = True

    pii = grievance_pii_masked(grievance) if grievance else {}
    if backend_down:
        pii["_backend_unavailable"] = True

    original = ""
    if grievance:
        original = reveal_field(grievance.get("grievance_description")) or ""
    if not original:
        original = ticket.grievance_summary or ""

    field_reports, other_notes, resolution_ev = _notes_for_llm(db, ticket_id)
    res_payload = (resolution_ev.payload or {}) if resolution_ev else {}
    category = res_payload.get("resolution_category", "")
    resolution_text = resolution_ev.note if resolution_ev else ""

    project_name = ticket.project_code or ""
    package_code = None
    package_name = None
    if ticket.project_id:
        proj = db.get(Project, ticket.project_id)
        if proj:
            project_name = proj.name or proj.short_code or project_name
        if ticket.package_id:
            pkg = db.get(ProjectPackage, ticket.package_id)
            if pkg:
                package_code = pkg.package_code
                package_name = pkg.name

    primary_language = "ne" if _looks_nepali(original) else "en"

    return {
        "ticket": ticket,
        "ticket_id": ticket_id,
        "grievance_id": ticket.grievance_id,
        "is_seah": ticket.is_seah,
        "field_reports": field_reports,
        "other_notes": other_notes,
        "resolution_ev": resolution_ev,
        "resolution": {
            "category": category,
            "category_label": resolution_category_label(category) if category else "",
            "text": resolution_text,
        },
        "original_complaint": original,
        "pii": pii,
        "officers": _collect_officers(db, ticket_id, ticket),
        "project": {
            "project_id": ticket.project_id,
            "project_code": ticket.project_code,
            "project_name": project_name,
            "package_id": ticket.package_id,
            "package_code": package_code,
            "package_name": package_name,
            "organization_id": ticket.organization_id,
            "location_code": ticket.location_code,
        },
        "primary_language": primary_language,
        "backend_down": backend_down,
    }


def _looks_nepali(text: str) -> bool:
    if not text:
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return (non_ascii / max(len(text), 1)) > 0.05


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _resolution_duration_days(filed_at: Any, resolved_at: Any) -> Optional[int]:
    filed_dt = _parse_iso_datetime(filed_at)
    resolved_dt = _parse_iso_datetime(resolved_at)
    if not filed_dt or not resolved_dt:
        return None
    delta_seconds = (resolved_dt - filed_dt).total_seconds()
    if delta_seconds <= 0:
        return 0
    return max(1, math.ceil(delta_seconds / 86400))


def build_summary_json(
    db: Session,
    data: dict[str, Any],
    llm_out: Optional[dict],
) -> dict[str, Any]:
    ticket: Ticket = data["ticket"]
    resolution_ev: Optional[TicketEvent] = data["resolution_ev"]
    llm_out = llm_out or {}
    resolved_at = resolution_ev.created_at if resolution_ev else _now()

    findings = {
        "field_reports_count": len(data["field_reports"]),
        "field_reports_digest_en": llm_out.get("field_reports_digest_en") or "",
        "other_notes_digest_en": llm_out.get("other_notes_digest_en") or "",
        "combined_digest_en": llm_out.get("combined_digest_en") or "",
        "ai_summary_en": ticket.ai_summary_en,
    }

    return {
        "version": 1,
        "generated_at": _now().isoformat(),
        "project": data["project"],
        "officers_involved": data["officers"],
        "complainant": {
            "complainant_id": ticket.complainant_id,
            "name": data["pii"].get("complainant_name"),
            "phone": data["pii"].get("phone_number"),
            "email": data["pii"].get("email"),
            "address_line": data["pii"].get("address"),
            "village": data["pii"].get("village"),
            "ward": data["pii"].get("ward"),
            "municipality": data["pii"].get("municipality"),
            "district": data["pii"].get("district"),
            "province": data["pii"].get("province"),
            "address_full": _format_address(data["pii"]),
            "_backend_unavailable": data["pii"].get("_backend_unavailable", False),
        },
        "complaint": {
            "filed_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "grievance_id": ticket.grievance_id,
            "categories": ticket.grievance_categories,
            "original_complaint": data["original_complaint"],
            "original_summary": ticket.grievance_summary,
        },
        "resolution": {
            "resolved_at": resolved_at.isoformat(),
            "resolved_by_user_id": ticket.updated_by_user_id,
            "resolved_by_display_name": _officer_display_name(
                db, ticket.updated_by_user_id
            ),
            "category": data["resolution"]["category"],
            "category_label": data["resolution"]["category_label"],
            "text": data["resolution"]["text"],
        },
        "findings_summary": findings,
        "workflow": {
            "final_status": ticket.status_code,
            "levels_reached": [
                ticket.current_step.display_name if ticket.current_step else None
            ],
            "sla_breached": ticket.sla_breached,
            "is_seah": ticket.is_seah,
        },
        "llm": {
            "model": _MODEL_SEAH if ticket.is_seah else _MODEL_STANDARD,
            "generated_at": _now().isoformat(),
        },
    }


def build_public_summary_json(
    data: dict[str, Any],
    summary_json: dict[str, Any],
    llm_out: Optional[dict],
) -> dict[str, Any]:
    llm_out = llm_out or {}
    ticket: Ticket = data["ticket"]
    complaint_filed_at = summary_json.get("complaint", {}).get("filed_at")
    resolved_at = summary_json.get("resolution", {}).get("resolved_at")
    resolved_by_display_name = summary_json.get("resolution", {}).get("resolved_by_display_name")
    duration_days = _resolution_duration_days(complaint_filed_at, resolved_at)
    return {
        "version": 1,
        "grievance_id": ticket.grievance_id,
        "primary_language": data["primary_language"],
        "project_name": data["project"].get("project_name") or data["project"].get("project_code"),
        "resolved_at": summary_json["resolution"]["resolved_at"],
        "complaint_filed_at": complaint_filed_at,
        "resolved_duration_days": duration_days,
        "resolved_by_display_name": resolved_by_display_name,
        "complainant_name": summary_json["complainant"].get("name"),
        "address_full": summary_json["complainant"].get("address_full"),
        "original_complaint": summary_json["complaint"]["original_complaint"],
        "resolution_category_label": summary_json["resolution"]["category_label"],
        "resolution_text_public": llm_out.get("resolution_text_public")
        or summary_json["resolution"]["text"],
        "findings_summary_public": llm_out.get("findings_summary_public")
        or llm_out.get("combined_digest_en")
        or "",
        "is_seah": ticket.is_seah,
    }


def assemble_llm_bundle(data: dict[str, Any], prior_findings: Optional[dict] = None) -> dict:
    ticket: Ticket = data["ticket"]
    phone_followup_notes = [
        n for n in data["other_notes"] if _PHONE_NOTE_RE.search(str(n.get("text") or ""))
    ]
    return {
        "case_ref": {"grievance_id": ticket.grievance_id, "is_seah": ticket.is_seah},
        "original_complaint": data["original_complaint"],
        "resolution": data["resolution"],
        "field_reports": data["field_reports"],
        "other_officer_notes": data["other_notes"],
        "investigation_facts": {
            "field_reports_count": len(data["field_reports"]),
            "other_notes_count": len(data["other_notes"]),
            "phone_followup_notes_count": len(phone_followup_notes),
        },
        "prior_ai_findings": prior_findings or {},
    }


def with_investigation_activity_preamble(data: dict[str, Any], llm_out: Optional[dict]) -> dict[str, Any]:
    """
    Ensure summaries consistently reflect documented investigation effort.
    Prepends a factual sentence built from source notes (no LLM invention).
    """
    out = dict(llm_out or {})
    field_count = len(data.get("field_reports") or [])
    other_notes = data.get("other_notes") or []
    phone_count = sum(
        1 for note in other_notes if _PHONE_NOTE_RE.search(str(note.get("text") or ""))
    )

    parts: list[str] = []
    if field_count:
        parts.append(f"{field_count} field visit{'s' if field_count != 1 else ''}")
    if phone_count:
        parts.append(f"{phone_count} phone follow-up note{'s' if phone_count != 1 else ''}")
    if parts:
        lead = f"Documented investigation activity included {', and '.join(parts)}."
        combined = str(out.get("combined_digest_en") or "").strip()
        if combined and lead.lower() not in combined.lower():
            out["combined_digest_en"] = f"{lead} {combined}"
        elif not combined:
            out["combined_digest_en"] = lead

        public_summary = str(out.get("findings_summary_public") or "").strip()
        if public_summary and lead.lower() not in public_summary.lower():
            out["findings_summary_public"] = f"{lead} {public_summary}"
        elif not public_summary:
            out["findings_summary_public"] = lead
    return out


def build_flat_narrative(public_json: dict[str, Any]) -> str:
    lines = [
        f"Grievance reference: {public_json.get('grievance_id', '')}",
        f"Project: {public_json.get('project_name', '')}",
        "",
        "Your complaint",
        public_json.get("original_complaint") or "",
        "",
        "Outcome",
        public_json.get("resolution_category_label") or "",
        public_json.get("resolution_text_public") or "",
        "",
        "Summary of findings",
        public_json.get("findings_summary_public") or "",
    ]
    return "\n".join(lines).strip()


def _resolution_step_at_close(db: Session, ticket_id: str) -> tuple[str, str]:
    """Workflow step active when the case was resolved (from RESOLVED event)."""
    ev = db.execute(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "RESOLVED",
        )
        .order_by(TicketEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not ev or not ev.workflow_step_id:
        return "", ""
    step = db.get(WorkflowStep, ev.workflow_step_id)
    if not step:
        return "", ""
    level = f"L{step.step_order}" if step.step_order is not None else ""
    return (step.display_name or "").strip(), level


def _total_overdue_days(db: Session, ticket_id: str) -> int:
    episodes = load_episodes_for_tickets(db, [ticket_id]).get(ticket_id, [])
    total = 0
    for ep in episodes:
        if ep.days_overdue is not None:
            total += int(ep.days_overdue)
            continue
        days = overdue_days_display(ep)
        if days is not None:
            total += days
    return total


def _iso_date_only(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return value[:10] if len(value) >= 10 else value


def build_closure_display_context(
    db: Session,
    ticket: Ticket,
    summary_json: dict[str, Any] | None,
    summary_public_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Officer closure page: shared header (complainant parity) + report-aligned metrics.
    """
    sj = summary_json or {}
    pub = summary_public_json or {}
    complaint = sj.get("complaint") or {}
    resolution = sj.get("resolution") or {}
    project = sj.get("project") or {}

    filed_at = pub.get("complaint_filed_at") or complaint.get("filed_at")
    resolved_at = pub.get("resolved_at") or resolution.get("resolved_at")
    duration = pub.get("resolved_duration_days")
    if duration is None and filed_at and resolved_at:
        duration = _resolution_duration_days(filed_at, resolved_at)

    aux = _fetch_auxiliary_maps(db, [ticket])
    report_row = build_report_row(
        ticket,
        step_map=aux[0],
        project_names=aux[1],
        package_labels=aux[2],
        resolved_at_map=aux[3],
        escalated_ids=aux[4],
        resolution_cat_map=aux[5],
        date_from=_now().date(),
        date_to=_now().date(),
    )

    stage_name, stage_level = _resolution_step_at_close(db, ticket.ticket_id)
    if not stage_name:
        stage_name = report_row.get("stage") or ""
    if not stage_level:
        stage_level = report_row.get("stage_level") or ""

    project_name = (
        pub.get("project_name")
        or project.get("project_name")
        or project.get("project_code")
        or report_row.get("project_name")
        or ""
    )
    package_label = (
        project.get("package_name")
        or project.get("package_code")
        or report_row.get("package_label")
        or ""
    )

    return {
        "case_header": {
            "reference": ticket.grievance_id,
            "complaint_date": _iso_date_only(filed_at) or report_row.get("complaint_date"),
            "resolved_date": _iso_date_only(resolved_at),
            "resolution_duration_days": duration,
            "resolved_by": (
                pub.get("resolved_by_display_name")
                or resolution.get("resolved_by_display_name")
                or ticket.updated_by_user_id
                or ""
            ),
            "project_name": project_name,
            "package_label": package_label,
        },
        "officer_metrics": {
            "complaint_category": normalize_complaint_category(
                complaint.get("categories") or ticket.grievance_categories
            ),
            "escalated_yn": report_row.get("escalated_yn", "N"),
            "stage_at_resolution": stage_name,
            "stage_level_at_resolution": stage_level,
            "days_spent_overdue": _total_overdue_days(db, ticket.ticket_id),
            "sla_breached_yn": report_row.get("sla_breached", "N"),
            "resolution_category": (
                resolution.get("category_label")
                or report_row.get("resolution_category")
                or ""
            ),
            "instance": report_row.get("is_seah", "Standard"),
            "location_display": report_row.get("location_display") or "",
        },
    }


def upsert_resolved_summary(
    db: Session,
    ticket_id: str,
    *,
    source_resolution_event_id: str,
    summary_json: dict,
    summary_public_json: dict,
    summary_text_primary: str,
    primary_language: str,
    generation_model: str,
    generation_status: str,
) -> TicketResolvedSummary:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise ValueError("ticket missing")

    settings = get_settings()
    row = db.get(TicketResolvedSummary, ticket_id)
    if row is None:
        token = str(uuid.uuid4())
        row = TicketResolvedSummary(
            ticket_id=ticket_id,
            grievance_id=ticket.grievance_id,
            resolved_at=_now(),
            resolved_by_user_id=ticket.updated_by_user_id,
            source_resolution_event_id=source_resolution_event_id,
            closure_public_token=token,
        )
        db.add(row)
    token = row.closure_public_token
    public_url = f"{settings.ticketing_public_base_url.rstrip('/')}/closure/{token}"

    row.summary_json = summary_json
    row.summary_public_json = summary_public_json
    row.summary_text_primary = summary_text_primary
    row.summary_text_en = summary_json.get("findings_summary", {}).get("combined_digest_en")
    row.primary_language = primary_language
    row.closure_public_url = public_url
    row.generation_model = generation_model
    row.generation_status = generation_status
    row.generated_at = _now()
    if row.resolved_at is None:
        row.resolved_at = _now()

    db.flush()
    return row
