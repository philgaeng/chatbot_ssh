"""
Executive Summary report — docs/ticketing_system/09_reports_and_report_builder.md §12–§13.
"""
from __future__ import annotations

import re
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser
from ticketing.constants.resolution import resolution_category_label
from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowStep
from ticketing.services.overdue_episodes import (
    episode_covers_instant,
    load_episodes_for_tickets,
    ticket_had_overdue_before,
)
from ticketing.services.report_rows import (
    NEPAL_TZ,
    _apply_officer_scope,
    _location_codes_with_descendants,
)

MAX_QUARTERS = 4
LEVEL_BUCKETS = ("L1", "L2", "L3", "L4+")


def _level_tooltip(level: str) -> str:
    tips = {
        "L1": "Level 1 — site safeguards focal person (first response).",
        "L2": "Level 2 — PD/PIU safeguards focal.",
        "L3": "Level 3 — GRC hearing level.",
        "L4+": "Level 4 and above — legal / senior escalation.",
    }
    return tips.get(level, level)


def _level_bucket(step_order: int) -> str:
    if step_order <= 1:
        return "L1"
    if step_order == 2:
        return "L2"
    if step_order == 3:
        return "L3"
    return "L4+"


def _parse_quarter_key(key: str) -> tuple[int, int]:
    m = re.match(r"^(\d{4})-Q([1-4])$", key.strip())
    if not m:
        raise ValueError(f"Invalid quarter key: {key}")
    return int(m.group(1)), int(m.group(2))


def _quarter_bounds(year: int, q: int) -> tuple[date, date, datetime]:
    start_month = (q - 1) * 3 + 1
    end_month = start_month + 2
    d_from = date(year, start_month, 1)
    last_day = monthrange(year, end_month)[1]
    d_to = date(year, end_month, last_day)
    end_dt = datetime(year, end_month, last_day, 23, 59, 59, tzinfo=NEPAL_TZ)
    return d_from, d_to, end_dt


def expand_period_keys(
    quarter_keys: list[str] | None,
    years: list[int] | None,
) -> list[dict[str, Any]]:
    keys: set[str] = set()
    for y in years or []:
        for q in (1, 2, 3, 4):
            keys.add(f"{y}-Q{q}")
    for k in quarter_keys or []:
        keys.add(k.strip())
    if not keys:
        today = date.today()
        cq = (today.month - 1) // 3 + 1
        keys.add(f"{today.year}-Q{cq}")
    sorted_keys = sorted(keys)
    if len(sorted_keys) > MAX_QUARTERS:
        sorted_keys = sorted_keys[-MAX_QUARTERS:]
    out = []
    for k in sorted_keys:
        y, q = _parse_quarter_key(k)
        d_from, d_to, end_dt = _quarter_bounds(y, q)
        out.append({"key": k, "date_from": d_from, "date_to": d_to, "quarter_end": end_dt})
    return out


def _max_level_before_resolve(
    db: Session,
    ticket_id: str,
    resolved_at: datetime,
    step_order_by_id: dict[str, int],
) -> str:
    max_order = 0
    rows = db.execute(
        select(TicketEvent.workflow_step_id, TicketEvent.created_at)
        .where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.created_at < resolved_at,
            TicketEvent.workflow_step_id.is_not(None),
        )
    ).all()
    for step_id, _ in rows:
        if step_id and step_id in step_order_by_id:
            max_order = max(max_order, step_order_by_id[step_id])
    return _level_bucket(max_order or 1)


def _resolved_at_map(db: Session, ticket_ids: list[str]) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    if not ticket_ids:
        return out
    for row in db.execute(
        select(TicketEvent.ticket_id, TicketEvent.created_at)
        .where(
            TicketEvent.ticket_id.in_(ticket_ids),
            TicketEvent.event_type == "RESOLVED",
        )
        .order_by(TicketEvent.created_at.desc())
    ).all():
        if row[0] not in out:
            out[row[0]] = row[1]
    return out


def _matches_province(ticket: Ticket, expanded_locations: list[str] | None) -> bool:
    if not expanded_locations:
        return True
    return ticket.location_code in expanded_locations


def _was_open_at_quarter_end(
    ticket: Ticket,
    resolved_at: datetime | None,
    quarter_end_date: date,
) -> bool:
    if resolved_at:
        return resolved_at.astimezone(NEPAL_TZ).date() > quarter_end_date
    return ticket.status_code not in ("RESOLVED", "CLOSED")


def _resolved_in_quarter(resolved_at: datetime | None, d_from: date, d_to: date) -> bool:
    if not resolved_at:
        return False
    res_date = resolved_at.astimezone(NEPAL_TZ).date()
    return d_from <= res_date <= d_to


def _current_level_bucket(ticket: Ticket, step_order_by_id: dict[str, int]) -> str:
    if ticket.current_step_id and ticket.current_step_id in step_order_by_id:
        return _level_bucket(step_order_by_id[ticket.current_step_id])
    return "L1"


