"""
Ops monitor entrypoint — broker-independent APScheduler.

Run: python -m ops.scheduler

Registers all platform jobs (health checks, security scan, maintenance, daily
report, external heartbeat) at their cadences and writes a self-liveness tick
(Redis key + status file) every minute so the container healthcheck and host
watchdog can detect a dead scheduler.
"""
from __future__ import annotations

import datetime as dt
import logging

import redis
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ops import checks, maintenance, reports, security
from ops.checks import OPS_TICK_KEY
from ops.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ops.scheduler")


def _write_tick() -> None:
    """Self-liveness marker: Redis key (read by watchdog) + file (read by selfcheck)."""
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        r = redis.from_url(s.redis_url, socket_timeout=3, socket_connect_timeout=3)
        r.set(OPS_TICK_KEY, now, ex=180)
    except Exception as exc:  # pragma: no cover - redis may be down; file still written
        logger.warning("tick: redis write failed: %s", exc)
    try:
        with open(s.ops_status_file, "w") as fh:
            fh.write(now)
    except Exception as exc:  # pragma: no cover
        logger.warning("tick: status file write failed: %s", exc)


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")

    # ── self-liveness ──
    sched.add_job(_write_tick, IntervalTrigger(minutes=1), id="ops_tick", max_instances=1)

    # ── L2 data-plane health checks ──
    sched.add_job(checks.db_connectivity_check, IntervalTrigger(minutes=5), id="db_connectivity_check")
    sched.add_job(checks.redis_check, IntervalTrigger(minutes=5), id="redis_check")
    sched.add_job(checks.queue_depth_check, IntervalTrigger(minutes=5), id="queue_depth_check")
    sched.add_job(checks.endpoint_check, IntervalTrigger(minutes=5), id="endpoint_check")
    sched.add_job(checks.stale_job_check, IntervalTrigger(minutes=15), id="stale_job_check")
    sched.add_job(checks.grm_beat_liveness_check, IntervalTrigger(minutes=5), id="grm_beat_liveness_check")
    sched.add_job(checks.cert_check, CronTrigger(hour=2, minute=30), id="cert_check")
    sched.add_job(checks.smtp_check, CronTrigger(hour=2, minute=35), id="smtp_check")
    sched.add_job(checks.backup_status_check, CronTrigger(hour=3, minute=0), id="backup_status_check")
    sched.add_job(checks.restore_drill, CronTrigger(day_of_week="sun", hour=4, minute=0), id="restore_drill")

    # ── L3 external dead-man's switch ──
    sched.add_job(checks.external_heartbeat, IntervalTrigger(minutes=10), id="external_heartbeat")

    # ── security monitoring ──
    sched.add_job(security.dependency_scan, CronTrigger(hour=1, minute=30), id="dependency_scan")
    sched.add_job(security.pg_security_check, CronTrigger(hour=1, minute=45), id="pg_security_check")

    # ── maintenance ──
    sched.add_job(maintenance.prune_health_checks, CronTrigger(hour=3, minute=20), id="prune_health_checks")
    sched.add_job(maintenance.prune_logs, CronTrigger(hour=3, minute=25), id="prune_logs")
    sched.add_job(maintenance.prune_uploads_orphans, CronTrigger(day_of_week="sun", hour=3, minute=40), id="prune_uploads_orphans")
    sched.add_job(maintenance.vacuum_analyze, CronTrigger(day_of_week="sun", hour=4, minute=30), id="vacuum_analyze")
    sched.add_job(maintenance.os_update_check, CronTrigger(day_of_week="mon", hour=5, minute=0), id="os_update_check")

    # ── daily ops report (tz-aware) ──
    s = get_settings()
    sched.add_job(
        reports.daily_ops_report,
        CronTrigger(hour=7, minute=0, timezone=s.daily_report_tz),
        id="daily_ops_report",
    )
    return sched


def main() -> None:
    logger.info("ops scheduler starting")
    _write_tick()  # immediate tick so healthcheck passes on boot
    sched = build_scheduler()
    sched.start()
    logger.info("ops scheduler started with %d jobs", len(sched.get_jobs()))

    # Block forever; APScheduler runs its jobs in background threads.
    try:
        import time
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("ops scheduler shutting down")
        sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
