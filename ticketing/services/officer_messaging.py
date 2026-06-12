"""Project-level officer SMS on assignment (link-only, no PII)."""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing.api.schemas.project_messaging import (
    OfficerMessagingConfig,
    ProjectMessagingPatch,
)
from ticketing.clients.messaging_api import send_sms
from ticketing.config.settings import get_settings
from ticketing.models.project import Project
from ticketing.models.project_workflow import ProjectWorkflow
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowStep
from ticketing.services.admin_access import is_country_admin, is_super_admin
from ticketing.services.keycloak_users import profiles_for_user_ids

if TYPE_CHECKING:
    from ticketing.api.dependencies import CurrentUser

logger = logging.getLogger(__name__)

DEFAULT_OFFICER_MESSAGING: dict[str, Any] = {
    "sms_enabled": False,
    "sms_levels": [],
    "whatsapp_levels": [],
}


def default_officer_messaging() -> dict[str, Any]:
    return dict(DEFAULT_OFFICER_MESSAGING)


def _config_from_raw(raw: dict[str, Any] | None) -> OfficerMessagingConfig:
    data = raw if isinstance(raw, dict) else {}
    return OfficerMessagingConfig(
        sms_enabled=bool(data.get("sms_enabled", False)),
        sms_levels=[int(x) for x in (data.get("sms_levels") or [])],
        whatsapp_levels=[int(x) for x in (data.get("whatsapp_levels") or [])],
    )


def _workflow_ids_for_project(db: Session, project_id: str) -> list[str]:
    return list(
        db.execute(
            select(ProjectWorkflow.workflow_id).where(
                ProjectWorkflow.project_id == project_id
            )
        ).scalars().all()
    )


def max_workflow_levels_for_project(db: Session, project_id: str) -> int:
    """MAX(step_order) across workflows linked in project_workflows."""
    workflow_ids = _workflow_ids_for_project(db, project_id)
    if not workflow_ids:
        return 0
    max_order = db.execute(
        select(func.max(WorkflowStep.step_order)).where(
            WorkflowStep.workflow_id.in_(workflow_ids)
        )
    ).scalar_one_or_none()
    return int(max_order or 0)


def get_officer_messaging(db: Session, project_id: str) -> OfficerMessagingConfig:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _config_from_raw(project.officer_messaging)


def update_officer_messaging(
    db: Session,
    project_id: str,
    patch: ProjectMessagingPatch,
) -> OfficerMessagingConfig:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current = _config_from_raw(project.officer_messaging)
    data = current.model_dump()
    if patch.sms_enabled is not None:
        data["sms_enabled"] = patch.sms_enabled
    if patch.sms_levels is not None:
        data["sms_levels"] = patch.sms_levels
    if patch.whatsapp_levels is not None:
        data["whatsapp_levels"] = patch.whatsapp_levels

    max_levels = max_workflow_levels_for_project(db, project_id)
    if max_levels and any(level > max_levels for level in data["sms_levels"]):
        raise HTTPException(
            status_code=422,
            detail=f"sms_levels must be within 1..{max_levels}",
        )
    if max_levels and any(level > max_levels for level in data["whatsapp_levels"]):
        raise HTTPException(
            status_code=422,
            detail=f"whatsapp_levels must be within 1..{max_levels}",
        )

    # Master on with empty sms_levels: allowed — no sends until levels are checked.
    project.officer_messaging = data
    return OfficerMessagingConfig(**data)


def can_edit_project_messaging(user: CurrentUser, project: Project) -> bool:
    if is_super_admin(user):
        return True
    if not is_country_admin(user):
        return False
    scopes = getattr(user, "admin_scopes", []) or []
    return any(
        s.role_key == "country_admin" and s.country_code == project.country_code
        for s in scopes
    )


def require_project_messaging_edit(user: CurrentUser, project: Project) -> None:
    if can_edit_project_messaging(user, project):
        return
    raise HTTPException(
        status_code=403,
        detail="requires country_admin or super_admin",
    )


def resolve_project_id(db: Session, ticket: Ticket) -> str | None:
    if not ticket.project_code:
        return None
    row = db.execute(
        select(Project.project_id).where(Project.short_code == ticket.project_code)
    ).scalar_one_or_none()
    return row


def _step_order(db: Session, step_id: str | None) -> int | None:
    if not step_id:
        return None
    step = db.get(WorkflowStep, step_id)
    return step.step_order if step else None


def should_send_officer_sms(config: OfficerMessagingConfig, step_order: int) -> bool:
    return bool(config.sms_enabled and step_order in config.sms_levels)


def _category_snippet(ticket: Ticket) -> str:
    cats = ticket.grievance_categories
    if isinstance(cats, list) and cats:
        return str(cats[0])
    if isinstance(cats, str) and cats.strip():
        return cats.strip()
    return "General"