def build_report_summary(
    db: Session,
    current_user: CurrentUser,
    *,
    project_id: str,
    province_code: str | None = None,
    quarter_keys: list[str] | None = None,
    years: list[int] | None = None,
    chart_package_ids: list[str] | None = None,
    include_seah: bool = False,
) -> dict[str, Any]:
    periods = expand_period_keys(quarter_keys, years)
    expanded_locations = (
        _location_codes_with_descendants(db, [province_code]) if province_code else None
    )

    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")

    q = select(Ticket).where(
        Ticket.is_deleted.is_(False),
        or_(
            Ticket.project_id == project_id,
            Ticket.project_code == project.short_code,
        ),
    )
    if not include_seah and not current_user.can_see_seah:
        q = q.where(Ticket.is_seah.is_(False))
    elif not include_seah:
        q = q.where(Ticket.is_seah.is_(False))
    q = _apply_officer_scope(q, db, current_user)
    tickets = list(db.execute(q).scalars().all())

    packages = list(
        db.execute(
            select(ProjectPackage).where(ProjectPackage.project_id == project_id)
        ).scalars().all()
    )
    package_by_id = {p.package_id: p for p in packages}

    step_rows = db.execute(select(WorkflowStep)).scalars().all()
    step_order_by_id = {s.step_id: int(s.step_order) for s in step_rows}

    ticket_ids = [t.ticket_id for t in tickets]
    episodes_map = load_episodes_for_tickets(db, ticket_ids)
    resolved_at = _resolved_at_map(db, ticket_ids)

    escalated_ids: set[str] = set()
    if ticket_ids:
        escalated_ids = set(
            db.execute(
                select(TicketEvent.ticket_id).where(
                    TicketEvent.ticket_id.in_(ticket_ids),
                    TicketEvent.event_type == "ESCALATED",
                ).distinct()
            ).scalars().all()
        )

    resolution_cat: dict[str, str] = {}
    for row in db.execute(
        select(TicketEvent.ticket_id, TicketEvent.payload)
        .where(
            TicketEvent.ticket_id.in_(ticket_ids),
            TicketEvent.event_type == "RESOLVED",
        )
        .order_by(TicketEvent.created_at.desc())
    ).all():
        if row[0] not in resolution_cat:
            payload = row[1] or {}
            code = payload.get("resolution_category")
            resolution_cat[row[0]] = resolution_category_label(code) if code else "Unknown"

    matrix_rows: list[dict[str, Any]] = []
    row_keys: list[tuple[str, str | None]] = [(project_id, None)]
    for pkg in packages:
        row_keys.append((project_id, pkg.package_id))
    row_keys.append((project_id, "__none__"))

    def empty_cells() -> dict[str, int]:
        return defaultdict(int)

    row_cells = {rk: empty_cells() for rk in row_keys}

    def row_key_for(ticket: Ticket) -> tuple[str, str | None]:
        if not ticket.package_id:
            return (project_id, "__none__")
        return (project_id, ticket.package_id)

    union_from = min(p["date_from"] for p in periods)
    union_to = max(p["date_to"] for p in periods)

    pie_ontime = 0
    pie_overdue = 0
    pie_escalated = 0
    pie_not_escalated = 0
    pie_levels: dict[str, int] = defaultdict(int)
    pie_categories: dict[str, int] = defaultdict(int)
    monthly: dict[tuple[str, str], int] = defaultdict(int)

    today = date.today()
    chart_month_start = today.replace(day=1) - timedelta(days=365)

    for ticket in tickets:
        if not _matches_province(ticket, expanded_locations):
            continue

        rk = row_key_for(ticket)
        if rk not in row_cells:
            row_cells[rk] = empty_cells()

        episodes = episodes_map.get(ticket.ticket_id, [])
        res_at = resolved_at.get(ticket.ticket_id)
        pkg_id = ticket.package_id or "__none__"
        pkg_label = (
            package_by_id[ticket.package_id].name
            if ticket.package_id and ticket.package_id in package_by_id
            else "(No package)"
        )

        for period in periods:
            qkey = period["key"]
            qend = period["quarter_end"]
            d_from = period["date_from"]
            d_to = period["date_to"]

            if _was_open_at_quarter_end(ticket, res_at, d_to):
                open_level = _current_level_bucket(ticket, step_order_by_id)
                row_cells[rk][f"open_all_{qkey}_{open_level}"] += 1
                if any(episode_covers_instant(ep, qend) for ep in episodes):
                    row_cells[rk][f"open_overdue_{qkey}_{open_level}"] += 1

            if _resolved_in_quarter(res_at, d_from, d_to):
                had_overdue = ticket_had_overdue_before(db, ticket.ticket_id, res_at) or any(
                    ep.started_at < res_at for ep in episodes
                )
                timing = "overdue" if had_overdue else "on_time"
                level = _max_level_before_resolve(
                    db, ticket.ticket_id, res_at, step_order_by_id
                )
                row_cells[rk][f"closed_{qkey}_{timing}_{level}"] += 1

                chart_ok = not chart_package_ids or (
                    ticket.package_id is not None
                    and ticket.package_id in chart_package_ids
                )
                if chart_ok:
                    res_date = res_at.astimezone(NEPAL_TZ).date()
                    if timing == "on_time":
                        pie_ontime += 1
                    else:
                        pie_overdue += 1
                    if ticket.ticket_id in escalated_ids:
                        pie_escalated += 1
                    else:
                        pie_not_escalated += 1
                    pie_levels[level] += 1
                    pie_categories[resolution_cat.get(ticket.ticket_id, "Unknown")] += 1
                    if res_date >= chart_month_start:
                        month_key = res_date.strftime("%Y-%m")
                        monthly[(month_key, pkg_id)] += 1

    column_groups: list[dict[str, Any]] = []
    for period in periods:
        qkey = period["key"]
        column_groups.append(
            {
                "id": f"open_all_{qkey}",
                "label": f"Open at end of {qkey}",
                "tooltip": f"Cases still open on the last day of {qkey}, by level reached.",
                "children": [
                    {"key": f"open_all_{qkey}_{lv}", "label": lv, "tooltip": _level_tooltip(lv)}
                    for lv in LEVEL_BUCKETS
                ],
            }
        )
        column_groups.append(
            {
                "id": f"open_pipeline_{qkey}",
                "label": f"Overdue open at end of {qkey}",
                "tooltip": f"Still open on the last day of {qkey} with an active overdue episode.",
                "children": [
                    {"key": f"open_overdue_{qkey}_{lv}", "label": lv, "tooltip": _level_tooltip(lv)}
                    for lv in LEVEL_BUCKETS
                ],
            }
        )
        for timing, tlabel in (("on_time", "On time"), ("overdue", "Overdue")):
            children = [
                {"key": f"closed_{qkey}_{timing}_{lv}", "label": lv, "tooltip": _level_tooltip(lv)}
                for lv in LEVEL_BUCKETS
            ]
            column_groups.append(
                {
                    "id": f"closed_{qkey}_{timing}",
                    "label": f"Closed during {qkey} — {tlabel}",
                    "tooltip": f"Resolved in {qkey} — {tlabel.lower()} per SLA episode rules.",
                    "children": children,
                }
            )

    for rk in row_keys:
        pid, pkg_id = rk
        pkg_name = "(No package)"
        if pkg_id and pkg_id != "__none__" and pkg_id in package_by_id:
            pkg_name = package_by_id[pkg_id].name
        elif pkg_id == "__none__":
            pkg_name = "(No package)"
        matrix_rows.append(
            {
                "project_id": pid,
                "project_name": project.name,
                "package_id": None if pkg_id == "__none__" else pkg_id,
                "package_name": pkg_name,
                "cells": dict(row_cells[rk]),
            }
        )

    month_series: dict[str, dict[str, Any]] = {}
    for (month, pkg), cnt in sorted(monthly.items()):
        pname = package_by_id[pkg].name if pkg in package_by_id else "(No package)"
        if pkg == "__none__":
            pname = "(No package)"
        month_series.setdefault(month, {"month": month, "packages": []})
        month_series[month]["packages"].append(
            {"package_id": pkg if pkg != "__none__" else None, "package_name": pname, "count": cnt}
        )

    def pie_slices(counts: dict[str, int]) -> list[dict[str, Any]]:
        total = sum(counts.values()) or 1
        return [
            {"label": k, "value": v, "percent": round(100.0 * v / total, 1)}
            for k, v in sorted(counts.items(), key=lambda x: -x[1])
        ]

    return {
        "filters": {
            "project_id": project_id,
            "project_name": project.name,
            "province_code": province_code,
            "quarter_keys": [p["key"] for p in periods],
            "chart_package_ids": chart_package_ids or [],
            "include_seah": include_seah,
            "period_union_from": str(union_from),
            "period_union_to": str(union_to),
        },
        "matrix": {
            "column_groups": column_groups,
            "rows": matrix_rows,
        },
        "charts": {
            "resolved_by_month": list(month_series.values()),
            "pies": {
                "overdue_vs_ontime": pie_slices(
                    {"On time": pie_ontime, "Closed overdue": pie_overdue}
                ),
                "escalated": pie_slices(
                    {"Escalated": pie_escalated, "Never escalated": pie_not_escalated}
                ),
                "max_level": pie_slices(dict(pie_levels)),
                "resolution_category": pie_slices(dict(pie_categories)),
            },
        },
        "definitions": {
            "closed_on_time": "Resolved with no SLA overdue episode during the case.",
            "closed_overdue": "Resolved after at least one overdue episode.",
            "level_l1": _level_tooltip("L1"),
            "level_l2": _level_tooltip("L2"),
            "level_l3": _level_tooltip("L3"),
            "level_l4": _level_tooltip("L4+"),
            "package_row": "Counts grouped by project package (road section / contract).",
        },
    }
