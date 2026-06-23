"""
Ops monitor configuration via pydantic-settings.

All values from env.local / .env — no hardcoded credentials. The ops container
connects to Postgres as the scoped least-privilege role `ops_app` (r/w on ops.*,
read-only on the reporting tables) and reaches every other component over the
network (HTTP / Redis), never via a broker.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpsSettings(BaseSettings):
    # ── Database (scoped ops_app role — see ops migration ops001) ──
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "app_db"
    # Default to ops_app; in WSL dev the compose env may still pass user/password.
    ops_db_user: str = "ops_app"
    ops_db_password: str = ""
    # Fallbacks so the container still boots if only POSTGRES_* are present.
    postgres_user: str = "user"
    postgres_password: str = "password"

    # ── Redis (read-only introspection: PING, INFO, LLEN on broker db) ──
    # Broker db holds Celery queue lists; default matches compose CELERY_BROKER_URL.
    celery_broker_url: str = "redis://redis:6379/1"
    redis_url: str = "redis://redis:6379/0"

    # ── Messaging API (HTTP — alerts + reports, no broker dependency) ──
    messaging_api_url: str = "http://backend:5001"
    messaging_api_key: str = ""
    ticketing_secret_key: str = ""

    # ── Service /health endpoints to probe (comma-separated name=url pairs) ──
    health_endpoints: str = (
        "orchestrator=http://orchestrator:8000/health,"
        "backend=http://backend:5001/health,"
        "ticketing=http://ticketing_api:5002/health"
    )

    # ── Alerting / reporting ──
    health_alert_email: str = ""
    daily_report_email: str = ""
    daily_report_tz: str = "Asia/Kathmandu"
    # External dead-man's switch (L3): healthchecks.io ping URL (https://hc-ping.com/...).
    # Accept HEARTBEAT_URL / STRATCON_HEARTBEAT_URL (shared across projects) and the
    # legacy HEALTHCHECKS_PING_URL. UptimeRobot is NOT used here — its heartbeat/cron
    # monitors are paid; UptimeRobot only does inbound HTTP(s) uptime checks (see spec 11 §7).
    heartbeat_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "HEARTBEAT_URL", "STRATCON_HEARTBEAT_URL", "HEALTHCHECKS_PING_URL"
        ),
    )
    ops_status_file: str = "/tmp/ops_scheduler.tick"
    alert_dedup_seconds: int = 3600          # max 1 alert per signature / hour

    # ── Thresholds (8 GiB host defaults) ──
    health_disk_warn_pct: int = 75
    health_disk_crit_pct: int = 85
    health_mem_crit_pct: int = 90
    health_cert_warn_days: int = 14
    queue_depth_warn: int = 200              # backlog size before warn
    redis_mem_warn_pct: int = 80
    db_conn_warn_pct: int = 80

    # ── Public TLS host (cert_check target) ──
    public_tls_host: str = "grm-chatbot.dor.gov.np"
    public_tls_port: int = 443

    # ── Backups (self-hosted) ──
    backup_dir: str = "/var/backups/grms"
    backup_status_file: str = "/var/backups/grms/last_backup.json"
    backup_max_age_hours: int = 26

    model_config = SettingsConfigDict(
        env_file=("env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def healthchecks_ping_url(self) -> str:
        """Backward-compatible alias for the heartbeat ping URL."""
        return self.heartbeat_url

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL for the scoped ops_app role (falls back to POSTGRES_*)."""
        user = self.ops_db_user or self.postgres_user
        password = self.ops_db_password or self.postgres_password
        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def parsed_health_endpoints(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for pair in self.health_endpoints.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            name, _, url = pair.partition("=")
            out[name.strip()] = url.strip()
        return out


@lru_cache
def get_settings() -> OpsSettings:
    return OpsSettings()
