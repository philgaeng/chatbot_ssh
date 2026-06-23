"""
Data-plane health checks (L2) — run by the ops scheduler, persisted to
ops.system_health_checks, alerting on warn/critical.

These reach every component over the network/DB, never via a broker, so they keep
working during a Redis/worker outage. Host-level disk/RAM and container restart
are the host watchdog's job (L0), not here.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import smtplib
import socket
import ssl
import json

import httpx
import redis
from sqlalchemy import text

from ops.alerts import send_alert
from ops.config import get_settings
from ops.db import record_check, session_scope

logger = logging.getLogger("ops.checks")

OK, WARN, CRIT = "ok", "warn", "critical"

# Celery queues to watch for backlog (chatbot + GRM).
_WATCHED_QUEUES = ["llm_queue", "default", "file_queue", "grm_ticketing"]

BEAT_HEARTBEAT_KEY = "health:beat:last_run"
OPS_TICK_KEY = "ops:scheduler:last_tick"


def _emit(name: str, status: str, value: dict | None = None, message: str | None = None) -> None:
    record_check(name, status, value=value, message=message)
    if status in (WARN, CRIT):
        sev = "CRITICAL" if status == CRIT else "WARNING"
        send_alert(
            signature=f"{name}:{status}",
            subject=f"{sev}: {name}",
            body_html=f"<p><b>{name}</b> = {status}</p><p>{message or ''}</p>"
            f"<pre>{json.dumps(value or {}, indent=2)}</pre>",
        )


def _redis(url: str) -> redis.Redis:
    return redis.from_url(url, socket_timeout=5, socket_connect_timeout=5)


# ── Checks ──────────────────────────────────────────────────────────────────

def db_connectivity_check() -> None:
    s = get_settings()
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
            total = db.execute(text("SELECT setting::int FROM pg_settings WHERE name='max_connections'")).scalar()
            used = db.execute(text("SELECT count(*) FROM pg_stat_activity")).scalar()
        pct = round(100 * used / total, 1) if total else 0
        status = CRIT if pct >= s.db_conn_warn_pct else OK
        _emit("db_connectivity_check", status, {"connections": used, "max": total, "pct": pct})
    except Exception as exc:
        _emit("db_connectivity_check", CRIT, message=f"DB unreachable: {exc}")


def redis_check() -> None:
    s = get_settings()
    try:
        r = _redis(s.redis_url)
        if r.ping():
            info = r.info("memory")
            used = info.get("used_memory", 0)
            maxmem = info.get("maxmemory", 0) or 0
            pct = round(100 * used / maxmem, 1) if maxmem else 0
            status = WARN if (maxmem and pct >= s.redis_mem_warn_pct) else OK
            _emit("redis_check", status, {"used_memory": used, "maxmemory": maxmem, "pct": pct})
        else:
            _emit("redis_check", CRIT, message="PING returned falsy")
    except Exception as exc:
        _emit("redis_check", CRIT, message=f"Redis unreachable: {exc}")


def queue_depth_check() -> None:
    s = get_settings()
    try:
        r = _redis(s.celery_broker_url)
        depths = {q: r.llen(q) for q in _WATCHED_QUEUES}
        worst = max(depths.values()) if depths else 0
        status = WARN if worst >= s.queue_depth_warn else OK
        _emit("queue_depth_check", status, {"depths": depths, "max": worst})
    except Exception as exc:
        _emit("queue_depth_check", CRIT, message=f"Broker unreachable: {exc}")


def endpoint_check() -> None:
    s = get_settings()
    results: dict[str, int | str] = {}
    worst = OK
    for name, url in s.parsed_health_endpoints().items():
        try:
            resp = httpx.get(url, timeout=8.0)
            results[name] = resp.status_code
            if resp.status_code != 200:
                worst = CRIT
        except Exception as exc:
            results[name] = f"ERR: {exc}"
            worst = CRIT
    _emit("endpoint_check", worst, results)


def cert_check() -> None:
    s = get_settings()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((s.public_tls_host, s.public_tls_port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=s.public_tls_host) as ssock:
                cert = ssock.getpeercert()
        not_after = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days = (not_after - dt.datetime.utcnow()).days
        status = CRIT if days < s.health_cert_warn_days else OK
        _emit("cert_check", status, {"host": s.public_tls_host, "days_remaining": days})
    except Exception as exc:
        _emit("cert_check", WARN, message=f"Cert check failed: {exc}")


def smtp_check() -> None:
    server = os.environ.get("SMTP_SERVER")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    if not (server and user and password):
        _emit("smtp_check", OK, message="SMTP env not configured; skipped")
        return
    try:
        with smtplib.SMTP(server, port, timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(user, password)
        _emit("smtp_check", OK, {"server": server, "port": port})
    except Exception as exc:
        _emit("smtp_check", CRIT, message=f"SMTP login failed: {exc}")


def grm_beat_liveness_check() -> None:
    s = get_settings()
    try:
        r = _redis(s.redis_url)
        last = r.get(BEAT_HEARTBEAT_KEY)
        if not last:
            _emit("grm_beat_liveness_check", CRIT, message="No GRM beat heartbeat (key missing/expired)")
            return
        _emit("grm_beat_liveness_check", OK, {"last_run": last.decode("utf-8", "ignore")})
    except Exception as exc:
        _emit("grm_beat_liveness_check", WARN, message=f"Heartbeat read failed: {exc}")


def stale_job_check() -> None:
    """Best-effort: flag tasks STARTED long past the soft time limit.

    Reads public.task_tracking when the ops_app role has SELECT on it; otherwise
    records 'ok' with a skipped note (don't fail on missing grant).
    """
    try:
        with session_scope() as db:
            exists = db.execute(text("SELECT to_regclass('public.task_tracking')")).scalar()
            if not exists:
                _emit("stale_job_check", OK, message="task_tracking not present; skipped")
                return
            stale = db.execute(text(
                "SELECT count(*) FROM public.task_tracking "
                "WHERE status = 'STARTED' AND created_at < now() - interval '20 minutes'"
            )).scalar()
        status = WARN if (stale or 0) > 0 else OK
        _emit("stale_job_check", status, {"stale_started": stale})
    except Exception as exc:
        _emit("stale_job_check", OK, message=f"skipped ({exc})")


def backup_status_check() -> None:
    s = get_settings()
    try:
        if not os.path.exists(s.backup_status_file):
            _emit("backup_status_check", CRIT, message=f"No backup status file at {s.backup_status_file}")
            return
        with open(s.backup_status_file) as fh:
            data = json.load(fh)
        ts = dt.datetime.fromisoformat(data["completed_at"])
        age_h = (dt.datetime.now(dt.timezone.utc) - ts).total_seconds() / 3600
        status = CRIT if age_h > s.backup_max_age_hours else OK
        _emit("backup_status_check", status, {"age_hours": round(age_h, 1), **data})
    except Exception as exc:
        _emit("backup_status_check", CRIT, message=f"Backup status unreadable: {exc}")


def external_heartbeat() -> None:
    """L3 dead-man's switch: ping healthchecks.io only when the latest checks are green.

    UptimeRobot is the inverse tool (it probes our public HTTP endpoints); this is the
    "we check in" side, so silence here makes healthchecks.io alert the operator.
    """
    s = get_settings()
    if not s.heartbeat_url:
        return
    try:
        with session_scope() as db:
            bad = db.execute(text(
                "SELECT count(*) FROM ops.system_health_checks h "
                "WHERE h.status = 'critical' "
                "AND h.checked_at > now() - interval '15 minutes' "
                "AND h.checked_at = (SELECT max(h2.checked_at) FROM ops.system_health_checks h2 "
                "                    WHERE h2.check_name = h.check_name)"
            )).scalar()
        if (bad or 0) > 0:
            logger.warning("External heartbeat skipped: %s critical checks", bad)
            return
        httpx.get(s.heartbeat_url, timeout=10.0)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("External heartbeat failed: %s", exc)


def restore_drill() -> None:
    """Placeholder hook — the actual restore is driven by scripts/ops/restore-drill.sh.

    That script restores the latest dump into a scratch DB, asserts table counts,
    and writes a status file this check reads. Here we surface its last result.
    """
    path = "/var/backups/grms/last_restore_drill.json"
    try:
        if not os.path.exists(path):
            _emit("restore_drill", WARN, message="No restore-drill result yet")
            return
        with open(path) as fh:
            data = json.load(fh)
        status = OK if data.get("ok") else CRIT
        _emit("restore_drill", status, data)
    except Exception as exc:
        _emit("restore_drill", WARN, message=f"Restore-drill status unreadable: {exc}")