def _location_snippet(ticket: Ticket) -> str:
    return (ticket.grievance_location or ticket.location_code or "—").strip() or "—"


def build_officer_sms_body(ticket: Ticket, *, event: str = "assignment") -> str:
    settings = get_settings()
    url = f"{settings.ticketing_public_base_url.rstrip('/')}/tickets/{ticket.ticket_id}"
    prefix = {
        "assignment": "New case:",
        "escalation": "Escalation:",
        "reassign": "Assigned:",
    }.get(event, "New case:")
    category = _category_snippet(ticket)
    location = _location_snippet(ticket)
    body = f"{prefix} {ticket.grievance_id} ({category}, {location}). Open: {url}"
    if len(body) <= 160:
        return body
    # Truncate category/location snippets to fit ~160 chars.
    overhead = len(f"{prefix} {ticket.grievance_id} (, ). Open: {url}")
    budget = max(20, 160 - overhead)
    half = budget // 2
    cat_short = category if len(category) <= half else category[: half - 1] + "…"
    loc_budget = budget - len(cat_short)
    loc_short = location if len(location) <= loc_budget else location[: max(1, loc_budget - 1)] + "…"
    return f"{prefix} {ticket.grievance_id} ({cat_short}, {loc_short}). Open: {url}"


def _log_officer_sms_event(
    db: Session,
    ticket_id: str,
    event_type: str,
    *,
    level: int | None,
    reason: str,
) -> None:
    db.add(
        TicketEvent(
            event_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            event_type=event_type,
            note=reason[:500],
            payload={"channel": "sms", "level": level, "reason": reason},
            seen=True,
            created_by_user_id="system",
        )
    )


def notify_officer_assignment_sync(
    db: Session,
    ticket_id: str,
    assigned_to_user_id: str,
    step_id: str | None,
    *,
    event: str = "assignment",
) -> dict[str, Any]:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        return {"sent": False, "skipped": True, "reason": "ticket_not_found"}

    project_id = resolve_project_id(db, ticket)
    if not project_id:
        _log_officer_sms_event(
            db, ticket_id, "OFFICER_SMS_SKIPPED", level=None, reason="no_project"
        )
        db.commit()
        return {"sent": False, "skipped": True, "reason": "no_project"}

    config = get_officer_messaging(db, project_id)
    step_order = _step_order(db, step_id or ticket.current_step_id)
    if step_order is None:
        _log_officer_sms_event(
            db, ticket_id, "OFFICER_SMS_SKIPPED", level=None, reason="no_step"
        )
        db.commit()
        return {"sent": False, "skipped": True, "reason": "no_step"}

    if not should_send_officer_sms(config, step_order):
        _log_officer_sms_event(
            db,
            ticket_id,
            "OFFICER_SMS_SKIPPED",
            level=step_order,
            reason="config_off_or_level_disabled",
        )
        db.commit()
        return {"sent": False, "skipped": True, "reason": "config_off_or_level_disabled"}

    profiles = profiles_for_user_ids([assigned_to_user_id])
    profile = profiles.get(assigned_to_user_id.lower())
    phone = (profile.phone_number if profile else "").strip()
    if not phone:
        _log_officer_sms_event(
            db,
            ticket_id,
            "OFFICER_SMS_SKIPPED",
            level=step_order,
            reason="no_phone",
        )
        db.commit()
        return {"sent": False, "skipped": True, "reason": "no_phone"}

    body = build_officer_sms_body(ticket, event=event)
    try:
        send_sms(phone, body)
        _log_officer_sms_event(
            db, ticket_id, "OFFICER_SMS_SENT", level=step_order, reason="sent"
        )
        db.commit()
        return {"sent": True, "skipped": False, "reason": "sent"}
    except Exception as exc:
        logger.warning(
            "Officer SMS failed ticket_id=%s assignee=%s: %s",
            ticket_id,
            assigned_to_user_id,
            exc,
        )
        _log_officer_sms_event(
            db,
            ticket_id,
            "OFFICER_SMS_SKIPPED",
            level=step_order,
            reason="api_failure",
        )
        db.commit()
        return {"sent": False, "skipped": True, "reason": "api_failure"}


def role_keys_at_level(db: Session, project_id: str, step_order: int) -> set[str]:
    workflow_ids = _workflow_ids_for_project(db, project_id)
    if not workflow_ids:
        return set()
    rows = db.execute(
        select(WorkflowStep.assigned_role_key).where(
            WorkflowStep.workflow_id.in_(workflow_ids),
            WorkflowStep.step_order == step_order,
            WorkflowStep.assigned_role_key.is_not(None),
        )
    ).scalars().all()
    return {r for r in rows if r}
