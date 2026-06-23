"""
Daily ops report (spec 11 §11) — run by the ops scheduler at 07:00 Asia/Kathmandu.

Broker-independent: reads activity straight from Postgres and the latest
ops.system_health_checks / ops.dependency_findings rows, then sends via the
Messaging API. Always sends (silence is itself a signal). Distinct from the GRM
quarterly report, which stays on Celery.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os

from sqlalchemy import text

from ops.alerts import send_report
from ops.checks import external_heartbeat
from ops.db import session_scope

logger = logging.getLogger("ops.reports")


def _safe_scalar(db, sql: str, default=0):
    try:
        val = db.execute(text(sql)).scalar()
        return val if val is not None else default
    except Exception as exc:
        logger.warning("report query failed (%s): %s", sql[:40], exc)
        return f"n/a ({type(exc).__name__})"


def _activity_rows(db) -> list[tuple[str, object]]:
    win = "now() - interval '24 hours'"
    rows: list[tuple[str, object]] = []
    rows.append(("Grievances submitted (24h)", _safe_scalar(db, f"SELECT count(*) FROM public.grievances WHERE created_at > {win}")))
    rows.append(("Tickets created (24h)", _safe_scalar(db, f"SELECT count(*) FROM ticketing.tickets WHERE created_at > {win}")))
    rows.append(("Tickets resolved (24h)", _safe_scalar(db, f"SELECT count(*) FROM ticketing.tickets WHERE updated_at > {win} AND status = 'resolved'")))
    rows.append(("Currently open tickets", _safe_scalar(db, "SELECT count(*) FROM ticketing.tickets WHERE status NOT IN ('resolved','closed','archived')")))
    # SLA breaches + files (best-effort; degrade to n/a if tables differ).
    rows.append(("SLA-breach episodes (24h)", _safe_scalar(db, f"SELECT count(*) FROM ticketing.ticket_overdue_episodes WHERE created_at > {win}")))
    rows.append(("Files uploaded (24h)", _safe_scalar(db, f"SELECT count(*) FROM ticketing.ticket_files WHERE created_at > {win}")))
    rows.append(("Officer logins (24h)", _safe_scalar(db, f"SELECT count(*) FROM keycloak.event_entity WHERE type = 'LOGIN' AND to_timestamp(event_time/1000) > {win}")))
    return rows


def _security_rows(db, deps: dict) -> list[tuple[str, object]]:
    win = "now() - interval '24 hours'"
    rows: list[tuple[str, object]] = []
    rows.append(("Open critical/high deps", deps.get("open_critical_high")))
    rows.append(("Open total deps", deps.get("open_total")))
    rows.append(("Failed logins (24h)", _safe_scalar(db, f"SELECT count(*) FROM keycloak.event_entity WHERE type = 'LOGIN_ERROR' AND to_timestamp(event_time/1000) > {win}")))
    rows.append(("Contact-reveal events (24h)", _safe_scalar(db, f"SELECT count(*) FROM ticketing.admin_audit_log WHERE action ILIKE '%reveal%' AND created_at > {win}")))
    rows.append(("Preflight gate (last run)", _preflight_status()))
    return rows


def _preflight_status() -> str:
    path = "/var/backups/grms/last_preflight.json"
    try:
        if not os.path.exists(path):
            return "never run"
        with open(path) as fh:
            data = json.load(fh)
        return f"{'PASS' if data.get('ok') else 'FAIL'} @ {data.get('ran_at', '?')}"
    except Exception:
        return "unreadable"


def _health_rows(db) -> list[tuple[str, str, str]]:
    """Latest status per check."""
    try:
        result = db.execute(text(
            "SELECT DISTINCT ON (check_name) check_name, status, coalesce(message,'') "
            "FROM ops.system_health_checks ORDER BY check_name, checked_at DESC"
        ))
        return [(r[0], r[1], r[2]) for r in result]
    except Exception as exc:
        logger.warning("health summary query failed: %s", exc)
        return []


def _dependency_summary(db) -> dict:
    try:
        crit = db.execute(text(
            "SELECT count(*) FROM ops.dependency_findings "
            "WHERE resolved_at IS NULL AND severity IN ('critical','high')"
        )).scalar()
        total = db.execute(text(
            "SELECT count(*) FROM ops.dependency_findings WHERE resolved_at IS NULL"
        )).scalar()
        return {"open_critical_high": crit or 0, "open_total": total or 0}
    except Exception:
        return {"open_critical_high": "n/a", "open_total": "n/a"}


def _render_html(activity, health, deps, security) -> str:
    def table(title, rows, headers):
        head = "".join(f"<th align='left'>{h}</th>" for h in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
        )
        return f"<h3>{title}</h3><table cellpadding='4' border='1' style='border-collapse:collapse'>" \
               f"<tr>{head}</tr>{body}</table>"

    health_rows = [
        (n, ("✅" if s == "ok" else ("⚠️" if s == "warn" else "🔴")) + f" {s}", m)
        for n, s, m in health
    ]
    parts = [
        f"<h2>GRM daily ops report — {dt.date.today().isoformat()}</h2>",
        table("Activity (rolling 24h)", activity, ["Metric", "Value"]),
        table("System health (latest per check)", health_rows or [("(none)", "", "")],
              ["Check", "Status", "Note"]),
        table("Security signals (24h)", security, ["Signal", "Value"]),
    ]
    return "".join(parts)


def daily_ops_report() -> None:
    with session_scope() as db:
        activity = _activity_rows(db)
        health = _health_rows(db)
        deps = _dependency_summary(db)
        security = _security_rows(db, deps)
    html = _render_html(activity, health, deps, security)
    subject = f"GRM daily ops report — {dt.date.today().isoformat()}"
    ok = send_report(subject, html)
    logger.info("daily ops report sent=%s", ok)
    if ok:
        external_heartbeat()
