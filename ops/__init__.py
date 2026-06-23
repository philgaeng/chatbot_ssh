"""
Platform ops / monitoring module.

Cross-cutting health, backup-status, security-scan, daily-report and external
heartbeat for the self-hosted Nepal GRM stack. Runs in its own `ops` container
on a broker-independent APScheduler (NOT Celery) so a Redis/worker outage cannot
blind the monitor. Persists to the dedicated `ops.*` schema via the scoped
`ops_app` role; alerts/reports go out over HTTP via the Messaging API.

Spec: docs/services/11_health_and_monitoring_service.md
      docs/services/12_security_monitoring_service.md
"""
