"""
Maintenance jobs (spec 11 §9.4) — run by the ops scheduler.

Data-plane/DB tasks run here. Host-level actions (Docker log rotation enforcement,
applying OS updates) require host visibility and belong to the host watchdog/cron;
those tasks here only *report*.
"""
from __future__ import annotations

import logging
import os

from sqlalchemy import text

from ops.checks import OK, WARN, _emit
from ops.db import session_scope

logger = logging.getLogger("ops.maintenance")


def prune_health_checks() -> None:
    """Delete ops.system_health_checks rows older than 90 days."""
    try:
        with session_scope() as db:
            deleted = db.execute(text(
                "DELETE FROM ops.system_health_checks WHERE checked_at < now() - interval '90 days'"
            )).rowcount
        _emit("prune_health_checks", OK, {"deleted": deleted})
    except Exception as exc:
        _emit("prune_health_checks", WARN, message=f"prune failed: {exc}")


def prune_logs() -> None:
    """Report-only: surface logs/ directory size. Docker log rotation is daemon/compose config."""
    log_dir = os.environ.get("OPS_LOG_DIR", "/app/logs")
    try:
        if not os.path.isdir(log_dir):
            _emit("prune_logs", OK, message=f"{log_dir} not mounted; skipped")
            return
        total = 0
        for root, _dirs, files in os.walk(log_dir):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        mb = round(total / 1_048_576, 1)
        _emit("prune_logs", OK, {"log_dir": log_dir, "size_mb": mb})
    except Exception as exc:
        _emit("prune_logs", OK, message=f"skipped ({exc})")


def prune_uploads_orphans() -> None:
    """Report-only: count upload files with no DB reference (requires read grant)."""
    _emit("prune_uploads_orphans", OK, message="report-only stub — wire to file_attachments when grant available")


def vacuum_analyze() -> None:
    """VACUUM ANALYZE hot ops tables (off-peak). Requires AUTOCOMMIT."""
    try:
        from ops.db import engine
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text("VACUUM ANALYZE ops.system_health_checks"))
            conn.execute(text("VACUUM ANALYZE ops.dependency_findings"))
        _emit("vacuum_analyze", OK, {"tables": ["ops.system_health_checks", "ops.dependency_findings"]})
    except Exception as exc:
        _emit("vacuum_analyze", WARN, message=f"vacuum failed: {exc}")


def os_update_check() -> None:
    """Report-only: count pending apt security updates if /usr/lib/update-notifier present."""
    path = "/var/lib/update-notifier/updates-available"
    try:
        if os.path.exists(path):
            with open(path) as fh:
                _emit("os_update_check", OK, message=fh.read().strip()[:500])
        else:
            _emit("os_update_check", OK, message="update-notifier not present; host watchdog should report")
    except Exception as exc:
        _emit("os_update_check", OK, message=f"skipped ({exc})")
