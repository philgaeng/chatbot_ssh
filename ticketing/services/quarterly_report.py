"""
Quarterly scheduled report: load template + schedule from ticketing.settings,
generate XLSX (overview four-sheet or pivot), resolve recipient emails.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser
from ticketing.api.schemas.reports import PivotConfig, PivotValueSpec
from ticketing.services.pivot_table import build_pivot_table
from ticketing.services.report_rows import (
    DEFAULT_REPORT_COLUMNS,
    build_xlsx_workbook,
    load_report_rows,
    project_row,
    split_sections,
)

logger = logging.getLogger(__name__)

SETTING_SCHEDULE = "report_schedule"
SETTING_TEMPLATE = "quarterly_report_template"

DEFAULT_SCHEDULE: dict[str, Any] = {
    "frequency": "quarterly",
    "day_of_month": 5,
    "recipients_by_role": [
        "adb_national_project_director",
        "adb_hq_safeguards",
        "adb_hq_project",
    ],
}

DEFAULT_TEMPLATE: dict[str, Any] = {
    "name": "GRM quarterly overview",
    "kind": "overview",
    "include_seah": False,
    "project_ids": [],
    "package_ids": [],
    "location_codes": [],
    "pivot": None,
}


def last_completed_quarter(today: date | None = None) -> tuple[date, date]:
    """Inclusive date range for the quarter that ended most recently."""
    today = today or date.today()
    cq = (today.month - 1) // 3
    first_of_current_q = date(today.year, cq * 3 + 1, 1)
    d_to = first_of_current_q - timedelta(days=1)
    pq = (cq - 1) % 4
    pq_year = today.year if cq > 0 else today.year - 1
    d_from = date(pq_year, pq * 3 + 1, 1)
    return d_from, d_to


def _get_setting(db: Session, key: str) -> dict | None:
    from ticketing.models.settings import Settings

    row = db.get(Settings, key)
    if not row:
        return None
    return row.value if isinstance(row.value, dict) else None


def load_quarterly_config(db: Session) -> dict[str, Any]:
    schedule = _get_setting(db, SETTING_SCHEDULE) or dict(DEFAULT_SCHEDULE)
    template = _get_setting(db, SETTING_TEMPLATE) or dict(DEFAULT_TEMPLATE)
    return {"schedule": schedule, "template": template}


def save_quarterly_config(
    db: Session,
    *,
    schedule: dict[str, Any] | None,
    template: dict[str, Any] | None,
    updated_by: str,
) -> dict[str, Any]:
    from ticketing.models.settings import Settings

    if schedule is not None:
        row = db.get(Settings, SETTING_SCHEDULE)
        if row:
            row.value = schedule
            row.updated_by_user_id = updated_by
        else:
            db.add(
                Settings(
                    key=SETTING_SCHEDULE,
                    value=schedule,
                    updated_by_user_id=updated_by,
                )
            )
    if template is not None:
        row = db.get(Settings, SETTING_TEMPLATE)
        if row:
            row.value = template
            row.updated_by_user_id = updated_by
        else:
            db.add(
                Settings(
                    key=SETTING_TEMPLATE,
                    value=template,
                    updated_by_user_id=updated_by,
                )
            )
    db.commit()
    return load_quarterly_config(db)


def _parse_pivot(template: dict[str, Any]) -> PivotConfig | None:
    raw = template.get("pivot")
    if not raw:
        return None
    values = [
        PivotValueSpec(field=v.get("field", "ticket_id"), agg=v.get("agg", "count"))
        for v in raw.get("values") or [{"field": "ticket_id", "agg": "count"}]
    ]
    return PivotConfig(
        rows=list(raw.get("rows") or []),
        columns=list(raw.get("columns") or []),
        values=values,
        filters=dict(raw.get("filters") or {}),
    )


def generate_quarterly_xlsx(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    template: dict[str, Any],
    organization_id: str | None = None,
) -> tuple[bytes, str, int]:
    """
    Returns (xlsx_bytes, filename, ticket_count).
    """
    system_user = CurrentUser(
        user_id="system",
        role_keys=["super_admin"],
        organization_id=organization_id or "DOR",
    )
    include_seah = bool(template.get("include_seah"))
    project_ids = template.get("project_ids") or None
    package_ids = template.get("package_ids") or None
    location_codes = template.get("location_codes") or None
    if project_ids == []:
        project_ids = None
    if package_ids == []:
        package_ids = None
    if location_codes == []:
        location_codes = None

    built = load_report_rows(
        db,
        system_user,
        date_from=date_from,
        date_to=date_to,
        project_ids=project_ids,
        package_ids=package_ids,
        location_codes=location_codes,
        include_seah=include_seah,
    )
    if organization_id:
        built = [r for r in built if r.get("organization_id") == organization_id]

    kind: Literal["overview", "pivot"] = template.get("kind") or "overview"
    public_rows = [{k: v for k, v in row.items() if not str(k).startswith("_")} for row in built]

    if kind == "pivot":
        pivot_cfg = _parse_pivot(template)
        if not pivot_cfg or not (pivot_cfg.rows or pivot_cfg.columns or pivot_cfg.values):
            kind = "overview"
        else:
            value_specs = [{"field": v.field, "agg": v.agg} for v in pivot_cfg.values]
            pivot_result = build_pivot_table(
                public_rows,
                row_dims=pivot_cfg.rows,
                col_dims=pivot_cfg.columns,
                value_specs=value_specs,
                filters=pivot_cfg.filters,
            )
            from ticketing.services.report_export import pivot_workbook_bytes

            xlsx_bytes = pivot_workbook_bytes(pivot_result)
            name = (template.get("name") or "grm_quarterly_pivot").replace(" ", "_")
            filename = f"{name}_{date_from}_{date_to}.xlsx"
            return xlsx_bytes, filename, len(built)

    sections = split_sections(built)
    public = {
        k: [project_row(r, DEFAULT_REPORT_COLUMNS) for r in v]
        for k, v in sections.items()
    }
    xlsx_bytes = build_xlsx_workbook(public, DEFAULT_REPORT_COLUMNS)
    filename = f"grm_quarterly_report_{date_from}_{date_to}.xlsx"
    return xlsx_bytes, filename, len(built)


def resolve_recipient_emails(db: Session, role_keys: list[str]) -> list[str]:
    from sqlalchemy import select

    from ticketing.models.user import Role, UserRole
    from ticketing.services.keycloak_users import list_grm_officer_profiles

    roles = db.execute(select(Role).where(Role.role_key.in_(role_keys))).scalars().all()
    role_ids = [r.role_id for r in roles]
    if not role_ids:
        return []

    user_ids = db.execute(
        select(UserRole.user_id).where(UserRole.role_id.in_(role_ids)).distinct()
    ).scalars().all()

    emails: set[str] = set()
    profiles = list_grm_officer_profiles()
    for uid in user_ids:
        uid_l = (uid or "").strip().lower()
        if "@" in uid_l:
            emails.add(uid_l)
            continue
        prof = profiles.get(uid_l)
        if prof and prof.email:
            emails.add(prof.email.lower())

    for email, prof in profiles.items():
        if any(rk in role_keys for rk in prof.role_keys):
            emails.add(email)

    return sorted(emails)


def dispatch_assignment_email(
    db: Session,
    *,
    assignment_id: str,
    quarter_key: str,
    role_key: str,
    emails: list[str],
    date_from: date,
    date_to: date,
    ticket_count: int,
    template_name: str,
    xlsx_bytes: bytes,
    filename: str,
    actor_user_id: str = "system",
) -> bool:
    """One email per saved quarterly assignment (all officers with that role)."""
    if not emails:
        return False

    from ticketing.clients.messaging_api import send_email
    from ticketing.config.settings import get_settings
    from ticketing.services.report_limits import log_assignment_sent, quarterly_email_enabled

    if not quarterly_email_enabled(db):
        logger.warning("Quarterly email disabled in report_limits")
        return False

    settings = get_settings()
    from ticketing.clients.backend_auth import service_integration_api_key

    if not service_integration_api_key():
        logger.warning("TICKETING_SECRET_KEY not set — skipping quarterly email")
        return False

    import base64 as b64

    body = (
        f"<p>GRM quarterly report <strong>{template_name}</strong> "
        f"for <strong>{quarter_key}</strong> "
        f"(<strong>{date_from}</strong> – <strong>{date_to}</strong>).</p>"
        f"<p>Audience role: <em>{role_key}</em><br/>"
        f"Grievances in period: <strong>{ticket_count}</strong></p>"
        f"<p><small>Generated automatically by the GRM Ticketing System.</small></p>"
    )
    attachments = [
        {
            "filename": filename,
            "content_base64": b64.b64encode(xlsx_bytes).decode("ascii"),
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
    ]
    subject = f"GRM Report — {template_name} ({quarter_key})"
    try:
        send_email(to=emails, subject=subject, body=body, attachments=attachments)
        log_assignment_sent(
            db,
            actor_user_id=actor_user_id,
            assignment_id=assignment_id,
            quarter_key=quarter_key,
            role_key=role_key,
            recipient_emails=emails,
            ticket_count=ticket_count,
            template_name=template_name,
        )
        return True
    except Exception as exc:
        logger.exception("Assignment email failed (body-only retry): %s", exc)
        try:
            send_email(
                to=emails,
                subject=subject,
                body=body + "<p><em>Attachment could not be delivered; download from Reports.</em></p>",
            )
            log_assignment_sent(
                db,
                actor_user_id=actor_user_id,
                assignment_id=assignment_id,
                quarter_key=quarter_key,
                role_key=role_key,
                recipient_emails=emails,
                ticket_count=ticket_count,
                template_name=template_name,
            )
            return True
        except Exception:
            return False
